#!/usr/bin/env python3
"""
簡化版 Discord Voice Bot - Push-to-Talk 模式
避免即時串流的複雜度，使用錄音檔案方式

工作流程：
1. 使用者輸入 !record 開始錄音
2. 說完話後輸入 !stop 結束錄音
3. Bot 處理：STT → LLM → TTS
4. Bot 播放回應
"""

import discord
from discord.ext import commands, tasks
import asyncio
import os
import tempfile
import wave
import io
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS
import numpy as np
from datetime import datetime

# Bot 設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 全域狀態
recording_sessions = {}  # guild_id -> {audio_buffer, start_time, user_id}
whisper_model = None

def get_whisper_model():
    """取得 Whisper 模型（Lazy loading）"""
    global whisper_model
    if whisper_model is None:
        print("🔄 載入 Whisper 模型...")
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("✅ Whisper 載入完成")
    return whisper_model

# ============ 核心處理函式 ============
async def process_audio_buffer(audio_buffer, sample_rate=48000):
    """
    處理音訊緩衝區
    1. 轉換為 WAV 格式
    2. STT
    3. LLM
    4. TTS
    5. 回傳音訊檔案路徑
    """
    # 儲存為臨時 WAV 檔案
    temp_wav = tempfile.mktemp(suffix=".wav")
    
    try:
        # 寫入 WAV 格式
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(2)  # Discord 語音是立體聲
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(audio_buffer)
        
        print(f"📁 音訊已儲存: {os.path.getsize(temp_wav)} bytes")
        
        # STT
        model = get_whisper_model()
        segments, info = model.transcribe(temp_wav, beam_size=5, language="zh")
        transcript = " ".join([s.text for s in segments])
        
        if not transcript.strip():
            return None, "沒有偵測到語音"
        
        print(f"📝 轉錄: {transcript}")
        
        # LLM
        response = await get_llm_response(transcript)
        print(f"💬 LLM: {response}")
        
        # TTS
        tts_file = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=response[:500], lang='zh-tw')
        tts.save(tts_file)
        
        # 清理
        os.remove(temp_wav)
        
        return tts_file, response
        
    except Exception as e:
        print(f"❌ 處理錯誤: {e}")
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        return None, str(e)

async def get_llm_response(text):
    """取得 LLM 回應"""
    models = ["kimi-k2.5:cloud", "qwen3-coder-next:cloud"]
    prompt = f"請簡短回應（50字以內）：{text}"
    
    for model_name in models:
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response['message']['content'].strip()
        except:
            continue
    
    return f"收到：{text}"

# ============ Discord 指令 ============
@bot.event
async def on_ready():
    """Bot 啟動"""
    print(f"✅ Bot 已登入: {bot.user}")
    print("\n📋 可用指令:")
    print("  !join    - 加入語音頻道")
    print("  !record  - 開始錄音")
    print("  !stop    - 停止錄音並處理")
    print("  !leave   - 離開頻道")

@bot.command()
async def join(ctx):
    """加入語音頻道"""
    if ctx.author.voice is None:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    channel = ctx.author.voice.channel
    voice_client = await channel.connect()
    
    # 初始化錄音狀態
    recording_sessions[ctx.guild.id] = {
        'voice_client': voice_client,
        'recording': False,
        'audio_buffer': bytearray(),
        'user_id': ctx.author.id
    }
    
    await ctx.send(f"✅ 已加入 {channel.name}！\n輸入 `!record` 開始錄音，`!stop` 結束")

@bot.command()
async def record(ctx):
    """開始錄音"""
    if ctx.guild.id not in recording_sessions:
        await ctx.send("❌ 請先用 `!join` 加入語音頻道")
        return
    
    session = recording_sessions[ctx.guild.id]
    
    if session['recording']:
        await ctx.send("⚠️ 已經在錄音中了")
        return
    
    # 開始錄音
    session['recording'] = True
    session['audio_buffer'] = bytearray()
    session['start_time'] = datetime.now()
    
    # 開始接收語音封包
    def callback(user_id, data):
        """接收到語音封包時的 Callback"""
        if session['recording'] and user_id == session['user_id']:
            session['audio_buffer'].extend(data)
    
    session['voice_client'].listen(discord.UserFilter(callback, session['user_id']))
    
    await ctx.send("🎙️ **開始錄音！**\n請說話，說完後輸入 `!stop`")

@bot.command()
async def stop(ctx):
    """停止錄音並處理"""
    if ctx.guild.id not in recording_sessions:
        await ctx.send("❌ 沒有進行中的錄音")
        return
    
    session = recording_sessions[ctx.guild.id]
    
    if not session['recording']:
        await ctx.send("⚠️ 沒有正在錄音")
        return
    
    # 停止錄音
    session['recording'] = False
    
    # 計算錄音時長
    duration = (datetime.now() - session['start_time']).total_seconds()
    
    await ctx.send(f"⏹️ **錄音結束** ({duration:.1f} 秒)\n🔄 處理中...")
    
    # 處理音訊
    audio_buffer = bytes(session['audio_buffer'])
    
    if len(audio_buffer) < 1000:
        await ctx.send("❌ 錄音太短，請再試一次")
        return
    
    # 處理
    result = await process_audio_buffer(audio_buffer)
    audio_file, response_text = result
    
    if audio_file and os.path.exists(audio_file):
        # 發送結果
        await ctx.send(f"📝 你說：\n> {response_text[:100]}", 
                      file=discord.File(audio_file, "response.mp3"))
        
        # 播放回應
        if not session['voice_client'].is_playing():
            source = discord.FFmpegPCMAudio(audio_file)
            session['voice_client'].play(source)
        
        # 清理
        os.remove(audio_file)
    else:
        await ctx.send(f"❌ 處理失敗: {response_text}")

@bot.command()
async def leave(ctx):
    """離開語音頻道"""
    if ctx.guild.id in recording_sessions:
        await recording_sessions[ctx.guild.id]['voice_client'].disconnect()
        del recording_sessions[ctx.guild.id]
        await ctx.send("👋 已離開語音頻道")
    else:
        await ctx.send("❌ 我不在任何語音頻道中")

# ============ 啟動 ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    
    bot.run(token)
