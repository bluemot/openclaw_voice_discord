"""
Event Serializer for CRAG Event System.

This module provides serialization/deserialization for events:
- JSON serialization for persistence
- Type registry for polymorphic deserialization
- Validation during deserialization

Usage:
    from codebase_rag.events.serializer import EventSerializer
    
    # Serialize
    json_str = EventSerializer.serialize(action)
    
    # Deserialize
    event = EventSerializer.deserialize(json_str)
"""

import json
from typing import Type, Dict, Any, Optional, Union
from datetime import datetime

from .base import Event, Action, Observation, EventMetadata
from .action import (
    TraceAction, SearchAction, QueryAction,
    ShellAction, ParseAction, ResolveAction
)
from .observation import (
    TraceObservation, SearchObservation, QueryObservation,
    ShellObservation, ParseObservation, ResolveObservation, ErrorObservation
)


class EventSerializer:
    """
    Serializer for events.
    
    Handles serialization and deserialization of events to/from JSON.
    Uses a type registry for polymorphic deserialization.
    
    Example:
        serializer = EventSerializer()
        
        # Serialize
        json_str = serializer.serialize(action)
        
        # Deserialize
        event = serializer.deserialize(json_str)
    """
    
    # Type registry mapping event type names to classes
    _TYPE_REGISTRY: Dict[str, Type[Event]] = {
        # Actions
        "TraceAction": TraceAction,
        "SearchAction": SearchAction,
        "QueryAction": QueryAction,
        "ShellAction": ShellAction,
        "ParseAction": ParseAction,
        "ResolveAction": ResolveAction,
        # Observations
        "TraceObservation": TraceObservation,
        "SearchObservation": SearchObservation,
        "QueryObservation": QueryObservation,
        "ShellObservation": ShellObservation,
        "ParseObservation": ParseObservation,
        "ResolveObservation": ResolveObservation,
        "ErrorObservation": ErrorObservation,
    }
    
    @classmethod
    def register_type(cls, name: str, event_class: Type[Event]) -> None:
        """
        Register a new event type.
        
        Args:
            name: Type name for serialization
            event_class: Event class to register
        """
        cls._TYPE_REGISTRY[name] = event_class
    
    @classmethod
    def serialize(cls, event: Event, **kwargs) -> str:
        """
        Serialize an event to JSON string.
        
        Args:
            event: Event to serialize
            **kwargs: Additional arguments for json.dumps
            
        Returns:
            JSON string representation
        """
        data = event.model_dump(mode="json")
        data["_event_type"] = event.event_type
        
        default_kwargs = {"indent": 2, "default": cls._json_encoder}
        default_kwargs.update(kwargs)
        
        return json.dumps(data, **default_kwargs)
    
    @classmethod
    def deserialize(cls, data: Union[str, Dict[str, Any]]) -> Event:
        """
        Deserialize an event from JSON string or dict.
        
        Args:
            data: JSON string or dict to deserialize
            
        Returns:
            Deserialized Event instance
            
        Raises:
            ValueError: If event type is unknown or data is invalid
        """
        if isinstance(data, str):
            data = json.loads(data)
        
        if not isinstance(data, dict):
            raise ValueError(f"Expected dict, got {type(data)}")
        
        event_type = data.pop("_event_type", None)
        if not event_type:
            raise ValueError("Missing _event_type field")
        
        event_class = cls._TYPE_REGISTRY.get(event_type)
        if not event_class:
            raise ValueError(f"Unknown event type: {event_type}")
        
        # Parse metadata if present
        if "metadata" in data and isinstance(data["metadata"], dict):
            data["metadata"] = EventMetadata(**data["metadata"])
        
        return event_class(**data)
    
    @classmethod
    def to_dict(cls, event: Event) -> Dict[str, Any]:
        """
        Convert event to dictionary.
        
        Args:
            event: Event to convert
            
        Returns:
            Dictionary representation
        """
        data = event.model_dump(mode="json")
        data["_event_type"] = event.event_type
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Event:
        """
        Create event from dictionary.
        
        Args:
            data: Dictionary to convert
            
        Returns:
            Event instance
        """
        return cls.deserialize(data)
    
    @classmethod
    def _json_encoder(cls, obj: Any) -> Any:
        """
        Custom JSON encoder for special types.
        
        Args:
            obj: Object to encode
            
        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    @classmethod
    def get_registered_types(cls) -> Dict[str, Type[Event]]:
        """
        Get all registered event types.
        
        Returns:
            Dictionary of type names to classes
        """
        return cls._TYPE_REGISTRY.copy()


class EventBatch:
    """
    Batch of events for bulk operations.
    
    Useful for persisting or transmitting multiple events.
    
    Example:
        batch = EventBatch()
        batch.add(action)
        batch.add(observation)
        
        json_str = batch.serialize()
        loaded = EventBatch.deserialize(json_str)
    """
    
    def __init__(self):
        self.events: list[Event] = []
    
    def add(self, event: Event) -> None:
        """Add an event to the batch."""
        self.events.append(event)
    
    def extend(self, events: list[Event]) -> None:
        """Extend batch with multiple events."""
        self.events.extend(events)
    
    def serialize(self) -> str:
        """Serialize batch to JSON string."""
        data = {
            "events": [
                EventSerializer.to_dict(e) for e in self.events
            ]
        }
        return json.dumps(data, indent=2)
    
    @classmethod
    def deserialize(cls, data: Union[str, Dict[str, Any]]) -> "EventBatch":
        """Deserialize batch from JSON."""
        if isinstance(data, str):
            data = json.loads(data)
        
        batch = cls()
        for event_data in data.get("events", []):
            event = EventSerializer.deserialize(event_data)
            batch.add(event)
        
        return batch
    
    def __len__(self) -> int:
        return len(self.events)
    
    def __iter__(self):
        return iter(self.events)
