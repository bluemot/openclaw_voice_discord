# CHECK.md

## Update Check Procedure

Run every hour by cron. Check the following:

### 1. Config Changes
- AGENTS.md changed?
- PROJECTS.md changed?
- OpenClaw config changed?

### 2. New Rules/Updates
- Any new agent rules added?
- Documentation updates?

### 3. Errors/Issues
- Gateway issues?
- Session problems?

## Response Format

**If NO updates:**
```
NO_UPDATE
```

**If updates found:**
Report what changed:
- Files: [list]
- Rules: [summary]

**If errors:**
Report specific error details.