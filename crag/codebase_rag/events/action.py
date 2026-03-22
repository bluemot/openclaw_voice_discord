"""
Action types for CRAG Event System.

This module defines concrete action types for various operations:
- TraceAction: Code tracing (callers/callees)
- SearchAction: Code search
- QueryAction: Knowledge graph queries
- ShellAction: Shell command execution
- ParseAction: Code parsing
- ResolveAction: Symbol resolution

Each action type includes:
- Required parameters for the operation
- Validation rules
- Conversion to/from Trace Protocol types
"""

from typing import Optional, List, Dict, Any
from enum import Enum

from pydantic import Field, field_validator

from .base import Action, ActionStatus, EventMetadata


class TraceDirection(str, Enum):
    """Direction for code tracing."""
    UP = "up"       # Trace callers (who calls this)
    DOWN = "down"   # Trace callees (what this calls)
    BOTH = "both"   # Bidirectional tracing


class TraceAction(Action):
    """
    Action to trace code paths.
    
    Traces relationships between code elements (functions, methods, etc.)
    in a specified direction.
    
    Attributes:
        entry_point: Starting symbol to trace from
        direction: Trace direction (up/down/both)
        depth: Current depth in trace tree
        max_depth: Maximum depth to trace
        context: Optional surrounding code context
        file_hint: Optional file path hint
    
    Example:
        action = TraceAction(
            entry_point="main",
            direction=TraceDirection.UP,
            depth=0,
            max_depth=10
        )
    """
    entry_point: str = Field(..., description="Starting symbol to trace from")
    direction: TraceDirection = Field(default=TraceDirection.UP)
    depth: int = Field(default=0, ge=0, description="Current depth in trace tree")
    max_depth: int = Field(default=15, ge=1, le=100, description="Maximum trace depth")
    context: Optional[str] = Field(default=None, description="Surrounding code context")
    file_hint: Optional[str] = Field(default=None, description="File path hint")
    
    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str) -> str:
        """Ensure entry_point is not empty."""
        if not v or not v.strip():
            raise ValueError("entry_point cannot be empty")
        return v.strip()
    
    def to_trace_protocol_task(self) -> Dict[str, Any]:
        """
        Convert to Trace Protocol Task format.
        
        Returns:
            Dict compatible with trace_protocol.Task
        """
        return {
            "task_id": self.action_id,
            "entry_point": self.entry_point,
            "direction": self.direction.value,
            "depth": self.depth,
            "context": self.context,
            "priority": self.depth,  # Lower depth = higher priority
        }
    
    @classmethod
    def from_trace_protocol_task(cls, task: Dict[str, Any]) -> "TraceAction":
        """
        Create from Trace Protocol Task.
        
        Args:
            task: Task dict from trace_protocol
            
        Returns:
            TraceAction instance
        """
        return cls(
            action_id=task.get("task_id", ""),
            entry_point=task.get("entry_point", ""),
            direction=TraceDirection(task.get("direction", "up")),
            depth=task.get("depth", 0),
            context=task.get("context"),
        )


class SearchScope(str, Enum):
    """Scope for code search."""
    SYMBOL = "symbol"       # Search by symbol name
    DEFINITION = "definition"  # Search definitions
    REFERENCE = "reference"    # Search references
    FILE = "file"          # Search within file
    PROJECT = "project"     # Search entire project


class SearchAction(Action):
    """
    Action to search code.
    
    Searches for symbols, definitions, or references in the codebase.
    
    Attributes:
        query: Search query string
        scope: Search scope
        language: Optional language filter
        file_pattern: Optional file pattern (e.g., "*.py")
        limit: Maximum results to return
    
    Example:
        action = SearchAction(
            query="cudaMemcpy",
            scope=SearchScope.SYMBOL,
            language="cpp"
        )
    """
    query: str = Field(..., description="Search query")
    scope: SearchScope = Field(default=SearchScope.SYMBOL)
    language: Optional[str] = Field(default=None, description="Language filter")
    file_pattern: Optional[str] = Field(default=None, description="File pattern filter")
    limit: int = Field(default=50, ge=1, le=1000, description="Maximum results")
    
    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty."""
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        return v.strip()


class QueryType(str, Enum):
    """Type of knowledge graph query."""
    NEIGHBORS = "neighbors"      # Get neighboring nodes
    PATH = "path"                # Find path between nodes
    CALLERS = "callers"          # Get callers of a function
    CALLEES = "callees"          # Get callees of a function
    DEFINITIONS = "definitions"  # Get definitions
    REFERENCES = "references"    # Get references
    CUSTOM = "custom"            # Custom Cypher query


class QueryAction(Action):
    """
    Action to query the knowledge graph.
    
    Queries the code knowledge graph for relationships and paths.
    
    Attributes:
        query_type: Type of query
        target: Target symbol or node
        source: Optional source for path queries
        language: Optional language filter
        extra_params: Additional query parameters
    
    Example:
        action = QueryAction(
            query_type=QueryType.CALLERS,
            target="main"
        )
    """
    query_type: QueryType = Field(..., description="Type of query")
    target: str = Field(..., description="Target symbol or node")
    source: Optional[str] = Field(default=None, description="Source for path queries")
    language: Optional[str] = Field(default=None, description="Language filter")
    extra_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional query parameters"
    )
    
    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        """Ensure target is not empty."""
        if not v or not v.strip():
            raise ValueError("target cannot be empty")
        return v.strip()


class ShellAction(Action):
    """
    Action to execute a shell command.
    
    Executes a shell command and captures output.
    
    Attributes:
        command: Shell command to execute
        working_dir: Optional working directory
        timeout: Timeout in seconds
        env: Optional environment variables
        capture_output: Whether to capture stdout/stderr
    
    Example:
        action = ShellAction(
            command="find . -name '*.py' | head -10",
            timeout=30
        )
    """
    command: str = Field(..., description="Shell command to execute")
    working_dir: Optional[str] = Field(default=None, description="Working directory")
    timeout: int = Field(default=60, ge=1, le=3600, description="Timeout in seconds")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    capture_output: bool = Field(default=True, description="Capture stdout/stderr")
    
    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Ensure command is not empty."""
        if not v or not v.strip():
            raise ValueError("command cannot be empty")
        return v.strip()
    
    @property
    def is_dangerous(self) -> bool:
        """Check if command contains dangerous operations."""
        dangerous = ["rm -rf", "> /dev", "mkfs", "dd if", "del /f"]
        cmd_lower = self.command.lower()
        return any(d in cmd_lower for d in dangerous)


class ParseAction(Action):
    """
    Action to parse code.
    
    Parses code to extract AST, symbols, or other structural information.
    
    Attributes:
        code: Code to parse
        language: Programming language
        file_path: Optional file path for context
        extract_symbols: Whether to extract symbols
        extract_calls: Whether to extract call relationships
    
    Example:
        action = ParseAction(
            code="def foo(): pass",
            language="python",
            extract_symbols=True
        )
    """
    code: str = Field(..., description="Code to parse")
    language: str = Field(..., description="Programming language")
    file_path: Optional[str] = Field(default=None, description="File path for context")
    extract_symbols: bool = Field(default=True, description="Extract symbols")
    extract_calls: bool = Field(default=True, description="Extract call relationships")
    
    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """Ensure code is not empty."""
        if not v or not v.strip():
            raise ValueError("code cannot be empty")
        return v
    
    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Normalize language name."""
        lang_map = {
            "py": "python",
            "js": "javascript",
            "ts": "typescript",
            "cpp": "cpp",
            "c++": "cpp",
            "c": "c",
            "rs": "rust",
            "go": "go",
            "java": "java",
        }
        normalized = v.lower().strip()
        return lang_map.get(normalized, normalized)


class ResolveAction(Action):
    """
    Action to resolve a symbol to its definition.
    
    Resolves a symbol name to its full qualified name and location.
    
    Attributes:
        symbol: Symbol to resolve
        language: Optional language hint
        file_hint: Optional file hint
        search_imports: Whether to search imports
    
    Example:
        action = ResolveAction(
            symbol="cudaMemcpy",
            language="cpp"
        )
    """
    symbol: str = Field(..., description="Symbol to resolve")
    language: Optional[str] = Field(default=None, description="Language hint")
    file_hint: Optional[str] = Field(default=None, description="File hint")
    search_imports: bool = Field(default=True, description="Search imports")
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Ensure symbol is not empty."""
        if not v or not v.strip():
            raise ValueError("symbol cannot be empty")
        return v.strip()
