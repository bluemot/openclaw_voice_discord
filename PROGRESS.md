# Voice Assistant 開發進度

## 📅 2026-03-23

### ✅ 已完成

- [x] CosBot (Voice Bot) 多頻道版本完成
- [x] 使用 GPU STT (Systran/faster-whisper-medium)
- [x] 使用 GPU TTS (tts-1 alloy)
- [x] 動態頻道設定系統
- [x] @CosBot 💬 標記觸發語音回覆

### 🔧 目前架構

```
┌─────────────────────────────────────────────────────────┐
│  CosBot (Voice Bot) #6388                             │
├─────────────────────────────────────────────────────────┤
│  STT: GPU (192.168.122.1:8000)                        │
│  - Model: Systran/faster-whisper-medium               │
│  - 比 local faster-whisper 準確很多                    │
│                                                         │
│  TTS: GPU (192.168.122.1:8000)                        │
│  - Model: tts-1 (alloy)                               │
│  - Fallback: gTTS (zh-tw)                             │
└─────────────────────────────────────────────────────────┘
```

### 📊 頻道設定

| 頻道 ID | 名稱 | 模式 |
|---------|------|------|
| 1481223673519280211 | 語音助手-接上discord | voice → voice |
| 1482401200384114933 | 語擦-app | voice → voice |

### 🎯 使用流程

1. 上傳語音 → CosBot GPU STT 轉文字
2. @CosBot 💬 回覆內容 → CosBot GPU TTS 播放

### 📋 檔案

- `voice_bot.py` - CosBot 主程式

---

## 📅 2026-03-22

### ✅ 已完成

- [x] 建立專案目錄結構
- [x] 完成 STT → LLM → TTS 完整流程
- [x] 多頻道自動處理 Bot (multi_channel_voice_bot.py)
- [x] Discord 頻道正常運作
- [x] GitHub repo 建立

### 🔧 Bot 版本

| 檔案 | 說明 |
|-----|------|
| `voice_bot.py` | **最新版本** - GPU STT/TTS + 多頻道 |
| `multi_channel_voice_bot.py` | 多頻道版本 |
| `smart_voice_bot.py` | 智能狀態管理版本 |

### ⚠️ 已知限制

- Bot 無法主動監聽所有頻道（Discord 限制）
- 語音頻道即時對話尚未穩定
- 目前採用的方案：文字頻道傳語音檔 → 處理 → 回傳語音

### 📋 待辦

- [ ] 加入對話歷史記憶
- [ ] 支援更多語言
- [ ] 優化回應延遲

---

## 📅 2026-03-21

### ✅ 已完成

- [x] 建立多個 Bot 版本測試
- [x] 確認 Whisper 模型載入正常
- [x] 完成 Discord Bot 部署

### 📝 備註

初期嘗試使用 Py-Cord + discord.sinks 實現即時語音對話，但因 Discord 限制：
1. Bot 無法主動監聽語音頻道
2. 錄音時無法同時播放（避免回音）
3. 改用「語音檔上傳 → 處理 → 回傳語音」方案
