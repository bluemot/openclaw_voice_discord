#!/usr/bin/env python3
"""
多頻道語音助手 Bot

功能：
1. 自動處理指定頻道中的所有語音檔案
2. 在其他頻道只回應 @Bot 的訊息
3. 支援多個頻道同時運作

設定：
- AUTO_PROCESS_CHANNELS: 自動處理的頻道 ID 列表
- 這些頻道中的語音檔案會自動觸發 STT → LLM → TTS

Usage:
    export DISCORD_BOT_TOKEN="你的token"
    python3 multi_channel_voice_bot.py
"""

import discord
from discord.ext import commands
import os
import tempfile
from faster_whisper import WhisperModel
import ollama
from gtts import gTTS

# ============ 設定 ============
# 自動處理的頻道 ID 列表
AUTO_PROCESS_CHANNELS = [
    "1481223673519280211",  # 語音助手-接上 discord
    # 添加更多頻道...
]

# ============ Bot 設定 ============
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 全域模型（Lazy loading）
whisper_model = None

def get_whisper():
    """取得 Whisper 模型"""
    global whisper_model
    if whisper_model is None:
        print("🔄 載入 Whisper 模型...")
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("✅ Whisper 載入完成")
    return whisper_model

# ============ 核心處理函式 ============
async def process_voice_file(audio_path, channel):
    """處理單個語音檔案"""
    try:
        print(f"🔄 處理: {os.path.basename(audio_path)}")
        
        # STT
        model = get_whisper()
        segments, info = model.transcribe(audio_path, beam_size=5, language="zh")
        transcript = " ".join([s.text for s in segments]).strip()
        
        if not transcript:
            await channel.send("❌ 沒有偵測到語音內容")
            return
        
        print(f"📝 轉錄: {transcript}")
        
        # 發送轉錄結果
        await channel.send(f"📝 **使用者說：**\n> {transcript}")
        
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
        
        print(f"💬 AI: {llm_text}")
        
        # TTS
        tts_file = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=llm_text[:500], lang='zh-tw')
        tts.save(tts_file)
        
        # 發送回應
        await channel.send(f"💬 **AI 回應：**\n{llm_text}\n🔊", 
                          file=discord.File(tts_file))
        
        # 清理
        os.remove(tts_file)
        
        print(f"✅ 處理完成")
        
    except Exception as e:
        print(f"❌ 錯誤: {e}")
        await channel.send(f"❌ 處理失敗: {e}")

# ============ Discord 事件 ============
@bot.event
async def on_ready():
    """Bot 啟動"""
    print(f"✅ 多頻道語音助手已登入: {bot.user}")
    print(f"📋 自動處理頻道: {len(AUTO_PROCESS_CHANNELS)} 個")
    for ch_id in AUTO_PROCESS_CHANNELS:
        channel = bot.get_channel(int(ch_id))
        if channel:
            print(f"   - {channel.name} ({ch_id})")
        else:
            print(f"   - [無法存取] {ch_id}")
    print("\n🎯 功能:")
    print("   - 指定頻道：自動處理所有語音檔案")
    print("   - 其他頻道：回應 @Bot 的訊息")
    print("   - 指令: !help 查看說明")

@bot.event
async def on_message(message):
    """處理訊息"""
    # 忽略自己的訊息
    if message.author == bot.user:
        return
    
    # 檢查是否在自動處理頻道
    channel_id = str(message.channel.id)
    is_auto_channel = channel_id in AUTO_PROCESS_CHANNELS
    
    # 檢查是否有附件
    if message.attachments:
        # 檢查是否為音訊檔案
        audio_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.mov', '.mp4']
        attachment = message.attachments[0]
        
        if any(attachment.filename.lower().endswith(ext) for ext in audio_extensions):
            if is_auto_channel:
                # 自動處理
                await message.channel.send(f"🎙️ 收到語音檔案，處理中...")
                
                # 下載
                temp_dir = tempfile.mkdtemp()
                input_path = os.path.join(temp_dir, attachment.filename)
                await attachment.save(input_path)
                
                # 轉換為 WAV
                wav_path = os.path.join(temp_dir, "audio.wav")
                if attachment.filename.lower().endswith(('.ogg', '.mov', '.mp4', '.m4a')):
                    os.system(f'ffmpeg -i "{input_path}" -ar 16000 -ac 1 "{wav_path}" -y 2>/dev/null')
                else:
                    wav_path = input_path
                
                if os.path.exists(wav_path):
                    await process_voice_file(wav_path, message.channel)
                
                # 清理
                import shutil
                shutil.rmtree(temp_dir)
                
                return
            else:
                # 非自動頻道，只回應 @Bot
                if bot.user in message.mentions:
                    await message.channel.send("🎙️ 請將語音檔案傳到指定的語音頻道，或直接使用文字對話！")
    
    # 處理 @Bot 的文字訊息（非自動頻道）
    if bot.user in message.mentions and not is_auto_channel:
        # 取得提到 Bot 後的文字
        content = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        if content:
            await message.channel.send("🤖 思考中...")
            
            try:
                response = ollama.chat(
                    model='kimi-k2.5:cloud',
                    messages=[{'role': 'user', 'content': content}]
                )
                llm_text = response['message']['content'].strip()
                await message.channel.send(f"💬 {llm_text}")
            except Exception as e:
                await message.channel.send(f"❌ AI 回應失敗: {e}")
    
    # 處理指令
    await bot.process_commands(message)

# ============ 指令 ============
@bot.command()
async def help(ctx):
    """顯示說明"""
    embed = discord.Embed(
        title="🎙️ 多頻道語音助手",
        description="自動處理語音檔案，AI 即時回應",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 自動處理頻道",
        value=f"{len(AUTO_PROCESS_CHANNELS)} 個頻道已啟用自動處理",
        inline=False
    )
    
    embed.add_field(
        name="🎯 使用方式",
        value="在自動處理頻道上傳語音檔案，Bot 會自動回應",
        inline=False
    )
    
    embed.add_field(
        name="💬 其他頻道",
        value="@Bot 可以直接對話",
        inline=False
    )
    
    embed.add_field(
        name="🔧 管理指令",
        value="`!status` - 查看狀態\n`!channels` - 列出自動頻道",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command()
async def status(ctx):
    """查看狀態"""
    await ctx.send(
        f"✅ Bot 運作中\n"
        f"📊 自動處理頻道: {len(AUTO_PROCESS_CHANNELS)} 個"
    )

@bot.command()
async def channels(ctx):
    """列出自動處理頻道"""
    channel_list = []
    for ch_id in AUTO_PROCESS_CHANNELS:
        channel = bot.get_channel(int(ch_id))
        if channel:
            channel_list.append(f"✅ {channel.name} ({ch_id})")
        else:
            channel_list.append(f"❌ 無法存取 ({ch_id})")
    
    await ctx.send(
        "📋 **自動處理頻道列表：**\n" + "\n".join(channel_list)
    )

# ============ 啟動 ============
if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ 請設定 DISCORD_BOT_TOKEN 環境變數")
        exit(1)
    
    print("🚀 啟動多頻道語音助手...")
    bot.run(token)
