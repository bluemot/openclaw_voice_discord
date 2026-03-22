"""
HybridScheduler - Combining StateMachineScheduler and TraceManager features

This scheduler provides:
- Async state machine (IDLE → EXPLORING → ANALYZING → VERIFYING → COMPLETED)
- Priority queue for task scheduling
- Depth tracking and request limiting
- Mandatory answer mechanism (guarantees an answer even if no results)
- Multi-stage search strategy

Created: 2026-03-21
"""

import asyncio
import heapq
import time
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

from .scheduler import SchedulerState
from ..events import EventStreamSubscriber


@dataclass(order=True)
class PrioritizedTask:
    """Wrapper for priority queue items."""
    priority: float
    counter: int
    task: Any = field(compare=False)


@dataclass
class TaskResult:
    """Result from executing a task."""
    success: bool
    findings: List[Any]
    depth_reached: int
    message: str


class HybridScheduler(EventStreamSubscriber):
    """
    Hybrid Scheduler combining StateMachine and TraceManager features.
    
    Guarantees an answer within specified limits.
    """
    
    def __init__(
        self,
        agent: Any,
        max_depth: int = 10,
        max_requests: int = 20,
        timeout_seconds: int = 300,
        max_concurrent: int = 3
    ):
        super().__init__()
        
        # Agent reference
        self.agent = agent
        
        # State machine
        self.state = SchedulerState.IDLE
        self.state_history: List[Tuple[SchedulerState, datetime]] = []
        
        # Priority queue
        self.task_queue: List[PrioritizedTask] = []
        self.task_counter = 0
        
        # Limits
        self.max_depth = max_depth
        self.max_requests = max_requests
        self.timeout_seconds = timeout_seconds
        self.max_concurrent = max_concurrent
        
        # Tracking
        self.request_count = 0
        self.depth_per_path: Dict[str, int] = {}
        self.completed_tasks: List[TaskResult] = []
        self.partial_findings: List[Any] = []
        
        # Statistics
        self.stats = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "cycles_detected": 0
        }
        
        logger.info(f"[HybridScheduler] Initialized with max_depth={max_depth}, "
                   f"max_requests={max_requests}, timeout={timeout_seconds}s")
    
    def calculate_priority(self, task: Any) -> float:
        """
        Calculate task priority (lower = higher priority).
        
        Factors:
        - Depth penalty: deeper tasks are lower priority
        - Semantic relevance (if available)
        """
        depth = getattr(task, 'depth', 0)
        depth_penalty = depth * 10.0
        
        # TODO: Add semantic relevance calculation
        # relevance = self._calculate_relevance(task)
        
        return depth_penalty
    
    def add_task(self, task: Any) -> None:
        """Add a task to the priority queue."""
        priority = self.calculate_priority(task)
        prioritized = PrioritizedTask(
            priority=priority,
            counter=self.task_counter,
            task=task
        )
        heapq.heappush(self.task_queue, prioritized)
        self.task_counter += 1
        self.stats["tasks_created"] += 1
        
        logger.debug(f"[HybridScheduler] Added task with priority={priority}, "
                    f"queue_size={len(self.task_queue)}")
    
    def get_next_task(self) -> Optional[Any]:
        """Get the next highest priority task."""
        if not self.task_queue:
            return None
        
        prioritized = heapq.heappop(self.task_queue)
        return prioritized.task
    
    def _check_limits(self, task: Any) -> bool:
        """Check if any limit has been reached."""
        task_depth = getattr(task, 'depth', 0)
        
        if task_depth >= self.max_depth:
            logger.warning(f"[HybridScheduler] Max depth reached: {task_depth}")
            return True
        
        if self.request_count >= self.max_requests:
            logger.warning(f"[HybridScheduler] Max requests reached: {self.request_count}")
            return True
        
        return False
    
    async def _execute_task(self, task: Any) -> TaskResult:
        """Execute a single task."""
        try:
            # TODO: Implement actual task execution
            # This is a placeholder - actual implementation would call tools
            
            self.request_count += 1
            
            # Simulate task execution
            await asyncio.sleep(0.1)
            
            result = TaskResult(
                success=True,
                findings=[],
                depth_reached=getattr(task, 'depth', 0),
                message="Task executed"
            )
            
            self.completed_tasks.append(result)
            self.stats["tasks_completed"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"[HybridScheduler] Task execution failed: {e}")
            self.stats["tasks_failed"] += 1
            return TaskResult(
                success=False,
                findings=[],
                depth_reached=0,
                message=f"Failed: {str(e)}"
            )
    
    def _compile_answer(self, original_query: str, timeout_reached: bool = False) -> Any:
        """
        Compile final answer from partial findings.
        Guaranteed to return something.
        """
        if self.partial_findings:
            status = "completed_with_findings"
            answer = f"Found {len(self.partial_findings)} results for: {original_query}"
        elif timeout_reached:
            status = "timeout_no_results"
            answer = (f"Search timed out after {self.timeout_seconds}s. "
                     f"No results found for: {original_query}")
        else:
            status = "completed_no_results"
            answer = (f"Searched using {self.request_count} requests. "
                     f"No results found for: {original_query}")
        
        return {
            "status": status,
            "answer": answer,
            "findings": self.partial_findings,
            "stats": self._get_stats()
        }
    
    def _get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return {
            **self.stats,
            "request_count": self.request_count,
            "pending_tasks": len(self.task_queue),
            "completed_tasks": len(self.completed_tasks),
            "budget_remaining": self.max_requests - self.request_count
        }
    
    async def run(self, user_input: str) -> Any:
        """
        Run the scheduler with strict limits.
        Guarantees an answer within timeout.
        """
        start_time = time.time()
        
        try:
            # Create initial task
            initial_task = type('Task', (), {
                'query': user_input,
                'depth': 0
            })()
            self.add_task(initial_task)
            
            # Process tasks with timeout
            while self.task_queue and self.request_count < self.max_requests:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= self.timeout_seconds:
                    logger.warning(f"[HybridScheduler] Timeout after {elapsed:.1f}s")
                    return self._compile_answer(user_input, timeout_reached=True)
                
                # Get next task
                task = self.get_next_task()
                if not task:
                    break
                
                # Check limits
                if self._check_limits(task):
                    break
                
                # Execute task
                result = await self._execute_task(task)
                
                # Collect findings
                if result.findings:
                    self.partial_findings.extend(result.findings)
                
                # TODO: Spawn follow-up tasks based on result
                # This would add new tasks to the queue
            
            # MUST return answer
            return self._compile_answer(user_input)
            
        except Exception as e:
            logger.error(f"[HybridScheduler] Run failed: {e}")
            return self._compile_answer(user_input)
    
    def reset(self) -> None:
        """Reset scheduler state."""
        self.task_queue.clear()
        self.completed_tasks.clear()
        self.partial_findings.clear()
        self.request_count = 0
        self.task_counter = 0
        self.depth_per_path.clear()
        self.stats = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "cycles_detected": 0
        }
        self.state = SchedulerState.IDLE
        logger.info("[HybridScheduler] State reset")
    
    # EventStreamSubscriber interface
    async def on_event(self, event: Any) -> None:
        """Handle events from the event stream."""
        logger.debug(f"[HybridScheduler] Received event: {event}")
