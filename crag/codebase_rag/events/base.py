"""
Base classes for Action/Observation pattern.

This module defines the foundational types for the event system:
- Event: Base class for all events (actions and observations)
- EventMetadata: Common metadata for all events
- Action: Base class for actions (operations to perform)
- Observation: Base class for observations (results of actions)

Design Principles:
1. All events are immutable Pydantic models
2. Events have unique IDs for tracking
3. Events carry metadata (timestamp, source, etc.)
4. Actions and Observations are linked by action_id
"""

from abc import ABC
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class EventSource(str, Enum):
    """Source of an event."""
    USER = "user"           # Direct user input
    AGENT = "agent"         # Agent-generated
    SYSTEM = "system"       # System-generated
    TOOL = "tool"           # Tool output
    LLM = "llm"             # LLM-generated


class ActionStatus(str, Enum):
    """Status of an action."""
    PENDING = "pending"     # Waiting to be executed
    RUNNING = "running"     # Currently executing
    COMPLETED = "completed" # Successfully completed
    FAILED = "failed"       # Execution failed
    CANCELLED = "cancelled" # Cancelled before completion


class ObservationStatus(str, Enum):
    """Status of an observation."""
    SUCCESS = "success"     # Action succeeded
    ERROR = "error"         # Action failed
    PARTIAL = "partial"     # Partial success
    TIMEOUT = "timeout"     # Action timed out
    CANCELLED = "cancelled" # Action was cancelled


class EventMetadata(BaseModel):
    """
    Metadata common to all events.
    
    Attributes:
        timestamp: When the event was created
        source: Source of the event
        session_id: Session identifier for grouping events
        parent_id: Parent event ID for hierarchical relationships
        tags: Optional tags for categorization
        extra: Additional metadata
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: EventSource = Field(default=EventSource.AGENT)
    session_id: Optional[str] = Field(default=None)
    parent_id: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(frozen=True)


class Event(BaseModel, ABC):
    """
    Base class for all events.
    
    All events in the system inherit from this class.
    Events are immutable and have unique IDs.
    
    Attributes:
        id: Unique event identifier
        action_id: ID of the action this event relates to
        metadata: Event metadata
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    action_id: str = Field(..., description="ID of the related action")
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def event_type(self) -> str:
        """Return the event type (class name)."""
        return self.__class__.__name__
    
    def with_metadata(self, **kwargs) -> "Event":
        """Create a new event with updated metadata."""
        current = self.metadata.model_dump()
        current.update(kwargs)
        new_metadata = EventMetadata(**current)
        return self.model_copy(update={"metadata": new_metadata})


class Action(Event, ABC):
    """
    Base class for all actions.
    
    Actions represent operations to be performed by the system.
    They are executed by an executor and produce observations.
    
    Attributes:
        status: Current status of the action
        thought: Optional reasoning/thought process
    """
    status: ActionStatus = Field(default=ActionStatus.PENDING)
    thought: Optional[str] = Field(
        default=None,
        description="Reasoning or thought process behind this action"
    )
    
    model_config = ConfigDict(frozen=True)
    
    def to_pending(self) -> "Action":
        """Mark action as pending."""
        return self.model_copy(update={"status": ActionStatus.PENDING})
    
    def to_running(self) -> "Action":
        """Mark action as running."""
        return self.model_copy(update={"status": ActionStatus.RUNNING})
    
    def to_completed(self) -> "Action":
        """Mark action as completed."""
        return self.model_copy(update={"status": ActionStatus.COMPLETED})
    
    def to_failed(self) -> "Action":
        """Mark action as failed."""
        return self.model_copy(update={"status": ActionStatus.FAILED})
    
    def to_cancelled(self) -> "Action":
        """Mark action as cancelled."""
        return self.model_copy(update={"status": ActionStatus.CANCELLED})


class Observation(Event, ABC):
    """
    Base class for all observations.
    
    Observations represent the results of actions.
    They are produced by executors after running actions.
    
    Attributes:
        status: Status of the observation
        message: Human-readable message
        cause: Optional error cause or additional context
    """
    status: ObservationStatus = Field(default=ObservationStatus.SUCCESS)
    message: str = Field(default="")
    cause: Optional[str] = Field(
        default=None,
        description="Error cause or additional context"
    )
    
    model_config = ConfigDict(frozen=True)
    
    @property
    def success(self) -> bool:
        """Check if observation indicates success."""
        return self.status == ObservationStatus.SUCCESS
    
    @property
    def error(self) -> bool:
        """Check if observation indicates error."""
        return self.status == ObservationStatus.ERROR
    
    def with_message(self, message: str) -> "Observation":
        """Create a new observation with updated message."""
        return self.model_copy(update={"message": message})
