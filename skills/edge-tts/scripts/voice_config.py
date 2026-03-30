#!/usr/bin/env python3
"""
Voice Configuration Manager for Edge TTS
Stores and manages voice preferences
"""

import json
import os

# Default config file location
CONFIG_DIR = os.path.expanduser("~/.config/openclaw/edge-tts")
CONFIG_FILE = os.path.join(CONFIG_DIR, "voice_config.json")

# Available voices
VOICES = {
    "zh-tw-female": "zh-TW-HsiaoChenNeural",   # Taiwan Female (default)
    "zh-tw-male": "zh-TW-YunJheNeural",         # Taiwan Male
    "zh-cn-female": "zh-CN-XiaoxiaoNeural",    # China Female
    "zh-cn-male": "zh-CN-YunyangNeural",       # China Male
}

DEFAULT_VOICE_KEY = "zh-tw-female"


def _ensure_config_dir():
    """Ensure config directory exists"""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def get_voice_config():
    """
    Get current voice configuration
    
    Returns:
        dict with 'voice_key' and 'voice_id'
    """
    _ensure_config_dir()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                voice_key = config.get('voice_key', DEFAULT_VOICE_KEY)
                return {
                    'voice_key': voice_key,
                    'voice_id': VOICES.get(voice_key, VOICES[DEFAULT_VOICE_KEY])
                }
        except Exception:
            pass
    
    # Return default
    return {
        'voice_key': DEFAULT_VOICE_KEY,
        'voice_id': VOICES[DEFAULT_VOICE_KEY]
    }


def set_voice(voice_key: str) -> bool:
    """
    Set the voice preference
    
    Args:
        voice_key: One of the available voice keys
        
    Returns:
        True if successful, False otherwise
        
    Example:
        set_voice("zh-tw-male")
        set_voice("zh-cn-female")
    """
    if voice_key not in VOICES:
        print(f"[Voice Config] Error: Unknown voice key '{voice_key}'")
        print(f"[Voice Config] Available: {', '.join(VOICES.keys())}")
        return False
    
    _ensure_config_dir()
    
    try:
        config = {'voice_key': voice_key}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"[Voice Config] Voice changed to: {voice_key} ({VOICES[voice_key]})")
        return True
    except Exception as e:
        print(f"[Voice Config] Error saving config: {e}")
        return False


def list_voices():
    """List all available voices"""
    current = get_voice_config()
    print("Available voices:")
    for key, voice_id in VOICES.items():
        marker = " (current)" if key == current['voice_key'] else ""
        print(f"  • {key}: {voice_id}{marker}")


# Command handlers for Discord integration
def handle_voice_command(command: str, args: list = None) -> str:
    """
    Handle voice-related commands from Discord
    
    Args:
        command: Command name (set, get, list)
        args: Additional arguments
        
    Returns:
        Response message
        
    Examples:
        handle_voice_command("get")
        handle_voice_command("set", ["zh-tw-male"])
        handle_voice_command("list")
    """
    if command == "get":
        config = get_voice_config()
        return f"目前聲音：{config['voice_key']} ({config['voice_id']})"
    
    elif command == "set":
        if not args or len(args) < 1:
            return "請提供聲音代碼，例如：`!voice set zh-tw-male`"
        
        voice_key = args[0]
        if set_voice(voice_key):
            return f"✅ 聲音已切換為：{voice_key}"
        else:
            available = ", ".join(VOICES.keys())
            return f"❌ 無效的聲音代碼。可用選項：{available}"
    
    elif command == "list":
        current = get_voice_config()
        lines = ["🎙️ **可用聲音：**"]
        for key, voice_id in VOICES.items():
            marker = " ⭐ 目前" if key == current['voice_key'] else ""
            lines.append(f"• `{key}`{marker}")
        return "\n".join(lines)
    
    else:
        return "未知指令。可用：`!voice get`, `!voice set <voice_key>`, `!voice list`"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 voice_config.py get          # Get current voice")
        print("  python3 voice_config.py set <key>    # Set voice")
        print("  python3 voice_config.py list         # List all voices")
        sys.exit(1)
    
    cmd = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    if cmd == "get":
        config = get_voice_config()
        print(f"Current: {config['voice_key']}")
    elif cmd == "set":
        if args:
            set_voice(args[0])
        else:
            print("Usage: python3 voice_config.py set <voice_key>")
    elif cmd == "list":
        list_voices()
    else:
        print(f"Unknown command: {cmd}")
