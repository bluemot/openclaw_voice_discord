"""
Events Package - Action/Observation Pattern for CRAG

This package implements the Action/Observation pattern inspired by OpenHands:
- Actions represent operations to be performed (e.g., "trace_callers", "search_code")
- Observations represent the results of those operations

This pattern enables:
1. Typed communication between agents
2. EventStream architecture for async workflows
3. Serialization for persistence and distributed execution
4. Clear separation of concerns

Usage:
    from codebase_rag.events import Action, Observation
    from codebase_rag.events.action import TraceAction
    from codebase_rag.events.observation import TraceObservation

    # Create an action
    action = TraceAction(
        entry_point="main",
        direction="up",
        depth=0
    )

    # Execute and get observation
    observation = await executor.execute(action)

Architecture:
    Action -> Executor -> Observation
      ^                      |
      |______ EventStream ___|
"""

from typing import Optional, Any
from datetime import datetime

# Export base classes
from .base import (
    Event,
    EventMetadata,
    EventSource,
    Action,
    Observation,
    ActionStatus,
    ObservationStatus,
)

# Export concrete action types
from .action import (
    TraceAction,
    SearchAction,
    QueryAction,
    ShellAction,
    ParseAction,
    ResolveAction,
)

# Export concrete observation types
from .observation import (
    TraceObservation,
    SearchObservation,
    QueryObservation,
    ShellObservation,
    ParseObservation,
    ResolveObservation,
    ErrorObservation,
)

# Export utilities
from .serializer import EventSerializer
from .stream import EventStream, EventStreamSubscriber

__all__ = [
    # Base classes
    "Event",
    "EventMetadata",
    "EventSource",
    "Action",
    "Observation",
    "ActionStatus",
    "ObservationStatus",
    # Actions
    "TraceAction",
    "SearchAction",
    "QueryAction",
    "ShellAction",
    "ParseAction",
    "ResolveAction",
    # Observations
    "TraceObservation",
    "SearchObservation",
    "QueryObservation",
    "ShellObservation",
    "ParseObservation",
    "ResolveObservation",
    "ErrorObservation",
    # Utilities
    "EventSerializer",
    "EventStream",
    "EventStreamSubscriber",
]


__version__ = "0.1.0"
