# Voice Assistant 開發進度

## 📅 2026-03-23 (今日)

### ✅ 已完成

- [x] CosBot (Voice Bot) 多頻道版本完成
- [x] GPU STT (deepdml/faster-whisper-large-v3-turbo-ct2)
- [x] VAD Filter 車上降噪功能
- [x] Context Prompt 技術術語增強
- [x] 動態頻道設定系統 (`!voice here`)
- [x] @CosBot 💬 標記觸發語音回覆
- [x] GitHub 已 Push

### 🔧 STT 參數

```python
extra_body={
    "vad_filter": True,                      # 語音活動偵測
    "condition_on_previous_text": False,     # 防止幻覺循環
    "no_speech_threshold": 0.6              # 提高無語音門檻
}
```

### 🔧 Context Prompt 術語庫

```
AI 機器人：CosBot、Jarvis
軟體平台：Discord、OpenClaw、Telegram
語音技術：STT、TTS
版本控制：GitHub、git、pull、push、clone、commit、branch、switch
Discord 術語：channel、頻道、server、guild
AI 工具：gemini、CLI、llm、session、model、prompt
系統指令：exec、shell、bash、command、script
```

### 🔧 目前架構

```
┌─────────────────────────────────────────────────────────┐
│  CosBot (Voice Bot) #6388                             │
├─────────────────────────────────────────────────────────┤
│  STT: GPU (192.168.122.1:8000)                        │
│  - Model: deepdml/faster-whisper-large-v3-turbo-ct2  │
│  - VAD Filter + Context Prompt                         │
│                                                          │
│  TTS: gTTS (zh-tw) [GPU TTS 待確認模型]              │
│  - Fallback: gTTS                                     │
└─────────────────────────────────────────────────────────┘
```

### 📊 頻道設定

| 頻道 ID | 名稱 | 模式 |
|---------|------|------|
| 1481223673519280211 | 語音助手-接上discord | voice → voice |

### 🎯 使用流程

1. 上傳語音 → CosBot GPU STT 轉文字
2. @CosBot 💬 回覆內容 → CosBot TTS 播放

### ⚠️ 待確認

- [ ] GPU TTS 模型（tts-1 安裝中）
- [ ] Kokoro TTS 模型

### 📋 Git Commit

```
[main a439617] feat: Add VAD filter and anti-hallucination parameters
[main 8492b3e] docs: Update PROGRESS.md with VAD parameters
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

---

## 📅 2026-03-21

### ✅ 已完成

- [x] 建立多個 Bot 版本測試
- [x] 確認 Whisper 模型載入正常
- [x] 完成 Discord Bot 部署
