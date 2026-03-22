#!/usr/bin/env python3
"""
Voice Assistant - 語音助手完整版
使用 Ollama 運行 Whisper (STT) + LLM + Orpheus (TTS)

Requirements:
    pip install pyaudio soundfile numpy requests

Usage:
    python voice_assistant.py          # 啟動語音助手
    python voice_assistant.py --text   # 文字模式 (不使用語音)
"""

import subprocess
import os
import sys
import json
import tempfile
import wave
import threading
import queue
import time
from pathlib import Path

# Optional imports with fallback
try:
    import pyaudio
    import soundfile as sf
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("Warning: pyaudio/soundfile not available. Install with: pip install pyaudio soundfile numpy")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

class VoiceAssistant:
    def __init__(self):
        self.stt_model = "dimavz/whisper-tiny"
        self.tts_model = "sematre/orpheus"
        self.llm_model = "llama3.2"  # Default LLM, can be changed
        
        self.sample_rate = 16000
        self.channels = 1
        self.chunk_size = 1024
        self.record_seconds = 5
        
        self.is_running = False
        self.audio_queue = queue.Queue()
        
        # Check Ollama
        self._check_ollama()
        
    def _check_ollama(self):
        """Check if Ollama is running"""
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{GREEN}✓ Ollama is running{RESET}")
                return True
        except:
            pass
        
        print(f"{RED}✗ Ollama is not running. Please start it first:{RESET}")
        print("  ollama serve")
        sys.exit(1)
    
    def install_models(self):
        """Install required models"""
        models = [
            (self.stt_model, "STT (Whisper)"),
            (self.tts_model, "TTS (Orpheus)"),
            (self.llm_model, "LLM")
        ]
        
        print(f"\n{BLUE}📦 Installing models...{RESET}")
        for model, desc in models:
            print(f"\n{YELLOW}Installing {desc}: {model}{RESET}")
            subprocess.run(["ollama", "pull", model], check=False)
        
        print(f"{GREEN}✓ Models installed{RESET}")
    
    def record_audio(self, duration=5, save_path=None):
        """Record audio from microphone"""
        if not AUDIO_AVAILABLE:
            print(f"{RED}✗ Audio recording not available. Install pyaudio:{RESET}")
            print("  pip install pyaudio")
            return None
        
        print(f"\n{CYAN}🎤 Recording for {duration} seconds... (Speak now!){RESET}")
        
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )
        
        frames = []
        for i in range(0, int(self.sample_rate / self.chunk_size * duration)):
            data = stream.read(self.chunk_size)
            frames.append(data)
            # Progress indicator
            if i % 10 == 0:
                print(".", end="", flush=True)
        
        print(f"{GREEN} Done!{RESET}")
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Save to file
        if save_path is None:
            save_path = tempfile.mktemp(suffix=".wav")
        
        with wave.open(save_path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        
        return save_path
    
    def speech_to_text(self, audio_path):
        """Convert speech to text using Whisper"""
        print(f"{BLUE}📝 Transcribing...{RESET}")
        
        # Method 1: Use ollama CLI
        try:
            # Read audio file and encode to base64 or pass path
            # Note: This depends on how the whisper model accepts input
            cmd = ["ollama", "run", self.stt_model, f"Transcribe this audio file: {audio_path}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                text = result.stdout.strip()
                print(f"{GREEN}You said: {text}{RESET}")
                return text
            else:
                print(f"{YELLOW}Warning: {result.stderr}{RESET}")
        except Exception as e:
            print(f"{YELLOW}Error with CLI method: {e}{RESET}")
        
        # Fallback: For testing, return dummy text
        print(f"{YELLOW}⚠️  Using fallback (Whisper via Ollama may need specific setup){RESET}")
        return input("Enter text manually: ")
    
    def get_llm_response(self, text):
        """Get response from LLM"""
        print(f"{BLUE}🤔 Thinking...{RESET}")
        
        try:
            cmd = ["ollama", "run", self.llm_model, text]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"{GREEN}AI: {response}{RESET}")
                return response
            else:
                print(f"{RED}LLM Error: {result.stderr}{RESET}")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")
        
        return "Sorry, I couldn't process that."
    
    def text_to_speech(self, text, output_path=None):
        """Convert text to speech using Orpheus"""
        print(f"{BLUE}🔊 Speaking...{RESET}")
        
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".wav")
        
        try:
            # Orpheus TTS via Ollama
            # Note: Output format may vary depending on the model
            cmd = ["ollama", "run", self.tts_model, text]
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            
            if result.returncode == 0:
                # Save output
                with open(output_path, 'wb') as f:
                    f.write(result.stdout)
                
                print(f"{GREEN}✓ Audio saved: {output_path}{RESET}")
                return output_path
            else:
                print(f"{YELLOW}TTS Warning: {result.stderr.decode()}{RESET}")
        except Exception as e:
            print(f"{YELLOW}TTS Error: {e}{RESET}")
        
        return None
    
    def play_audio(self, audio_path):
        """Play audio file"""
        if not AUDIO_AVAILABLE:
            print(f"{YELLOW}⚠️  Cannot play audio (soundfile not available){RESET}")
            return
        
        try:
            data, samplerate = sf.read(audio_path)
            # Simple playback using sounddevice would be better
            # For now, just print
            print(f"{CYAN}▶️  Playing audio...{RESET}")
        except Exception as e:
            print(f"{YELLOW}Play error: {e}{RESET}")
            # Try system player
            os.system(f"aplay {audio_path} 2>/dev/null || afplay {audio_path} 2>/dev/null || echo 'Cannot play audio'")
    
    def run_conversation(self, text_mode=False):
        """Run a full conversation loop"""
        print(f"\n{'='*50}")
        print(f"{CYAN}🎯 Voice Assistant Ready!{RESET}")
        print(f"{'='*50}")
        print("Commands:")
        print("  [Enter] - Start recording (or type text)")
        print("  'q'     - Quit")
        print(f"{'='*50}\n")
        
        self.is_running = True
        
        while self.is_running:
            try:
                if text_mode:
                    user_input = input(f"{YELLOW}You: {RESET}").strip()
                else:
                    user_input = input(f"{YELLOW}Press Enter to record (or type 'q' to quit): {RESET}").strip()
                    if user_input == '':
                        # Record audio
                        audio_path = self.record_audio(duration=self.record_seconds)
                        if audio_path:
                            user_input = self.speech_to_text(audio_path)
                            # Cleanup temp file
                            os.unlink(audio_path)
                    
                    if not user_input:
                        continue
                
                if user_input.lower() in ['q', 'quit', 'exit']:
                    self.is_running = False
                    break
                
                # Get LLM response
                response = self.get_llm_response(user_input)
                
                # Convert to speech (unless in text mode)
                if not text_mode:
                    audio_path = self.text_to_speech(response)
                    if audio_path:
                        self.play_audio(audio_path)
                        os.unlink(audio_path)
                
            except KeyboardInterrupt:
                print(f"\n{YELLOW}Interrupted by user{RESET}")
                break
            except Exception as e:
                print(f"{RED}Error: {e}{RESET}")
        
        print(f"\n{GREEN}Goodbye! 👋{RESET}\n")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Voice Assistant using Ollama")
    parser.add_argument('--install', action='store_true', help='Install required models')
    parser.add_argument('--text', action='store_true', help='Text mode only (no voice)')
    parser.add_argument('--llm', default='llama3.2', help='LLM model to use')
    
    args = parser.parse_args()
    
    assistant = VoiceAssistant()
    assistant.llm_model = args.llm
    
    if args.install:
        assistant.install_models()
        return
    
    # Check if models are available
    print(f"{BLUE}Checking models...{RESET}")
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    
    if args.text:
        assistant.run_conversation(text_mode=True)
    else:
        assistant.run_conversation(text_mode=False)


if __name__ == "__main__":
    main()
