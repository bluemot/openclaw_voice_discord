# Design: Trace Manager Architecture

**Created:** 2026-03-14
**Status:** Draft
**Related:** CRAG_DESIGN_CALLER_TRACE.md

---

## Overview

Multi-worker architecture for parallel code tracing with context isolation.

**Key Insight:** Tracer = Graph Node Sensors (Structured Output Protocol)
Python Trace Manager = State Store + Brain (Zero Token Cost)

---

## Final Decisions (After Gemini CLI Consultation)

### 1. Max Workers
- **Decision:** Dynamic Worker Pool with `min_workers=1`, `max_workers=5~10`
- **Mechanism:** Adjust based on API Rate Limit (TPM/RPM)
- **Implementation:** Use `asyncio.Semaphore` for concurrency control

### 2. Priority Queue
- **Decision:** Best-First Search with Heuristic Score
- **Formula:** `Score = (Depth_Weight * Depth) - (Semantic_Relevance) + Penalty`
- **Semantic Relevance:** Simple string matching (keyword bonus), NOT embedding
- **Depth Penalty:** Deeper nodes get lower priority

### 3. Termination Conditions
- **Multi-defense Strategy:**
  1. `MAX_DEPTH = 15` (hard limit)
  2. `MAX_API_CALLS = 50` (global limit)
  3. Cycle Detection (Global Set + Path Stack)
  4. Empty Priority Queue (all branches explored)

### 4. Timeout & Error Handling
- **Timeout:** 45-60 seconds per API call
- **Retry:** Max 2 retries with exponential backoff
- **Error Node:** Mark as `Error_Node`, continue other branches
- **JSON Validation:** Use Pydantic AI's built-in `result_type` for auto-validation

### 5. Graph Storage
- **Hybrid Approach:**
  - **Runtime:** NetworkX (in-memory, fast operations)
  - **Persistence:** Memgraph (async mirror for cross-session sharing)
- **Node ID:** `Filepath:Function` as unique key

### 6. Cycle Detection
- **Two-tier Mechanism:**
  1. **Global Seen Nodes:** For deduplication (avoid repeated work)
  2. **Path History (Stack):** For cycle breaking (avoid infinite loops)

### 7. Result Merging
- **Merge Logic:**
  - Same node from multiple Tracers → merge findings array
  - More detailed info wins (e.g., `struct Buffer*` over `void*`)
  - Conflicts preserved with `conflict: true` tag
- **Conflict Resolution:** Later: dedicated Arbitrator Agent for critical paths

### 8. Output Format
- **Default:** Mermaid diagram + indented tree text
- **Optional:** LLM Summary (only when user asks for "explain" or "summarize")

---

## Implementation Priority (MVP - 1 Week)

### Must-Have
1. **Schema Definition** - Pydantic models for TraceResult
2. **Core Search Engine** - NetworkX + PriorityQueue
3. **Cycle Detection** - Global Set + Path Stack
4. **Knowledge Gap Reporting** - When target not reached, report missing nodes

### Nice-to-Have (Deferred)
1. Complex conflict handling (use Last-write-wins initially)
2. Persistence to Memgraph (run in-memory first)
3. Visualization (output JSON/Markdown first)

---

## Development Order

```
1. Schema Definition (Pydantic TraceResult)
   ↓
2. NetworkX + Priority Queue + Cycle Detection (Core)
   ↓
3. Knowledge Gap Logic
   ↓
4. Unit Tests (Python Logic)
   ↓
5. MVP Release
```

---

## Test Strategy Priority

1. **Unit Tests (Priority 1):** NetworkX operations, PQ scoring, cycle detection
2. **Integration Tests (Priority 2):** Tracer + Manager JSON exchange
3. **End-to-End Tests (Priority 3):** Full trace flow

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Trace Manager (Python)                       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  NetworkX Graph (Runtime)                                  │ │
│  │  - visited_nodes: Set[str]                                 │ │
│  │  - pending_queue: PriorityQueue[(score, task)]            │ │
│  │  - completed_tasks: List[TraceResult]                    │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Async Mirror to Memgraph (Persistence)                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Worker Pool (asyncio.Semaphore)                          │ │
│  │  - max_concurrent: 5~10                                    │ │
│  │  - quota_manager: request_count                            │ │
│  └────────────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────────┘
                            │ JSON (Structured Output)
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
         ┌────────┐   ┌────────┐   ┌────────┐
         │Tracer#1│   │Tracer#2│   │Tracer#3│
         │(LLM)   │   │(LLM)   │   │(LLM)   │
         │        │   │        │   │        │
         │Output: │   │Output: │   │Output: │
         │JSON    │   │JSON    │   │JSON    │
         └────────┘   └────────┘   └────────┘
```

---

## Key Classes (Pydantic)

```python
from pydantic import BaseModel
from typing import List, Optional
import networkx as nx
import heapq

class GraphEdge(BaseModel):
    source: str
    relation: str  # "CALLS", "REFERENCES", "ALLOCATES"
    target: str

class UnexploredBranch(BaseModel):
    function: str
    reason: str
    depth: int

class Finding(BaseModel):
    line: Optional[int]
    type: str  # "allocation", "branch", "lock", "async"
    desc: str

class TraceResult(BaseModel):
    tracer_id: str
    task_id: str
    parent_task: Optional[str] = None
    status: str  # "done" | "need_help" | "dead_end" | "error"
    explored_graph: List[GraphEdge] = []
    unexplored_branches: List[UnexploredBranch] = []
    findings: List[Finding] = []
    conclusion: str = ""

class Task(BaseModel):
    task_id: str
    entry_point: str
    direction: str  # "up" (callers) or "down" (callees)
    depth: int
    parent_task: Optional[str] = None

class TraceManager:
    def __init__(self, max_concurrent: int = 5, max_depth: int = 15):
        self.graph = nx.DiGraph()
        self.visited_nodes: Set[str] = set()
        self.pending_queue: List[Tuple[float, int, Task]] = []  # heapq
        self.completed_results: List[TraceResult] = []
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_depth = max_depth
        self.request_count = 0
        self.max_requests = 50
    
    def calculate_priority(self, task: Task) -> float:
        """Lower score = higher priority"""
        # Keyword bonus (semantic relevance)
        keyword_score = 0
        # Depth penalty
        depth_score = task.depth * 5
        return depth_score - keyword_score
    
    def is_cycle(self, node: str, path: List[str]) -> bool:
        """Check if adding node creates a cycle in path"""
        return node in path
    
    async def process_result(self, result: TraceResult):
        """Process Tracer result: sync to graph, dedupe, queue new tasks"""
        # 1. Sync explored edges to NetworkX
        for edge in result.explored_graph:
            self.graph.add_edge(edge.source, edge.target, relation=edge.relation)
            self.visited_nodes.add(edge.source)
            self.visited_nodes.add(edge.target)
        
        # 2. Check for cycles and dedupe
        for branch in result.unexplored_branches:
            if branch.function not in self.visited_nodes:
                if branch.depth < self.max_depth:
                    priority = self.calculate_priority(branch)
                    heapq.heappush(self.pending_queue, (priority, self.task_counter, branch))
        
        # 3. Store result
        self.completed_results.append(result)
```

---

## Next Steps

1. **Implement `find_callers` tool** — See CRAG_DESIGN_CALLER_TRACE.md
2. **Define Pydantic TraceResult schema** — Above
3. **Implement NetworkX core + Priority Queue** — Above
4. **Add cycle detection** — Global Set + Path Stack
5. **Unit tests** — Priority scoring, cycle detection, merging