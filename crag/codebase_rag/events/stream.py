"""
EventStream for CRAG Event System.

This module provides EventStream architecture for async workflows:
- EventStream: Central event bus for publishing and subscribing
- EventStreamSubscriber: Interface for event consumers
- Async support for non-blocking event processing

Usage:
    from codebase_rag.events.stream import EventStream
    
    stream = EventStream()
    
    # Subscribe to events
    async for event in stream.subscribe():
        print(f"Received: {event}")
    
    # Publish events
    await stream.publish(action)
"""

import asyncio
from typing import Callable, Optional, AsyncIterator, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .base import Event, Action, Observation, EventSource


class EventPriority(int, Enum):
    """Priority levels for events."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class StreamEvent:
    """
    Wrapper for events in the stream.
    
    Adds metadata like priority and timestamp.
    """
    event: Event
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __lt__(self, other: "StreamEvent") -> bool:
        """Compare by priority for queue ordering."""
        return self.priority.value < other.priority.value


class EventStreamSubscriber:
    """
    Subscriber interface for EventStream.
    
    Implement this to receive events from the stream.
    
    Example:
        class MySubscriber(EventStreamSubscriber):
            async def on_event(self, event: Event) -> None:
                print(f"Received: {event}")
            
            def filter(self, event: Event) -> bool:
                return isinstance(event, TraceAction)
    """
    
    async def on_event(self, event: Event) -> None:
        """
        Called when an event is received.
        
        Args:
            event: The received event
        """
        pass
    
    def filter(self, event: Event) -> bool:
        """
        Filter events before receiving.
        
        Args:
            event: Event to filter
            
        Returns:
            True if event should be received
        """
        return True


class EventStream:
    """
    Central event bus for async event processing.
    
    Provides publish/subscribe pattern for events with:
    - Async queue-based processing
    - Priority-based event ordering
    - Multiple subscribers
    - Event filtering
    
    Example:
        stream = EventStream()
        
        # Start processing
        await stream.start()
        
        # Subscribe
        subscriber = MySubscriber()
        stream.add_subscriber(subscriber)
        
        # Publish events
        await stream.publish(action, priority=EventPriority.HIGH)
        
        # Stop processing
        await stream.stop()
    """
    
    def __init__(self, maxsize: int = 1000):
        """
        Initialize EventStream.
        
        Args:
            maxsize: Maximum queue size (0 = unlimited)
        """
        self._queue: asyncio.PriorityQueue[StreamEvent] = asyncio.PriorityQueue(maxsize=maxsize)
        self._subscribers: List[EventStreamSubscriber] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """Start the event processing loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_loop())
    
    async def stop(self) -> None:
        """Stop the event processing loop."""
        if not self._running:
            return
        
        self._running = False
        
        # Add sentinel to unblock queue
        await self._queue.put(StreamEvent(
            event=None,  # type: ignore
            priority=EventPriority.CRITICAL
        ))
        
        if self._task:
            await self._task
            self._task = None
    
    async def publish(
        self,
        event: Event,
        priority: EventPriority = EventPriority.NORMAL
    ) -> None:
        """
        Publish an event to the stream.
        
        Args:
            event: Event to publish
            priority: Event priority
        """
        stream_event = StreamEvent(event=event, priority=priority)
        await self._queue.put(stream_event)
    
    def add_subscriber(self, subscriber: EventStreamSubscriber) -> None:
        """
        Add a subscriber to the stream.
        
        Args:
            subscriber: Subscriber to add
        """
        self._subscribers.append(subscriber)
    
    def remove_subscriber(self, subscriber: EventStreamSubscriber) -> None:
        """
        Remove a subscriber from the stream.
        
        Args:
            subscriber: Subscriber to remove
        """
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)
    
    async def subscribe(
        self,
        event_types: Optional[List[type]] = None,
        timeout: Optional[float] = None
    ) -> AsyncIterator[Event]:
        """
        Subscribe to events as an async iterator.
        
        Args:
            event_types: Optional list of event types to filter
            timeout: Optional timeout in seconds
            
        Yields:
            Events from the stream
            
        Example:
            async for event in stream.subscribe(event_types=[TraceAction]):
                print(event)
        """
        while self._running:
            try:
                stream_event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=timeout
                )
                
                # Check for sentinel
                if stream_event.event is None:
                    break
                
                # Filter by type
                if event_types and not any(
                    isinstance(stream_event.event, t) for t in event_types
                ):
                    continue
                
                yield stream_event.event
                
            except asyncio.TimeoutError:
                break
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                stream_event = await self._queue.get()
                
                # Check for sentinel
                if stream_event.event is None:
                    break
                
                # Notify subscribers
                await self._notify_subscribers(stream_event.event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing event: {e}")
    
    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers of an event."""
        for subscriber in self._subscribers:
            try:
                if subscriber.filter(event):
                    await subscriber.on_event(event)
            except Exception as e:
                print(f"Error in subscriber: {e}")
    
    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()


class ActionExecutor:
    """
    Executor that processes Actions and produces Observations.
    
    Integrates with EventStream to execute actions asynchronously.
    
    Example:
        executor = ActionExecutor()
        stream = EventStream()
        
        # Connect executor to stream
        stream.add_subscriber(executor)
        
        # Start processing
        await stream.start()
        
        # Publish action
        await stream.publish(action)
        
        # Observation will be published back to stream
    """
    
    def __init__(self, stream: Optional[EventStream] = None):
        """
        Initialize ActionExecutor.
        
        Args:
            stream: Optional EventStream to publish observations to
        """
        self.stream = stream
        self._handlers: Dict[type, Callable[[Action], Observation]] = {}
    
    def register_handler(
        self,
        action_type: type,
        handler: Callable[[Action], Observation]
    ) -> None:
        """
        Register a handler for an action type.
        
        Args:
            action_type: Type of action to handle
            handler: Handler function
        """
        self._handlers[action_type] = handler
    
    async def on_event(self, event: Event) -> None:
        """
        Process an action event.
        
        Args:
            event: Event to process
        """
        if not isinstance(event, Action):
            return
        
        # Find handler
        handler = self._handlers.get(type(event))
        if not handler:
            from .observation import ErrorObservation
            observation = ErrorObservation(
                action_id=event.action_id,
                message=f"No handler for action type: {type(event).__name__}",
                error_type="NoHandlerError"
            )
        else:
            try:
                observation = handler(event)
            except Exception as e:
                from .observation import ErrorObservation
                observation = ErrorObservation(
                    action_id=event.action_id,
                    message=str(e),
                    error_type=type(e).__name__,
                    error_details=str(e)
                )
        
        # Publish observation back to stream
        if self.stream:
            await self.stream.publish(observation)
    
    def filter(self, event: Event) -> bool:
        """Filter to only accept Actions."""
        return isinstance(event, Action)


# Make ActionExecutor a proper subscriber
EventStreamSubscriber.register(ActionExecutor)
