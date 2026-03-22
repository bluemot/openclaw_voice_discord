# CHECK.md

## Update Check Procedure

Run every hour by cron. Check the following:

### 1. Content Updates
- New notes added?
- Existing notes modified?

### 2. Organization
- Categories/tags updated?
- Index files changed?

### 3. Sync Status
- Any sync conflicts?
- Backup status?

## Response Format

**If NO updates:**
```
NO_UPDATE
```

**If updates found:**
Report what changed:
- Files: [list]
- Summary: [description]

**If errors:**
Report specific error details.
