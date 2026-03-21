# AGENTS.md Update Log

## 2026-03-13 Session

### New Rules Added

#### 1. Gemini CLI for Coding
- **Use Gemini CLI by default for code modifications**
- Required constraint: `ONLY modify the code. DO NOT run any tests, DO NOT run make, and DO NOT execute any shell commands.`
- Execution: Simple tasks run directly, complex tasks use background execution (10+ minutes)
- After completion: Verify with `py_compile` or syntax check

#### 2. Software Architect Standards

**Core Engineering Principles:**
1. Clear Functional Layering - Strict separation of concerns
2. No Redundancy (DRY) - Eliminate duplication, prefer reuse
3. Test-Driven Mindset - No tests = incomplete feature

**Modification Workflow:**
1. Rescan the Project - Complete scan of project structure
2. Impact Assessment - Evaluate change impact on existing architecture
3. Consult Before Acting - STOP if issues found, report and wait for approval
4. Verify After Coding - Full test / unit test / syntax check / functional verification

**Commit Rules:**
- Do NOT commit code without explicit request

#### 3. Memory Rules
- Project memory does NOT go in MEMORY.md
- Project memory does NOT go in daily notes
- Project memory belongs in project directories (README.md, PROJECT.md, etc.)

#### 4. Project Documentation Language
- Project documentation (README.md, PROJECT.md, PROGRESS.md, etc.) MUST be written in **English**
- Exception: Proper nouns, specific terminology, technical terms

#### 5. Verify Assumptions Before Concluding
- When a tool is limited, don't assume the task is impossible
- Try alternatives first (e.g., use `exec` instead of `write`)
- Then conclude

### System Configuration

- Timezone set to Taipei (CST, +0800)
- Gemini CLI installed and authenticated (v0.33.0)

### File Structure

```
/home/ubuntu/.openclaw/workspace/
├── AGENTS.md          # Rules read by all sessions
├── PROJECTS.md        # Project index (all sessions read)
├── MEMORY.md          # Long-term memory (main session only)
├── manager/           # Management records
│   └── AGENTS_UPDATES.md
└── stock_crawler/     # Stock analysis project
```

---

## 2026-03-17 Session

### AGENTS.md Condensed

**Reduced from 11,600+ characters to ~1,100 characters (~90% reduction)**

#### Key Changes

1. **Removed daily notes** - Now only for unclassified content
2. **Channel notes** - Moved to project directories
3. **Gemini CLI** - Moved to separate section
4. **Extreme simplification** - Bullet points only, minimal words

#### Current Structure

```
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

- Simple: `gemini "prompt"`
- Complex: `nohup` or background
- After: `py_compile` verify

---
**NO EXCEPTIONS**
```