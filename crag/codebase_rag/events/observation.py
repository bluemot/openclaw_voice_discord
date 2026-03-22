"""
Observation types for CRAG Event System.

This module defines concrete observation types for various operations:
- TraceObservation: Results of code tracing
- SearchObservation: Results of code search
- QueryObservation: Results of knowledge graph queries
- ShellObservation: Results of shell command execution
- ParseObservation: Results of code parsing
- ResolveObservation: Results of symbol resolution
- ErrorObservation: Error results

Each observation type includes:
- Structured result data
- Status and error information
- Conversion to/from Trace Protocol types
"""

from typing import Optional, List, Dict, Any
from datetime import datetime

from pydantic import Field, field_validator

from .base import Observation, ObservationStatus, EventMetadata


class GraphEdge(BaseModel):
    """An edge in the code graph."""
    source: str = Field(..., description="Source node")
    relation: str = Field(..., description="Relationship type")
    target: str = Field(..., description="Target node")
    
    model_config = ConfigDict(frozen=True)


class CodeLocation(BaseModel):
    """Location of code in a file."""
    file_path: str = Field(..., description="File path")
    line_start: int = Field(..., ge=1, description="Start line number")
    line_end: Optional[int] = Field(default=None, description="End line number")
    column_start: Optional[int] = Field(default=None, description="Start column")
    column_end: Optional[int] = Field(default=None, description="End column")
    
    model_config = ConfigDict(frozen=True)


class SymbolInfo(BaseModel):
    """Information about a code symbol."""
    name: str = Field(..., description="Symbol name")
    qualified_name: str = Field(..., description="Fully qualified name")
    kind: str = Field(..., description="Symbol kind (function, class, etc.)")
    location: CodeLocation = Field(..., description="Code location")
    docstring: Optional[str] = Field(default=None, description="Documentation")
    signature: Optional[str] = Field(default=None, description="Function signature")
    
    model_config = ConfigDict(frozen=True)


class TraceObservation(Observation):
    """
    Observation from code tracing.
    
    Contains the results of tracing code paths, including:
    - Explored graph edges
    - Unexplored branches for further tracing
    - Key findings during tracing
    
    Attributes:
        entry_point: Starting symbol that was traced
        direction: Direction of trace
        edges: Discovered graph edges
        branches: Unexplored branches needing further tracing
        findings: Key findings during tracing
        depth_reached: Maximum depth reached
        nodes_visited: Number of nodes visited
    
    Example:
        observation = TraceObservation(
            action_id="action-123",
            entry_point="main",
            direction="up",
            edges=[GraphEdge(source="foo", relation="CALLS", target="main")],
            status=ObservationStatus.SUCCESS
        )
    """
    entry_point: str = Field(..., description="Starting symbol")
    direction: str = Field(..., description="Trace direction")
    edges: List[GraphEdge] = Field(default_factory=list, description="Discovered edges")
    branches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Unexplored branches"
    )
    findings: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Key findings"
    )
    depth_reached: int = Field(default=0, description="Maximum depth reached")
    nodes_visited: int = Field(default=0, description="Number of nodes visited")
    
    @field_validator("edges", mode="before")
    @classmethod
    def validate_edges(cls, v):
        """Ensure edges is a list."""
        if v is None:
            return []
        return v
    
    @classmethod
    def from_trace_protocol_result(
        cls,
        action_id: str,
        result: Dict[str, Any]
    ) -> "TraceObservation":
        """
        Create from Trace Protocol TraceResult.
        
        Args:
            action_id: The action ID
            result: TraceResult dict from trace_protocol
            
        Returns:
            TraceObservation instance
        """
        status_map = {
            "done": ObservationStatus.SUCCESS,
            "need_help": ObservationStatus.PARTIAL,
            "dead_end": ObservationStatus.SUCCESS,
            "error": ObservationStatus.ERROR,
        }
        
        raw_status = result.get("status", "error")
        status = status_map.get(raw_status, ObservationStatus.ERROR)
        
        # Convert explored_graph to GraphEdge objects
        raw_edges = result.get("explored_graph", [])
        edges = []
        for edge in raw_edges:
            if isinstance(edge, dict):
                edges.append(GraphEdge(
                    source=edge.get("source", ""),
                    relation=edge.get("relation", ""),
                    target=edge.get("target", "")
                ))
        
        return cls(
            action_id=action_id,
            entry_point=result.get("task_id", ""),
            direction=result.get("direction", "up"),
            edges=edges,
            branches=result.get("unexplored_branches", []),
            findings=result.get("findings", []),
            depth_reached=result.get("depth_reached", 0),
            status=status,
            message=result.get("conclusion", ""),
        )
    
    def to_trace_protocol_result(self) -> Dict[str, Any]:
        """
        Convert to Trace Protocol TraceResult format.
        
        Returns:
            Dict compatible with trace_protocol.TraceResult
        """
        status_map = {
            ObservationStatus.SUCCESS: "done",
            ObservationStatus.PARTIAL: "need_help",
            ObservationStatus.ERROR: "error",
            ObservationStatus.TIMEOUT: "error",
            ObservationStatus.CANCELLED: "error",
        }
        
        return {
            "tracer_id": f"tracer_{self.action_id}",
            "task_id": self.entry_point,
            "status": status_map.get(self.status, "error"),
            "direction": self.direction,
            "explored_graph": [
                {"source": e.source, "relation": e.relation, "target": e.target}
                for e in self.edges
            ],
            "unexplored_branches": self.branches,
            "findings": self.findings,
            "conclusion": self.message,
            "depth_reached": self.depth_reached,
        }


class SearchObservation(Observation):
    """
    Observation from code search.
    
    Contains search results with matching symbols and locations.
    
    Attributes:
        query: Original search query
        results: List of matching symbols
        total_count: Total number of matches
        truncated: Whether results were truncated
    
    Example:
        observation = SearchObservation(
            action_id="action-123",
            query="cudaMemcpy",
            results=[SymbolInfo(...)],
            status=ObservationStatus.SUCCESS
        )
    """
    query: str = Field(..., description="Search query")
    results: List[SymbolInfo] = Field(default_factory=list, description="Search results")
    total_count: int = Field(default=0, description="Total matches")
    truncated: bool = Field(default=False, description="Results truncated")
    
    @field_validator("results", mode="before")
    @classmethod
    def validate_results(cls, v):
        """Ensure results is a list."""
        if v is None:
            return []
        return v


class QueryObservation(Observation):
    """
    Observation from knowledge graph query.
    
    Contains query results with nodes, edges, and paths.
    
    Attributes:
        query_type: Type of query executed
        target: Target symbol
        nodes: List of nodes in result
        edges: List of edges in result
        paths: List of paths (for path queries)
        raw_result: Raw query result
    
    Example:
        observation = QueryObservation(
            action_id="action-123",
            query_type="callers",
            target="main",
            nodes=["foo", "bar", "main"],
            edges=[GraphEdge(...)],
            status=ObservationStatus.SUCCESS
        )
    """
    query_type: str = Field(..., description="Query type")
    target: str = Field(..., description="Target symbol")
    nodes: List[str] = Field(default_factory=list, description="Result nodes")
    edges: List[GraphEdge] = Field(default_factory=list, description="Result edges")
    paths: List[List[str]] = Field(default_factory=list, description="Paths found")
    raw_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw query result"
    )
    
    @field_validator("nodes", mode="before")
    @classmethod
    def validate_nodes(cls, v):
        """Ensure nodes is a list."""
        if v is None:
            return []
        return v


class ShellObservation(Observation):
    """
    Observation from shell command execution.
    
    Contains command output and exit information.
    
    Attributes:
        command: Executed command
        return_code: Command exit code
        stdout: Standard output
        stderr: Standard error
        execution_time: Execution time in seconds
    
    Example:
        observation = ShellObservation(
            action_id="action-123",
            command="ls -la",
            return_code=0,
            stdout="...",
            status=ObservationStatus.SUCCESS
        )
    """
    command: str = Field(..., description="Executed command")
    return_code: int = Field(..., description="Exit code")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    execution_time: Optional[float] = Field(default=None, description="Execution time")
    
    @field_validator("return_code")
    @classmethod
    def validate_return_code(cls, v: int) -> int:
        """Ensure return_code is an integer."""
        return int(v) if v is not None else 0
    
    @property
    def success(self) -> bool:
        """Check if command succeeded (return code 0)."""
        return self.return_code == 0 and self.status == ObservationStatus.SUCCESS


class ParseObservation(Observation):
    """
    Observation from code parsing.
    
    Contains parsed AST information and extracted symbols.
    
    Attributes:
        language: Programming language
        symbols: Extracted symbols
        calls: Extracted call relationships
        ast: Optional AST representation
        errors: Parse errors if any
    
    Example:
        observation = ParseObservation(
            action_id="action-123",
            language="python",
            symbols=[SymbolInfo(...)],
            calls=[GraphEdge(...)],
            status=ObservationStatus.SUCCESS
        )
    """
    language: str = Field(..., description="Programming language")
    symbols: List[SymbolInfo] = Field(default_factory=list, description="Extracted symbols")
    calls: List[GraphEdge] = Field(default_factory=list, description="Call relationships")
    ast: Optional[Dict[str, Any]] = Field(default=None, description="AST representation")
    errors: List[str] = Field(default_factory=list, description="Parse errors")
    
    @field_validator("symbols", mode="before")
    @classmethod
    def validate_symbols(cls, v):
        """Ensure symbols is a list."""
        if v is None:
            return []
        return v


class ResolveObservation(Observation):
    """
    Observation from symbol resolution.
    
    Contains resolved symbol information.
    
    Attributes:
        symbol: Original symbol name
        resolved: Whether symbol was resolved
        candidates: List of candidate symbols
        selected: Selected symbol (if resolved)
        confidence: Resolution confidence (0-1)
    
    Example:
        observation = ResolveObservation(
            action_id="action-123",
            symbol="cudaMemcpy",
            resolved=True,
            selected=SymbolInfo(...),
            confidence=0.95,
            status=ObservationStatus.SUCCESS
        )
    """
    symbol: str = Field(..., description="Original symbol")
    resolved: bool = Field(default=False, description="Whether resolved")
    candidates: List[SymbolInfo] = Field(default_factory=list, description="Candidates")
    selected: Optional[SymbolInfo] = Field(default=None, description="Selected symbol")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence")
    
    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Clamp confidence to [0, 1]."""
        return max(0.0, min(1.0, float(v) if v is not None else 0.0))


class ErrorObservation(Observation):
    """
    Generic error observation.
    
    Used when an action fails with an error.
    
    Attributes:
        error_type: Type of error
        error_details: Detailed error information
        traceback: Optional traceback
        recoverable: Whether error is recoverable
    
    Example:
        observation = ErrorObservation(
            action_id="action-123",
            message="Failed to execute",
            error_type="TimeoutError",
            error_details="Command timed out after 60s",
            status=ObservationStatus.ERROR
        )
    """
    error_type: str = Field(default="UnknownError", description="Error type")
    error_details: Optional[str] = Field(default=None, description="Error details")
    traceback: Optional[str] = Field(default=None, description="Traceback")
    recoverable: bool = Field(default=False, description="Whether recoverable")


# Import here to avoid circular imports
from pydantic import ConfigDict, BaseModel
