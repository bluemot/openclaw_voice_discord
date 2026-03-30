#!/usr/bin/env python3
"""
Generate speech using CosBot TTS
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cosbot_api import generate_speech, get_tts_model


def main():
    parser = argparse.ArgumentParser(description='Generate speech with CosBot TTS')
    parser.add_argument('text', help='Text to convert to speech')
    parser.add_argument('-o', '--output', default='cosbot_tts.mp3', help='Output file')
    parser.add_argument('-l', '--lang', choices=['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'ru', 'pt', 'it'],
                        help='Language code (auto-detect if not specified)')
    parser.add_argument('-m', '--model', help='TTS model (auto-select if not specified)')
    parser.add_argument('-v', '--voice', default='alloy', help='Voice ID')
    
    args = parser.parse_args()
    
    # Determine model
    if args.model:
        model = args.model
    elif args.lang:
        model = get_tts_model(args.lang)
    else:
        model = None  # Auto-detect
    
    print(f"🔊 Generating speech: {args.text[:50]}...")
    
    result = generate_speech(
        text=args.text,
        output_file=args.output,
        model=model,
        voice=args.voice
    )
    
    if result:
        print(f"\n✅ Audio saved: {result}")
    else:
        print("\n❌ Failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
