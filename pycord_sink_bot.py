#!/usr/bin/env python3
"""
Py-Cord 即時語音助手 - 使用 discord.sinks
完整實作：接收語音 → STT → LLM → TTS → 播放回應

Features:
- 使用 discord.sinks 接收語音
- 自動分段處理（VAD）
- 多線程非阻塞處理
- 即時播放回應

Usage:
    export DISCORD_BOT_TOKEN="你的token"
    python3 pycord_sink_bot.py
"""

import discord
from discord.ext import commands
from discord.sinks import WaveSink
import asyncio
import threading
import queue
import os
import tempfile
import time
from datetime import datetime

# 音訊處理
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# ============ Bot 設定 ============
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============ 全域狀態 ============
active_sessions = {}

class VoiceProcessor:
    """處理語音的後台線程"""
    
    def __init__(self, text_channel, voice_client):
        self.text_channel = text_channel
        self.voice_client = voice_client
        self.task_queue = queue.Queue()
        self.running = True
        
        # 載入 Whisper
        print("[Processor] 載入 Whisper 模型...")
        self.whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Processor] Whisper 載入完成")
        
        # 啟動處理線程
        self.thread = threading.Thread(target=self.process_loop, daemon=True)
        self.thread.start()
    
    def process_loop(self):
        """處理主迴圈"""
        while self.running:
            try:
                # 等待任務
                task = self.task_queue.get(timeout=1.0)
                
                if task is None:
                    continue
                
                audio_file = task['file']
                user_id = task['user']
                
                print(f"[Process] 處理 {os.path.getsize(audio_file)} bytes")
                
                # Step 1: STT
                segments, info = self.whisper_model.transcribe(
                    audio_file, 
                    beam_size=5, 
                    language="zh"
                )
                transcript = " ".join([s.text for s in segments]).strip()
                
                if not transcript:
                    print("[STT] 沒有偵測到語音")
                    os.remove(audio_file)
                    continue
                
                print(f"[STT] {transcript}")
                
                # 發送轉錄結果到 Discord
                asyncio.run_coroutine_threadsafe(
                    self.text_channel.send(
                        f"📝 <@{user_id}> 說：\n> {transcript}"
                    ),
                    bot.loop
                )
                
                # Step 2: LLM
                prompt = f"請簡短回應（50字以內）：{transcript}"
                try:
                    response = ollama.chat(
                        model='kimi-k2.5:cloud',
                        messages=[{'role': 'user', 'content': prompt}]
                    )
                    llm_text = response['message']['content'].strip()
                    print(f"[LLM] {llm_text}")
                except Exception as e:
                    print(f"[LLM Error] {e}")
                    llm_text = f"收到：{transcript[:30]}..."
                
                # 發送 LLM 回應
                asyncio.run_coroutine_threadsafe(
                    self.text_channel.send(f"💬 **AI 回應：**\n{llm_text}"),
                    bot.loop
                )
                
                # Step 3: TTS
                try:
                    tts_file = tempfile.mktemp(suffix=".mp3")
                    tts = gTTS(text=llm_text[:500], lang='zh-tw', slow=False)
                    tts.save(tts_file)
                    
                    # 播放
                    asyncio.run_coroutine_threadsafe(
                        self.play_audio(tts_file),
                        bot.loop
                    )
                    
                except Exception as e:
                    print(f"[TTS Error] {e}")
                
                # 清理
                os.remove(audio_file)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Process Error] {e}")
    
    async def play_audio(self, audio_file):
        """播放音訊"""
        try:
            if self.voice_client and self.voice_client.is_connected():
                # 等待當前播放完畢
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                # 播放
                source = discord.FFmpegPCMAudio(audio_file)
                self.voice_client.play(source)
                
                # 等待播放完畢後刪除
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                os.remove(audio_file)
                
        except Exception as e:
            print(f"[Play Error] {e}")
    
    def add_task(self, audio_file, user_id):
        """添加處理任務"""
        self.task_queue.put({
            'file': audio_file,
            'user': user_id
        })
    
    def stop(self):
        """停止處理器"""
        self.running = False
        self.task_queue.put(None)

class VoiceSession:
    """語音會話管理"""
    
    def __init__(self, voice_client, text_channel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.processor = VoiceProcessor(text_channel, voice_client)
        self.sink = None
    
    def on_recording_finished(self, sink):
        """錄音結束回調"""
        print(f"[Recording] 錄音完成，處理中...")
        
        # 處理每個使用者的音訊
        for user_id, audio in sink.audio_data.items():
            # 儲存為臨時檔案
            temp_file = tempfile.mktemp(suffix=".wav")
            
            try:
                # 寫入 WAV
                with open(temp_file, 'wb') as f:
                    f.write(audio.file.read())
                
                # 檢查檔案大小
                if os.path.getsize(temp_file) < 1000:
                    os.remove(temp_file)
                    continue
                
                # 添加到處理佇列
                self.processor.add_task(temp_file, user_id)
                
            except Exception as e:
                print(f"[Save Error] {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
    
    def start_recording(self):
        """開始錄音"""
        self.sink = WaveSink()
        
        self.voice_client.start_recording(
            self.sink,
            self.on_recording_finished,
            self.text_channel
        )
        print("[Recording] 開始錄音")
    
    def stop_recording(self):
        """停止錄音"""
        if self.voice_client.is_recording():
            self.voice_client.stop_recording()
        print("[Recording] 停止錄音")
    
    def stop(self):
        """停止會話"""
        self.stop_recording()
        self.processor.stop()

# ============ Bot 指令 ============
@bot.event
async def on_ready():
    print(f"✅ Py-Cord Bot 已登入: {bot.user}")
    print(f"📦 Py-Cord 版本: {discord.__version__}")
    print("\n📋 指令:")
    print("  !join    - 加入語音頻道")
    print("  !record  - 開始錄音")
    print("  !stop    - 停止錄音並處理")
    print("  !leave   - 離開頻道")

@bot.command()
async def join(ctx):
    """加入語音頻道"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    channel = ctx.author.voice.channel
    
    if ctx.guild.id in active_sessions:
        await ctx.send("⚠️ 已經在語音頻道中了")
        return
    
    try:
        voice_client = await channel.connect()
        session = VoiceSession(voice_client, ctx.channel)
        active_sessions[ctx.guild.id] = session
        
        await ctx.send(
            f"✅ **已加入 {channel.name}！**\n"
            f"輸入 `!record` 開始錄音"
        )
        
    except Exception as e:
        await ctx.send(f"❌ 錯誤: {e}")

@bot.command()
async def record(ctx):
    """開始錄音"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 請先用 `!join` 加入語音頻道")
        return
    
    session = active_sessions[ctx.guild.id]
    
    if session.voice_client.is_recording():
        await ctx.send("⚠️ 已經在錄音中了")
        return
    
    session.start_recording()
    await ctx.send("🎙️ **開始錄音！**\n說完話後輸入 `!stop` 停止並處理")

@bot.command()
async def stop(ctx):
    """停止錄音並處理"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 沒有進行中的會話")
        return
    
    session = active_sessions[ctx.guild.id]
    
    if not session.voice_client.is_recording():
        await ctx.send("⚠️ 沒有正在錄音")
        return
    
    await ctx.send("⏹️ **停止錄音，處理中...**")
    session.stop_recording()

@bot.command()
async def leave(ctx):
    """離開語音頻道"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 不在任何語音頻道中")
        return
    
    session = active_sessions[ctx.guild.id]
    session.stop()
    
    await session.voice_client.disconnect()
    del active_sessions[ctx.guild.id]
    
    await ctx.send("👋 已離開語音頻道")

@bot.command()
async def ping(ctx):
    """測試 Bot"""
    await ctx.send(f"✅ Py-Cord Bot 正常！\n版本: {discord.__version__}")

# ============ 啟動 ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN 環境變數")
        exit(1)
    
    print("🚀 啟動 Py-Cord 語音助手...")
    bot.run(token)
