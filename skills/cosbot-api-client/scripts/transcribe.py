#!/usr/bin/env python3
"""
Transcribe audio file using CosBot STT
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cosbot_api import transcribe_audio


def main():
    if len(sys.argv) < 2:
        print("Usage: ./transcribe.py <audio_file>")
        print("       ./transcribe.py recording.mp3")
        print("       ./transcribe.py voice.wav --lang en")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    
    # Check for language flag
    lang = "zh"
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]
    
    print(f"🎙️  Transcribing: {audio_file}")
    print(f"   Language: {lang}")
    print()
    
    result = transcribe_audio(audio_file, language=lang)
    
    if result:
        print(f"\n📝 Transcription:\n{result}")
    else:
        print("\n❌ Transcription failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
