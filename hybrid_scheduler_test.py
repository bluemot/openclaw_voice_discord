"""
Standalone test of HybridScheduler
"""

import asyncio
import heapq
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# Mock classes for testing
class SchedulerState:
    IDLE = 'idle'
    EXPLORING = 'exploring'
    ANALYZING = 'analyzing'
    VERIFYING = 'verifying'
    COMPLETED = 'completed'


class EventStreamSubscriber:
    def __init__(self):
        pass


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
    """
    
    def __init__(
        self,
        agent: Any = None,
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
        self.state_history: List[tuple] = []
        
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
        
        print(f"[HybridScheduler] Initialized with max_depth={max_depth}, "
              f"max_requests={max_requests}, timeout={timeout_seconds}s")
    
    def calculate_priority(self, task: Any) -> float:
        """Calculate task priority (lower = higher priority)."""
        depth = getattr(task, 'depth', 0)
        depth_penalty = depth * 10.0
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
        print(f"[HybridScheduler] Added task with priority={priority}, queue_size={len(self.task_queue)}")
    
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
            print(f"[HybridScheduler] Max depth reached: {task_depth}")
            return True
        
        if self.request_count >= self.max_requests:
            print(f"[HybridScheduler] Max requests reached: {self.request_count}")
            return True
        
        return False
    
    async def _execute_task(self, task: Any) -> TaskResult:
        """Execute a single task."""
        try:
            self.request_count += 1
            
            # Simulate task execution
            await asyncio.sleep(0.5)
            
            # Simulate finding something
            findings = []
            if self.request_count == 2:
                findings = ["Found rtl8852bu_probe in driver.c:123"]
            
            result = TaskResult(
                success=True,
                findings=findings,
                depth_reached=getattr(task, 'depth', 0),
                message=f"Task executed (request #{self.request_count})"
            )
            
            self.completed_tasks.append(result)
            self.stats["tasks_completed"] += 1
            
            return result
            
        except Exception as e:
            print(f"[HybridScheduler] Task execution failed: {e}")
            self.stats["tasks_failed"] += 1
            return TaskResult(
                success=False,
                findings=[],
                depth_reached=0,
                message=f"Failed: {str(e)}"
            )
    
    def _compile_answer(self, original_query: str, timeout_reached: bool = False) -> Any:
        """Compile final answer from partial findings."""
        if self.partial_findings:
            status = "completed_with_findings"
            answer = f"Found {len(self.partial_findings)} results for: {original_query}\n"
            answer += "\n".join([f"  - {f}" for f in self.partial_findings])
        elif timeout_reached:
            status = "timeout_no_results"
            answer = f"Search timed out after {self.timeout_seconds}s. No results found for: {original_query}"
        else:
            status = "completed_no_results"
            answer = f"Searched using {self.request_count} requests. No results found for: {original_query}"
        
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
        """Run the scheduler with strict limits."""
        start_time = time.time()
        
        # Create initial task
        class Task:
            def __init__(self, query, depth):
                self.query = query
                self.depth = depth
        
        initial_task = Task(user_input, 0)
        self.add_task(initial_task)
        
        # Process tasks
        while self.task_queue and self.request_count < self.max_requests:
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed >= self.timeout_seconds:
                print(f"[HybridScheduler] Timeout after {elapsed:.1f}s")
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
            
            # Add follow-up tasks if found something
            if result.findings and task.depth < self.max_depth - 1:
                follow_up = Task(f"Follow-up for {task.query}", task.depth + 1)
                self.add_task(follow_up)
        
        # MUST return answer
        return self._compile_answer(user_input)


async def main():
    print("=" * 60)
    print("HybridScheduler Test")
    print("=" * 60)
    
    scheduler = HybridScheduler(
        agent=None,
        max_depth=3,
        max_requests=5,
        timeout_seconds=30
    )
    
    result = await scheduler.run('Find rtl8852bu_probe function location')
    
    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)
    print(f"Status: {result['status']}")
    print(f"Answer: {result['answer']}")
    print(f"Stats: {result['stats']}")


if __name__ == "__main__":
    asyncio.run(main())
