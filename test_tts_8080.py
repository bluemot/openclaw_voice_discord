#!/usr/bin/env python3
"""
測試 TTS - port 8080
"""

from openai import OpenAI
import os

HOST_IP = "192.168.122.1"
PORT = "8080"

tts_client = OpenAI(
    api_key="dummy",
    base_url=f"http://{HOST_IP}:{PORT}/v1"
)

print(f"Testing TTS on port {PORT}...")
print("=" * 50)

# Check models
print("\n1. Checking available models...")
try:
    models = tts_client.models.list()
    for m in models.data:
        print(f"   - {m.id}")
except Exception as e:
    print(f"   Error: {e}")

# Test TTS
print(f"\n2. Testing tts-1 generation...")
try:
    resp = tts_client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input="你好，我是 CosBot，這是 port 8080 的 TTS 測試。",
        response_format="mp3"
    )
    resp.stream_to_file("tts_8080_test.mp3")
    size = os.path.getsize("tts_8080_test.mp3")
    print(f"   ✅ Success! tts_8080_test.mp3 ({size/1024:.1f} KB)")
except Exception as e:
    print(f"   ❌ Error: {e}")