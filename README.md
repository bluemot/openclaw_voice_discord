# Voice Assistant - Discord 語音助手

## 專案概述

在 Discord 頻道中透過語音訊息與 AI 對話的助手系統。

## 功能

- 🎙️ **語音轉文字 (STT)** - 使用 faster-whisper 將語音轉為文字
- 🤖 **AI 對話 (LLM)** - 使用 Ollama 的 kimi-k2.5:cloud 模型
- 🔊 **文字轉語音 (TTS)** - 使用 gTTS 生成中文語音回應
- 💬 **多頻道支援** - 可設定多個頻道自動處理語音

## 技術架構

```
使用者錄音 (.ogg/.mp3/.wav)
    ↓
FFmpeg 轉換 (16kHz mono)
    ↓
Whisper STT (tiny model)
    ↓
Ollama LLM (kimi-k2.5:cloud)
    ↓
gTTS TTS (zh-tw)
    ↓
Discord 語音回應 (.mp3)
```

## 檔案結構

| 檔案 | 說明 |
|-----|------|
| `multi_channel_voice_bot.py` | 多頻道語音 Bot（最新） |
| `smart_voice_bot.py` | 智能狀態管理版本 |
| `pycord_sink_bot.py` | Py-Cord + discord.sinks |
| `discord_file_bot.py` | 基礎檔案處理版本 |

## 使用方式

1. 在 Discord 文字頻道傳送語音檔案
2. Bot 自動處理並回應語音

## 依賴

- faster-whisper
- ollama
- gTTS
- discord.py / py-cord
- ffmpeg

## 開發者

Jarvis (AI Assistant) + Tom
