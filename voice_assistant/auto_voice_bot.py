#!/usr/bin/env python3
"""
即時語音對話模擬 - 最接近真實體驗的版本

概念：
1. Bot 加入後自動開始「分段錄音」
2. 說話 → 自動分段 → 即時處理 → 播放回應
3. 無需按任何按鈕，像真人對話

工作流程：
- 偵測到聲音 → 開始錄音
- 靜音超過 0.5 秒 → 自動停止並處理
- 處理完成 → 播放回應
- 循環重複
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
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 設定
SILENCE_THRESHOLD = 1.0  # 靜音多久視為說話結束（秒）
MAX_RECORD_TIME = 10     # 最長錄音時間（秒）

class AutoVoiceSession:
    """自動語音對話會話"""
    
    def __init__(self, voice_client, text_channel):
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.is_active = True
        self.is_recording = False
        self.last_audio_time = time.time()
        self.processor = VoiceProcessor(text_channel, voice_client)
        
        # 啟動監控循環
        self.monitor_task = None
        
    async def start_auto_mode(self):
        """啟動自動對話模式"""
        await self.text_channel.send(
            "🎙️ **自動對話模式啟動！**\n"
            "直接對著麥克風說話，我會自動回應！\n"
            "輸入 `!stopauto` 停止，或 `!leave` 離開"
        )
        
        # 開始第一輪錄音
        await self.start_recording_cycle()
    
    async def start_recording_cycle(self):
        """開始錄音循環"""
        if not self.is_active:
            return
        
        try:
            # 建立新的 sink
            self.current_sink = WaveSink()
            self.is_recording = True
            self.last_audio_time = time.time()
            
            # 開始錄音
            self.voice_client.start_recording(
                self.current_sink,
                self.on_recording_finished,
                self.text_channel
            )
            
            print(f"[Auto] 開始錄音循環")
            
            # 啟動監控
            if self.monitor_task:
                self.monitor_task.cancel()
            self.monitor_task = asyncio.create_task(self.monitor_recording())
            
        except Exception as e:
            print(f"[Recording Error] {e}")
            # 重試
            await asyncio.sleep(1)
            if self.is_active:
                await self.start_recording_cycle()
    
    async def monitor_recording(self):
        """監控錄音狀態"""
        start_time = time.time()
        
        while self.is_recording and self.is_active:
            await asyncio.sleep(0.1)
            
            elapsed = time.time() - start_time
            silence = time.time() - self.last_audio_time
            
            # 檢查是否超時或靜音太久
            if elapsed > MAX_RECORD_TIME or silence > SILENCE_THRESHOLD:
                if elapsed > 0.5:  # 至少錄了 0.5 秒
                    print(f"[Auto] 自動停止: elapsed={elapsed:.1f}s, silence={silence:.1f}s")
                    await self.stop_and_process()
                    return
        
        # 如果還在活動，重新開始錄音
        if self.is_active:
            await asyncio.sleep(0.5)
            await self.start_recording_cycle()
    
    def on_audio_received(self):
        """接收到音訊時更新時間"""
        self.last_audio_time = time.time()
    
    async def stop_and_process(self):
        """停止並處理"""
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        try:
            if self.voice_client.is_recording():
                self.voice_client.stop_recording()
                print("[Auto] 停止錄音，等待處理...")
                # 處理會在 on_recording_finished 中進行
        except Exception as e:
            print(f"[Stop Error] {e}")
    
    def on_recording_finished(self, sink):
        """錄音結束回調"""
        if not self.is_active:
            return
        
        print(f"[Auto] 錄音完成，處理中...")
        
        # 處理音訊
        for user_id, audio in sink.audio_data.items():
            temp_file = tempfile.mktemp(suffix=".wav")
            
            try:
                with open(temp_file, 'wb') as f:
                    f.write(audio.file.read())
                
                # 檢查大小
                if os.path.getsize(temp_file) > 1000:
                    self.processor.add_task(temp_file, user_id)
                else:
                    os.remove(temp_file)
                    
            except Exception as e:
                print(f"[Save Error] {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        # 延遲後重新開始錄音
        asyncio.run_coroutine_threadsafe(
            self.restart_after_delay(),
            bot.loop
        )
    
    async def restart_after_delay(self):
        """延遲後重新開始"""
        await asyncio.sleep(2)  # 等待處理完成
        if self.is_active:
            await self.start_recording_cycle()
    
    def stop(self):
        """停止會話"""
        self.is_active = False
        self.is_recording = False
        self.processor.stop()
        if self.monitor_task:
            self.monitor_task.cancel()

class VoiceProcessor:
    """背景處理"""
    
    def __init__(self, text_channel, voice_client):
        self.text_channel = text_channel
        self.voice_client = voice_client
        self.task_queue = queue.Queue()
        self.running = True
        
        print("[Processor] 載入 Whisper...")
        self.whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Processor] Whisper 載入完成")
        
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
        """處理單個檔案"""
        try:
            print(f"[Process] 處理 {os.path.getsize(audio_file)} bytes")
            
            # STT
            segments, info = self.whisper_model.transcribe(
                audio_file, beam_size=5, language="zh"
            )
            transcript = " ".join([s.text for s in segments]).strip()
            os.remove(audio_file)
            
            if not transcript:
                return
            
            print(f"[STT] {transcript}")
            
            # 發送到 Discord
            asyncio.run_coroutine_threadsafe(
                self.text_channel.send(f"📝 <@{user_id}>：{transcript}"),
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
            
            # TTS
            tts_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=llm_text[:500], lang='zh-tw')
            tts.save(tts_file)
            
            # 發送並播放
            asyncio.run_coroutine_threadsafe(
                self._send_and_play(llm_text, tts_file),
                bot.loop
            )
            
        except Exception as e:
            print(f"[Process Error] {e}")
    
    async def _send_and_play(self, text, audio_file):
        """發送並播放"""
        try:
            await self.text_channel.send(f"💬 **AI：**{text}")
            
            if self.voice_client and self.voice_client.is_connected():
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                source = discord.FFmpegPCMAudio(audio_file)
                self.voice_client.play(source)
                
                while self.voice_client.is_playing():
                    await asyncio.sleep(0.1)
                
                os.remove(audio_file)
                
        except Exception as e:
            print(f"[Play Error] {e}")
    
    def add_task(self, audio_file, user_id):
        self.task_queue.put({'file': audio_file, 'user': user_id})
    
    def stop(self):
        self.running = False
        self.task_queue.put(None)

# ============ Bot 指令 ============
active_sessions = {}

@bot.event
async def on_ready():
    print(f"✅ Bot 已登入: {bot.user}")
    print("📋 指令:")
    print("  !join      - 加入並啟動自動對話模式")
    print("  !stopauto  - 停止自動對話（保持連接）")
    print("  !leave     - 離開頻道")

@bot.command()
async def join(ctx):
    """加入並啟動自動對話"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    if ctx.guild.id in active_sessions:
        await ctx.send("⚠️ 已經在自動對話中了")
        return
    
    try:
        voice_client = await ctx.author.voice.channel.connect()
        session = AutoVoiceSession(voice_client, ctx.channel)
        active_sessions[ctx.guild.id] = session
        
        # 啟動自動模式
        await session.start_auto_mode()
        
    except Exception as e:
        await ctx.send(f"❌ 錯誤: {e}")

@bot.command()
async def stopauto(ctx):
    """停止自動對話"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 沒有進行中的對話")
        return
    
    session = active_sessions[ctx.guild.id]
    session.is_active = False
    
    if session.is_recording:
        await session.stop_and_process()
    
    await ctx.send("⏹️ **已停止自動對話**\n輸入 `!join` 重新啟動")

@bot.command()
async def leave(ctx):
    """離開頻道"""
    if ctx.guild.id not in active_sessions:
        await ctx.send("❌ 不在任何語音頻道中")
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
