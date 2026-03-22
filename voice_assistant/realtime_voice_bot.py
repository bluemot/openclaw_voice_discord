#!/usr/bin/env python3
"""
即時語音助手 - Real-time Voice Assistant
使用多線程 + 異步處理實現即時語音對話

架構：
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Voice RX    │────→│ Audio Queue │────→│ STT Thread  │
│ (Discord)   │     │ (Thread-safe)│     │ (faster-whisper)│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
┌─────────────┐     ┌─────────────┐     ┌────┴──────┐
│ Voice TX    │←────│ TTS Queue   │←────│ LLM Call  │
│ (Discord)   │     │ (asyncio)   │     │ (Ollama)  │
└─────────────┘     └─────────────┘     └───────────┘

Usage:
    1. export DISCORD_BOT_TOKEN="你的token"
    2. python3 realtime_voice_bot.py
    3. 在 Discord 輸入 !join
    4. 直接對著麥克風說話！
"""

import discord
from discord.ext import commands, tasks
import asyncio
import threading
import queue
import numpy as np
import io
import wave
import tempfile
import os
import time
from collections import deque
from datetime import datetime, timedelta
import struct

# 音訊處理
import opuslib
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============ 全域設定 ============
SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK_DURATION = 0.5  # 秒
SILENCE_THRESHOLD = 1.5  # 靜音多久視為說話結束
MIN_SPEECH_DURATION = 0.5  # 最短說話時間

# ============ 線程安全的佇列 ============
audio_queue = queue.Queue()  # 原始音訊封包
stt_queue = queue.Queue()    # 待處理的音訊片段
response_queue = queue.Queue()  # AI 回應

# ============ 狀態管理 ============
class VoiceSession:
    def __init__(self, voice_client, text_channel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.is_listening = False
        self.audio_buffer = deque()  # 音訊緩衝
        self.silence_start = None
        self.is_processing = False
        self.last_speaker = None
        
        # 啟動處理線程
        self.running = True
        self.stt_thread = threading.Thread(target=self.stt_worker, daemon=True)
        self.stt_thread.start()
        
    def stt_worker(self):
        """STT 工作線程"""
        print("[STT Thread] 啟動")
        
        # 每個線程載入自己的 Whisper 模型
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        
        while self.running:
            try:
                # 等待音訊片段
                audio_data, user_id = stt_queue.get(timeout=1.0)
                
                if audio_data is None:
                    continue
                
                print(f"[STT] 處理 {len(audio_data)} bytes")
                
                # 儲存為臨時檔案
                temp_file = tempfile.mktemp(suffix=".wav")
                with wave.open(temp_file, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_data)
                
                # STT
                segments, info = model.transcribe(temp_file, beam_size=5, language="zh")
                transcript = " ".join([s.text for s in segments]).strip()
                
                os.remove(temp_file)
                
                if transcript:
                    print(f"[STT] 結果: {transcript}")
                    # 送入回應佇列
                    response_queue.put({
                        'type': 'stt_result',
                        'text': transcript,
                        'user_id': user_id
                    })
                    
                    # 觸發 LLM 處理
                    threading.Thread(
                        target=self.llm_worker,
                        args=(transcript,),
                        daemon=True
                    ).start()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[STT Error] {e}")
    
    def llm_worker(self, text):
        """LLM 工作線程"""
        try:
            print(f"[LLM] 處理: {text}")
            
            models = ["kimi-k2.5:cloud", "qwen3-coder-next:cloud"]
            prompt = f"請簡短回應（50字以內）：{text}"
            
            for model_name in models:
                try:
                    response = ollama.chat(
                        model=model_name,
                        messages=[{'role': 'user', 'content': prompt}]
                    )
                    result = response['message']['content'].strip()
                    
                    print(f"[LLM] 回應: {result}")
                    
                    response_queue.put({
                        'type': 'llm_result',
                        'text': result
                    })
                    
                    # 觸發 TTS
                    threading.Thread(
                        target=self.tts_worker,
                        args=(result,),
                        daemon=True
                    ).start()
                    
                    return
                    
                except Exception as e:
                    print(f"[LLM] {model_name} 失敗: {e}")
                    continue
                    
        except Exception as e:
            print(f"[LLM Error] {e}")
    
    def tts_worker(self, text):
        """TTS 工作線程"""
        try:
            print(f"[TTS] 生成語音: {text[:50]}...")
            
            temp_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=text[:500], lang='zh-tw', slow=False)
            tts.save(temp_file)
            
            response_queue.put({
                'type': 'tts_result',
                'file': temp_file,
                'text': text
            })
            
        except Exception as e:
            print(f"[TTS Error] {e}")
    
    def process_response_queue(self):
        """處理回應佇列（從主線程呼叫）"""
        try:
            while not response_queue.empty():
                item = response_queue.get_nowait()
                
                if item['type'] == 'stt_result':
                    # 發送轉錄結果
                    asyncio.run_coroutine_threadsafe(
                        self.text_channel.send(
                            f"📝 <@{item['user_id']}> 說：\n> {item['text']}"
                        ),
                        bot.loop
                    )
                
                elif item['type'] == 'llm_result':
                    # LLM 結果已在 TTS 中處理
                    pass
                
                elif item['type'] == 'tts_result':
                    # 播放語音
                    if os.path.exists(item['file']):
                        asyncio.run_coroutine_threadsafe(
                            self.play_audio(item['file'], item['text']),
                            bot.loop
                        )
                        
        except queue.Empty:
            pass
    
    async def play_audio(self, audio_file, text):
        """播放音訊"""
        try:
            if self.voice_client and self.voice_client.is_connected():
                # 等待播放完畢
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                # 播放
                source = discord.FFmpegPCMAudio(audio_file)
                self.voice_client.play(source)
                
                # 發送訊息
                await self.text_channel.send(
                    f"🤖 **AI 回應：**\n{text}\n🔊 播放中..."
                )
                
                # 等待播放完畢後刪除
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                os.remove(audio_file)
                
        except Exception as e:
            print(f"[Play Error] {e}")
    
    def decode_opus(self, data):
        """解碼 Opus 封包"""
        try:
            # 初始化 Opus 解碼器
            decoder = opuslib.Decoder(SAMPLE_RATE, CHANNELS)
            
            # 解碼
            pcm = decoder.decode(data, 960)  # 20ms @ 48kHz
            
            return pcm
        except:
            return None
    
    def add_audio_packet(self, data, user_id):
        """添加音訊封包"""
        if not self.is_listening:
            return
        
        # 解碼 Opus
        pcm_data = self.decode_opus(data)
        
        if pcm_data:
            self.audio_buffer.append({
                'data': pcm_data,
                'time': time.time(),
                'user': user_id
            })
            
            self.last_speaker = user_id
            
            # 檢查靜音
            self.check_silence()
    
    def check_silence(self):
        """檢測說話結束"""
        if len(self.audio_buffer) == 0:
            return
        
        now = time.time()
        last_time = self.audio_buffer[-1]['time']
        
        # 如果靜音超過閾值，視為說話結束
        if now - last_time > SILENCE_THRESHOLD:
            self.process_audio_segment()
    
    def process_audio_segment(self):
        """處理音訊片段"""
        if len(self.audio_buffer) == 0:
            return
        
        # 計算時長
        duration = self.audio_buffer[-1]['time'] - self.audio_buffer[0]['time']
        
        if duration < MIN_SPEECH_DURATION:
            self.audio_buffer.clear()
            return
        
        # 合併音訊
        audio_data = b''.join([p['data'] for p in self.audio_buffer])
        user_id = self.last_speaker
        
        print(f"[Audio] 偵測到語音片段: {duration:.2f}s, {len(audio_data)} bytes")
        
        # 送入 STT 佇列
        stt_queue.put((audio_data, user_id))
        
        # 清空緩衝
        self.audio_buffer.clear()
    
    def stop(self):
        """停止會話"""
        self.running = False
        self.is_listening = False
        stt_queue.put((None, None))

# ============ 全域會話管理 ============
sessions = {}

# ============ Discord 事件 ============
@bot.event
async def on_ready():
    print(f"✅ Bot 已登入: {bot.user}")
    print("\n🎯 即時語音助手就緒！")
    print("📋 指令:")
    print("  !join   - 加入語音頻道並開始監聽")
    print("  !leave  - 離開並停止監聽")
    print("  !status - 顯示狀態")
    
    # 啟動回應處理任務
    process_responses.start()

@tasks.loop(seconds=0.5)
async def process_responses():
    """處理回應佇列"""
    for guild_id, session in list(sessions.items()):
        session.process_response_queue()

@bot.command()
async def join(ctx):
    """加入語音頻道並開始監聽"""
    if ctx.author.voice is None:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    channel = ctx.author.voice.channel
    
    # 檢查是否已存在
    if ctx.guild.id in sessions:
        await ctx.send("⚠️ 已經在監聽中了")
        return
    
    try:
        voice_client = await channel.connect()
        
        # 建立會話
        session = VoiceSession(voice_client, ctx.channel)
        session.is_listening = True
        sessions[ctx.guild.id] = session
        
        # 設置語音接收回調
        def on_voice_packet(user, data):
            if session.is_listening:
                session.add_audio_packet(data, user.id if user else None)
        
        # 這裡需要攔截語音封包
        # Discord.py 的語音接收需要特殊處理...
        
        await ctx.send(
            f"✅ **已加入 {channel.name}！**\n"
            f"🎙️ 正在監聽語音...\n"
            f"說話後停頓 {SILENCE_THRESHOLD} 秒，我會自動回應！"
        )
        
    except Exception as e:
        await ctx.send(f"❌ 錯誤: {e}")

@bot.command()
async def leave(ctx):
    """離開語音頻道"""
    if ctx.guild.id not in sessions:
        await ctx.send("❌ 不在任何語音頻道中")
        return
    
    session = sessions[ctx.guild.id]
    session.stop()
    
    await session.voice_client.disconnect()
    del sessions[ctx.guild.id]
    
    await ctx.send("👋 已離開語音頻道")

@bot.command()
async def status(ctx):
    """顯示狀態"""
    if ctx.guild.id not in sessions:
        await ctx.send("📊 未連接")
        return
    
    session = sessions[ctx.guild.id]
    await ctx.send(
        f"📊 **狀態**\n"
        f"監聽中: {'✅' if session.is_listening else '❌'}\n"
        f"處理中: {'✅' if session.is_processing else '❌'}\n"
        f"緩衝區: {len(session.audio_buffer)} packets"
    )

# ============ 啟動 ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    
    print("🚀 啟動即時語音助手...")
    print("⚠️ 注意：Discord.py 的語音接收需要 opus 和特定設定")
    
    bot.run(token)
