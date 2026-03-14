# codebase_rag/services/trace_manager.py
"""
Trace Manager - Core Engine for Multi-Agent Code Tracing

This module implements the central coordinator for the Structured Output Protocol:
- Maintains NetworkX graph for explored nodes/edges
- Priority Queue for task scheduling
- Cycle detection for deduplication
- Result processing and graph merging

Architecture:
- Manager receives JSON from Tracers (zero token cost)
- Manager coordinates multiple tracers
- Manager outputs final summary (Mermaid diagram + text)

Created: 2026-03-14
Branch: trace-manager-architecture
"""

import asyncio
import heapq
import networkx as nx
from typing import Set, List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

from .trace_protocol import (
    Task,
    TraceResult,
    TraceStatus,
    TraceSummary,
    Intent,
    GraphEdge,
    UnexploredBranch
)


@dataclass(order=True)
class PrioritizedTask:
    """Wrapper for priority queue items."""
    priority: float
    counter: int  # Tie-breaker for same priority
    task: Task = field(compare=False)


class TraceManager:
    """
    Central coordinator for multi-agent code tracing.
    
    Responsibilities:
    1. Maintain NetworkX graph of explored code
    2. Schedule tasks via Priority Queue
    3. Detect cycles and deduplicate nodes
    4. Process Tracer results and merge into graph
    5. Generate final summary
    
    Usage:
        manager = TraceManager(max_concurrent=5, max_depth=15)
        manager.add_task(Task(entry_point="main", direction="down"))
        
        while not manager.is_complete():
            task = manager.get_next_task()
            result = await run_tracer(task)
            await manager.process_result(result)
        
        summary = manager.get_summary()
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        max_depth: int = 15,
        max_requests: int = 50
    ):
        """
        Initialize Trace Manager.
        
        Args:
            max_concurrent: Maximum number of concurrent tracers
            max_depth: Maximum trace depth
            max_requests: Maximum total API requests (budget)
        """
        # NetworkX Graph (runtime, in-memory)
        self.graph = nx.DiGraph()
        
        # Deduplication sets
        self.visited_nodes: Set[str] = set()
        self.visited_edges: Set[Tuple[str, str]] = set()
        
        # Priority Queue (heapq-based)
        self.pending_queue: List[PrioritizedTask] = []
        self.task_counter = 0
        
        # Completed results
        self.completed_results: List[TraceResult] = []
        
        # Concurrency control
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Limits
        self.max_depth = max_depth
        self.max_requests = max_requests
        self.request_count = 0
        
        # Path tracking for cycle detection
        self.path_history: Dict[str, List[str]] = {}  # task_id -> path
        
        # Statistics
        self.stats = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "cycles_detected": 0,
            "branches_spawned": 0
        }
    
    # =========================================================================
    # Priority Queue Management
    # =========================================================================
    
    def calculate_priority(self, task: Task) -> float:
        """
        Calculate priority score for a task.
        
        Lower score = higher priority.
        
        Factors:
        - Depth penalty: deeper tasks are lower priority
        - (Future: keyword bonus for semantic relevance)
        
        Args:
            task: Task to prioritize
            
        Returns:
            Priority score (lower = higher priority)
        """
        depth_penalty = task.depth * 5.0
        
        # TODO: Add keyword bonus for semantic relevance
        # keyword_bonus = self._calculate_keyword_bonus(task)
        
        return depth_penalty
    
    def add_task(self, task: Task, parent_path: Optional[List[str]] = None) -> None:
        """
        Add a task to the priority queue.
        
        Args:
            task: Task to add
            parent_path: Path history for cycle detection
        """
        priority = self.calculate_priority(task)
        prioritized = PrioritizedTask(
            priority=priority,
            counter=self.task_counter,
            task=task
        )
        heapq.heappush(self.pending_queue, prioritized)
        self.task_counter += 1
        self.stats["tasks_created"] += 1
        
        # Store path history
        if parent_path:
            self.path_history[task.task_id] = parent_path + [task.entry_point]
        else:
            self.path_history[task.task_id] = [task.entry_point]
        
        logger.debug(f"[TraceManager] Added task {task.task_id}: {task.entry_point} (priority={priority})")
    
    def get_next_task(self) -> Optional[Task]:
        """
        Get the next highest priority task.
        
        Returns:
            Next task or None if queue is empty
        """
        if not self.pending_queue:
            return None
        
        prioritized = heapq.heappop(self.pending_queue)
        return prioritized.task
    
    def is_complete(self) -> bool:
        """
        Check if tracing is complete.
        
        Returns:
            True if no more tasks or budget exhausted
        """
        return len(self.pending_queue) == 0 or self.request_count >= self.max_requests
    
    # =========================================================================
    # Cycle Detection
    # =========================================================================
    
    def is_cycle(self, node: str, path: List[str]) -> bool:
        """
        Check if adding node to path creates a cycle.
        
        This is path-based cycle detection (prevents infinite loops).
        
        Args:
            node: Node to check
            path: Current path (list of nodes)
            
        Returns:
            True if cycle detected
        """
        return node in path
    
    def is_visited_node(self, node: str) -> bool:
        """
        Check if node has been visited before (deduplication).
        
        This is node-based deduplication (avoids redundant work).
        
        Args:
            node: Node to check
            
        Returns:
            True if node already visited
        """
        return node in self.visited_nodes
    
    def is_visited_edge(self, source: str, target: str) -> bool:
        """
        Check if edge has been visited before.
        
        Args:
            source: Source node
            target: Target node
            
        Returns:
            True if edge already visited
        """
        return (source, target) in self.visited_edges
    
    # =========================================================================
    # Result Processing
    # =========================================================================
    
    async def process_result(self, result: TraceResult) -> None:
        """
        Process a Tracer result: sync to graph, dedupe, queue new tasks.
        
        This is the core method that handles Structured Output Protocol.
        
        Args:
            result: TraceResult from Tracer
        """
        self.stats["tasks_completed"] += 1
        
        # Get path history for cycle detection
        current_path = self.path_history.get(result.task_id, [])
        
        # 1. Sync explored edges to NetworkX
        for edge in result.explored_graph:
            self._add_edge_to_graph(edge)
        
        # 2. Process unexplored branches
        for branch in result.unexplored_branches:
            self._process_branch(branch, result, current_path)
        
        # 3. Store result
        self.completed_results.append(result)
        
        # 4. Update statistics
        self.request_count += 1
        
        logger.info(
            f"[TraceManager] Processed result {result.task_id}: "
            f"status={result.status.value}, "
            f"edges={len(result.explored_graph)}, "
            f"branches={len(result.unexplored_branches)}"
        )
    
    def _add_edge_to_graph(self, edge: GraphEdge) -> None:
        """Add edge to NetworkX graph and mark as visited."""
        self.graph.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation
        )
        self.visited_nodes.add(edge.source)
        self.visited_nodes.add(edge.target)
        self.visited_edges.add((edge.source, edge.target))
    
    def _process_branch(
        self,
        branch: UnexploredBranch,
        result: TraceResult,
        current_path: List[str]
    ) -> None:
        """
        Process an unexplored branch: check cycles, create new tasks.
        
        Args:
            branch: Branch to process
            result: Parent result
            current_path: Current path for cycle detection
        """
        # Check if already visited (deduplication)
        if self.is_visited_node(branch.function):
            logger.debug(f"[TraceManager] Skipping visited node: {branch.function}")
            return
        
        # Check for cycles (path-based)
        if self.is_cycle(branch.function, current_path):
            self.stats["cycles_detected"] += 1
            logger.debug(f"[TraceManager] Cycle detected: {branch.function}")
            return
        
        # Check depth limit
        new_depth = result.depth_reached if result.depth_reached else len(current_path)
        if new_depth + 1 >= self.max_depth:
            logger.debug(f"[TraceManager] Max depth reached, skipping: {branch.function}")
            return
        
        # Check budget
        if self.request_count >= self.max_requests:
            logger.debug(f"[TraceManager] Budget exhausted, skipping: {branch.function}")
            return
        
        # Create new task
        new_task = Task(
            task_id=f"{result.task_id}_{branch.function}",
            entry_point=branch.function,
            direction=result.direction,
            depth=new_depth + 1,
            parent_task=result.task_id
        )
        
        self.add_task(new_task, parent_path=current_path)
        self.stats["branches_spawned"] += 1
    
    # =========================================================================
    # Summary Generation
    # =========================================================================
    
    def get_summary(self) -> TraceSummary:
        """
        Generate final summary after all tasks complete.
        
        Returns:
            TraceSummary with graph and findings
        """
        # Collect all nodes and edges
        nodes = list(self.visited_nodes)
        edges = [(e[0], e[1]) for e in self.visited_edges]
        
        # Collect all findings
        all_findings = []
        for result in self.completed_results:
            all_findings.extend(result.findings)
        
        # Collect gaps (dead ends)
        gaps = [
            result.task_id
            for result in self.completed_results
            if result.status == TraceStatus.DEAD_END
        ]
        
        # Generate Mermaid diagram
        mermaid_diagram = self._generate_mermaid()
        
        return TraceSummary(
            nodes=nodes,
            edges=edges,
            paths_found=len(self.completed_results),
            total_depth=max(
                (r.depth_reached or 0) for r in self.completed_results
            ) if self.completed_results else 0,
            all_findings=all_findings,
            gaps=gaps,
            mermaid_diagram=mermaid_diagram
        )
    
    def _generate_mermaid(self) -> str:
        """Generate Mermaid.js graph definition."""
        lines = ["graph TD"]
        
        for edge in self.visited_edges:
            source, target = edge
            lines.append(f"    {source} --> {target}")
        
        return "\n".join(lines)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tracing progress."""
        return {
            **self.stats,
            "pending_tasks": len(self.pending_queue),
            "completed_tasks": len(self.completed_results),
            "visited_nodes": len(self.visited_nodes),
            "visited_edges": len(self.visited_edges),
            "request_count": self.request_count,
            "budget_remaining": self.max_requests - self.request_count
        }
    
    def reset(self) -> None:
        """Reset manager state for new trace."""
        self.graph.clear()
        self.visited_nodes.clear()
        self.visited_edges.clear()
        self.pending_queue.clear()
        self.completed_results.clear()
        self.path_history.clear()
        self.task_counter = 0
        self.request_count = 0
        self.stats = {
            "tasks_created": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "cycles_detected": 0,
            "branches_spawned": 0
        }
        logger.info("[TraceManager] State reset for new trace")
    
    # =========================================================================
    # Context Manager Support
    # =========================================================================
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Could add cleanup here
        pass