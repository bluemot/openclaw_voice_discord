"""
Tests for trace_manager.py

Tests validate:
1. Priority Queue ordering
2. Cycle detection
3. Graph merging
4. Result processing
"""

import pytest
import asyncio
from trace_manager import TraceManager, PrioritizedTask
from trace_protocol import (
    Task,
    TraceResult,
    TraceStatus,
    GraphEdge,
    UnexploredBranch,
    Finding
)


class TestPriorityQueue:
    """Tests for Priority Queue functionality."""
    
    def test_empty_queue(self):
        """Test empty queue returns None."""
        manager = TraceManager()
        task = manager.get_next_task()
        assert task is None
    
    def test_priority_ordering(self):
        """Test that lower priority tasks come first."""
        manager = TraceManager()
        
        # Add tasks with different depths
        task1 = Task(task_id="t1", entry_point="main", direction="down", depth=0)
        task2 = Task(task_id="t2", entry_point="init", direction="down", depth=5)
        task3 = Task(task_id="t3", entry_point="driver", direction="down", depth=2)
        
        manager.add_task(task1)
        manager.add_task(task2)
        manager.add_task(task3)
        
        # Should get tasks in priority order (depth 0, 2, 5)
        first = manager.get_next_task()
        assert first.task_id == "t1"
        
        second = manager.get_next_task()
        assert second.task_id == "t3"
        
        third = manager.get_next_task()
        assert third.task_id == "t2"
    
    def test_priority_score(self):
        """Test priority calculation."""
        manager = TraceManager()
        
        # Depth 0 should have lower score (higher priority)
        task_shallow = Task(task_id="t1", entry_point="a", direction="down", depth=0)
        task_deep = Task(task_id="t2", entry_point="b", direction="down", depth=10)
        
        score_shallow = manager.calculate_priority(task_shallow)
        score_deep = manager.calculate_priority(task_deep)
        
        assert score_shallow < score_deep  # Lower score = higher priority


class TestCycleDetection:
    """Tests for cycle detection."""
    
    def test_path_cycle_detection(self):
        """Test cycle detection in path."""
        manager = TraceManager()
        
        path = ["A", "B", "C"]
        
        # D is not in path
        assert manager.is_cycle("D", path) is False
        
        # B is in path (cycle)
        assert manager.is_cycle("B", path) is True
    
    def test_node_deduplication(self):
        """Test node deduplication."""
        manager = TraceManager()
        
        # First visit
        assert manager.is_visited_node("A") is False
        
        # Mark as visited
        manager.visited_nodes.add("A")
        
        # Second visit
        assert manager.is_visited_node("A") is True
    
    def test_edge_deduplication(self):
        """Test edge deduplication."""
        manager = TraceManager()
        
        # First visit
        assert manager.is_visited_edge("A", "B") is False
        
        # Mark as visited
        manager.visited_edges.add(("A", "B"))
        
        # Second visit
        assert manager.is_visited_edge("A", "B") is True


class TestGraphMerging:
    """Tests for NetworkX graph merging."""
    
    def test_add_single_edge(self):
        """Test adding a single edge to graph."""
        manager = TraceManager()
        
        edge = GraphEdge(source="main", relation="CALLS", target="init")
        manager._add_edge_to_graph(edge)
        
        assert "main" in manager.visited_nodes
        assert "init" in manager.visited_nodes
        assert ("main", "init") in manager.visited_edges
        assert manager.graph.has_edge("main", "init")
    
    def test_multiple_edges(self):
        """Test adding multiple edges."""
        manager = TraceManager()
        
        edges = [
            GraphEdge(source="main", relation="CALLS", target="init"),
            GraphEdge(source="init", relation="CALLS", target="driver"),
            GraphEdge(source="driver", relation="CALLS", target="gpu_malloc"),
        ]
        
        for edge in edges:
            manager._add_edge_to_graph(edge)
        
        assert len(manager.visited_nodes) == 4
        assert len(manager.visited_edges) == 3
        assert manager.graph.has_path("main", "gpu_malloc")
    
    def test_merges_duplicate_edges(self):
        """Test that duplicate edges are merged."""
        manager = TraceManager()
        
        edge1 = GraphEdge(source="A", relation="CALLS", target="B")
        edge2 = GraphEdge(source="A", relation="CALLS", target="B")
        
        manager._add_edge_to_graph(edge1)
        manager._add_edge_to_graph(edge2)
        
        # Should only have one edge
        assert len(manager.visited_edges) == 1


class TestResultProcessing:
    """Tests for result processing."""
    
    @pytest.mark.asyncio
    async def test_process_done_result(self):
        """Test processing a successful result."""
        manager = TraceManager()
        
        # Add initial task
        task = Task(task_id="t1", entry_point="main", direction="down", depth=0)
        manager.add_task(task)
        
        # Create result
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.DONE,
            explored_graph=[
                GraphEdge(source="main", relation="CALLS", target="init")
            ],
            conclusion="Traced successfully"
        )
        
        await manager.process_result(result)
        
        assert len(manager.completed_results) == 1
        assert manager.stats["tasks_completed"] == 1
    
    @pytest.mark.asyncio
    async def test_process_need_help_result(self):
        """Test processing a result with multiple branches."""
        manager = TraceManager(max_depth=10)
        
        # Create result with unexplored branches
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.NEED_HELP,
            unexplored_branches=[
                UnexploredBranch(function="branch_a", reason="caller at line 10"),
                UnexploredBranch(function="branch_b", reason="caller at line 20"),
            ],
            depth_reached=1
        )
        
        # Set up path history
        manager.path_history["t1"] = ["main"]
        
        await manager.process_result(result)
        
        # Should spawn new tasks
        assert manager.stats["branches_spawned"] == 2
        assert len(manager.pending_queue) == 2
    
    @pytest.mark.asyncio
    async def test_cycle_prevents_spawn(self):
        """Test that cycles prevent task spawning."""
        manager = TraceManager(max_depth=10)
        
        # Create result that would create a cycle
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.NEED_HELP,
            unexplored_branches=[
                UnexploredBranch(function="main", reason="cycle back"),
            ],
            depth_reached=2
        )
        
        # Set up path history that includes "main"
        manager.path_history["t1"] = ["main", "init"]
        
        await manager.process_result(result)
        
        # Should NOT spawn new task (cycle detected)
        assert manager.stats["cycles_detected"] == 1
        assert len(manager.pending_queue) == 0
    
    @pytest.mark.asyncio
    async def test_max_depth_prevents_spawn(self):
        """Test that max depth prevents task spawning."""
        manager = TraceManager(max_depth=2)
        
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.NEED_HELP,
            unexplored_branches=[
                UnexploredBranch(function="deep_branch", reason="deep"),
            ],
            depth_reached=2  # Already at max
        )
        
        manager.path_history["t1"] = ["A", "B"]
        
        await manager.process_result(result)
        
        # Should NOT spawn new task (max depth)
        assert len(manager.pending_queue) == 0


class TestSummaryGeneration:
    """Tests for summary generation."""
    
    def test_empty_summary(self):
        """Test empty summary."""
        manager = TraceManager()
        summary = manager.get_summary()
        
        assert len(summary.nodes) == 0
        assert len(summary.edges) == 0
        assert summary.paths_found == 0
    
    @pytest.mark.asyncio
    async def test_summary_with_results(self):
        """Test summary with processed results."""
        manager = TraceManager()
        
        # Add some results
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.DONE,
            explored_graph=[
                GraphEdge(source="main", relation="CALLS", target="init"),
                GraphEdge(source="init", relation="CALLS", target="driver"),
            ],
            findings=[
                Finding(key="TYPE", value="GPU")
            ]
        )
        
        await manager.process_result(result)
        
        summary = manager.get_summary()
        
        assert len(summary.nodes) == 3
        assert len(summary.edges) == 2
        assert len(summary.all_findings) == 1
        assert summary.paths_found == 1
    
    def test_mermaid_generation(self):
        """Test Mermaid diagram generation."""
        manager = TraceManager()
        
        manager.visited_edges.add(("A", "B"))
        manager.visited_edges.add(("B", "C"))
        
        mermaid = manager._generate_mermaid()
        
        assert "graph TD" in mermaid
        assert "A --> B" in mermaid
        assert "B --> C" in mermaid


class TestStatistics:
    """Tests for statistics."""
    
    def test_initial_stats(self):
        """Test initial statistics."""
        manager = TraceManager()
        stats = manager.get_stats()
        
        assert stats["tasks_created"] == 0
        assert stats["tasks_completed"] == 0
        assert stats["pending_tasks"] == 0
    
    @pytest.mark.asyncio
    async def test_stats_after_processing(self):
        """Test statistics after processing."""
        manager = TraceManager()
        
        task = Task(task_id="t1", entry_point="main", direction="down")
        manager.add_task(task)
        
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.DONE
        )
        
        await manager.process_result(result)
        
        stats = manager.get_stats()
        
        assert stats["tasks_created"] == 1
        assert stats["tasks_completed"] == 1


class TestReset:
    """Tests for reset functionality."""
    
    @pytest.mark.asyncio
    async def test_reset_clears_state(self):
        """Test that reset clears all state."""
        manager = TraceManager()
        
        # Add some state
        manager.visited_nodes.add("A")
        manager.visited_edges.add(("A", "B"))
        manager.add_task(Task(task_id="t1", entry_point="main", direction="down"))
        
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.DONE
        )
        await manager.process_result(result)
        
        # Reset
        manager.reset()
        
        assert len(manager.visited_nodes) == 0
        assert len(manager.visited_edges) == 0
        assert len(manager.pending_queue) == 0
        assert len(manager.completed_results) == 0


class TestBudget:
    """Tests for budget management."""
    
    def test_budget_tracking(self):
        """Test budget tracking."""
        manager = TraceManager(max_requests=10)
        
        assert manager.request_count == 0
        assert manager.get_stats()["budget_remaining"] == 10
    
    @pytest.mark.asyncio
    async def test_budget_exhausted(self):
        """Test that budget exhaustion prevents task spawning."""
        manager = TraceManager(max_requests=1)
        
        # First task
        task1 = Task(task_id="t1", entry_point="main", direction="down")
        manager.add_task(task1)
        
        result1 = TraceResult(
            tracer_id="tracer_01",
            task_id="t1",
            status=TraceStatus.DONE
        )
        await manager.process_result(result1)
        
        assert manager.request_count == 1
        
        # Try to add another task (should work since we check budget in _process_branch)
        # But if we manually call is_complete, it should show exhausted
        assert manager.is_complete() is True