"""
Tests for trace_protocol.py

Tests validate that TraceResult and related models can be:
1. Parsed from JSON
2. Validated correctly
3. Serialized back to JSON
"""

import pytest
from trace_protocol import (
    TraceResult,
    TraceStatus,
    GraphEdge,
    UnexploredBranch,
    Finding,
    Task,
    Intent,
    TraceSummary,
    validate_trace_result,
    create_task_id
)


class TestGraphEdge:
    """Tests for GraphEdge model."""
    
    def test_basic_edge(self):
        """Test basic edge creation."""
        edge = GraphEdge(
            source="main",
            relation="CALLS",
            target="init_driver"
        )
        assert edge.source == "main"
        assert edge.relation == "CALLS"
        assert edge.target == "init_driver"
    
    def test_edge_serialization(self):
        """Test edge can be serialized to dict."""
        edge = GraphEdge(
            source="init_driver",
            relation="ALLOCATES",
            target="irq_struct"
        )
        data = edge.model_dump()
        assert data["source"] == "init_driver"
        assert data["relation"] == "ALLOCATES"


class TestUnexploredBranch:
    """Tests for UnexploredBranch model."""
    
    def test_basic_branch(self):
        """Test basic branch creation."""
        branch = UnexploredBranch(
            function="pci_alloc_irq",
            reason="External library call"
        )
        assert branch.function == "pci_alloc_irq"
        assert branch.location is None
    
    def test_branch_with_location(self):
        """Test branch with file location."""
        branch = UnexploredBranch(
            function="cudaMemcpy",
            reason="caller at line 45",
            location="driver.c:45",
            depth=2
        )
        assert branch.location == "driver.c:45"
        assert branch.depth == 2


class TestFinding:
    """Tests for Finding model."""
    
    def test_basic_finding(self):
        """Test basic finding creation."""
        finding = Finding(
            key="IRQ_TYPE",
            value="MSI-X"
        )
        assert finding.key == "IRQ_TYPE"
        assert finding.value == "MSI-X"
        assert finding.severity == "info"
    
    def test_finding_with_location(self):
        """Test finding with line number."""
        finding = Finding(
            key="MEMORY_POOL",
            value="GFP_ATOMIC",
            severity="warning",
            line=123,
            file="driver.c"
        )
        assert finding.severity == "warning"
        assert finding.line == 123


class TestTraceResult:
    """Tests for TraceResult model."""
    
    def test_done_status(self):
        """Test result with done status."""
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="task_001",
            status=TraceStatus.DONE,
            conclusion="Path traced successfully"
        )
        assert result.status == TraceStatus.DONE
        assert len(result.explored_graph) == 0
    
    def test_need_help_status(self):
        """Test result with need_help status."""
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="task_001",
            status=TraceStatus.NEED_HELP,
            unexplored_branches=[
                UnexploredBranch(function="caller_a", reason="branch at line 10"),
                UnexploredBranch(function="caller_b", reason="branch at line 20")
            ],
            conclusion="Found 2 branches"
        )
        assert result.status == TraceStatus.NEED_HELP
        assert len(result.unexplored_branches) == 2
    
    def test_with_explored_graph(self):
        """Test result with explored graph."""
        result = TraceResult(
            tracer_id="tracer_01",
            task_id="task_001",
            status=TraceStatus.DONE,
            explored_graph=[
                GraphEdge(source="main", relation="CALLS", target="init"),
                GraphEdge(source="init", relation="CALLS", target="driver")
            ]
        )
        assert len(result.explored_graph) == 2
        assert result.explored_graph[0].source == "main"
    
    def test_from_dict(self):
        """Test parsing from dictionary."""
        data = {
            "tracer_id": "tracer_01",
            "task_id": "task_001",
            "status": "done",
            "explored_graph": [
                {"source": "A", "relation": "CALLS", "target": "B"}
            ]
        }
        result = TraceResult(**data)
        assert result.status == TraceStatus.DONE
        assert result.explored_graph[0].source == "A"


class TestTask:
    """Tests for Task model."""
    
    def test_basic_task(self):
        """Test basic task creation."""
        task = Task(
            task_id="task_001",
            entry_point="main",
            direction="down"
        )
        assert task.depth == 0
        assert task.parent_task is None
    
    def test_task_with_depth(self):
        """Test task with depth."""
        task = Task(
            task_id="task_002",
            entry_point="init",
            direction="up",
            depth=3,
            parent_task="task_001"
        )
        assert task.depth == 3
        assert task.parent_task == "task_001"


class TestIntent:
    """Tests for Intent model."""
    
    def test_trace_callers_intent(self):
        """Test intent for trace_callers."""
        intent = Intent(
            type="trace_callers",
            target="cudaMemcpy"
        )
        assert intent.type == "trace_callers"
        assert intent.target == "cudaMemcpy"
        assert intent.strategy == "unidirectional"
    
    def test_trace_path_intent(self):
        """Test intent for trace_path with meet_in_the_middle."""
        intent = Intent(
            type="trace_path",
            source="main",
            target="gpu_malloc",
            strategy="meet_in_the_middle"
        )
        assert intent.strategy == "meet_in_the_middle"
        assert intent.source == "main"


class TestValidateTraceResult:
    """Tests for validate_trace_result utility."""
    
    def test_valid_result(self):
        """Test validation of valid result."""
        data = {
            "tracer_id": "tracer_01",
            "task_id": "task_001",
            "status": "done"
        }
        result = validate_trace_result(data)
        assert result is not None
        assert result.status == TraceStatus.DONE
    
    def test_invalid_result(self):
        """Test validation of invalid result."""
        data = {
            "tracer_id": "tracer_01",
            # missing task_id
            "status": "done"
        }
        result = validate_trace_result(data)
        assert result is None
    
    def test_invalid_status(self):
        """Test validation with invalid status."""
        data = {
            "tracer_id": "tracer_01",
            "task_id": "task_001",
            "status": "invalid_status"
        }
        result = validate_trace_result(data)
        assert result is None


class TestCreateTaskId:
    """Tests for create_task_id utility."""
    
    def test_unique_ids(self):
        """Test that different inputs produce different IDs."""
        id1 = create_task_id("task_001", "func_a")
        id2 = create_task_id("task_001", "func_b")
        assert id1 != id2
    
    def test_consistent_ids(self):
        """Test that same inputs produce same ID."""
        id1 = create_task_id("task_001", "func_a")
        id2 = create_task_id("task_001", "func_a")
        assert id1 == id2
    
    def test_id_format(self):
        """Test ID format."""
        task_id = create_task_id("task_001", "func_a")
        assert task_id.startswith("task_001_")
        assert len(task_id.split("_")[-1]) == 8  # 8 char hash


class TestTraceSummary:
    """Tests for TraceSummary model."""
    
    def test_empty_summary(self):
        """Test empty summary."""
        summary = TraceSummary()
        assert len(summary.nodes) == 0
        assert summary.paths_found == 0
    
    def test_summary_with_findings(self):
        """Test summary with findings."""
        summary = TraceSummary(
            nodes=["main", "init", "driver"],
            edges=[("main", "init"), ("init", "driver")],
            paths_found=1,
            all_findings=[
                Finding(key="IRQ_TYPE", value="MSI-X")
            ]
        )
        assert len(summary.nodes) == 3
        assert summary.paths_found == 1