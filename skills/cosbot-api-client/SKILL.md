---
name: cosbot-api-client
description: Use CosBot's GPU STT and Microsoft Edge TTS services. Use when user wants speech-to-text (STT) transcription or high-quality text-to-speech (TTS) generation. TTS uses Microsoft Azure Neural Voices via edge-tts (free, high quality).
---

# CosBot API Client

Use CosBot's GPU-powered Speech-to-Text (STT) and Microsoft Edge TTS services.

## Quick Start

### STT (Speech to Text)

```python
from skills.cosbot-api-client.scripts.cosbot_api import transcribe_audio

# Transcribe an audio file
text = transcribe_audio("recording.mp3")
print(f"Transcription: {text}")
```

### TTS (Text to Speech) - Microsoft Edge TTS

```python
from skills.cosbot-api-client.scripts.cosbot_api import speak, generate_speech

# Simple usage (Taiwan female voice by default)
audio_file = speak("你好，這是測試語音")

# Specify voice
audio_file = speak("你好", voice_key="zh-tw-male")
audio_file = speak("Hello", voice_key="zh-cn-female")

# Custom output file
audio_file = generate_speech("你好世界", output_file="output.mp3")
print(f"Audio saved to: {audio_file}")
```

## Configuration

| Service | Endpoint | Technology |
|---------|----------|------------|
| **STT** | `192.168.122.1:8000` | Whisper (GPU) |
| **TTS** | Microsoft Edge TTS (Free) | Azure Neural Voices |

## Available Voices

| Voice Key | Description |
|-----------|-------------|
| `zh-tw-female` | 曉臻 - Taiwan Female (default) |
| `zh-tw-male` | 雲哲 - Taiwan Male |
| `zh-cn-female` | 曉曉 - China Female |
| `zh-cn-male` | 雲揚 - China Male |

## CLI Usage

```bash
# STT
./scripts/transcribe.py recording.mp3

# TTS
./scripts/tts_cli.py "你好世界"
./scripts/tts_cli.py "Hello" --voice zh-cn-female
```

## Dependencies

```bash
pip install edge-tts openai
```

Microsoft Edge TTS is free and doesn't require API keys.
