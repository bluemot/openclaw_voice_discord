#!/bin/bash
# CosBot Auto-start Script

cd /home/ubuntu/.openclaw/workspace/voice_assistant

# Check if already running
if pgrep -f "voice_bot.py" > /dev/null; then
    echo "CosBot is already running."
    exit 0
fi

# Load token from .env
export $(grep -v '^#' .env | xargs)

# Start bot
nohup python3 voice_bot.py > bot_run.log 2>&1 &
echo "CosBot started with PID: $!"