# Voice Assistant - Check File

Last updated: 2026-03-22

## Check Pattern

Check the following indicators for project status:

1. **Recent file modifications** (last 24h)
2. **Running processes** - check for active voice bot processes
3. **Error logs** - any recent errors in logs
4. **Configuration changes** - any changes to bot setup

## Quick Status

- Bot process: Check if any `*voice*bot*.py` processes are running
- Discord connection: Check if bot is connected to Discord
- API status: Check Ollama API availability

## Update Detection

Updates found if:
- New Python files added or modified
- Configuration files changed (requirements.txt, etc.)
- Documentation updated
- Bot functionality broken or fixed
