"""
Tests for tracer_prompts.py and json_sanitizer.py
"""

import pytest
from codebase_rag.services.trace_protocol import Task
from codebase_rag.services.tracer_prompts import (
    build_tracer_prompt,
    build_direction_prompt,
    build_error_recovery_prompt,
    build_intent_prompt,
    TRACER_SYSTEM_PROMPT,
    FEW_SHOT_EXAMPLES
)
from codebase_rag.services.json_sanitizer import (
    extract_json,
    sanitize_and_parse,
    validate_trace_result_json,
    is_valid_json,
    JSONSanitizationError
)


class TestTracerPrompts:
    """Tests for tracer prompt building."""
    
    def test_system_prompt_contains_constraints(self):
        """Test that system prompt contains necessary constraints."""
        assert "JSON" in TRACER_SYSTEM_PROMPT
        assert "TraceResult" in TRACER_SYSTEM_PROMPT
        assert "status" in TRACER_SYSTEM_PROMPT
        assert "explored_graph" in TRACER_SYSTEM_PROMPT
    
    def test_few_shot_examples_contain_all_statuses(self):
        """Test that few-shot examples cover all status types."""
        assert '"status": "done"' in FEW_SHOT_EXAMPLES
        assert '"status": "need_help"' in FEW_SHOT_EXAMPLES
        assert '"status": "dead_end"' in FEW_SHOT_EXAMPLES
        assert '"status": "error"' in FEW_SHOT_EXAMPLES
    
    def test_build_tracer_prompt_basic(self):
        """Test basic prompt building."""
        task = Task(
            task_id="task_001",
            entry_point="main",
            direction="down"
        )
        
        prompt = build_tracer_prompt(task)
        
        assert "task_001" in prompt
        assert "main" in prompt
        assert "down" in prompt
    
    def test_build_tracer_prompt_with_context(self):
        """Test prompt building with context."""
        task = Task(
            task_id="task_002",
            entry_point="init",
            direction="up",
            context="void init() { setup(); }"
        )
        
        prompt = build_tracer_prompt(task)
        
        assert "void init() { setup(); }" in prompt
        assert "up" in prompt
    
    def test_build_tracer_prompt_without_few_shot(self):
        """Test prompt building without few-shot examples."""
        task = Task(
            task_id="task_003",
            entry_point="test",
            direction="down"
        )
        
        prompt = build_tracer_prompt(task, few_shot=False)
        
        assert "Example 1" not in prompt
        assert "task_003" in prompt
    
    def test_build_direction_prompt_up(self):
        """Test direction prompt for 'up'."""
        prompt = build_direction_prompt("up")
        
        assert "CALLERS" in prompt
        assert "find_callers" in prompt
    
    def test_build_direction_prompt_down(self):
        """Test direction prompt for 'down'."""
        prompt = build_direction_prompt("down")
        
        assert "CALLEES" in prompt
        assert "analyze_function_deeply" in prompt
    
    def test_build_error_recovery_prompt(self):
        """Test error recovery prompt."""
        original = "Task: test"
        error = "Missing closing brace"
        
        prompt = build_error_recovery_prompt(original, error)
        
        assert "Error Recovery" in prompt
        assert "Missing closing brace" in prompt
    
    def test_build_intent_prompt(self):
        """Test intent prompt building."""
        prompt = build_intent_prompt("Who calls cudaMemcpy?")
        
        assert "Intent Parser" in prompt
        assert "Who calls cudaMemcpy?" in prompt


class TestJSONSanitizer:
    """Tests for JSON sanitization."""
    
    def test_extract_json_pure_json(self):
        """Test extraction of pure JSON."""
        raw = '{"tracer_id": "t1", "task_id": "task1", "status": "done"}'
        
        result = extract_json(raw)
        
        assert result == raw
    
    def test_extract_json_with_markdown(self):
        """Test extraction from markdown code block."""
        raw = '```json\n{"tracer_id": "t1", "status": "done"}\n```'
        
        result = extract_json(raw)
        
        assert result == '{"tracer_id": "t1", "status": "done"}'
    
    def test_extract_json_with_preamble(self):
        """Test extraction with preamble."""
        raw = 'Here is the result:\n{"tracer_id": "t1", "status": "done"}'
        
        result = extract_json(raw)
        
        assert result == '{"tracer_id": "t1", "status": "done"}'
    
    def test_extract_json_with_extra_text(self):
        """Test extraction with extra text after."""
        raw = '{"tracer_id": "t1"} some extra text'
        
        result = extract_json(raw)
        
        assert result == '{"tracer_id": "t1"}'
    
    def test_extract_json_no_json_raises(self):
        """Test that no JSON raises error."""
        raw = "This is just plain text"
        
        with pytest.raises(JSONSanitizationError):
            extract_json(raw)
    
    def test_sanitize_and_parse_valid(self):
        """Test parsing valid JSON."""
        raw = '{"tracer_id": "t1", "task_id": "task1", "status": "done"}'
        
        result = sanitize_and_parse(raw)
        
        assert result["tracer_id"] == "t1"
        assert result["status"] == "done"
    
    def test_sanitize_and_parse_with_markdown(self):
        """Test parsing JSON from markdown."""
        raw = '```json\n{"tracer_id": "t1", "task_id": "task1", "status": "done"}\n```'
        
        result = sanitize_and_parse(raw)
        
        assert result["tracer_id"] == "t1"
    
    def test_validate_trace_result_json_valid(self):
        """Test validation of valid TraceResult."""
        raw = '''
        {
            "tracer_id": "tracer_01",
            "task_id": "task_001",
            "status": "done",
            "explored_graph": [],
            "unexplored_branches": [],
            "findings": [],
            "conclusion": "Success"
        }
        '''
        
        result = validate_trace_result_json(raw, "tracer_01", "task_001")
        
        assert result.tracer_id == "tracer_01"
        assert result.status.value == "done"
    
    def test_validate_trace_result_json_missing_fields(self):
        """Test validation fills missing fields."""
        raw = '{"status": "done"}'
        
        result = validate_trace_result_json(raw, "default_tracer", "default_task")
        
        assert result.tracer_id == "default_tracer"
        assert result.task_id == "default_task"
    
    def test_validate_trace_result_json_invalid_status(self):
        """Test validation with invalid status."""
        raw = '{"tracer_id": "t1", "task_id": "task1", "status": "invalid"}'
        
        with pytest.raises(JSONSanitizationError):
            validate_trace_result_json(raw, "t1", "task1")
    
    def test_is_valid_json_true(self):
        """Test JSON validation for valid JSON."""
        assert is_valid_json('{"key": "value"}') is True
        assert is_valid_json('[1, 2, 3]') is True
    
    def test_is_valid_json_false(self):
        """Test JSON validation for invalid JSON."""
        assert is_valid_json('not json') is False
        assert is_valid_json('{key: value}') is False  # missing quotes


class TestTraceResultEdgeCases:
    """Tests for edge cases in TraceResult parsing."""
    
    def test_empty_explored_graph(self):
        """Test parsing with empty explored_graph."""
        raw = '''
        {
            "tracer_id": "t1",
            "task_id": "task1",
            "status": "done",
            "explored_graph": [],
            "conclusion": "No edges found"
        }
        '''
        
        result = validate_trace_result_json(raw, "t1", "task1")
        
        assert len(result.explored_graph) == 0
    
    def test_nested_json_in_findings(self):
        """Test parsing with nested structures."""
        raw = '''
        {
            "tracer_id": "t1",
            "task_id": "task1",
            "status": "done",
            "findings": [
                {"key": "TYPE", "value": "GPU", "severity": "info"},
                {"key": "LOC", "value": "123", "severity": "warning"}
            ]
        }
        '''
        
        result = validate_trace_result_json(raw, "t1", "task1")
        
        assert len(result.findings) == 2
        assert result.findings[0].key == "TYPE"
    
    def test_unicode_in_conclusion(self):
        """Test parsing with unicode characters."""
        raw = '''
        {
            "tracer_id": "t1",
            "task_id": "task1",
            "status": "done",
            "conclusion": "Found 路徑 → 終點"
        }
        '''
        
        result = validate_trace_result_json(raw, "t1", "task1")
        
        assert "路徑" in result.conclusion