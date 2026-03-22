# CRAG vs OpenHands Codebase Comparison Analysis

## Executive Summary

This document provides a detailed comparison between **CRAG (Codebase RAG)** - a code analysis agent for C/C++ codebases using Memgraph, and **OpenHands** - a general-purpose coding agent with EventStream architecture. The analysis identifies specific areas where CRAG can be improved based on OpenHands patterns.

---

## 1. Architecture Overview

### CRAG (Codebase RAG)

**Location:** `/home/ubuntu/workspace/crag`

**Core Components:**
- `codebase_rag/main.py` (118KB) - Main entry point with chat loop and tool orchestration
- `codebase_rag/services/scheduler.py` (26KB) - StateMachineScheduler for managing analysis phases
- `codebase_rag/factory.py` - Service initialization and tool creation
- `codebase_rag/tools/` - Individual tool implementations (code_retrieval, file_editor, etc.)
- `codebase_rag/services/navigation.py` - JunctionLedger for loop detection
- `codebase_rag/services/compression.py` - ContextCompressor for managing long conversations

**Current Architecture Pattern:**
- Direct function calls between components
- State machine with phases: IDLE, EXPLORING, ANALYZING, RECOVERING, NAVIGATING, COMPLETED
- Pydantic-AI based agent with tool injection
- Memgraph for knowledge graph storage

### OpenHands

**Location:** `/home/ubuntu/workspace/OpenHands`

**Core Components:**
- `openhands/events/stream.py` - EventStream with pub/sub architecture
- `openhands/events/event.py` - Base Event class with metadata
- `openhands/events/action/` - Typed Action classes (FileReadAction, CmdRunAction, etc.)
- `openhands/events/observation/` - Typed Observation classes
- `openhands/controller/agent_controller.py` - Agent controller with delegation support
- `openhands/agenthub/codeact_agent/` - CodeAct agent implementation

**Architecture Pattern:**
- Event-driven architecture with EventStream
- Action/Observation pattern for all operations
- Multi-agent delegation with parent/child controllers
- Comprehensive exception hierarchy
- JSON schema-based tool definitions

---

## 2. Detailed Comparison

### 2.1 Event-Driven Architecture

#### OpenHands Implementation

**File:** `/home/ubuntu/workspace/OpenHands/openhands/events/stream.py`

```python
class EventStream(EventStore):
    _subscribers: dict[str, dict[str, Callable]]
    _queue: queue.Queue[Event]
    
    def subscribe(self, subscriber_id: EventStreamSubscriber, 
                  callback: Callable[[Event], None], callback_id: str) -> None:
        """Subscribe to events with a callback"""
        
    def add_event(self, event: Event, source: EventSource) -> None:
        """Publish event to all subscribers"""
        event._timestamp = datetime.now().isoformat()
        event._source = source
        # Add to queue for async processing
        self._queue.put(event)
        
    async def _process_queue(self) -> None:
        """Process events asynchronously"""
        while not self._stop_flag.is_set():
            event = self._queue.get(timeout=0.1)
            for subscriber_id, callbacks in self._subscribers.items():
                for callback_id, callback in callbacks.items():
                    pool = self._thread_pools[subscriber_id][callback_id]
                    future = pool.submit(callback, event)
```

**Key Features:**
- Thread-safe event queue with async processing
- Multiple subscribers per event type
- Event persistence with caching
- Secret redaction in events
- Event replay capability

#### CRAG Current State

**File:** `/home/ubuntu/workspace/crag/codebase_rag/services/scheduler.py`

```python
class StateMachineScheduler:
    def __init__(self, agent: Agent, ledger: JunctionLedger, ...):
        self.agent = agent
        self.ledger = ledger
        
    async def run_iteration(self, user_input: str, message_history: List[ModelMessage]):
        # Direct function calls - no event abstraction
        result = await self.agent.run(current_prompt, message_history=message_history)
        # Process result directly
        for msg in result.new_messages():
            # Handle tool calls inline
```

**Issues:**
- No event abstraction - direct coupling between components
- Cannot replay or debug execution flow
- No way to add cross-cutting concerns (logging, metrics)
- Tight coupling between scheduler and tools

#### Recommendation for CRAG

Create `/home/ubuntu/workspace/crag/codebase_rag/events/stream.py`:

```python
from enum import Enum
from typing import Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import queue

class EventSource(str, Enum):
    USER = 'user'
    AGENT = 'agent'
    TOOL = 'tool'
    SYSTEM = 'system'

class EventStreamSubscriber(str, Enum):
    SCHEDULER = 'scheduler'
    TOOL_EXECUTOR = 'tool_executor'
    LOGGER = 'logger'
    METRICS = 'metrics'

@dataclass
class Event:
    id: int = field(default=-1)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: EventSource = field(default=EventSource.SYSTEM)
    cause: int = field(default=None)  # ID of causing event
    
class EventStream:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._subscribers: Dict[EventStreamSubscriber, Dict[str, Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._cur_id = 0
        
    def subscribe(self, subscriber_id: EventStreamSubscriber, 
                  callback: Callable[[Event], None], callback_id: str):
        if subscriber_id not in self._subscribers:
            self._subscribers[subscriber_id] = {}
        self._subscribers[subscriber_id][callback_id] = callback
        
    def add_event(self, event: Event, source: EventSource):
        event.source = source
        event.id = self._cur_id
        self._cur_id += 1
        self._queue.put_nowait(event)
        
    async def process_events(self):
        while True:
            event = await self._queue.get()
            for subscriber_callbacks in self._subscribers.values():
                for callback in subscriber_callbacks.values():
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
```

---

### 2.2 Action/Observation Pattern

#### OpenHands Implementation

**Files:** 
- `/home/ubuntu/workspace/OpenHands/openhands/events/action/files.py`
- `/home/ubuntu/workspace/OpenHands/openhands/events/observation/files.py`

```python
# Action - represents intent to do something
@dataclass
class FileReadAction(Action):
    path: str
    view_range: list[int] | None = None
    action: str = ActionType.READ
    
    @property
    def message(self) -> str:
        return f'Reading file: {self.path}'

# Observation - represents result of action
@dataclass  
class FileReadObservation(Observation):
    content: str
    path: str
    view_range: list[int] | None = None
    
    @property
    def message(self) -> str:
        return f'Read {len(self.content)} characters from {self.path}'
```

**Benefits:**
- Clear separation between intent (Action) and result (Observation)
- Type-safe operations
- Easy to serialize/deserialize for persistence
- Enables event replay and debugging

#### CRAG Current State

**File:** `/home/ubuntu/workspace/crag/codebase_rag/tools/code_retrieval.py`

```python
class CodeRetriever:
    async def find_code_snippet(self, qualified_name: str) -> CodeSnippet:
        # Returns raw data structure
        return CodeSnippet(
            qualified_name=qualified_name,
            source_code=source_code,
            file_path=file_path,
            ...
        )
        
async def get_call_hierarchy(self, function_name: str, ...) -> Any:
    # Returns untyped data
    return results  # List of dicts or error dict
```

**Issues:**
- No distinction between action and observation
- Return types are inconsistent (CodeSnippet vs Any vs List[Dict])
- No standardized way to track what operation was performed
- Hard to add metadata (timing, errors, etc.)

#### Recommendation for CRAG

Create `/home/ubuntu/workspace/crag/codebase_rag/events/action.py`:

```python
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum

class ActionType(str, Enum):
    CODE_RETRIEVAL = 'code_retrieval'
    GRAPH_QUERY = 'graph_query'
    FILE_READ = 'file_read'
    FILE_EDIT = 'file_edit'
    ANALYSIS = 'analysis'
    DELEGATE = 'delegate'

@dataclass
class Action:
    action: ActionType
    source: str = 'agent'
    thought: str = ''
    _id: int = -1
    
@dataclass
class CodeRetrievalAction(Action):
    qualified_name: str
    action: ActionType = ActionType.CODE_RETRIEVAL
    
@dataclass
class GraphQueryAction(Action):
    query: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    action: ActionType = ActionType.GRAPH_QUERY
    
@dataclass
class AnalysisAction(Action):
    function_name: str
    analysis_type: str  # 'deep', 'impact', 'cfg'
    action: ActionType = ActionType.ANALYSIS
```

Create `/home/ubuntu/workspace/crag/codebase_rag/events/observation.py`:

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass
class Observation:
    content: str
    cause: int  # ID of action that caused this
    
@dataclass
class CodeRetrievalObservation(Observation):
    qualified_name: str
    source_code: str
    file_path: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    
@dataclass
class GraphQueryObservation(Observation):
    query: str
    results: List[Dict[str, Any]]
    execution_time_ms: float
    
@dataclass
class ErrorObservation(Observation):
    error_id: str
    error_message: str
    suggestion: Optional[str] = None
```

---

### 2.3 Multi-Agent Delegation

#### OpenHands Implementation

**File:** `/home/ubuntu/workspace/OpenHands/openhands/controller/agent_controller.py` (lines 701-800)

```python
class AgentController:
    parent: 'AgentController | None' = None
    delegate: 'AgentController | None' = None
    
    async def start_delegate(self, action: AgentDelegateAction) -> None:
        """Start a delegate agent to handle a subtask."""
        agent_cls = Agent.get_cls(action.agent)
        agent_config = self.agent_configs.get(action.agent, self.agent.config)
        
        delegate_agent = agent_cls(config=agent_config, 
                                   llm_registry=self.agent.llm_registry)
        
        # Create child state
        state = State(
            session_id=self.id.removesuffix('-delegate'),
            delegate_level=self.state.delegate_level + 1,
            start_id=self.event_stream.get_latest_event_id() + 1,
            parent_metrics_snapshot=self.state_tracker.get_metrics_snapshot(),
        )
        
        # Create delegate controller - shares event stream
        self.delegate = AgentController(
            sid=self.id + '-delegate',
            event_stream=self.event_stream,  # Shared!
            agent=delegate_agent,
            initial_state=state,
            is_delegate=True,  # Don't subscribe to event stream
        )
        
    def end_delegate(self) -> None:
        """End delegate and emit observation."""
        if self.delegate is None:
            return
            
        # Get delegate results
        delegate_outputs = self.delegate.state.outputs
        
        # Create observation
        obs = AgentDelegateObservation(outputs=delegate_outputs)
        self.event_stream.add_event(obs, EventSource.AGENT)
        
        # Clean up
        self.delegate = None
```

**Key Features:**
- Parent/child controller hierarchy
- Shared EventStream between parent and delegate
- Delegate state isolation with level tracking
- Automatic result aggregation

#### CRAG Current State

**File:** `/home/ubuntu/workspace/crag/codebase_rag/services/scheduler.py`

```python
class StateMachineScheduler:
    def __init__(self, agent: Agent, ledger: JunctionLedger, ...):
        self.agent = agent  # Single agent
        self.ledger = ledger
        # No delegation support
        
    async def run_iteration(self, user_input: str, ...):
        # All processing happens in single agent
        result = await self.agent.run(current_prompt, message_history=message_history)
```

**Issues:**
- No way to delegate specialized tasks
- Single agent handles everything (graph queries, code analysis, file operations)
- No isolation between different types of analysis

#### Recommendation for CRAG

Create specialized agents in `/home/ubuntu/workspace/crag/codebase_rag/agents/`:

```python
# agents/cypher_agent.py
class CypherAgent:
    """Specialized agent for graph queries."""
    def __init__(self, ingestor: MemgraphIngestor):
        self.ingestor = ingestor
        
    async def execute(self, query_action: GraphQueryAction) -> GraphQueryObservation:
        # Optimized for Cypher queries
        results = self.ingestor.fetch_all(query_action.query, query_action.parameters)
        return GraphQueryObservation(...)

# agents/analysis_agent.py
class AnalysisAgent:
    """Specialized agent for deep code analysis."""
    def __init__(self, codebase_root: Path):
        self.codebase_root = codebase_root
        
    async def execute(self, analysis_action: AnalysisAction) -> AnalysisObservation:
        # Deep analysis with CFG, call graphs, etc.
        pass

# agents/delegation.py
class DelegationManager:
    def __init__(self, event_stream: EventStream):
        self.event_stream = event_stream
        self.agents: Dict[str, Any] = {}
        
    def register_agent(self, name: str, agent: Any):
        self.agents[name] = agent
        
    async def delegate(self, action: DelegateAction) -> DelegateObservation:
        agent = self.agents.get(action.target_agent)
        if not agent:
            return ErrorObservation(error_id='AGENT_NOT_FOUND', ...)
            
        # Execute and return result
        result = await agent.execute(action.sub_action)
        return DelegateObservation(result=result, agent_name=action.target_agent)
```

Update scheduler to support delegation:

```python
class StateMachineScheduler:
    def __init__(self, ..., delegation_manager: DelegationManager):
        self.delegation_manager = delegation_manager
        
    async def run_iteration(self, user_input: str, ...):
        # Check if we should delegate
        if self._should_delegate(user_input):
            delegate_action = self._create_delegate_action(user_input)
            observation = await self.delegation_manager.delegate(delegate_action)
            return observation
```

---

### 2.4 Tool Definition and Function Calling

#### OpenHands Implementation

**File:** `/home/ubuntu/workspace/OpenHands/openhands/agenthub/codeact_agent/function_calling.py`

```python
def response_to_actions(response: ModelResponse, ...) -> list[Action]:
    """Convert LLM response to typed Actions."""
    actions: list[Action] = []
    
    for tool_call in assistant_msg.tool_calls:
        arguments = json.loads(tool_call.function.arguments)
        
        if tool_call.function.name == 'execute_bash':
            action = CmdRunAction(command=arguments['command'])
            
        elif tool_call.function.name == 'read_file':
            action = FileReadAction(path=arguments['path'])
            
        elif tool_call.function.name == 'edit_file':
            action = FileEditAction(
                path=arguments['path'],
                content=arguments['content']
            )
        # ... etc
        
    return actions
```

**Tool Definition:**

**File:** `/home/ubuntu/workspace/OpenHands/openhands/agenthub/codeact_agent/tools/bash.py`

```python
def create_cmd_run_tool(use_short_description: bool = False):
    return {
        'type': 'function',
        'function': {
            'name': 'execute_bash',
            'description': 'Execute a bash command',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {
                        'type': 'string',
                        'description': 'The bash command to execute'
                    },
                    'timeout': {
                        'type': 'number',
                        'description': 'Timeout in seconds'
                    }
                },
                'required': ['command']
            }
        }
    }
```

**Benefits:**
- JSON schema validation
- Clear parameter definitions
- Consistent error handling
- Easy to extend with new tools

#### CRAG Current State

**File:** `/home/ubuntu/workspace/crag/codebase_rag/tools/code_retrieval.py`

```python
def create_code_retrieval_tool(code_retriever: CodeRetriever) -> Tool:
    """Factory function to create the code snippet retrieval tool."""
    
    async def get_code_snippet(
        ctx: RunContext,
        qualified_name: Annotated[str, Field(..., description="...")]
    ) -> CodeSnippet:
        return await code_retriever.find_code_snippet(qualified_name)

    return Tool(
        function=get_code_snippet,
        name="retrieve_code",
        description="Retrieves the source code...",
    )
```

**Issues:**
- Pydantic-AI Tool abstraction is framework-specific
- No JSON schema for validation
- Tool definitions scattered across files
- No centralized registry

#### Recommendation for CRAG

Create `/home/ubuntu/workspace/crag/codebase_rag/tools/registry.py`:

```python
from typing import Callable, Dict, Any
from dataclasses import dataclass

@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema
    handler: Callable
    
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        
    def register(self, tool_def: ToolDefinition):
        self._tools[tool_def.name] = tool_def
        
    def get_tool(self, name: str) -> ToolDefinition:
        return self._tools.get(name)
        
    def get_all_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
        
    def validate_arguments(self, tool_name: str, arguments: Dict) -> tuple[bool, str]:
        """Validate arguments against JSON schema."""
        tool = self._tools.get(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found"
            
        # Validate required parameters
        required = tool.parameters.get('required', [])
        for param in required:
            if param not in arguments:
                return False, f"Missing required parameter: {param}"
                
        return True, ""
        
    async def execute(self, tool_name: str, arguments: Dict) -> Any:
        """Execute a tool with given arguments."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise FunctionCallNotExistsError(f"Tool '{tool_name}' not found")
            
        valid, error = self.validate_arguments(tool_name, arguments)
        if not valid:
            raise FunctionCallValidationError(error)
            
        return await tool.handler(**arguments)

# Global registry
registry = ToolRegistry()

def register_tool(name: str, description: str, parameters: Dict):
    """Decorator to register a tool."""
    def decorator(func: Callable):
        registry.register(ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=func
        ))
        return func
    return decorator

# Example usage
@register_tool(
    name="retrieve_code",
    description="Retrieves source code for a qualified name",
    parameters={
        "type": "object",
        "properties": {
            "qualified_name": {
                "type": "string",
                "description": "Fully qualified name of function/class"
            }
        },
        "required": ["qualified_name"]
    }
)
async def retrieve_code(qualified_name: str) -> CodeRetrievalObservation:
    # Implementation
    pass
```

---

### 2.5 Timeout and Error Handling

#### OpenHands Implementation

**File:** `/home/ubuntu/workspace/OpenHands/openhands/core/exceptions.py`

```python
# LLM Exceptions
class LLMMalformedActionError(Exception):
    """Raised when LLM returns malformed action"""
    def __init__(self, message: str = 'Malformed response'):
        self.message = message
        super().__init__(message)

class FunctionCallValidationError(Exception):
    """Raised when tool call validation fails"""
    pass

class FunctionCallNotExistsError(Exception):
    """Raised when LLM calls non-existent tool"""
    pass

class AgentStuckInLoopError(Exception):
    """Raised when agent detects it's stuck"""
    pass

class LLMContextWindowExceedError(RuntimeError):
    """Raised when context window exceeded"""
    pass

# Runtime Exceptions
class AgentRuntimeTimeoutError(Exception):
    """Raised when operation times out"""
    pass
```

**Timeout on Actions:**

**File:** `/home/ubuntu/workspace/OpenHands/openhands/events/event.py`

```python
class Event:
    @property
    def timeout(self) -> float | None:
        return getattr(self, '_timeout', None)
        
    def set_hard_timeout(self, value: float | None, blocking: bool = True):
        """Set hard timeout for event execution."""
        self._timeout = value
        if hasattr(self, 'blocking'):
            self.blocking = blocking
```

**Controller Error Handling:**

**File:** `/home/ubuntu/workspace/OpenHands/openhands/controller/agent_controller.py` (lines 301-400)

```python
async def _react_to_exception(self, e: Exception) -> None:
    """React to exception by setting agent state."""
    self.state.last_error = f'{type(e).__name__}: {str(e)}'
    
    # Map exceptions to runtime status
    if isinstance(e, AuthenticationError):
        runtime_status = RuntimeStatus.ERROR_LLM_AUTHENTICATION
    elif isinstance(e, RateLimitError):
        await self.set_agent_state_to(AgentState.RATE_LIMITED)
        return
    elif isinstance(e, ContextWindowExceededError):
        if self.agent.config.enable_history_truncation:
            self.event_stream.add_event(CondensationRequestAction(), 
                                        EventSource.AGENT)
            return
        else:
            raise LLMContextWindowExceedError()
            
    await self.set_agent_state_to(AgentState.ERROR)
```

#### CRAG Current State

**File:** `/home/ubuntu/workspace/crag/codebase_rag/utils.py`

```python
class WatchdogTimeout(Exception):
    """Exception raised when watchdog timer expires."""
    pass

class AsyncWatchdog:
    """Simple watchdog timer."""
    def __init__(self, timeout: float, callback=None):
        self.timeout = timeout
        self._last_feed = time.time()
        
    async def _run(self):
        while True:
            elapsed = time.time() - self._last_feed
            if elapsed >= self.timeout:
                if self._monitored_task:
                    self._monitored_task.cancel()
                break
            await asyncio.sleep(min(10, self.timeout - elapsed + 0.1))
```

**File:** `/home/ubuntu/workspace/crag/codebase_rag/services/scheduler.py`

```python
async def run_iteration(self, user_input: str, message_history: List[ModelMessage]):
    try:
        result = await self.agent.run(...)
    except UsageLimitExceeded as e:
        # Generic error handling
        error_msg = "### ⚠️ Analysis interrupted..."
        return SyntheticResult(error_msg)
    except Exception as e:
        self.transition_to(AnalysisState.RECOVERING, f"Agent Error: {e}")
        raise e
```

**Issues:**
- Only generic watchdog timeout
- No per-action timeout support
- No specific exception types
- Error handling is ad-hoc

#### Recommendation for CRAG

Create `/home/ubuntu/workspace/crag/codebase_rag/exceptions.py`:

```python
class CRAGError(Exception):
    """Base exception for CRAG."""
    pass

# Graph Query Errors
class GraphQueryError(CRAGError):
    """Raised when graph query fails."""
    def __init__(self, query: str, error: str, suggestion: str = None):
        self.query = query
        self.error = error
        self.suggestion = suggestion
        super().__init__(f"Graph query failed: {error}")

class EntityNotFoundError(GraphQueryError):
    """Raised when entity not found in graph."""
    def __init__(self, qualified_name: str):
        self.qualified_name = qualified_name
        super().__init__(
            query=f"MATCH (n) WHERE n.qualified_name = '{qualified_name}'",
            error=f"Entity '{qualified_name}' not found",
            suggestion="Check the qualified name or use global_text_search"
        )

# Code Retrieval Errors
class CodeRetrievalError(CRAGError):
    """Raised when code retrieval fails."""
    pass

class FileNotFoundInCodebaseError(CodeRetrievalError):
    """Raised when file not found."""
    def __init__(self, path: str, codebase_root: str):
        self.path = path
        self.codebase_root = codebase_root
        super().__init__(f"File not found: {path}")

# Analysis Errors
class AnalysisError(CRAGError):
    """Raised when analysis fails."""
    pass

class FunctionResolutionError(AnalysisError):
    """Raised when function pointer resolution fails."""
    def __init__(self, function_name: str, reason: str):
        self.function_name = function_name
        self.reason = reason
        super().__init__(f"Cannot resolve function '{function_name}': {reason}")

class AnalysisStuckError(AnalysisError):
    """Raised when analysis appears stuck."""
    def __init__(self, current_function: str, path_length: int):
        self.current_function = current_function
        self.path_length = path_length
        super().__init__(f"Analysis stuck at '{current_function}' after {path_length} steps")

# Tool Errors
class ToolExecutionError(CRAGError):
    """Raised when tool execution fails."""
    def __init__(self, tool_name: str, error: str):
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {error}")

class ToolTimeoutError(ToolExecutionError):
    """Raised when tool execution times out."""
    def __init__(self, tool_name: str, timeout: float):
        self.timeout = timeout
        super().__init__(tool_name, f"Timed out after {timeout}s")
```

Update scheduler with proper error handling:

```python
class StateMachineScheduler:
    async def run_iteration(self, user_input: str, message_history: List[ModelMessage]):
        try:
            result = await self._execute_with_timeout(
                self.agent.run(current_prompt, message_history=message_history),
                timeout=300  # 5 minute timeout per iteration
            )
        except ToolTimeoutError as e:
            logger.error(f"Tool timeout: {e}")
            self.transition_to(AnalysisState.RECOVERING, f"Timeout: {e.tool_name}")
            return await self._handle_timeout_recovery(e)
            
        except FunctionResolutionError as e:
            logger.error(f"Function resolution failed: {e}")
            self.transition_to(AnalysisState.RECOVERING, "Function resolution failed")
            return await self._handle_resolution_failure(e)
            
        except EntityNotFoundError as e:
            logger.warning(f"Entity not found: {e.qualified_name}")
            return await self._handle_entity_not_found(e)
            
        except Exception as e:
            logger.exception("Unexpected error in run_iteration")
            self.transition_to(AnalysisState.RECOVERING, f"Unexpected error: {e}")
            raise
            
    async def _execute_with_timeout(self, coro, timeout: float):
        """Execute coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            raise ToolTimeoutError("agent_run", timeout)
```

---

## 3. Specific Improvements for Function Pointer Resolution

### Current Challenge

Function pointer resolution in C/C++ codebases is difficult because:
1. Pointers are assigned dynamically at runtime
2. Callbacks are registered in struct fields
3. Indirect calls through function pointers

### Recommended Architecture

```python
# agents/resolution_agent.py
class FunctionResolutionAgent:
    """Specialized agent for resolving function pointers."""
    
    def __init__(self, ingestor: MemgraphIngestor, event_stream: EventStream):
        self.ingestor = ingestor
        self.event_stream = event_stream
        
    async def resolve_function_pointer(
        self, 
        action: FunctionPointerResolutionAction
    ) -> FunctionPointerResolutionObservation:
        """
        Resolve a function pointer using multiple strategies:
        1. Static analysis of struct initializations
        2. Text search for assignments
        3. Graph traversal for callback registrations
        """
        strategies = [
            self._resolve_from_struct_init(action),
            self._resolve_from_text_search(action),
            self._resolve_from_graph_patterns(action),
        ]
        
        for strategy in strategies:
            try:
                result = await asyncio.wait_for(strategy, timeout=30)
                if result.resolved:
                    return result
            except asyncio.TimeoutError:
                continue
                
        return FunctionPointerResolutionObservation(
            resolved=False,
            candidates=[],
            error="Could not resolve function pointer with any strategy"
        )
        
    async def _resolve_from_struct_init(self, action):
        """Look for struct field initializations."""
        query = """
            MATCH (s:Struct)-[:HAS_FIELD]->(f:Field)
            WHERE f.name = $field_name
            MATCH (s)-[:INITIALIZED_WITH]->(init:Initializer)
            RETURN init.code as code
        """
        # Execute query and analyze results
        pass
        
    async def _resolve_from_text_search(self, action):
        """Text search for pattern: struct->field = function"""
        pattern = f"{action.struct_type}->{action.field_name}"
        # Search codebase for pattern
        pass
```

---

## 4. Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
1. Create `events/` module with EventStream
2. Define Action/Observation base classes
3. Create exception hierarchy
4. Add event logging

### Phase 2: Tool Refactoring (Week 3-4)
1. Create ToolRegistry
2. Convert existing tools to new pattern
3. Add JSON schema validation
4. Implement proper error handling

### Phase 3: Multi-Agent Support (Week 5-6)
1. Create specialized agents (CypherAgent, AnalysisAgent)
2. Implement DelegationManager
3. Add agent lifecycle management
4. Test delegation scenarios

### Phase 4: Advanced Features (Week 7-8)
1. Implement function pointer resolution agent
2. Add comprehensive timeout handling
3. Create event replay/debugging tools
4. Performance optimization

---

## 5. File Structure Recommendations

```
codebase_rag/
├── events/
│   ├── __init__.py
│   ├── stream.py          # EventStream implementation
│   ├── event.py           # Base Event class
│   ├── action.py          # Action classes
│   ├── observation.py     # Observation classes
│   └── serialization.py   # Event serialization
├── agents/
│   ├── __init__.py
│   ├── base.py            # Base agent interface
│   ├── cypher_agent.py    # Graph query agent
│   ├── analysis_agent.py  # Code analysis agent
│   ├── resolution_agent.py # Function pointer resolution
│   └── delegation.py      # Delegation manager
├── tools/
│   ├── __init__.py
│   ├── registry.py        # ToolRegistry
│   ├── base.py            # Base tool definitions
│   ├── code_retrieval.py  # Updated with new pattern
│   └── ...
├── exceptions.py          # Custom exceptions
└── main.py               # Updated to use EventStream
```

---

## 6. Key Takeaways

1. **Event-Driven Architecture** enables better debugging, replay, and extensibility
2. **Action/Observation Pattern** provides clear separation of intent and result
3. **Multi-Agent Delegation** allows specialized handling of complex tasks
4. **Comprehensive Error Handling** with specific exceptions improves reliability
5. **Standardized Tool Definitions** with JSON schema enable validation and consistency

The OpenHands architecture demonstrates production-ready patterns that would significantly improve CRAG's maintainability, extensibility, and robustness, especially for complex code tracing scenarios like function pointer resolution.
