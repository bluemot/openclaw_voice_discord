# PROJECTS.md - Project Index

All sessions read this file on startup. Match your session's `chat_id` and `platform` from inbound metadata to find the corresponding project.

## How to Match

When a session starts, it receives metadata like:
```json
{
  "chat_id": "channel:1478378878295867443",
  "channel": "discord",
  "platform": "discord"
}
```

Find the project where `Chat ID` matches your `chat_id`. If found, read the project's documentation files.

---

## CRAG

Code-Graph RAG for code understanding.

- **Channel Name**: `#crag`
- **Chat ID**: `channel:1477323611843858475`
- **Platform**: `discord`
- **Location**: `/home/ubuntu/workspace/crag/`
- **Documentation**: `README.md`, `PROGRESS_GLOBAL.md`

---

## Stock Crawler

Taiwan stock analysis and LINE notification bot.

- **Channel Name**: `#股票分析`
- **Chat ID**: `channel:1477359322760613898`
- **Platform**: `discord`
- **Location**: `/home/ubuntu/.openclaw/workspace/stock_crawler/`
- **Documentation**: `README.md`, `PROGRESS.md`, `STOCK_TOOLS.md`

---

## Manager

Policy and configuration management for OpenClaw.

- **Channel Name**: `#管理`
- **Chat ID**: `channel:1478378878295867443`
- **Platform**: `discord`
- **Location**: `/home/ubuntu/.openclaw/workspace/manager/`
- **Documentation**: `AGENTS_UPDATES.md` - Policy change records

---

## LLM Cosplay Fun

角色扮演研究專案，目標是透過程式與 prompt 工程讓 LLM 能精準模擬特定角色的語氣與人設。

- **Channel Name**: `#app`
- **Chat ID**: `channel:1482401200384114933`
- **Platform**: `discord`
- **Location**: `/home/ubuntu/.openclaw/workspace/llm-cos-fun/`
- **Documentation**: `README.md`, `docs/AICOS_PROGRESS.md`

---

## Adding New Projects

1. Create `README.md` or `PROJECT.md` in the project directory
2. Copy the template below and fill in the details
3. Add the new section above

### Template

```markdown
## Project Name

Brief description of the project.

- **Channel Name**: `#channel-name` (or "none" if not channel-specific)
- **Chat ID**: `channel:XXXXXXXXXXXXXXXXX` (from inbound metadata)
- **Platform**: `discord` / `telegram` / `slack` / etc.
- **Location**: `/path/to/project/`
- **Documentation**: `README.md`, `PROGRESS.md`, etc.
```

---

## Notes

- A project may span multiple channels (add multiple entries with same Location)
- A channel may have multiple projects (read all matching documentation)
- If no project matches, session proceeds without project-specific context
