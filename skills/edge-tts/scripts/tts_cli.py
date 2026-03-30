#!/usr/bin/env python3
"""
CLI for Edge TTS
"""

import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from edge_tts_client import speak, VOICES


def main():
    parser = argparse.ArgumentParser(description="Edge TTS - Text to Speech")
    parser.add_argument("text", help="Text to convert to speech")
    parser.add_argument("--voice", "-v", default="zh-tw-female",
                        choices=list(VOICES.keys()),
                        help="Voice to use (default: zh-tw-female)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output MP3 file path")
    parser.add_argument("--list-voices", "-l", action="store_true",
                        help="List available voices")
    
    args = parser.parse_args()
    
    if args.list_voices:
        print("Available voices:")
        for key, voice_id in VOICES.items():
            marker = " (default)" if key == "zh-tw-female" else ""
            print(f"  {key}: {voice_id}{marker}")
        return
    
    result = speak(args.text, args.output, args.voice)
    if result:
        print(f"Generated: {result}")
    else:
        print("Failed to generate audio")
        sys.exit(1)


if __name__ == "__main__":
    main()
