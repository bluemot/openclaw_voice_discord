# Voice Assistant 開發進度

## 📅 2026-03-23 (今日)

### ✅ 已完成

- [x] CosBot (Voice Bot) 多頻道版本完成
- [x] 使用 GPU STT (deepdml/faster-whisper-large-v3-turbo-ct2)
- [x] 使用 GPU TTS (tts-1 alloy)
- [x] 動態頻道設定系統
- [x] @CosBot 💬 標記觸發語音回覆
- [x] Context Prompt 技術術語增強

### 🔧 Context Prompt 術語庫

```
AI 機器人：CosBot、Jarvis
軟體平台：Discord、OpenClaw、Telegram
語音技術：STT、TTS
版本控制：GitHub、git、pull、push、clone、commit、branch、switch、stash、merge、rebase、fetch、diff
Discord 術語：channel、頻道、server、guild、role、permission
AI/ML：Whisper、Ollama、GPT、Claude、LLaMA、faster-whisper、large-v3-turbo、Gemini
AI 工具：gemini、CLI、llm、session、model、prompt、temperature、token
硬體：GPU、CPU、VRAM
API相關：token、key、endpoint、base_url、webhook、API、REST
程式框架：Python、JavaScript、Node.js、React
系統指令：update、install、download、upload、restart、debug、log、run、execute、build、exec、shell、bash、command、script、process
其他：config、setting、workspace、directory、path、file、folder、memory
```

### 🔧 VAD Filter 參數（車上降噪關鍵）

```python
extra_body={
    "vad_filter": True,                      # 啟用語音活動偵測
    "condition_on_previous_text": False,     # 防止幻覺循環
    "no_speech_threshold": 0.6              # 提高無語音門檻
}
```

| 參數 | 功能 | 效果 |
|-----|------|------|
| `vad_filter: True` | 語音活動偵測 | 剪掉純引擎聲、冷氣聲等沒有人聲的片段 |
| `condition_on_previous_text: False` | 關閉前文依賴 | 防止「階段階段階段...」的幻覺循環 |
| `no_speech_threshold: 0.6` | 提高無語音門檻 | 不夠確定的聲音直接當靜音處理 |

> 🚗 **車上錄音測試結果：非常成功！** VAD filter 大幅改善了車內噪音環境的語音辨識品質。

### 🔧 目前架構

```
┌─────────────────────────────────────────────────────────┐
│  CosBot (Voice Bot) #6388                             │
├─────────────────────────────────────────────────────────┤
│  STT: GPU (192.168.122.1:8000)                        │
│  - Model: deepdml/faster-whisper-large-v3-turbo-ct2  │
│  - Context Prompt: 技術術語增強                         │
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

### 🎯 使用流程

1. 上傳語音 → CosBot GPU STT 轉文字
2. @CosBot 💬 回覆內容 → CosBot GPU TTS 播放

### ⚠️ 已知限制

- STT 辨識精準度對某些詞彙仍有限制（已用 Context Prompt 改善）
- Bot 需要被 @ 才能觸發語音回覆

---

## 📅 2026-03-22

### ✅ 已完成

- [x] 建立專案目錄結構
- [x] 完成 STT → LLM → TTS 完整流程
- [x] 多頻道自動處理 Bot
- [x] Discord 頻道正常運作
- [x] GitHub repo 建立

### 🔧 Bot 版本演進

| 版本 | 說明 |
|-----|------|
| `voice_bot.py` | **最終版本** - GPU STT/TTS + Context Prompt |
| `multi_channel_voice_bot.py` | 多頻道版本 |
| `smart_voice_bot.py` | 智能狀態管理版本 |

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
