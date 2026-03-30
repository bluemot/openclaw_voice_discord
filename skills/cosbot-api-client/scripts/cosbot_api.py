#!/usr/bin/env python3
"""
CosBot API Client - STT and TTS services
Using Microsoft Edge TTS (Azure) for high-quality Chinese speech
"""

from openai import OpenAI
import asyncio
import edge_tts
import os
import tempfile

# GPU server configuration for STT only
HOST_IP = "192.168.122.1"
STT_PORT = "8000"

# Initialize STT client
stt_client = OpenAI(api_key="dummy", base_url=f"http://{HOST_IP}:{STT_PORT}/v1")

# Edge TTS Voices
VOICES = {
    "zh-tw-female": "zh-TW-HsiaoChenNeural",  # 曉臻 - Natural female (default)
    "zh-tw-male": "zh-TW-YunJheNeural",        # 雲哲 - Natural male
    "zh-cn-female": "zh-CN-XiaoxiaoNeural",    # 曉曉
    "zh-cn-male": "zh-CN-YunyangNeural",      # 雲揚
}

DEFAULT_VOICE = VOICES["zh-tw-female"]


def transcribe_audio(audio_file, language="zh"):
    """
    Transcribe audio file to text using STT service
    
    Args:
        audio_file: Path to audio file (.mp3, .wav, .ogg)
        language: Language code (default: zh)
    
    Returns:
        Transcribed text, or None if failed
    """
    print(f"[STT] Transcribing: {audio_file}")
    
    if not os.path.exists(audio_file):
        print(f"[STT] Error: File not found: {audio_file}")
        return None
    
    try:
        with open(audio_file, "rb") as f:
            response = stt_client.audio.transcriptions.create(
                model="deepdml/faster-whisper-large-v3-turbo-ct2",
                file=f,
                language=language,
                temperature=0.0
            )
        text = response.text
        print(f"[STT] Result: {text[:100]}...")
        return text
    except Exception as e:
        print(f"[STT] Error: {e}")
        return None


async def generate_speech_async(text, output_file=None, voice=None):
    """
    Generate speech using Microsoft Edge TTS (async)
    
    Args:
        text: Text to convert
        output_file: Output path (default: auto-generated)
        voice: Voice ID (default: zh-TW-HsiaoChenNeural)
    
    Returns:
        Path to audio file, or None if failed
    """
    if not text or not text.strip():
        print("[TTS] Error: Empty text")
        return None
    
    if output_file is None:
        output_file = tempfile.mktemp(suffix=".mp3")
    
    voice = voice or DEFAULT_VOICE
    
    print(f"[TTS] Generating: {text[:50]}...")
    print(f"[TTS] Voice: {voice}")
    
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        
        size = os.path.getsize(output_file)
        print(f"[TTS] Success: {output_file} ({size/1024:.1f} KB)")
        return output_file
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None


def generate_speech(text, output_file=None, voice=None):
    """
    Generate speech using Microsoft Edge TTS (sync wrapper)
    
    Args:
        text: Text to convert
        output_file: Output path (default: auto-generated)
        voice: Voice ID
    
    Returns:
        Path to audio file, or None if failed
    """
    return asyncio.run(generate_speech_async(text, output_file, voice))


def speak(text, output_file=None, voice_key="zh-tw-female"):
    """
    Simple wrapper for TTS generation
    
    Args:
        text: Text to speak
        output_file: Output file path
        voice_key: Voice key (zh-tw-female, zh-tw-male, zh-cn-female, zh-cn-male)
    
    Returns:
        Path to audio file
    """
    voice = VOICES.get(voice_key, DEFAULT_VOICE)
    return generate_speech(text, output_file, voice)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  STT: python3 cosbot_api.py stt audio.mp3")
        print("  TTS: python3 cosbot_api.py tts 'text to speak'")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "stt":
        if len(sys.argv) < 3:
            print("Usage: python3 cosbot_api.py stt audio.mp3")
            sys.exit(1)
        result = transcribe_audio(sys.argv[2])
        if result:
            print(f"\nTranscription: {result}")
    
    elif mode == "tts":
        if len(sys.argv) < 3:
            print("Usage: python3 cosbot_api.py tts 'text'")
            sys.exit(1)
        result = speak(sys.argv[2])
        if result:
            print(f"\nAudio: {result}")
