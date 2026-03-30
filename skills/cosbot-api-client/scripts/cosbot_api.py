#!/usr/bin/env python3
"""
CosBot API Client - STT and TTS services
"""

from openai import OpenAI
import os
import tempfile

# GPU server configuration
HOST_IP = "192.168.122.1"
STT_PORT = "8000"
TTS_PORT = "8080"

# Initialize clients
stt_client = OpenAI(api_key="dummy", base_url=f"http://{HOST_IP}:{STT_PORT}/v1")
tts_client = OpenAI(api_key="dummy", base_url=f"http://{HOST_IP}:{TTS_PORT}/v1")


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


def make_text_tts_friendly(original_text, llm_client=None):
    """
    Use wetext + LLM to rewrite text into TTS-foolproof format.
    Prevents mispronunciations by processing acronyms, polyphones, numbers, etc.
    
    Args:
        original_text: Text to process
        llm_client: LLM client for processing (optional)
    
    Returns:
        Processed text optimized for TTS
    """
    processed_text = original_text
    
    # Step 1: Use wetext for text normalization (numbers, time, currency, etc.)
    try:
        import wetext
        processed_text = wetext.normalize(processed_text)
        print(f"[TTS-Friendly] wetext normalized: {original_text[:50]}... -> {processed_text[:50]}...")
    except ImportError:
        print("[TTS-Friendly] Warning: wetext not available, using fallback normalization")
    except Exception as e:
        print(f"[TTS-Friendly] wetext error: {e}")
    
    # Step 2: Use LLM for acronyms and polyphones
    if llm_client is None:
        try:
            import ollama
            llm_client = ollama
        except ImportError:
            return processed_text
    
    system_prompt = """You are a TTS text preparation assistant. Rewrite the input text so a TTS engine will not mispronounce it.

Rules:
1. Separate English acronyms with spaces (e.g., 'API' -> 'A P I', 'GUI' -> 'G U I', 'JSON' -> 'J S O N', 'TTS' -> 'T T S')
2. For Chinese polyphones, replace with unambiguous homophones if necessary (e.g., '重慶' context-dependent pronunciation)
3. Keep the original meaning but make it TTS-friendly
4. Output ONLY the rewritten text, nothing else

Input:"""

    try:
        response = llm_client.generate(
            model='kimi-k2.5:cloud',
            system=system_prompt,
            prompt=processed_text,
            options={'temperature': 0.1}
        )
        final_text = response['response'].strip()
        print(f"[TTS-Friendly] LLM processed: {final_text[:50]}...")
        return final_text
    except Exception as e:
        print(f"[TTS-Friendly] LLM error: {e}, using wetext result only")
        return processed_text


def detect_language(text):
    """Auto-detect language from text"""
    if any('\u4e00' <= c <= '\u9fff' for c in text):
        return "zh"
    if any('\u3040' <= c <= '\u30ff' for c in text):
        return "ja"
    if any('\uac00' <= c <= '\ud7af' for c in text):
        return "ko"
    return "en"


def get_tts_model(lang):
    """Get appropriate TTS model for language"""
    models = {
        "zh": "qwen3-tts",
        "en": "tts-1-en",
        "ja": "tts-1-ja",
        "ko": "tts-1-ko",
        "de": "tts-1-de",
        "fr": "tts-1-fr",
        "es": "tts-1-es",
        "ru": "tts-1-ru",
        "pt": "tts-1-pt",
        "it": "tts-1-it",
    }
    return models.get(lang, "qwen3-tts")


def generate_speech(text, output_file=None, model=None, voice="alloy", tts_friendly=True):
    """
    Generate speech from text using TTS service
    
    Args:
        text: Text to convert
        output_file: Output path (default: auto-generated)
        model: TTS model (default: auto-detect)
        voice: Voice ID (default: alloy)
        tts_friendly: Pre-process text to avoid mispronunciations (default: True)
    
    Returns:
        Path to audio file, or None if failed
    """
    if not text or not text.strip():
        print("[TTS] Error: Empty text")
        return None
    
    # Pre-process text for better TTS
    if tts_friendly:
        text = make_text_tts_friendly(text)
    
    if output_file is None:
        output_file = tempfile.mktemp(suffix=".mp3")
    
    # Auto-detect model
    if model is None:
        lang = detect_language(text)
        model = get_tts_model(lang)
    
    print(f"[TTS] Generating: {text[:50]}...")
    print(f"[TTS] Model: {model}")
    
    try:
        response = tts_client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )
        response.stream_to_file(output_file)
        
        size = os.path.getsize(output_file)
        print(f"[TTS] Success: {output_file} ({size/1024:.1f} KB)")
        return output_file
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return None


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
        result = generate_speech(sys.argv[2])
        if result:
            print(f"\nAudio: {result}")
