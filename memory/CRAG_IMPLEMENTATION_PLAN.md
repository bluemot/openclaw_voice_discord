# Trace Manager Architecture - Implementation Plan

**Branch:** trace-manager-architecture
**Created:** 2026-03-14
**Status:** Planning

---

## Overview

實作 Structured Output Protocol 架構：
- Tracer = Graph Node Sensors（LLM，輸出 JSON）
- Trace Manager = Python Coordinator（狀態庫，零 Token）

---

## Implementation Order

```
Phase 1: Schema & Protocol      → trace_protocol.py
    ↓
Phase 2: Core Engine            → trace_manager.py
    ↓
Phase 3: find_callers Tool     → hound_tools.py
    ↓
Phase 4: Tracer Prompts        → tracer_prompts.py
    ↓
Phase 5: JSON Sanitizer         → json_sanitizer.py
    ↓
Phase 6: Test Bench             → tests/benchmark/
```

---

## Phase 1: Schema & Protocol

**File:** `codebase_rag/services/trace_protocol.py`

```python
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class TraceStatus(str, Enum):
    DONE = "done"
    NEED_HELP = "need_help"
    DEAD_END = "dead_end"
    ERROR = "error"

class GraphEdge(BaseModel):
    source: str
    relation: str  # "CALLS", "REFERENCES", "ALLOCATES"
    target: str

class UnexploredBranch(BaseModel):
    function: str
    reason: str
    location: Optional[str] = None

class Finding(BaseModel):
    key: str
    value: str
    severity: str = "info"

class TraceResult(BaseModel):
    tracer_id: str
    task_id: str
    parent_task: Optional[str] = None
    status: TraceStatus
    explored_graph: List[GraphEdge] = []
    unexplored_branches: List[UnexploredBranch] = []
    findings: List[Finding] = []
    conclusion: str = ""

class Task(BaseModel):
    task_id: str
    entry_point: str
    direction: str  # "up" | "down"
    depth: int = 0
    parent_task: Optional[str] = None
    context: Optional[str] = None
```

---

## Phase 2: Core Engine

**File:** `codebase_rag/services/trace_manager.py`

```python
import asyncio
import heapq
import networkx as nx
from typing import Set, List, Tuple, Optional
from .trace_protocol import Task, TraceResult

class TraceManager:
    def __init__(self, max_concurrent: int = 5, max_depth: int = 15):
        self.graph = nx.DiGraph()
        self.visited_nodes: Set[str] = set()
        self.pending_queue: List[Tuple[float, int, Task]] = []
        self.task_counter = 0
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_depth = max_depth
    
    def calculate_priority(self, task: Task) -> float:
        return task.depth * 5  # deeper = lower priority
    
    def add_task(self, task: Task):
        priority = self.calculate_priority(task)
        heapq.heappush(self.pending_queue, (priority, self.task_counter, task))
        self.task_counter += 1
    
    def is_cycle(self, node: str, path: List[str]) -> bool:
        return node in path
    
    async def process_result(self, result: TraceResult, current_path: List[str]):
        # Sync to graph
        for edge in result.explored_graph:
            self.graph.add_edge(edge.source, edge.target)
            self.visited_nodes.add(edge.source)
            self.visited_nodes.add(edge.target)
        
        # Queue new tasks
        for branch in result.unexplored_branches:
            if branch.function not in self.visited_nodes:
                if not self.is_cycle(branch.function, current_path):
                    if result.depth + 1 < self.max_depth:
                        self.add_task(Task(
                            task_id=f"{result.task_id}_{branch.function}",
                            entry_point=branch.function,
                            direction=result.direction,
                            depth=result.depth + 1
                        ))
```

---

## Success Criteria

1. TraceResult 可被 Pydantic 解析
2. Priority Queue 正確排序
3. 循環檢測（A→B→A）被標記
4. find_callers 返回 Graph + Hound 合併結果
5. JSON Sanitizer 處理 Markdown blocks