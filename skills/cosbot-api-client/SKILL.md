---
name: cosbot-api-client
description: Use CosBot's GPU STT and TTS API services with Text Normalization. Use when user wants speech-to-text (STT) transcription or text-to-speech (TTS) generation. Supports Chinese, English, and multiple languages with automatic number/time/date normalization using wetext.
---

# CosBot API Client

Use CosBot's GPU-powered Speech-to-Text (STT) and Text-to-Speech (TTS) services.

## Quick Start

### STT (Speech to Text)

```python
from skills.cosbot-api-client.scripts.cosbot_api import transcribe_audio

# Transcribe an audio file
text = transcribe_audio("recording.mp3")
print(f"Transcription: {text}")
```

### TTS (Text to Speech)

```python
from skills.cosbot-api-client.scripts.cosbot_api import generate_speech

# Generate speech from text (with automatic text normalization)
audio_file = generate_speech("你好，現在是12:30")
# Result: "你好，現在是十二点三十分"
print(f"Audio saved to: {audio_file}")
```

## Text Normalization Features

The TTS function automatically normalizes text using **wetext**:

| Input | Output |
|-------|--------|
| 12:30 | 十二点三十分 |
| 12345元 | 一万两千三百四十五元 |
| 25.5度 | 二十五点五度 |
| 60% | 百分之六十 |
| 2024年3月30日 | 二零二四年三月三十日 |

## API Configuration

| Service | Endpoint | Model |
|---------|----------|-------|
| **STT** | `192.168.122.1:8000` | faster-whisper-large-v3-turbo |
| **TTS** | `192.168.122.1:8080` | qwen3-tts |

## Supported Languages

**STT:** zh, en, ja, ko, de, es, fr, it, pt, ru, and more
**TTS:** zh (qwen3-tts), en, ja, ko, de, fr, es, ru, pt, it

## Dependencies

```bash
pip install wetext pypinyin jieba
```

Text normalization requires the `wetext` package for converting numbers, time, and dates to spoken form.
