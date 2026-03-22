#!/usr/bin/env python3
"""
最簡單的 Discord 語音助手
- 使用者上傳音訊檔案
- Bot 自動處理：STT → LLM → TTS
- Bot 回傳文字 + 語音回應

支援格式：mp3, wav, m4a, mov（錄音檔）
"""

import discord
from discord.ext import commands
import os
import tempfile
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS
import asyncio

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 全域模型（Lazy loading）
whisper_model = None

def get_whisper():
    global whisper_model
    if whisper_model is None:
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    return whisper_model

@bot.event
async def on_ready():
    print(f"✅ Bot 已登入: {bot.user}")
    print("📤 上傳音訊檔案，我會自動回應！")

@bot.event
async def on_message(message):
    """自動處理上傳的音訊檔案"""
    if message.author == bot.user:
        return
    
    # 檢查是否有附件
    if not message.attachments:
        await bot.process_commands(message)
        return
    
    # 檢查是否為音訊檔案
    audio_extensions = ['.mp3', '.wav', '.m4a', '.mov', '.mp4', '.ogg']
    attachment = message.attachments[0]
    
    if not any(attachment.filename.lower().endswith(ext) for ext in audio_extensions):
        await bot.process_commands(message)
        return
    
    # 開始處理
    await message.channel.send(f"🎙️ 收到音訊檔案：{attachment.filename}\n🔄 處理中...")
    
    try:
        # 下載檔案
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, attachment.filename)
        await attachment.save(input_path)
        
        # 轉換為 WAV（如果是 mov/mp4）
        wav_path = os.path.join(temp_dir, "audio.wav")
        if attachment.filename.lower().endswith(('.mov', '.mp4', '.m4a')):
            os.system(f'ffmpeg -i "{input_path}" -ar 16000 -ac 1 "{wav_path}" -y')
        else:
            wav_path = input_path
        
        if not os.path.exists(wav_path):
            await message.channel.send("❌ 音訊轉換失敗")
            return
        
        # STT
        model = get_whisper()
        segments, info = model.transcribe(wav_path, beam_size=5, language="zh")
        transcript = " ".join([s.text for s in segments])
        
        if not transcript.strip():
            await message.channel.send("❌ 沒有偵測到語音內容")
            return
        
        await message.channel.send(f"📝 **你說：**\n> {transcript}")
        
        # LLM
        prompt = f"請簡短回應（50字以內）：{transcript}"
        response = ollama.chat(
            model='kimi-k2.5:cloud',
            messages=[{'role': 'user', 'content': prompt}]
        )
        llm_text = response['message']['content'].strip()
        
        await message.channel.send(f"🤖 **AI 回應：**\n{llm_text}")
        
        # TTS
        tts_path = os.path.join(temp_dir, "response.mp3")
        tts = gTTS(text=llm_text[:500], lang='zh-tw')
        tts.save(tts_path)
        
        # 回傳音訊
        await message.channel.send("🔊 **語音回應：**", 
                                   file=discord.File(tts_path))
        
        # 清理
        import shutil
        shutil.rmtree(temp_dir)
        
    except Exception as e:
        await message.channel.send(f"❌ 處理失敗：{e}")

@bot.command()
async def ping(ctx):
    """測試 Bot 是否正常"""
    await ctx.send("✅ Bot 正常運作！上傳音訊檔案即可開始對話。")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    bot.run(token)
