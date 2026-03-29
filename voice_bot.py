#!/usr/bin/env python3
"""
Voice Bot - 動態多頻道語音助手

功能：
- 可加入多個 Discord 頻道
- 每個頻道可獨立設定輸入/輸出模式
- GPU STT + GPU TTS

流程：
1. 收到語音 → GPU STT 轉文字 → 發到頻道
2. 偵測到 @CosBot 💬 → GPU TTS 轉語音 → 播放

Usage:
    export DISCORD_BOT_TOKEN="你的token"
    python3 voice_bot.py
"""

import os
import json
import asyncio
import discord
from discord.ext import commands
import tempfile
import subprocess
from openai import OpenAI
import ollama
from gtts import gTTS
import torch
import numpy as np
import soundfile as sf

# ============ 設定 ============
CONFIG_FILE = "voice_channel_config.json"
JARVIS_USER_ID = "931691223989772308"  # Jarvis (Tom) 的 Discord user ID

# GPU 伺服器設定
HOST_IP = "192.168.122.1"
STT_PORT = "8000"
TTS_PORT = "8080"

# STT client (port 8000)
stt_client = OpenAI(
    api_key="dummy-key-not-used",
    base_url=f"http://{HOST_IP}:{STT_PORT}/v1"
)

# TTS client (port 8080)
tts_client = OpenAI(
    api_key="dummy-key-not-used",
    base_url=f"http://{HOST_IP}:{TTS_PORT}/v1"
)

# Silero VAD 模型
vad_model = None

def load_vad_model():
    """載入 Silero VAD 模型"""
    global vad_model
    if vad_model is None:
        print("[VAD] 載入 Silero VAD 模型...")
        try:
            vad_model, utils = torch.hub.load(
                'snakers4/silero-vad', 
                'silero_vad', 
                onnx=False,
                trust_repo=True
            )
            print("[VAD] Silero VAD 模型載入成功!")
        except Exception as e:
            print(f"[VAD] 載入失敗: {e}")
            vad_model = None
    return vad_model

def denoise_audio(audio_path):
    """使用 Silero VAD 去除非語音片段"""
    model = load_vad_model()
    if model is None:
        print("[VAD] VAD 模型未載入，返回原始音檔")
        return audio_path
    
    print("[VAD] 處理降噪...")
    try:
        # 讀取音訊
        wav, sr = sf.read(audio_path)
        
        # 轉換為單聲道如果需要
        if len(wav.shape) > 1:
            wav = wav.mean(axis=1)
        
        # 確保是 float32
        wav = wav.astype(np.float32)
        
        # 標準化
        if wav.max() > 1.0:
            wav = wav / 32768.0
        
        wav_tensor = torch.from_numpy(wav).float()
        
        # 取得每個片段的語音機率
        chunk_size = 512  # 32ms at 16kHz
        speech_probs = []
        
        for i in range(0, len(wav_tensor), chunk_size):
            chunk = wav_tensor[i:i+chunk_size]
            if len(chunk) == chunk_size:
                with torch.no_grad():
                    prob = model(chunk.unsqueeze(0), 16000).item()
                speech_probs.append(prob)
            else:
                speech_probs.append(0.0)
        
        # 找出語音片段（機率 > 0.5）
        threshold = 0.5
        speech_chunks = []
        for i, prob in enumerate(speech_probs):
            if prob > threshold:
                speech_chunks.append(wav_tensor[i*chunk_size:(i+1)*chunk_size])
        
        if not speech_chunks:
            print("[VAD] 未偵測到語音，返回原始音檔")
            return audio_path
        
        # 合併語音片段
        speech = torch.cat(speech_chunks)
        
        # 寫入新檔案
        denoised_path = audio_path.replace('.wav', '_denoised.wav')
        sf.write(denoised_path, speech.numpy(), 16000)
        print(f"[VAD] 降噪完成: {len(speech_chunks)} 片段")
        return denoised_path
        
    except Exception as e:
        print(f"[VAD] 降噪錯誤: {e}")
        return audio_path

intents = discord.Intents.default()
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 語音客戶端
connected_voice_clients = {}

# ============ GPU STT/TTS 函式 ============
def transcribe_via_gpu(audio_path):
    """使用 GPU 做 STT"""
    print(f"[GPU-STT] 檢查音檔: {audio_path}")
    if not os.path.exists(audio_path):
        print("[GPU-STT] 錯誤：檔案不存在")
        return ""
    
    print("[GPU-STT] 上傳到 GPU 處理...")
    
    # 上下文提示詞，幫助辨識專有名詞
    context_prompt = """以下是技術相關術語，請根據發音轉換：
    
    AI 機器人：CosBot、Jarvis
    
    軟體平台：Discord、OpenClaw、Telegram
    
    語音技術：STT、TTS
    
    版本控制：GitHub、git、pull、push、clone、commit、branch、switch、stash、merge、rebase、fetch、diff
    
    Discord 術語：channel、頻道、server、guild、role、permission
    
    AI/ML：Whisper、Ollama、GPT、Claude、LLaMA、faster-whisper、large-v3-turbo、Gemini、LLaMA
    
    AI 工具：gemini、CLI、llm、session、model、prompt、temperature、token、code、coding
    
    硬體：GPU、CPU、VRAM
    
    API相關：token、key、endpoint、base_url、webhook、API、REST
    
    程式框架：Python、JavaScript、Node.js、React
    
    系統指令：update、install、download、upload、restart、debug、log、run、execute、build、exec、shell、bash、command、script、process
    
    其他：config、setting、workspace、directory、path、file、folder、memory"""
    
    
    try:
        with open(audio_path, "rb") as f:
            response = stt_client.audio.transcriptions.create(
                model="deepdml/faster-whisper-large-v3-turbo-ct2",
                file=f,
                language="zh",
                temperature=0.0,
                prompt=context_prompt,
                extra_body={
                    "vad_filter": True,
                    "condition_on_previous_text": False,
                    "no_speech_threshold": 0.6
                }
            )
        print(f"[GPU-STT] 成功: {response.text}")
        return response.text
    except Exception as e:
        print(f"[GPU-STT] 錯誤: {e}")
        return ""

def generate_voice_via_gpu(text, output_filename=None, voice="alloy", model="qwen3-tts"):
    """使用 GPU 做 TTS (port 8080) - qwen3-tts 模型"""
    if not text.strip():
        print("[GPU-TTS] 錯誤：無文字內容")
        return None
    
    if output_filename is None:
        output_filename = tempfile.mktemp(suffix=".mp3")
    
    print(f"[GPU-TTS] 生成語音: {text[:50]}...")
    print(f"[GPU-TTS] 使用模型: {model}")
    try:
        response = tts_client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )
        response.stream_to_file(output_filename)
        print(f"[GPU-TTS] 成功: {output_filename}")
        return output_filename
    except Exception as e:
        print(f"[GPU-TTS] 錯誤: {e}")
        return None


def test_tts_sample(text="你好，這是 CosBot 的測試語音。", voice="alloy"):
    """測試 TTS 生成語音樣本"""
    print(f"[TTS Test] 生成測試語音...")
    print(f"[TTS Test] 文字: {text}")
    print(f"[TTS Test] Voice: {voice}")
    
    output_file = "cosbot_tts_sample.mp3"
    result = generate_voice_via_gpu(text, output_file, voice)
    
    if result:
        import os
        file_size = os.path.getsize(result)
        print(f"[TTS Test] ✅ 成功！檔案: {result} ({file_size/1024:.1f} KB)")
    else:
        print("[TTS Test] ❌ 失敗")
    
    return result

# ============ 設定管理 ============
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"channels": {}}
    return {"channels": {}}

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def set_channel_config(channel_id, name, input_mode, output_mode):
    config = load_config()
    config["channels"][str(channel_id)] = {
        "name": name,
        "input": input_mode,
        "output": output_mode
    }
    save_config(config)
    return config["channels"][str(channel_id)]

def remove_channel_config(channel_id):
    config = load_config()
    channel_id = str(channel_id)
    if channel_id in config["channels"]:
        del config["channels"][channel_id]
        save_config(config)
        return True
    return False

def get_channel_config(channel_id):
    config = load_config()
    return config["channels"].get(str(channel_id))

def is_audio(filename):
    audio_exts = ['.mp3', '.wav', '.m4a', '.ogg', '.mov', '.mp4']
    return any(filename.lower().endswith(ext) for ext in audio_exts)

# ============ 語音播放 ============
async def play_audio_file(audio_path, voice_client):
    """播放音訊檔案到語音頻道"""
    if not voice_client or not voice_client.is_connected():
        return False
    
    try:
        # 等待當前播放完畢
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        
        # 播放
        source = discord.FFmpegPCMAudio(audio_path)
        voice_client.play(source)
        
        # 等待播放完畢
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        
        return True
    except Exception as e:
        print(f"[播放錯誤] {e}")
        return False

async def play_tts(text, voice_client):
    """播放 TTS 語音到語音頻道（使用 GPU）"""
    if not voice_client or not voice_client.is_connected():
        return
    
    try:
        # 使用 GPU TTS
        tts_file = generate_voice_via_gpu(text)
        
        if tts_file and os.path.exists(tts_file):
            await play_audio_file(tts_file, voice_client)
            os.remove(tts_file)
        else:
            # fallback 到 gTTS
            tts_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=text[:500], lang='zh-tw')
            tts.save(tts_file)
            await play_audio_file(tts_file, voice_client)
            os.remove(tts_file)
        
    except Exception as e:
        print(f"[TTS Play Error] {e}")

async def play_tts_to_channel(text, channel_id):
    """發送 TTS 到文字頻道（使用 GPU）"""
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    
    try:
        # 使用 GPU TTS
        tts_file = generate_voice_via_gpu(text)
        
        if tts_file and os.path.exists(tts_file):
            await channel.send(file=discord.File(tts_file))
            os.remove(tts_file)
        else:
            # fallback 到 gTTS
            tts_file = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=text[:500], lang='zh-tw')
            tts.save(tts_file)
            await channel.send(file=discord.File(tts_file))
            os.remove(tts_file)
    except Exception as e:
        print(f"[TTS Send Error] {e}")

# ============ STT 處理 ============
async def process_speech_to_text(audio_path, text_channel, user):
    """語音轉文字，發送到頻道"""
    try:
        # 直接使用 GPU STT（GPU 端已有 VAD）
        transcript = transcribe_via_gpu(audio_path)
        
        if not transcript:
            await text_channel.send("❌ 沒有偵測到語音內容")
            return
        
        user_name = user.name if user else "使用者"
        
        # 發送轉錄文字到頻道
        await text_channel.send(
            f"📝 **{user_name}** 說：\n> {transcript}\n\n"
            f"_Jarvis 正在回覆中..._"
        )
        
        print(f"[STT] {user_name}: {transcript}")
        
    except Exception as e:
        print(f"[STT Error] {e}")
        await text_channel.send(f"❌ STT 處理失敗: {e}")

# ============ 訊息監控 ============
voice_bot_messages = set()  # message_ids

@bot.event
async def on_message(message):
    """處理訊息"""
    global voice_bot_messages
    
    # 忽略自己的訊息
    if message.author == bot.user:
        voice_bot_messages.add(message.id)
        if len(voice_bot_messages) > 100:
            voice_bot_messages = set(list(voice_bot_messages)[-50:])
        return
    
    # 檢查是否為設定的頻道
    config = get_channel_config(message.channel.id)
    if not config:
        await bot.process_commands(message)
        return
    
    # 處理 !voice 指令
    if message.content.startswith('!voice'):
        await bot.process_commands(message)
        return
    
    # ========== 語音輸入處理 ==========
    if config['input'] == 'voice':
        if message.attachments:
            for attachment in message.attachments:
                if is_audio(attachment.filename):
                    await message.channel.send("🎙️ 收到語音，轉換文字中...")
                    
                    # 下載
                    temp_dir = tempfile.mkdtemp()
                    audio_path = os.path.join(temp_dir, attachment.filename)
                    await attachment.save(audio_path)
                    
                    # 轉換
                    wav_path = os.path.join(temp_dir, "audio.wav")
                    subprocess.run(
                        f'ffmpeg -i "{audio_path}" -ar 16000 -ac 1 "{wav_path}" -y 2>/dev/null',
                        shell=True
                    )
                    
                    if os.path.exists(wav_path):
                        await process_speech_to_text(wav_path, message.channel, message.author)
                    
                    import shutil
                    shutil.rmtree(temp_dir)
                    break
    
    # ========== 偵測需要語音回覆 ==========
    if bot.user in message.mentions:
        text = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        # 檢查是否為語音回覆請求（包含 💬 標記）
        if text.startswith('💬'):
            clean_text = text[1:].strip()
            print(f"[語音回覆請求] {clean_text[:100]}...")
            
            voice_client = connected_voice_clients.get(message.guild.id)
            if voice_client and voice_client.is_connected():
                await message.channel.send("🔊 播放語音回覆...")
                await play_tts(clean_text, voice_client)
            else:
                await message.channel.send("🔊")
                await play_tts_to_channel(clean_text, message.channel.id)
    
    await bot.process_commands(message)

# ============ 語音頻道連接 ============
@bot.command(name='join')
async def join_voice(ctx):
    """加入語音頻道"""
    if not ctx.author.voice:
        await ctx.send("❌ 請先加入語音頻道")
        return
    
    voice_state = ctx.author.voice
    channel = voice_state.channel
    
    try:
        voice_client = await channel.connect()
        connected_voice_clients[ctx.guild.id] = voice_client
        await ctx.send(f"✅ 已連接到 **{channel.name}** 語音頻道")
    except Exception as e:
        await ctx.send(f"❌ 連接失敗: {e}")

@bot.command(name='leave')
async def leave_voice(ctx):
    """離開語音頻道"""
    guild_id = ctx.guild.id
    if guild_id in connected_voice_clients:
        await connected_voice_clients[guild_id].disconnect()
        del connected_voice_clients[guild_id]
        await ctx.send("👋 已離開語音頻道")
    else:
        await ctx.send("❌ 沒有連接到任何語音頻道")

# ============ 設定指令 ============
@bot.command(name='voice')
async def voice_cmd(ctx, action=None, *args):
    """頻道設定指令
    
    用法：
    !voice here 輸入 輸出    - 設定目前頻道
    !voice add 頻道ID 輸入 輸出 - 設定其他頻道
    !voice list              - 列出設定
    !voice remove 頻道ID      - 移除設定
    """
    
    if action is None or action == 'help':
        embed = discord.Embed(
            title="🎙️ Voice Bot 指令",
            color=discord.Color.blue()
        )
        embed.add_field(name="設定目前頻道", value="`!voice here 輸入 輸出`", inline=False)
        embed.add_field(name="範例", value="`!voice here voice text`", inline=False)
        embed.add_field(name="設定頻道", value="`!voice add 頻道ID 輸入 輸出`", inline=False)
        embed.add_field(name="加入語音", value="`!join` - 加入語音頻道", inline=False)
        embed.add_field(name="離開語音", value="`!leave` - 離開語音頻道", inline=False)
        await ctx.send(embed=embed)
        return
    
    # !voice here voice text - 快速設定目前頻道
    if action == 'here':
        if len(args) != 2:
            await ctx.send("❌ 請提供模式：`!voice here 輸入 輸出`")
            return
        
        input_mode, output_mode = args
        if input_mode not in ['voice', 'text'] or output_mode not in ['voice', 'text']:
            await ctx.send("❌ 模式錯誤：請使用 `voice` 或 `text`")
            return
        
        current_channel_id = ctx.channel.id
        set_channel_config(current_channel_id, ctx.channel.name, input_mode, output_mode)
        await ctx.send(f"✅ 已設定 **{ctx.channel.name}**\n📥 {input_mode} → 📤 {output_mode}")
        return
    
    if action == 'add':
        if len(args) != 3:
            await ctx.send("❌ 請提供完整參數：`!voice add 頻道ID 輸入 輸出`")
            return
        
        channel_id_str, input_mode, output_mode = args
        if input_mode not in ['voice', 'text'] or output_mode not in ['voice', 'text']:
            await ctx.send("❌ 模式錯誤：請使用 `voice` 或 `text`")
            return
        
        channel = ctx.guild.get_channel(int(channel_id_str))
        if not channel:
            await ctx.send(f"❌ 找不到頻道 ID：{channel_id_str}")
            return
        
        set_channel_config(channel.id, channel.name, input_mode, output_mode)
        await ctx.send(f"✅ 已設定 **{channel.name}**\n📥 {input_mode} → 📤 {output_mode}")
        return
        
    if action == 'remove':
        if len(args) != 1:
            await ctx.send("❌ 請提供頻道 ID：`!voice remove 頻道ID`")
            return
        
        channel_id_str = args[0]
        if remove_channel_config(int(channel_id_str)):
            await ctx.send("✅ 已移除")
        else:
            await ctx.send("❌ 該頻道沒有設定")
        return
            
    if action == 'list':
        config = load_config()
        channels = config.get("channels", {})
        
        if not channels:
            await ctx.send("📋 沒有設定任何頻道")
            return
        
        text = "**📋 頻道設定：**\n"
        for ch_id, ch in channels.items():
            text += f"#{ch['name']}: {ch['input']} → {ch['output']}\n"
        await ctx.send(text)
        return

# ============ 啟動 ============
@bot.event
async def on_ready():
    print(f"✅ Voice Bot 已登入: {bot.user}")
    print(f"🎯 Jarvis User ID: {JARVIS_USER_ID}")
    print(f"🌐 GPU STT: {HOST_IP}:{STT_PORT}")
    print(f"🌐 GPU TTS: {HOST_IP}:{TTS_PORT}")
    print(f"📝 STT 模型: deepdml/faster-whisper-large-v3-turbo-ct2")
    print(f"🔊 TTS 模型: qwen3-tts")
    
    print("\n📋 指令：")
    print("  !voice add 頻道ID 輸入 輸出  - 設定頻道")
    print("  !voice list                    - 列出頻道")
    print("  !join                          - 加入語音頻道")
    print("  !leave                         - 離開語音頻道")

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN")
        exit(1)
    
    print("🚀 啟動 Voice Bot...")
    bot.run(token)
