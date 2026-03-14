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