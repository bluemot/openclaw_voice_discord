# codebase_rag/services/trace_protocol.py
"""
Trace Manager Protocol - Structured Output for Multi-Agent Code Tracing

This module defines the data structures for the Structured Output Protocol:
- Tracer (LLM) outputs strict JSON following TraceResult schema
- Trace Manager (Python) processes and coordinates tracers

Architecture:
- Tracer = Graph Node Sensors (disposable, JSON output only)
- Trace Manager = State Store + Coordinator (zero token cost)

Created: 2026-03-14
Branch: trace-manager-architecture
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class TraceStatus(str, Enum):
    """Status of a Tracer's execution result."""
    DONE = "done"                     # Completed successfully, single path traced
    NEED_HELP = "need_help"           # Found multiple branches, needs other tracers
    DEAD_END = "dead_end"             # No more paths to trace
    ERROR = "error"                   # Execution error


class GraphEdge(BaseModel):
    """An edge in the explored graph."""
    source: str = Field(..., description="Source function/node name")
    relation: str = Field(
        ...,
        description="Relationship type: CALLS, REFERENCES, ALLOCATES, DEFINES, USES"
    )
    target: str = Field(..., description="Target function/node name")


class UnexploredBranch(BaseModel):
    """A branch that needs to be traced by another tracer."""
    function: str = Field(..., description="Function name to trace")
    reason: str = Field(..., description="Why this branch needs exploration")
    location: Optional[str] = Field(
        None,
        description="File location if known (e.g., 'src/main.c:45')"
    )
    depth: Optional[int] = Field(
        None,
        description="Depth at which this branch was discovered"
    )


class Finding(BaseModel):
    """A key finding during tracing."""
    key: str = Field(..., description="Finding key (e.g., 'IRQ_TYPE', 'MEMORY_POOL')")
    value: str = Field(..., description="Finding value")
    severity: str = Field(
        "info",
        description="Severity level: info, warning, error"
    )
    line: Optional[int] = Field(None, description="Line number if applicable")
    file: Optional[str] = Field(None, description="File path if applicable")


class TraceResult(BaseModel):
    """
    Structured output from a Tracer.
    
    Tracers MUST output valid JSON matching this schema.
    No prose, no explanations outside JSON.
    
    Status meanings:
    - done: Single path traced successfully, ready for next task
    - need_help: Found multiple branches, each needs separate tracer
    - dead_end: No more paths to trace (end of call chain)
    - error: Execution failed (describe in conclusion)
    """
    # Identity
    tracer_id: str = Field(..., description="Unique tracer identifier")
    task_id: str = Field(..., description="Task this tracer was assigned")
    parent_task: Optional[str] = Field(
        None,
        description="Parent task ID for tree tracking"
    )
    
    # Status
    status: TraceStatus = Field(..., description="Execution status")
    
    # Graph structure (explored edges)
    explored_graph: List[GraphEdge] = Field(
        default_factory=list,
        description="Edges discovered during this trace"
    )
    
    # Branches needing other tracers
    unexplored_branches: List[UnexploredBranch] = Field(
        default_factory=list,
        description="Branches that need separate tracers"
    )
    
    # Key findings
    findings: List[Finding] = Field(
        default_factory=list,
        description="Important findings discovered"
    )
    
    # Conclusion
    conclusion: str = Field(
        default="",
        description="One-line summary of trace result"
    )
    
    # Metadata (optional)
    depth_reached: Optional[int] = Field(None, description="Maximum depth reached")
    tokens_used: Optional[int] = Field(None, description="Tokens consumed (for tracking)")


class Task(BaseModel):
    """A task to be dispatched to a Tracer."""
    task_id: str = Field(..., description="Unique task identifier")
    entry_point: str = Field(..., description="Starting function/symbol")
    direction: str = Field(
        ...,
        description="Trace direction: 'up' (callers) or 'down' (callees)"
    )
    depth: int = Field(0, description="Current depth in trace tree")
    parent_task: Optional[str] = Field(None, description="Parent task ID")
    context: Optional[str] = Field(None, description="Surrounding code context")
    
    # Priority scoring
    priority: Optional[float] = Field(None, description="Priority score (lower = higher priority)")


class Intent(BaseModel):
    """
    Parsed intent from user question.
    
    Intent Parser (LLM) extracts this from user question.
    Trace Manager uses this to create initial Tasks.
    """
    type: str = Field(
        ...,
        description="Intent type: 'trace_path', 'trace_callers', 'trace_callees'"
    )
    source: Optional[str] = Field(None, description="Starting symbol (if known)")
    target: Optional[str] = Field(None, description="Target symbol (if known)")
    strategy: str = Field(
        "unidirectional",
        description="Strategy: 'unidirectional' or 'meet_in_the_middle'"
    )
    direction: str = Field(
        "down",
        description="Primary direction: 'up' or 'down'"
    )
    
    # Extracted entities
    symbols: List[str] = Field(
        default_factory=list,
        description="Key symbols mentioned in question"
    )
    
    # Context hints
    file_hint: Optional[str] = Field(None, description="File hint from question")


class TraceSummary(BaseModel):
    """
    Final summary output to user.
    
    Generated by Trace Manager after all tracers complete.
    """
    # Graph summary
    nodes: List[str] = Field(default_factory=list, description="All nodes in graph")
    edges: List[tuple] = Field(default_factory=list, description="All edges in graph")
    
    # Path summary
    paths_found: int = Field(0, description="Number of paths found")
    total_depth: int = Field(0, description="Maximum depth explored")
    
    # Findings
    all_findings: List[Finding] = Field(
        default_factory=list,
        description="All findings across tracers"
    )
    
    # Knowledge gaps
    gaps: List[str] = Field(
        default_factory=list,
        description="Functions that could not be traced"
    )
    
    # Mermaid diagram
    mermaid_diagram: Optional[str] = Field(None, description="Mermaid.js graph definition")


# Utility functions

def validate_trace_result(data: dict) -> Optional[TraceResult]:
    """
    Validate and parse TraceResult from raw dict.
    Returns None if validation fails.
    """
    try:
        return TraceResult(**data)
    except Exception:
        return None


def create_task_id(parent_id: str, branch_name: str) -> str:
    """Create a unique task ID from parent and branch."""
    import hashlib
    hash_input = f"{parent_id}_{branch_name}".encode()
    short_hash = hashlib.md5(hash_input).hexdigest()[:8]
    return f"{parent_id}_{short_hash}"