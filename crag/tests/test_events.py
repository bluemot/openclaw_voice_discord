"""
Unit tests for CRAG Event System.

Tests cover:
- Base classes (Event, Action, Observation)
- Concrete action types (TraceAction, SearchAction, etc.)
- Concrete observation types (TraceObservation, SearchObservation, etc.)
- Serialization/Deserialization
- EventStream functionality
- Integration with Trace Protocol
"""

import pytest
import asyncio
import json
from datetime import datetime
from typing import Dict, Any

# Add project root to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from codebase_rag.events.base import (
    Event, Action, Observation,
    ActionStatus, ObservationStatus,
    EventMetadata, EventSource
)
from codebase_rag.events.action import (
    TraceAction, SearchAction, QueryAction,
    ShellAction, ParseAction, ResolveAction,
    TraceDirection, SearchScope, QueryType
)
from codebase_rag.events.observation import (
    TraceObservation, SearchObservation, QueryObservation,
    ShellObservation, ParseObservation, ResolveObservation,
    ErrorObservation, GraphEdge, CodeLocation, SymbolInfo
)
from codebase_rag.events.serializer import EventSerializer, EventBatch


class TestBaseClasses:
    """Test base Event, Action, Observation classes."""
    
    def test_event_metadata_creation(self):
        """Test EventMetadata can be created."""
        metadata = EventMetadata(
            source=EventSource.AGENT,
            session_id="test-session"
        )
        assert metadata.source == EventSource.AGENT
        assert metadata.session_id == "test-session"
        assert isinstance(metadata.timestamp, datetime)
    
    def test_action_status_transitions(self):
        """Test Action status transitions."""
        action = Action(
            action_id="test-1",
            status=ActionStatus.PENDING
        )
        
        # Test status transitions
        running = action.to_running()
        assert running.status == ActionStatus.RUNNING
        
        completed = action.to_completed()
        assert completed.status == ActionStatus.COMPLETED
        
        failed = action.to_failed()
        assert failed.status == ActionStatus.FAILED
    
    def test_observation_success_check(self):
        """Test Observation success property."""
        success_obs = Observation(
            action_id="test-1",
            status=ObservationStatus.SUCCESS
        )
        assert success_obs.success is True
        assert success_obs.error is False
        
        error_obs = Observation(
            action_id="test-1",
            status=ObservationStatus.ERROR
        )
        assert error_obs.success is False
        assert error_obs.error is True


class TestTraceAction:
    """Test TraceAction and TraceObservation."""
    
    def test_trace_action_creation(self):
        """Test TraceAction can be created."""
        action = TraceAction(
            action_id="trace-1",
            entry_point="main",
            direction=TraceDirection.UP,
            depth=0,
            max_depth=10
        )
        
        assert action.entry_point == "main"
        assert action.direction == TraceDirection.UP
        assert action.depth == 0
        assert action.max_depth == 10
    
    def test_trace_action_validation(self):
        """Test TraceAction validation."""
        with pytest.raises(ValueError):
            TraceAction(
                action_id="trace-1",
                entry_point="",  # Empty entry_point should fail
                direction=TraceDirection.UP
            )
    
    def test_trace_action_to_protocol(self):
        """Test TraceAction conversion to Trace Protocol."""
        action = TraceAction(
            action_id="trace-1",
            entry_point="main",
            direction=TraceDirection.DOWN,
            depth=2,
            context="test context"
        )
        
        protocol_task = action.to_trace_protocol_task()
        assert protocol_task["entry_point"] == "main"
        assert protocol_task["direction"] == "down"
        assert protocol_task["depth"] == 2
    
    def test_trace_observation_creation(self):
        """Test TraceObservation can be created."""
        edge = GraphEdge(source="foo", relation="CALLS", target="bar")
        observation = TraceObservation(
            action_id="trace-1",
            entry_point="main",
            direction="up",
            edges=[edge],
            status=ObservationStatus.SUCCESS,
            message="Trace completed"
        )
        
        assert len(observation.edges) == 1
        assert observation.edges[0].source == "foo"
        assert observation.depth_reached == 0
    
    def test_trace_observation_from_protocol(self):
        """Test TraceObservation from Trace Protocol result."""
        result = {
            "task_id": "main",
            "direction": "up",
            "status": "done",
            "explored_graph": [
                {"source": "foo", "relation": "CALLS", "target": "main"}
            ],
            "conclusion": "Success"
        }
        
        observation = TraceObservation.from_trace_protocol_result("trace-1", result)
        assert observation.entry_point == "main"
        assert observation.status == ObservationStatus.SUCCESS
        assert len(observation.edges) == 1


class TestSearchAction:
    """Test SearchAction and SearchObservation."""
    
    def test_search_action_creation(self):
        """Test SearchAction can be created."""
        action = SearchAction(
            action_id="search-1",
            query="cudaMemcpy",
            scope=SearchScope.SYMBOL,
            language="cpp",
            limit=20
        )
        
        assert action.query == "cudaMemcpy"
        assert action.scope == SearchScope.SYMBOL
        assert action.language == "cpp"
        assert action.limit == 20
    
    def test_search_action_validation(self):
        """Test SearchAction validation."""
        with pytest.raises(ValueError):
            SearchAction(
                action_id="search-1",
                query="",  # Empty query should fail
                scope=SearchScope.SYMBOL
            )


class TestSerializer:
    """Test EventSerializer."""
    
    def test_serialize_action(self):
        """Test Action serialization."""
        action = TraceAction(
            action_id="trace-1",
            entry_point="main",
            direction=TraceDirection.UP
        )
        
        json_str = EventSerializer.serialize(action)
        assert isinstance(json_str, str)
        
        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["_event_type"] == "TraceAction"
        assert data["entry_point"] == "main"
    
    def test_deserialize_action(self):
        """Test Action deserialization."""
        action = TraceAction(
            action_id="trace-1",
            entry_point="main",
            direction=TraceDirection.UP
        )
        
        json_str = EventSerializer.serialize(action)
        restored = EventSerializer.deserialize(json_str)
        
        assert isinstance(restored, TraceAction)
        assert restored.entry_point == "main"
        assert restored.direction == TraceDirection.UP
    
    def test_deserialize_unknown_type(self):
        """Test deserialization of unknown type fails."""
        data = {"_event_type": "UnknownAction", "action_id": "test"}
        
        with pytest.raises(ValueError, match="Unknown event type"):
            EventSerializer.deserialize(json.dumps(data))
    
    def test_event_batch(self):
        """Test EventBatch functionality."""
        batch = EventBatch()
        
        action1 = TraceAction(action_id="t1", entry_point="main")
        action2 = SearchAction(action_id="s1", query="test")
        
        batch.add(action1)
        batch.add(action2)
        
        assert len(batch) == 2
        
        # Serialize and deserialize
        json_str = batch.serialize()
        restored = EventBatch.deserialize(json_str)
        
        assert len(restored) == 2


class TestEventStream:
    """Test EventStream functionality."""
    
    @pytest.mark.asyncio
    async def test_event_stream_basic(self):
        """Test basic EventStream publish/subscribe."""
        from codebase_rag.events.stream import EventStream
        
        stream = EventStream()
        
        # Create test action
        action = TraceAction(
            action_id="test-1",
            entry_point="main",
            direction=TraceDirection.UP
        )
        
        # Start stream
        await stream.start()
        assert stream.is_running
        
        # Publish event
        await stream.publish(action)
        assert stream.queue_size == 1
        
        # Stop stream
        await stream.stop()
        assert not stream.is_running
    
    @pytest.mark.asyncio
    async def test_event_stream_subscribe(self):
        """Test EventStream subscribe as async iterator."""
        from codebase_rag.events.stream import EventStream
        
        stream = EventStream()
        action = TraceAction(
            action_id="test-1",
            entry_point="main",
            direction=TraceDirection.UP
        )
        
        await stream.start()
        
        # Publish event
        await stream.publish(action)
        
        # Subscribe with timeout
        events = []
        async for event in stream.subscribe(timeout=1.0):
            events.append(event)
            break  # Just get one event
        
        assert len(events) == 1
        assert isinstance(events[0], TraceAction)
        
        await stream.stop()


class TestIntegration:
    """Test integration with existing CRAG code."""
    
    def test_trace_protocol_integration(self):
        """Test integration with Trace Protocol."""
        # Create action from trace protocol format
        task = {
            "task_id": "main",
            "entry_point": "main",
            "direction": "up",
            "depth": 0,
            "context": "test"
        }
        
        action = TraceAction.from_trace_protocol_task(task)
        assert action.entry_point == "main"
        assert action.direction == TraceDirection.UP
        
        # Convert back to protocol
        protocol_task = action.to_trace_protocol_task()
        assert protocol_task["entry_point"] == "main"
    
    def test_symbol_info_creation(self):
        """Test SymbolInfo and related types."""
        location = CodeLocation(
            file_path="/test/file.py",
            line_start=10,
            line_end=20
        )
        
        symbol = SymbolInfo(
            name="test_func",
            qualified_name="module.test_func",
            kind="function",
            location=location
        )
        
        assert symbol.name == "test_func"
        assert symbol.location.line_start == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])