# Discord Voice Bot 設定指南

## 🎯 功能
- 加入 Discord Voice Channel
- 接收語音訊息 → STT → LLM → TTS → 播放回應
- 支援文字指令

## 📋 前置需求

### 1. 安裝 Python 套件
```bash
cd voice_assistant
pip install --break-system-packages -q discord.py[voice] PyNaCl
# faster-whisper, ollama, gtts 已經安裝
```

### 2. 建立 Discord Bot

1. 前往 https://discord.com/developers/applications
2. 點擊 "New Application"
3. 在 "Bot" 分頁：
   - 點擊 "Add Bot"
   - 關閉 "Public Bot"（如果要私人使用）
   - 開啟以下 Privileged Gateway Intents:
     - ☑️ MESSAGE CONTENT INTENT
     - ☑️ SERVER MEMBERS INTENT
4. 複製 Token（稍後使用）

### 3. 設定 Bot 權限

在 OAuth2 > URL Generator：

**Scopes:**
- ☑️ bot

**Bot Permissions:**
- ☑️ Send Messages
- ☑️ Connect
- ☑️ Speak
- ☑️ Use Voice Activity

複製 URL，貼到瀏覽器，選擇你的伺服器，授權 Bot。

### 4. 設定環境變數

```bash
export DISCORD_BOT_TOKEN="你的機器人token"
```

或寫入 `.env` 檔案：
```bash
echo "DISCORD_BOT_TOKEN=你的機器人token" > .env
```

## 🚀 啟動 Bot

```bash
cd voice_assistant
python3 discord_voice_bot.py
```

## 📝 使用指令

| 指令 | 說明 |
|-----|------|
| `!join` | 讓 Bot 加入你所在的語音頻道 |
| `!leave` | 讓 Bot 離開語音頻道 |
| `!listen 5` | 錄音 5 秒並回應 |
| `!test` | 測試完整流程 |

## 🔧 工作流程

```
使用者說話
    ↓
Discord Voice Channel
    ↓
Bot 錄音
    ↓
faster-whisper (STT)
    ↓
Ollama LLM (kimi-k2.5:cloud)
    ↓
gTTS (TTS)
    ↓
Bot 播放回應
```

## ⚠️ 注意事項

1. **Discord 錄音限制**：Discord.py 的錄音功能需要額外設定
2. **Bot 需要 Manage Channels 權限**才能錄音
3. **Linux 可能需要安裝 opus**：`sudo apt-get install libopus-dev`
4. **FFmpeg 必須安裝**：`sudo apt-get install ffmpeg`

## 🐛 常見問題

**Q: Bot 加入後沒聲音**
A: 檢查 Bot 是否有 "Speak" 權限

**Q: !listen 指令沒反應**
A: Discord.py 的錄音功能比較複雜，可能需要改用其他方案（如接收語音封包）

**Q: TTS 太慢**
A: gTTS 需要網路連線到 Google，可以改用其他離線 TTS 方案

## 💡 進階改進

1. **使用 Discord 的語音接收事件** 代替錄音
2. **改用即時 TTS**（邊生成邊播放）
3. **加入喚醒詞**（如 "Hey Jarvis"）
4. **支援多語言**
5. **加入對話歷史**
