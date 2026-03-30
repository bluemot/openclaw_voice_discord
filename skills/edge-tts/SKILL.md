---
name: edge-tts
description: High-quality text-to-speech using Microsoft Edge TTS (Azure Neural Voices). Free, fast, and natural-sounding Chinese/English voices. Includes voice configuration management - users can switch voices with commands.
---

# Edge TTS Skill

High-quality text-to-speech using Microsoft Edge TTS (Azure Neural Voices).

## Features

- ⚡ **Fast**: Generates audio in seconds
- 🎯 **High Quality**: Azure Neural Voices (natural sounding)
- 💰 **Free**: No API key required
- 🌐 **Multi-language**: Chinese (TW/CN), English, and more
- 🎙️ **Voice Switching**: Change voices dynamically

## Quick Start

```python
from skills.edge-tts.scripts.edge_tts_client import speak
from skills.edge-tts.scripts.voice_config import set_voice, get_voice_config

# Speak with current/default voice
audio_file = speak("你好，這是測試語音")

# Switch to male voice
set_voice("zh-tw-male")

# Now speaks with male voice
audio_file = speak("現在是男聲")

# Check current voice
config = get_voice_config()
print(f"Current: {config['voice_key']}")
```

## Available Voices

| Voice Key | Voice ID | Description |
|-----------|----------|-------------|
| `zh-tw-female` | `zh-TW-HsiaoChenNeural` | Taiwan Female (default) |
| `zh-tw-male` | `zh-TW-YunJheNeural` | Taiwan Male |
| `zh-cn-female` | `zh-CN-XiaoxiaoNeural` | China Female |
| `zh-cn-male` | `zh-CN-YunyangNeural` | China Male |

## Voice Commands (for Discord/Bot Integration)

The skill includes command handlers for voice switching:

```python
from skills.edge-tts.scripts.voice_config import handle_voice_command

# Get current voice
response = handle_voice_command("get")

# Set voice
response = handle_voice_command("set", ["zh-tw-male"])

# List all voices
response = handle_voice_command("list")
```

**Example Discord commands:**
- `!voice get` - Show current voice
- `!voice set zh-tw-male` - Switch to male voice
- `!voice list` - Show all available voices

## CLI Usage

```bash
# Basic (uses configured/default voice)
./scripts/tts_cli.py "你好世界"

# Specify voice
./scripts/tts_cli.py "你好" --voice zh-tw-male

# Custom output
./scripts/tts_cli.py "Hello" --output my_audio.mp3

# List voices
./scripts/tts_cli.py --list-voices
```

## Voice Configuration

Voice preference is saved to `~/.config/openclaw/edge-tts/voice_config.json`

### API Reference

#### `speak(text, output_file=None, voice_key=None)`

Generate speech with optional voice key. Uses configured voice if not specified.

```python
audio_path = speak("Hello")  # Uses configured/default
audio_path = speak("Hello", voice_key="zh-tw-male")  # Override
```

#### `set_voice(voice_key)`

Set the default voice preference.

```python
set_voice("zh-tw-male")
set_voice("zh-cn-female")
```

#### `get_voice_config()`

Get current voice configuration.

```python
config = get_voice_config()
# Returns: {'voice_key': 'zh-tw-female', 'voice_id': 'zh-TW-HsiaoChenNeural'}
```

## Dependencies

```bash
pip install edge-tts
```

## Notes

- Edge TTS uses Microsoft's Azure Neural Voices (free tier)
- Requires internet connection
- Generated audio is saved as MP3 format
- Voice preference persists across sessions
