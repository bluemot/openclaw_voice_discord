# 🎙️ Voice Assistant - 語音助手

使用 Ollama 運行 Whisper (STT) + LLM + Orpheus (TTS) 的完整語音對話系統。

## 📁 檔案結構

```
voice_assistant/
├── voice_assistant.py    # 主程式
├── requirements.txt      # Python 依賴
└── README.md            # 說明文件
```

## 🔧 安裝步驟

### 1. 安裝系統依賴

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3-pip portaudio19-dev

# macOS
brew install portaudio
```

### 2. 安裝 Python 套件

```bash
cd voice_assistant
pip install -r requirements.txt
```

### 3. 安裝 Ollama 模型

```bash
# 方法 1: 使用腳本安裝
python3 voice_assistant.py --install

# 方法 2: 手動安裝
ollama pull dimavz/whisper-tiny
ollama pull sematre/orpheus
ollama pull llama3.2  # 或其他你喜歡的 LLM
```

## 🚀 使用方法

### 啟動語音助手

```bash
# 語音模式 (預設)
python3 voice_assistant.py

# 純文字模式 (用於測試)
python3 voice_assistant.py --text

# 使用特定 LLM
python3 voice_assistant.py --llm qwen2.5
```

### 使用流程

1. 啟動後按 **Enter** 開始錄音
2. 對著麥克風說話（預設錄音 5 秒）
3. Whisper 會轉換成文字
4. LLM 產生回應
5. Orpheus 合成語音並播放

### 指令

| 指令 | 說明 |
|-----|------|
| `Enter` | 開始錄音 |
| `q` / `quit` | 退出 |

## ⚙️ 配置

編輯 `voice_assistant.py` 修改設定：

```python
self.stt_model = "dimavz/whisper-tiny"  # 或改用更大的模型
self.tts_model = "sematre/orpheus"
self.llm_model = "llama3.2"            # 可換成其他 LLM

self.record_seconds = 5                # 錄音秒數
```

## 🐛 已知問題

1. **Orpheus TTS 輸出格式**: 需要確認模型輸出的是原始音訊還是文字，可能需要額外處理
2. **Whisper 輸入方式**: 不同版本的 Whisper 模型接受輸入的方式可能不同
3. **音訊播放**: 目前使用系統預設播放器，可能需要根據你的環境調整

## 💡 進階改進

未來可以考慮：
- 使用更快的錄音方式 (VAD - 語音活動檢測)
- 串流式 TTS (邊生成邊播放)
- 支援喚醒詞 (如 "Hey Jarvis")
- 整合到其他應用程式

## 📊 VRAM 使用

在 RTX 5060 (8GB) 上：
- Whisper Tiny: ~1GB
- Orpheus: ~2-3GB
- LLM (llama3.2): ~3-4GB
- 總計: ~6-8GB (剛好夠用)

建議一次只載入一個模型，用完釋放記憶體。
