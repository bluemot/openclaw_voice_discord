# 🤖 CosBot 使用指南

## CosBot 是什麼？

CosBot 是 Discord 語音助手，可以將語音轉成文字（STT）並用語音回覆（TTS）。

---

## 功能

| 功能 | 說明 |
|------|------|
| 🎙️ **STT** | 上傳語音檔案 → 自動轉成文字 |
| 🔊 **TTS** | 標記 CosBot 或 @語音助手 → 生成語音回覆 |

---

## 使用方法

### 1. 語音轉文字（STT）

直接在頻道上傳語音檔案（.mp3, .wav, .ogg 等），CosBot 會自動轉成文字。

### 2. 文字轉語音（TTS）

有兩種方式可以觸發語音回覆：

**方式一：標記 CosBot**
```
@CosBot 💬 這裡是要轉成語音的文字
```

**方式二：標記 @語音助手 角色**
```
@語音助手 💬 這裡是要轉成語音的文字
```

> 💡 一定要在文字前面加上 `💬` 表情符號！

---

## 使用範例

```
@語音助手 💬 你好，這是測試語音
```

CosBot 會回傳一個語音檔案，念出「你好，這是測試語音」。

---

## 技術規格

| 項目 | 規格 |
|------|------|
| **STT** | GPU Port 8000 / Whisper (faster-whisper-large-v3-turbo) |
| **TTS** | GPU Port 8080 / qwen3-tts |
| **支援語言** | 中文、英文（自動偵測） |

---

## 指令

| 指令 | 功能 |
|------|------|
| `!voice here voice text` | 設定目前頻道模式 |
| `!voice list` | 列出所有設定 |
| `!join` | 讓 CosBot 加入語音頻道 |
| `!leave` | 讓 CosBot 離開語音頻道 |

---

## GitHub

原始碼：https://github.com/bluemot/openclaw_voice_discord

---

如有問題請聯繫 Tom (@tj13990683)