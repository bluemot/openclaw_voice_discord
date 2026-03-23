# AGENTS.md

## Startup
1. SOUL.md, USER.md, PROJECTS.md
2. Match chat_id → read project docs
3. MEMORY.md (main session only)

## Memory
- Project/channel → project dirs
- Personal → MEMORY.md (main only)
- Other → memory/YYYY-MM-DD.md

## Safety
- `trash` > `rm`
- Verify assumptions before concluding impossible

## Chat
- Respond: mentioned, add value, correct misinfo
- Silent: banter, answered, interrupt flow
- One reaction max

## Coding Standards

### Language
- ALL code/docs in ENGLISH
- ASCII only in code blocks

### Before Code
1. Rescan project
2. Impact assessment
3. Consult (STOP if issues)

### After Code (MUST)
1. Run tests
2. Unit tests
3. Syntax check
4. Functional test

**NO VERIFY = NOT DONE**

### Commit
- **NO commit without explicit request**

### Principles
1. One responsibility per module
2. DRY — reuse, don't rewrite
3. Test-Driven

## Gemini CLI

**Default for code mods.**

**MANDATORY:** Include in EVERY prompt:
```
ONLY modify the code. DO NOT run any tests, DO NOT run make, and DO NOT execute any shell commands.
```

- Simple: `gemini -m gemini-3.1-pro-preview "prompt"`
- Complex: `nohup` or background
- After: `py_compile` verify

### Subagent Mode

Gemini CLI can spawn subagents for complex tasks:

```bash
gemini -m gemini-3.1-pro-preview -p "Please $do_somethings, please record what you have done in $the_project_record.md" --yolo
```

- `-m <model>`: Specify model (e.g., `gemini-3.1-pro-preview`)
- `-p` or `--prompt`: Task description
- `--yolo`: Auto-apply changes without confirmation
- Record progress in project documentation files
- **Timeout: Minimum 1800 seconds (30 minutes) for complex tasks**

---
**NO EXCEPTIONS**