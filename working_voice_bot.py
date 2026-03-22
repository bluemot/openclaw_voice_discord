#!/usr/bin/env python3
"""
真正能運作的即時語音方案：使用 discord.sinks
Discord.py 2.3+ 支援的錄音功能

工作流程：
1. !join 加入語音頻道
2. !listen 開始錄音
3. 說話
4. 錄音自動分段處理
5. STT -> LLM -> TTS -> 播放回應
"""

import discord
from discord.ext import commands
from discord.sinks import WaveSink
import asyncio
import os
import tempfile
import wave
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 模型載入
whisper_model = None

def get_whisper():
    global whisper_model
    if whisper_model is None:
        print("🔄 載入 Whisper 模型...")
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("✅ Whisper 載入完成")
    return whisper_model

async def process_audio_file(audio_file, channel, voice_client):
    """處理音訊檔案"""
    try:
        print(f"📁 處理音訊: {os.path.getsize(audio_file)} bytes")
        
        # STT
        await channel.send("🔄 語音轉文字...")
        model = get_whisper()
        segments, info = model.transcribe(audio_file, beam_size=5, language="zh")
        transcript = " ".join([s.text for s in segments]).strip()
        
        if not transcript:
            await channel.send("❌ 沒有偵測到語音")
            return
        
        await channel.send(f"📝 **你說：**\n> {transcript}")
        
        # LLM
        await channel.send("🤖 AI 思考中...")
        prompt = f"請簡短回應（50字以內）：{transcript}"
        
        response = ollama.chat(
            model='kimi-k2.5:cloud',
            messages=[{'role': 'user', 'content': prompt}]
        )
        llm_text = response['message']['content'].strip()
        
        await channel.send(f"💬 **AI 回應：**\n{llm_text}")
        
        # TTS
        await channel.send("🔊 生成語音...")
        tts_file = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=llm_text[:500], lang='zh-tw')
        tts.save(tts_file)
        
        # 播放
        if voice_client.is_connected() and not voice_client.is_playing():
            source = discord.FFmpegPCMAudio(tts_file)
            voice_client.play(source)
            
            # 等待播放完畢
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
            
            os.remove(tts_file)
            
        await channel.send("✅ 完成！")
        
    except Exception as e:
        await channel.send(f"❌ 處理錯誤: {e}")
        print(f"Error: {e}")

def after_recording(sink, channel, voice_client):
    """錄音結束後的回調"""
    print(f"[Recording] 錄音結束，處理中...")
    
    # 儲存錄音檔案
    temp_file = tempfile.mktemp(suffix=".wav")
    
    # 從 sink 獲取音訊資料
    audio = sink.audio_data
    
    # 合併所有使用者的音訊
    all_audio = bytearray()
    for user_id, data in audio.items():
        all_audio.extend(data.file.read())
    
    # 寫入 WAV
    with wave.open(temp_file, 'wb') as wf:
        wf.setnchannels(sink.vc.decoder.CHANNELS)
        wf.setsampwidth(sink.vc.decoder.SAMPLE_SIZE // sink.vc.decoder.CHANNELS)
        wf.setframerate(sink.vc.decoder.SAMPLING_RATE)
        wf.writeframes(bytes(all_audio))
    
    # 使用 asyncio 執行處理
    asyncio.run_coroutine_threadsafe(
        process_audio_file(temp_file, channel, voice_client),
        bot.loop
    )

@bot.event
async def on_ready():
    print(f"✅ Bot 已登入: {bot.user}")
    print("📋 指令:")
    print("  !join   - 加入語音頻道")
    print("  !listen - 開始錄音 (5秒)")
    print("  !stop   - 停止錄音並處理")
    print("  !leave  - 離開頻道")

@bot.command()
async def join(ctx):
    """加入語音頻道"""
    if ctx.author.voice is None:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    channel = ctx.author.voice.channel
    
    try:
        voice_client = await channel.connect()
        await ctx.send(f"✅ 已加入 {channel.name}！\n輸入 `!listen` 開始錄音")
    except Exception as e:
        await ctx.send(f"❌ 加入失敗: {e}")

@bot.command()
async def listen(ctx, duration: int = 5):
    """
    開始錄音
    用法: !listen [秒數]
    """
    voice_client = ctx.voice_client
    
    if not voice_client or not voice_client.is_connected():
        await ctx.send("❌ 請先用 `!join` 加入語音頻道")
        return
    
    if duration < 1 or duration > 30:
        await ctx.send("⚠️ 錄音時長請在 1-30 秒之間")
        return
    
    # 建立 WaveSink 錄音
    sink = WaveSink()
    
    await ctx.send(f"🎙️ **開始錄音 {duration} 秒...**\n請說話！")
    
    # 開始錄音
    voice_client.start_recording(
        sink,
        lambda *args: after_recording(sink, ctx.channel, voice_client),
        ctx.channel
    )
    
    # 等待指定時間
    await asyncio.sleep(duration)
    
    # 停止錄音
    if voice_client.is_recording():
        voice_client.stop_recording()

@bot.command()
async def stop(ctx):
    """手動停止錄音"""
    voice_client = ctx.voice_client
    
    if not voice_client or not voice_client.is_recording():
        await ctx.send("⚠️ 沒有正在進行的錄音")
        return
    
    await ctx.send("⏹️ **停止錄音，處理中...**")
    voice_client.stop_recording()

@bot.command()
async def leave(ctx):
    """離開語音頻道"""
    voice_client = ctx.voice_client
    
    if not voice_client or not voice_client.is_connected():
        await ctx.send("❌ 不在任何語音頻道中")
        return
    
    if voice_client.is_recording():
        voice_client.stop_recording()
    
    await voice_client.disconnect()
    await ctx.send("👋 已離開語音頻道")

@bot.command()
async def ping(ctx):
    """測試 Bot"""
    await ctx.send("✅ Bot 正常運作！輸入 `!join` 開始使用語音功能。")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    
    print("🚀 啟動 Discord 語音助手 (discord.sinks 版本)")
    bot.run(token)
