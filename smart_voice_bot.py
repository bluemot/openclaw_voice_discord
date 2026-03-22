#!/usr/bin/env python3
"""
Smart Auto Voice Bot - 聰明狀態管理

特點：
1. Bot 播放時暫停錄音（避免錄到自己的聲音）
2. 播放完畢後自動恢復監聽
3. 實現真正的「對話」體驗

狀態流程：
[Listening] → 偵測語音 → [Processing] → [Playing] → [Listening]...
                ↑                                          ↓
                └────────── 播放時暫停錄音 ←─────────────────┘
"""

import discord
from discord.ext import commands, tasks
from discord.sinks import WaveSink
import asyncio
import threading
import queue
import os
import tempfile
import time
from enum import Enum

from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# Bot 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

class BotState(Enum):
    """Bot 狀態"""
    IDLE = "idle"           # 閒置
    LISTENING = "listening" # 監聽中
    PROCESSING = "processing" # 處理中
    PLAYING = "playing"     # 播放中

class SmartVoiceSession:
    """聰明語音會話"""
    
    def __init__(self, voice_client, text_channel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.state = BotState.IDLE
        self.processor = VoiceProcessor(self)
        self.auto_mode = False
        
    async def start_auto_conversation(self):
        """啟動自動對話模式"""
        self.auto_mode = True
        self.state = BotState.LISTENING
        
        await self.text_channel.send(
            "🎙️ **智能對話模式啟動！**\n"
            "- 我說話時會暫停聆聽\n"
            "- 說完後自動恢復\n"
            "- 直接對著麥克風說話即可！"
        )
        
        # 開始第一輪錄音
        await self.start_listening()
    
    async def start_listening(self):
        """開始監聽（播放完畢後呼叫）"""
        if not self.auto_mode or self.state == BotState.PLAYING:
            return
        
        self.state = BotState.LISTENING
        
        # 建立錄音 sink
        self.current_sink = WaveSink()
        
        self.voice_client.start_recording(
            self.current_sink,
            self.on_recording_finished,
            self.text_channel
        )
        
        print(f"[State] → LISTENING (開始監聽)")
    
    def pause_listening(self):
        """暫停監聽（要播放時）"""
        if self.state == BotState.LISTENING:
            try:
                if self.voice_client.is_recording():
                    self.voice_client.stop_recording()
                    print("[State] 暫停監聽 (準備播放)")
            except:
                pass
    
    async def resume_listening(self):
        """恢復監聽（播放完畢後）"""
        await asyncio.sleep(0.5)  # 稍等避免回音
        self.state = BotState.LISTENING
        await self.start_listening()
    
    def on_recording_finished(self, sink):
        """錄音結束回調"""
        if not self.auto_mode:
            return
        
        print(f"[Recording] 收到音訊，處理中...")
        self.state = BotState.PROCESSING
        
        # 處理每個使用者的音訊
        for user_id, audio in sink.audio_data.items():
            temp_file = tempfile.mktemp(suffix=".wav")
            
            try:
                with open(temp_file, 'wb') as f:
                    f.write(audio.file.read())
                
                if os.path.getsize(temp_file) > 1000:
                    self.processor.add_task(temp_file, user_id)
                else:
                    os.remove(temp_file)
                    
            except Exception as e:
                print(f"[Error] {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
    
    async def play_response(self, text, tts_file):
        """播放回應"""
        # 1. 暫停監聽
        self.pause_listening()
        self.state = BotState.PLAYING
        
        print(f"[State] → PLAYING (播放: {text[:50]}...)")
        
        # 2. 發送文字
        await self.text_channel.send(f"💬 **AI：**{text}")
        
        # 3. 播放語音
        try:
            source = discord.FFmpegPCMAudio(tts_file)
            self.voice_client.play(source)
            
            # 等待播放完畢
            while self.voice_client.is_playing():
                await asyncio.sleep(0.1)
            
            os.remove(tts_file)
            
        except Exception as e:
            print(f"[Play Error] {e}")
        
        # 4. 恢復監聽
        if self.auto_mode:
            print("[State] → LISTENING (恢復監聽)")
            await self.resume_listening()
    
    def stop(self):
        """停止會話"""
        self.auto_mode = False
        self.processor.stop()
        try:
            if self.voice_client.is_recording():
                self.voice_client.stop_recording()
        except:
            pass

class VoiceProcessor:
    """背景處理器"""
    
    def __init__(self, session):
        self.session = session
        self.task_queue = queue.Queue()
        self.running = True
        
        print("[Processor] 載入 Whisper...")
        self.whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        
        self.thread = threading.Thread(target=self.process_loop, daemon=True)
        self.thread.start()
    
    def process_loop(self):
        """處理主迴圈"""
        while self.running:
            try:
                task = self.task_queue.get(timeout=1.0)
                if task is None:
                    continue
                
                self._process(task['file'], task['user'])
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Process Error] {e}")
    
    def _process(self, audio_file, user_id):
        """處理單個音訊"""
        try:
            print(f"[Process] STT 處理 {os.path.getsize(audio_file)} bytes")
            
            # STT
            segments, info = self.whisper_model.transcribe(
                audio_file, beam_size=5, language="zh"
            )
            transcript = " ".join([s.text for s in segments]).strip()
            os.remove(audio_file)
            
            if not transcript:
                print("[STT] 沒有內容，恢復監聽")
                asyncio.run_coroutine_threadsafe(
                    self.session.resume_listening(), bot.loop
                )
                return
            
            print(f"[STT] {transcript}")
            
            # 顯示轉錄
            asyncio.run_coroutine_threadsafe(
                self.session.text_channel.send(f"📝 <@{user_id}>：{transcript}"),
                bot.loop
            )
            
            # LLM
            prompt = f"請簡短回應（50字以內）：{transcript}"
            try:
                response = ollama.chat(
                    model='kimi-k2.5:cloud',
                    messages=[{'role': 'user', 'content': prompt}]
                )
                llm_text = response['message']['content'].strip()
            except:
                llm_text = f"收到：{transcript}"
            
            print(f"[LLM] {llm_text}")
            
            # TTS
            tts_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=llm_text[:500], lang='zh-tw')
            tts.save(tts_file)
            
            # 播放回應（會自動管理狀態）
            asyncio.run_coroutine_threadsafe(
                self.session.play_response(llm_text, tts_file),
                bot.loop
            )
            
        except Exception as e:
            print(f"[Process Error] {e}")
            # 出錯也要恢復監聽
            asyncio.run_coroutine_threadsafe(
                self.session.resume_listening(), bot.loop
            )
    
    def add_task(self, audio_file, user_id):
        self.task_queue.put({'file': audio_file, 'user': user_id})
    
    def stop(self):
        self.running = False
        self.task_queue.put(None)

# ============ Bot 指令 ============
active_sessions = {}

@bot.event
async def on_ready():
    print(f"✅ Smart Bot 已登入: {bot.user}")
    print("\n📋 智能對話 Bot")
    print("  !join   - 啟動自動對話")
    print("  !stop   - 暫停自動對話")
    print("  !leave  - 離開")

@bot.command()
async def join(ctx):
    """啟動智能對話"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    if ctx.guild.id in active_sessions:
        await ctx.send("⚠️ 已經在運作中")
        return
    
    try:
        voice_client = await ctx.author.voice.channel.connect()
        session = SmartVoiceSession(voice_client, ctx.channel)
        active_sessions[ctx.guild.id] = session
        
        await session.start_auto_conversation()
        
    except Exception as e:
        await ctx.send(f"❌ 錯誤: {e}")

@bot.command()
async def stop(ctx):
    """暫停對話"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 沒有進行中的對話")
        return
    
    session = active_sessions[ctx.guild.id]
    session.auto_mode = False
    session.pause_listening()
    
    await ctx.send("⏹️ **已暫停**\n輸入 `!join` 重新啟動")

@bot.command()
async def leave(ctx):
    """離開"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 不在任何頻道中")
        return
    
    session = active_sessions[ctx.guild.id]
    session.stop()
    await session.voice_client.disconnect()
    del active_sessions[ctx.guild.id]
    
    await ctx.send("👋 已離開")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    bot.run(token)
