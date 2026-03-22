#!/usr/bin/env python3
"""
Py-Cord 語音助手 - 完整即時語音處理
使用 pycord 的語音接收功能

Features:
- 即時語音接收 (Real-time)
- VAD (Voice Activity Detection)
- 自動分段處理
- 多線程 STT/LLM/TTS
- 非阻塞播放

Usage:
    python3 pycord_voice_bot.py
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

# 音訊處理
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# ============ 設定 ============
SAMPLE_RATE = 48000
CHANNELS = 2
CHUNK_DURATION_MS = 20  # Discord 語音封包間隔
VAD_THRESHOLD = 0.02    # 音量閾值
SILENCE_FRAMES = 25     # 靜音多少幀視為結束 (約0.5秒)
MIN_SPEECH_FRAMES = 10  # 最少說話幀數

# ============ Bot 設定 ============
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============ 全域狀態 ============
active_sessions = {}  # guild_id -> VoiceSession

class VoiceSession:
    """管理單個語音會話"""
    
    def __init__(self, voice_client, text_channel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.is_active = True
        
        # 音訊緩衝
        self.audio_buffer = deque()
        self.is_speaking = False
        self.silence_count = 0
        
        # 處理佇列
        self.processing_queue = queue.Queue()
        
        # 啟動處理線程
        self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
        self.processing_thread.start()
        
        print(f"[VoiceSession] 會話已建立")
    
    def processing_loop(self):
        """背景處理線程"""
        # 每個線程載入自己的模型
        print("[Thread] 載入 Whisper 模型...")
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Thread] Whisper 載入完成")
        
        while self.is_active:
            try:
                # 等待音訊片段
                audio_data = self.processing_queue.get(timeout=1.0)
                
                if audio_data is None:
                    continue
                
                # 處理
                self._process_audio_segment(audio_data, model)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Thread Error] {e}")
    
    def _process_audio_segment(self, audio_data, whisper_model):
        """處理單個音訊片段"""
        try:
            print(f"[Process] 處理 {len(audio_data)} bytes")
            
            # 儲存為臨時檔案
            temp_wav = tempfile.mktemp(suffix=".wav")
            with wave.open(temp_wav, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)
            
            # STT
            segments, info = whisper_model.transcribe(temp_wav, beam_size=5, language="zh")
            transcript = " ".join([s.text for s in segments]).strip()
            
            os.remove(temp_wav)
            
            if not transcript:
                print("[STT] 沒有偵測到語音")
                return
            
            print(f"[STT] {transcript}")
            
            # 發送轉錄結果
            asyncio.run_coroutine_threadsafe(
                self.text_channel.send(f"📝 **你說：**\n> {transcript}"),
                bot.loop
            )
            
            # LLM
            response = self._get_llm_response(transcript)
            print(f"[LLM] {response}")
            
            # 發送 LLM 回應
            asyncio.run_coroutine_threadsafe(
                self.text_channel.send(f"💬 **AI 回應：**\n{response}"),
                bot.loop
            )
            
            # TTS + 播放
            self._tts_and_play(response)
            
        except Exception as e:
            print(f"[Process Error] {e}")
    
    def _get_llm_response(self, text):
        """取得 LLM 回應"""
        try:
            prompt = f"請簡短回應（50字以內）：{text}"
            response = ollama.chat(
                model='kimi-k2.5:cloud',
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content'].strip()
        except:
            return f"收到：{text[:30]}..."
    
    def _tts_and_play(self, text):
        """TTS 並播放"""
        try:
            # TTS
            tts_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=text[:500], lang='zh-tw', slow=False)
            tts.save(tts_file)
            
            # 播放
            asyncio.run_coroutine_threadsafe(
                self._play_audio(tts_file),
                bot.loop
            )
            
        except Exception as e:
            print(f"[TTS Error] {e}")
    
    async def _play_audio(self, audio_file):
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
    
    def on_voice_data(self, data, user):
        """接收到語音封包"""
        if not self.is_active:
            return
        
        # 計算音量（RMS）
        audio_array = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(audio_array.astype(np.float32) ** 2))
        
        # VAD 檢測
        if rms > VAD_THRESHOLD * 32767:  # 16-bit 最大值為 32767
            # 檢測到聲音
            if not self.is_speaking:
                print(f"[VAD] 開始說話 (RMS: {rms:.0f})")
                self.is_speaking = True
            
            self.audio_buffer.append(data)
            self.silence_count = 0
        else:
            # 靜音
            if self.is_speaking:
                self.silence_count += 1
                self.audio_buffer.append(data)
                
                # 檢查是否結束說話
                if self.silence_count >= SILENCE_FRAMES:
                    print(f"[VAD] 結束說話")
                    self._finalize_speech_segment()
    
    def _finalize_speech_segment(self):
        """完成當前語音片段"""
        if len(self.audio_buffer) < MIN_SPEECH_FRAMES:
            # 太短，捨棄
            self.audio_buffer.clear()
            self.is_speaking = False
            self.silence_count = 0
            return
        
        # 合併音訊
        audio_data = b''.join(self.audio_buffer)
        
        # 送入處理佇列
        self.processing_queue.put(audio_data)
        
        # 重置
        self.audio_buffer.clear()
        self.is_speaking = False
        self.silence_count = 0
    
    def stop(self):
        """停止會話"""
        self.is_active = False
        self.processing_queue.put(None)

class VoiceReceiver(discord.AudioSink):
    """自定義語音接收器"""
    
    def __init__(self, session):
        super().__init__()
        self.session = session
    
    def write(self, data, user):
        """接收到音訊封包時呼叫"""
        if self.session and self.session.is_active:
            self.session.on_voice_data(data, user)
    
    def cleanup(self):
        """清理"""
        pass

# ============ Bot 指令 ============
@bot.event
async def on_ready():
    print(f"✅ Py-Cord Bot 已登入: {bot.user}")
    print(f"📦 Py-Cord 版本: {discord.__version__}")
    print("\n📋 指令:")
    print("  !join  - 加入語音頻道並開始監聽")
    print("  !leave - 離開並停止")

@bot.command()
async def join(ctx):
    """加入語音頻道"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    channel = ctx.author.voice.channel
    
    if ctx.guild.id in active_sessions:
        await ctx.send("⚠️ 已經在監聽中了")
        return
    
    try:
        # 連接語音
        voice_client = await channel.connect()
        
        # 建立會話
        session = VoiceSession(voice_client, ctx.channel)
        active_sessions[ctx.guild.id] = session
        
        # 設置語音接收器
        sink = VoiceReceiver(session)
        voice_client.start_recording(sink)
        
        await ctx.send(
            f"🎙️ **已加入 {channel.name}！**\n"
            f"開始監聽語音...\n"
            f"對著麥克風說話，我會自動回應！\n"
            f"輸入 `!leave` 停止監聽"
        )
        
    except Exception as e:
        await ctx.send(f"❌ 錯誤: {e}")
        print(f"[Error] {e}")

@bot.command()
async def leave(ctx):
    """離開語音頻道"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 不在任何語音頻道中")
        return
    
    session = active_sessions[ctx.guild.id]
    session.stop()
    
    if session.voice_client:
        session.voice_client.stop_recording()
        await session.voice_client.disconnect()
    
    del active_sessions[ctx.guild.id]
    
    await ctx.send("👋 已停止監聽並離開語音頻道")

@bot.command()
async def test(ctx):
    """測試 Bot"""
    await ctx.send("✅ Py-Cord Bot 正常運作！")

# ============ 啟動 ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN 環境變數")
        exit(1)
    
    print("🚀 啟動 Py-Cord 語音助手...")
    bot.run(token)
