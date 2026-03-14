# Design: Trace Manager Architecture

**Created:** 2026-03-14
**Status:** Draft
**Related:** CRAG_DESIGN_CALLER_TRACE.md

---

## Overview

Multi-worker architecture for parallel code tracing with context isolation.

```
┌─────────────────────────────────────────────────────────────────┐
│                       Trace Manager                              │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │   Context Manager    │◄──►│   Task Dispatcher    │           │
│  │ - Result Buffer      │    │ - 分配任務           │           │
│  │ - Pending Queue      │    │ - 決定完成條件       │           │
│  │ - Context 合併/裁減  │    │ - Worker 生命週期    │           │
│  └──────────┬───────────┘    └──────────┬───────────┘           │
│             │                           │                       │
│             │      Command Queue        │                       │
│             └─────────────┬─────────────┘                       │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
         ┌────────┐   ┌────────┐   ┌────────┐
         │Tracer#1│   │Tracer#2│   │Tracer#3│
         │        │   │        │   │        │
         │Scheduler│  │Scheduler│  │Scheduler│
         │+Agent   │  │+Agent   │  │+Agent   │
         │        │   │        │   │        │
         │Producer│   │Producer│   │Producer│
         └───┬────┘   └───┬────┘   └───┬────┘
             │            │            │
             └────────────┴────────────┘
                          │
                    Result Queue
                          │
                          ▼
                   Trace Manager
```

---

## Components

### 1. Code Tracer (Worker + Producer)

Each tracer is an independent unit: **Scheduler + Architect Agent**.

**Responsibilities:**
- Trace a single path from entry point
- Report findings and pending branches
- Maintain isolated context (no shared history with other tracers)

**Inputs:**
- `Task`: entry_point, direction, depth_limit, parent_task

**Outputs:**
- `TraceResult`: path, findings, pending_branches, status

```python
@dataclass
class TraceResult:
    tracer_id: str              # Which tracer produced this
    task_id: str                # Original task ID
    status: str                 # "done" | "need_help" | "dead_end" | "error" | "timeout"
    
    # Path traced
    path: List[str]            # ["func_a", "func_b", "func_c"]
    endpoint: Optional[str]     # Terminal point (if reached)
    
    # Findings
    findings: List[dict]        # [{"line": 45, "type": "lock", "desc": "..."}]
    
    # Branches that need other tracers
    pending_branches: List[dict]  # [{"name": "func_d", "reason": "branch at line 50"}]
    
    # Statistics
    depth_reached: int
    confidence: float
    tokens_used: int
    
    # Context snapshot (optional, for debugging)
    context_snapshot: Optional[dict]
```

---

### 2. Trace Manager (Coordinator)

Central coordinator that manages workers and merges results.

```
┌─────────────────────────────────────────────────────────────────┐
│                       Trace Manager                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Context Manager                          ││
│  │  - result_buffer: List[TraceResult]                        ││
│  │  - pending_queue: Queue[Task]                              ││
│  │  - merge_results(): Merge multiple tracer results          ││
│  │  - prune_context(): Remove old context                     ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    Task Dispatcher                          ││
│  │  - workers: Dict[str, CodeTracer]                          ││
│  │  - idle_workers: Set[str]                                   ││
│  │  - dispatch(task): Assign task to idle worker              ││
│  │  - collect(): Collect results from result queue            ││
│  │  - is_complete(): Check if task is finished                 ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Communication Protocol

### Task (Dispatcher → Tracer)

```python
@dataclass
class Task:
    task_id: str                    # Unique ID
    entry_point: str                # Starting function
    direction: str                  # "up" (callers) or "down" (callees)
    depth_limit: int                # Max depth
    parent_task: Optional[str]      # Parent task ID (for tree tracking)
    focus: Optional[str]            # Focus point (optional)
    context_hint: Optional[dict]    # Context hints (optional)
```

### TraceResult (Tracer → Manager)

```python
@dataclass
class TraceResult:
    # Identity
    tracer_id: str
    task_id: str
    parent_task: Optional[str]
    
    # Status
    status: str  # "done" | "need_help" | "dead_end" | "error" | "timeout"
    
    # Path
    path: List[str]
    endpoint: Optional[str]
    
    # Findings
    findings: List[dict]
    
    # Branches needing help
    pending_branches: List[dict]
    
    # Stats
    depth_reached: int
    confidence: float
    tokens_used: int
    
    # Snapshot
    context_snapshot: Optional[dict]
```

---

## Workflow Example

```
User asks: "Who calls ggml_backend_alloc_tensor? Trace the full path."

1. Trace Manager receives request, creates initial Task:
   Task(entry_point="ggml_backend_alloc_tensor", direction="up")

2. Task Dispatcher assigns to Tracer #1

3. Tracer #1 executes:
   - Finds 3 callers: ["ggml_backend_buffer_type_alloc_tensor", 
                       "ggml_backend_alloc_tensor_from_type",
                       "ggml_allocr_alloc_tensor"]
   - Continues tracing each caller
   
4. Tracer #1 hits branch point, produces TraceResult:
   {
     "status": "need_help",
     "path": ["ggml_backend_alloc_tensor"],
     "pending_branches": [
       {"name": "ggml_backend_buffer_type_alloc_tensor", "reason": "branch at depth 1"},
       {"name": "ggml_allocr_alloc_tensor", "reason": "branch at depth 1"}
     ]
   }

5. Trace Manager receives result:
   - Detects status="need_help"
   - Adds pending_branches to queue
   - Creates new Tasks for each branch

6. Task Dispatcher assigns to Tracer #2, #3:
   Task(entry="ggml_backend_buffer_type_alloc_tensor", parent=task_1)
   Task(entry="ggml_allocr_alloc_tensor", parent=task_1)

7. Tracer #2, #3 execute in parallel, each traces their branch

8. Collect results until all branches explored or termination condition met

9. Trace Manager merges results, returns to user
```

---

## "need_help" Trigger Conditions (Simplified)

**Definition: When Tracer discovers multiple trace targets, report and end task.**

### Simple Rule

```
if discovered_targets > 1:
    1. Summarize findings (locations, context)
    2. Return TraceResult(status="need_help", pending_branches=[...])
    3. Task ends

# Tracer only continues tracing if exactly 1 target found
```

### Examples

**Example 1: Multiple Callers Found**

```
Tracer #1 calls find_callers("ggml_backend_alloc_tensor")
Result: 3 callers found

Tracer #1 reports:
{
  "status": "need_help",
  "path": ["ggml_backend_alloc_tensor"],
  "findings": [
    {"file": "src/ggml-backend.c", "line": 123, "caller": "ggml_backend_buffer_type_alloc_tensor"},
    {"file": "src/ggml-alloc.c", "line": 456, "caller": "ggml_allocr_alloc_tensor"},
    {"file": "tests/test-alloc.c", "line": 789, "caller": "test_alloc"}
  ],
  "pending_branches": [
    {"name": "ggml_backend_buffer_type_alloc_tensor", "file": "src/ggml-backend.c", "line": 123},
    {"name": "ggml_allocr_alloc_tensor", "file": "src/ggml-alloc.c", "line": 456},
    {"name": "test_alloc", "file": "tests/test-alloc.c", "line": 789}
  ]
}

# Task ends. Manager will dispatch new Tracers for each branch.
```

**Example 2: Branch Detected**

```
Tracer #2 calls analyze_function_deeply("process_request")
Result: 2 callees found (branch in code)

Tracer #2 reports:
{
  "status": "need_help",
  "path": ["ggml_backend_alloc_tensor", "ggml_backend_buffer_type_alloc_tensor", "process_request"],
  "findings": [
    {"line": 50, "type": "branch", "desc": "if (type == CUDA) calls cuda_handler"},
    {"line": 52, "type": "branch", "desc": "else calls cpu_handler"}
  ],
  "pending_branches": [
    {"name": "cuda_handler", "reason": "branch at line 50"},
    {"name": "cpu_handler", "reason": "branch at line 52"}
  ]
}
```

**Example 3: Single Target - Continue**

```
Tracer #3 calls find_callers("cuda_handler")
Result: 1 caller found

Tracer #3 continues:
  - Calls analyze_function_deeply("cuda_init")
  - Continues until branch or endpoint
```

### Tracer State Machine (Simplified)

```
        ┌─────────────┐
        │   START     │
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │   SEARCH    │
        │   目標函數   │
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │  檢查結果   │
        └──────┬──────┘
               │
      ┌────────┴────────┐
      │                 │
   結果 = 1          結果 > 1
      │                 │
      ▼                 ▼
  繼續追蹤         回報報告
      │           (need_help)
      │                 │
      │            任務結束
      ▼
  ┌─────────────┐
  │ 達到終點    │
  │ (done)      │
  └─────────────┘
```

### Key Principle

**Tracer is a "single-path worker".** It never makes decisions about which branch to follow - it simply reports branches and ends. The Manager decides how to distribute branches to other Tracers.

---

## Implementation Files (TBD)

```
codebase_rag/services/
├── trace_manager.py      # TraceManager, ContextManager, TaskDispatcher
├── code_tracer.py        # CodeTracer class
├── trace_protocol.py     # Task, TraceResult dataclasses
└── scheduler.py          # Existing StateMachineScheduler (to be integrated)
```

---

## Open Questions

1. **"need_help" trigger conditions** - When should a tracer request help?
2. **Max workers** - How many concurrent tracers?
3. **Context sharing** - Should tracers share any context hints?
4. **Priority queue** - Should some branches be prioritized?
5. **Termination conditions** - When does the manager decide task is complete?