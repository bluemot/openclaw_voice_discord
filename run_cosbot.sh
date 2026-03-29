#!/bin/bash
cd /home/ubuntu/.openclaw/workspace/voice_assistant
# Load token from .env file
export $(grep -v '^#' .env | xargs)
exec python3 voice_bot.py
