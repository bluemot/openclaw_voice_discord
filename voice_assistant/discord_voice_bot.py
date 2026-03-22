#!/usr/bin/env python3
"""
Discord Voice Bot - 語音助手整合版
功能：
- 加入 Voice Channel
- 接收語音訊息 -> STT -> LLM -> TTS -> 播放回應
- 支援文字指令

Requirements:
    pip install discord.py[voice] PyNaCl faster-whisper ollama gtts

Usage:
    1. 設定 DISCORD_BOT_TOKEN
    2. python3 discord_voice_bot.py
    3. 在 Discord 輸入 /join 讓 Bot 加入語音頻道
    4. 對著麥克風說話，Bot 會回應！
"""

import discord
from discord.ext import commands
import asyncio
import os
import tempfile
import wave
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS
import logging

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 全域變數
whisper_model = None
voice_clients = {}  # 儲存各伺服器的 voice client

# ======== STT 相關 ========
def init_whisper():
    """初始化 Whisper 模型"""
    global whisper_model
    if whisper_model is None:
        logger.info("載入 Whisper 模型...")
        try:
            # 嘗試使用 GPU，沒有就用 CPU
            import torch
            has_gpu = torch.cuda.is_available()
            device = "cuda" if has_gpu else "cpu"
            compute_type = "float16" if has_gpu else "int8"
        except:
            device = "cpu"
            compute_type = "int8"
        
        whisper_model = WhisperModel("tiny", device=device, compute_type=compute_type)
        logger.info(f"Whisper 載入完成 (device: {device})")
    return whisper_model

async def transcribe_audio(audio_file):
    """語音轉文字"""
    model = init_whisper()
    
    try:
        segments, info = model.transcribe(audio_file, beam_size=5, language="zh")
        transcript = " ".join([segment.text for segment in segments])
        return transcript.strip()
    except Exception as e:
        logger.error(f"STT 錯誤: {e}")
        return None

# ======== LLM 相關 ========
async def get_llm_response(text):
    """取得 LLM 回應"""
    models = ["kimi-k2.5:cloud", "qwen3-coder-next:cloud", "deepseek-v3.2:cloud"]
    
    prompt = f"請簡短回應（50字以內）：{text}"
    
    for model_name in models:
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content'].strip()
        except Exception as e:
            logger.warning(f"{model_name} 失敗: {e}")
            continue
    
    return f"收到：{text[:30]}..."

# ======== TTS 相關 ========
async def text_to_speech(text):
    """文字轉語音"""
    try:
        output_file = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=text[:500], lang='zh-tw', slow=False)  # 限制字數
        tts.save(output_file)
        return output_file
    except Exception as e:
        logger.error(f"TTS 錯誤: {e}")
        return None

# ======== Discord Bot 指令 ========
@bot.event
async def on_ready():
    """Bot 啟動時"""
    logger.info(f"✅ Bot 已登入: {bot.user}")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, 
        name="語音指令"
    ))

@bot.command(name="join")
async def join_voice(ctx):
    """加入語音頻道"""
    if ctx.author.voice is None:
        await ctx.send("❌ 你必須先加入一個語音頻道！")
        return
    
    channel = ctx.author.voice.channel
    
    # 檢查是否已經在語音頻道
    if ctx.guild.id in voice_clients:
        await voice_clients[ctx.guild.id].disconnect()
    
    try:
        voice_client = await channel.connect()
        voice_clients[ctx.guild.id] = voice_client
        await ctx.send(f"✅ 已加入 {channel.name}！請對我說話，我會回應你。")
        logger.info(f"加入語音頻道: {channel.name}")
    except Exception as e:
        await ctx.send(f"❌ 加入失敗: {e}")

@bot.command(name="leave")
async def leave_voice(ctx):
    """離開語音頻道"""
    if ctx.guild.id in voice_clients:
        await voice_clients[ctx.guild.id].disconnect()
        del voice_clients[ctx.guild.id]
        await ctx.send("👋 已離開語音頻道")
    else:
        await ctx.send("❌ 我不在任何語音頻道中")

@bot.command(name="test")
async def test_pipeline(ctx):
    """測試完整流程"""
    await ctx.send("🧪 測試語音助手流程...")
    
    # 測試 STT
    test_text = "這是一個測試"
    await ctx.send(f"📝 測試文字: {test_text}")
    
    # 測試 LLM
    response = await get_llm_response(test_text)
    await ctx.send(f"💬 LLM 回應: {response}")
    
    # 測試 TTS
    audio_file = await text_to_speech(response)
    if audio_file:
        await ctx.send("🔊 TTS 成功！", file=discord.File(audio_file))
        os.remove(audio_file)

# ======== 語音訊息處理 ========
class VoiceReceiver(discord.sinks.WaveSink):
    """自訂語音接收器"""
    
    def __init__(self):
        super().__init__()
        self.audio_data = {}
    
    def write(self, data, user):
        """接收語音資料"""
        if user not in self.audio_data:
            self.audio_data[user] = []
        self.audio_data[user].append(data)

# 簡化的語音處理（使用現有 recording）
@bot.command(name="listen")
async def listen_command(ctx, duration: int = 5):
    """
    錄音並處理
    用法: !listen [秒數]
    """
    if ctx.guild.id not in voice_clients:
        await ctx.send("❌ 請先用 !join 讓我加入語音頻道")
        return
    
    voice_client = voice_clients[ctx.guild.id]
    
    if not voice_client.is_connected():
        await ctx.send("❌ 語音連接已斷開")
        return
    
    await ctx.send(f"🎙️ 開始錄音 {duration} 秒...")
    
    try:
        # 使用 discord 的錄音功能
        sink = discord.sinks.WaveSink()
        
        voice_client.start_recording(
            sink,
            lambda sink, channel, *args: asyncio.create_task(
                process_recording(sink, channel, ctx)
            ),
            ctx.channel
        )
        
        await asyncio.sleep(duration)
        voice_client.stop_recording()
        
    except Exception as e:
        await ctx.send(f"❌ 錄音失敗: {e}")
        logger.error(f"錄音錯誤: {e}")

async def process_recording(sink, channel, ctx):
    """處理錄音檔案"""
    await ctx.send("🔄 處理錄音...")
    
    # 儲存錄音檔案
    audio_file = tempfile.mktemp(suffix=".wav")
    
    try:
        # 儲存為 WAV
        with wave.open(audio_file, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            
            for user_id, audio in sink.audio_data.items():
                for data in audio:
                    wf.writeframes(data)
        
        await ctx.send(f"📁 錄音檔案大小: {os.path.getsize(audio_file)} bytes")
        
        # Step 1: STT
        transcript = await transcribe_audio(audio_file)
        if transcript:
            await ctx.send(f"📝 你說: {transcript}")
            
            # Step 2: LLM
            response = await get_llm_response(transcript)
            await ctx.send(f"🤖 AI: {response}")
            
            # Step 3: TTS
            audio_response = await text_to_speech(response)
            if audio_response:
                # 播放語音回應
                source = discord.FFmpegPCMAudio(audio_response)
                voice_clients[ctx.guild.id].play(source)
                
                await ctx.send("🔊 已播放回應！")
                os.remove(audio_response)
        else:
            await ctx.send("❌ 無法辨識語音")
        
        # 清理
        os.remove(audio_file)
        
    except Exception as e:
        await ctx.send(f"❌ 處理失敗: {e}")
        logger.error(f"處理錯誤: {e}")

# ======== 主程式 ========
def main():
    """啟動 Bot"""
    token = os.getenv("DISCORD_BOT_TOKEN")
    
    if not token:
        print("❌ 錯誤：請設定 DISCORD_BOT_TOKEN 環境變數")
        print("   export DISCORD_BOT_TOKEN='你的機器人token'")
        return
    
    print("🚀 啟動 Discord Voice Bot...")
    print("📋 可用指令:")
    print("   !join  - 加入語音頻道")
    print("   !leave - 離開語音頻道")
    print("   !listen [秒數] - 錄音並回應")
    print("   !test  - 測試流程")
    
    bot.run(token)

if __name__ == "__main__":
    main()
