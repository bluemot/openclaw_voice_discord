# Voice Assistant 開發進度

## 📅 2026-03-29

### ✅ 已完成

- [x] GPU TTS 服務確認：Port 8080 可用
- [x] Port 8080 支援多語言 TTS (qwen3-tts, tts-1, tts-1-zh, 等)
- [x] CosBot 已更新為分離式架構：
  - STT: Port 8000 (Whisper)
  - TTS: Port 8080 (qwen3-tts)
- [x] TTS 模型改用 qwen3-tts，中文語音品質更好

### 🔧 目前 TTS 架構

```
┌─────────────────────────────────────────────────────────┐
│  CosBot (Voice Bot) #6388                               │
├─────────────────────────────────────────────────────────┤
│  STT: GPU Port 8000                                     │
│  - Model: deepdml/faster-whisper-large-v3-turbo-ct2    │
│  - VAD Filter + Context Prompt                           │
│                                                            │
│  TTS: GPU Port 8080                                     │
│  - Model: tts-1 (英文) / tts-1-zh (中文)               │
│  - Auto-detect language                                  │
└─────────────────────────────────────────────────────────┘
```

### 🔧 Port 8080 可用模型

- `tts-1` / `tts-1-hd` - 通用
- `tts-1-en` / `tts-1-hd-en` - 英文
- `tts-1-zh` / `tts-1-hd-zh` - 中文
- `tts-1-ja` / `tts-1-hd-ja` - 日文
- `tts-1-ko` / `tts-1-hd-ko` - 韓文
- `tts-1-de` / `tts-1-hd-de` - 德文
- `tts-1-fr` / `tts-1-hd-fr` - 法文
- `tts-1-es` / `tts-1-hd-es` - 西班牙文
- `tts-1-ru` / `tts-1-hd-ru` - 俄文
- `tts-1-pt` / `tts-1-hd-pt` - 葡萄牙文
- `tts-1-it` / `tts-1-hd-it` - 義大利文
- `qwen3-tts` - Qwen3 TTS

---

## 📅 2026-03-27

### 🔧 GPU TTS 測試進度

測試多個 GPU TTS 服務端口：

| Port | 服務 | STT | TTS | 狀態 |
|------|------|-----|-----|------|
| 8000 | Kokoro + Whisper | ✅ Whisper | ⚠️ 英文可用，中文 0 bytes | 部分可用 |
| 8080 | - | - | ❌ Connection error | 無服務 |
| 8188 | CosyVoice | - | ❌ HTTP 500/400 error | 需創建 voice |

---

## 📅 2026-03-24

### ✅ 已完成

- [x] `!voice here` 指令 bug 修復（參數解析問題）
- [x] Context Prompt 新增 `code`、`coding` 術語
- [x] Bot 重啟正常運作

### 🔧 指令格式

```
!voice here 輸入 輸出    - 設定目前頻道（例：!voice here voice text）
!voice list              - 列出所有設定
```

---

## 📅 2026-03-23

### ✅ 已完成

- [x] CosBot (Voice Bot) 多頻道版本完成
- [x] GPU STT (deepdml/faster-whisper-large-v3-turbo-ct2)
- [x] VAD Filter 車上降噪功能
- [x] Context Prompt 技術術語增強
- [x] 動態頻道設定系統 (`!voice here`)
- [x] @CosBot 💬 標記觸發語音回覆

### 🔧 Context Prompt 術語庫

```
AI 機器人：CosBot、Jarvis
軟體平台：Discord、OpenClaw、Telegram
語音技術：STT、TTS
版本控制：GitHub、git、pull、push、clone、commit、branch、switch
Discord 術語：channel、頻道、server、guild
AI 工具：gemini、CLI、llm、session、model、prompt、code、coding
系統指令：exec、shell、bash、command、script
```

---

## 📅 2026-03-22

### ✅ 已完成

- [x] 建立專案目錄結構
- [x] 完成 STT → LLM → TTS 完整流程
- [x] 多頻道自動處理 Bot
- [x] Discord 頻道正常運作
- [x] GitHub repo 建立

### 📝 備註

初期嘗試使用 Py-Cord + discord.sinks 實現即時語音對話，但因 Discord 限制：
1. Bot 無法主動監聽語音頻道
2. 錄音時無法同時播放（避免回音）
3. 改用「語音檔上傳 → 處理 → 回傳語音」方案
