#!/usr/bin/env python3
"""
Edge TTS Client - Microsoft Azure Neural Voices (Free)
High-quality text-to-speech for Chinese and other languages
"""

import asyncio
import edge_tts
import os
import tempfile

# Voice Models - Azure Neural Voices
VOICES = {
    # Taiwan Chinese
    "zh-tw-female": "zh-TW-HsiaoChenNeural",  # 曉臻 - Natural female (default)
    "zh-tw-male": "zh-TW-YunJheNeural",        # 雲哲 - Natural male
    # Mainland Chinese  
    "zh-cn-female": "zh-CN-XiaoxiaoNeural",   # 曉曉 - Natural female
    "zh-cn-male": "zh-CN-YunyangNeural",      # 雲揚 - Natural male
    # English
    "en-us-female": "en-US-JennyNeural",
    "en-us-male": "en-US-GuyNeural",
}

DEFAULT_VOICE = VOICES["zh-tw-female"]


async def generate_speech_async(text: str, output_file: str = None, voice: str = None) -> str:
    """
    Generate speech using Microsoft Edge TTS (async)
    
    Args:
        text: Text to convert to speech
        output_file: Output MP3 file path (auto-generated if None)
        voice: Voice ID (default: zh-TW-HsiaoChenNeural)
        
    Returns:
        Path to generated audio file, or None if failed
    """
    if not text or not text.strip():
        print("[Edge TTS] Error: Empty text")
        return None
    
    if output_file is None:
        output_file = tempfile.mktemp(suffix=".mp3")
    
    voice = voice or DEFAULT_VOICE
    
    print(f"[Edge TTS] Generating: {text[:50]}...")
    print(f"[Edge TTS] Voice: {voice}")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        file_size = os.path.getsize(output_file)
        print(f"[Edge TTS] Success: {output_file} ({file_size/1024:.1f} KB)")
        return output_file
    except Exception as e:
        print(f"[Edge TTS] Error: {e}")
        return None


def generate_speech(text: str, output_file: str = None, voice: str = None) -> str:
    """
    Generate speech using Microsoft Edge TTS (sync wrapper)
    
    Args:
        text: Text to convert
        output_file: Output MP3 path
        voice: Voice ID
        
    Returns:
        Path to generated audio file
        
    Example:
        audio_path = generate_speech("Hello world")
        audio_path = generate_speech("Hello", voice="zh-TW-YunJheNeural")
    """
    return asyncio.run(generate_speech_async(text, output_file, voice))


def speak(text: str, output_file: str = None, voice_key: str = None) -> str:
    """
    Simple wrapper for TTS generation using voice keys
    Auto-uses configured voice if no voice_key specified
    
    Args:
        text: Text to speak
        output_file: Output file path (auto-generated if None)
        voice_key: Voice key (auto-detect from config if None)
        
    Returns:
        Path to generated audio file
        
    Example:
        audio_path = speak("你好世界")  # Uses configured/default voice
        audio_path = speak("你好", voice_key="zh-tw-male")
    """
    # Import here to avoid circular import
    try:
        from .voice_config import get_voice_config, VOICES as CONFIG_VOICES
        if voice_key is None:
            config = get_voice_config()
            voice_key = config['voice_key']
        voice = CONFIG_VOICES.get(voice_key, DEFAULT_VOICE)
    except ImportError:
        # Fallback if voice_config not available
        voice = VOICES.get(voice_key, DEFAULT_VOICE)
    
    return generate_speech(text, output_file, voice)


# Export for OpenClaw
__all__ = ["speak", "generate_speech", "generate_speech_async", "VOICES", "DEFAULT_VOICE"]


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 edge_tts_client.py 'text to speak'")
        print("       python3 edge_tts_client.py 'text' --voice zh-tw-male")
        print("       python3 edge_tts_client.py 'text' --output output.mp3")
        print()
        print("Available voices:")
        for key, voice_id in VOICES.items():
            marker = " (default)" if key == "zh-tw-female" else ""
            print(f"  {key}: {voice_id}{marker}")
        sys.exit(1)
    
    text = sys.argv[1]
    output = None
    voice_key = "zh-tw-female"
    
    # Parse arguments
    for i, arg in enumerate(sys.argv):
        if arg == "--output" and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
        if arg == "--voice" and i + 1 < len(sys.argv):
            voice_key = sys.argv[i + 1]
    
    result = speak(text, output, voice_key)
    if result:
        print(f"\nGenerated: {result}")
    else:
        print("\nFailed to generate audio")
        sys.exit(1)
