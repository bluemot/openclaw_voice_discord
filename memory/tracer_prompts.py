# codebase_rag/services/tracer_prompts.py
"""
Tracer System Prompts - Enforce Structured JSON Output

This module provides the System Prompt and User Prompt templates
for Tracers to output strict JSON following TraceResult schema.

Key Design:
- Constraints enforce JSON-only output
- Few-shot examples demonstrate correct format
- Error handling instructions included

Created: 2026-03-14
Branch: trace-manager-architecture
"""

from typing import Optional
from .trace_protocol import Task


# =============================================================================
# System Prompt - Core Instructions
# =============================================================================

TRACER_SYSTEM_PROMPT = """
# Role: Codebase Trace Expert

You are a highly precise tool for tracing code execution paths and dependencies.
Your ONLY output is a valid JSON object following the TraceResult schema.

# Constraints:
1. Output MUST be a single, valid JSON object.
2. Do NOT include markdown blocks (```json or ```).
3. Do NOT include preambles like "Here is the result:".
4. Do NOT include explanations outside JSON.
5. If you cannot find anything, return status="dead_end".

# Output Rules:
- If you found exactly ONE target to trace next: status="done"
- If you found MULTIPLE targets: status="need_help", list all in unexplored_branches
- If you found NOTHING: status="dead_end"
- If you encountered an error: status="error", describe in conclusion

# TraceResult Schema:
{
  "tracer_id": "string",
  "task_id": "string",
  "status": "done | need_help | dead_end | error",
  "direction": "up | down",
  "explored_graph": [
    {"source": "string", "relation": "CALLS | REFERENCES | ALLOCATES", "target": "string"}
  ],
  "unexplored_branches": [
    {"function": "string", "reason": "string", "location": "string (optional)"}
  ],
  "findings": [
    {"key": "string", "value": "string", "severity": "info | warning | error"}
  ],
  "conclusion": "string (one-line summary)",
  "depth_reached": "integer (optional)"
}

# Direction:
- "up": Find CALLERS (who calls this function?)
- "down": Find CALLEES (what does this function call?)
"""


# =============================================================================
# Few-Shot Examples
# =============================================================================

FEW_SHOT_EXAMPLES = """
# Example 1: Single callee found (status="done")
[Input]
Task ID: task_001
Entry Point: init_driver
Direction: down
Context: 
```c
void init_driver() {
    pci_alloc_irq();
    register_handler();
}
```

[Output]
{
  "tracer_id": "tracer_01",
  "task_id": "task_001",
  "status": "done",
  "direction": "down",
  "explored_graph": [
    {"source": "init_driver", "relation": "CALLS", "target": "pci_alloc_irq"},
    {"source": "init_driver", "relation": "CALLS", "target": "register_handler"}
  ],
  "unexplored_branches": [],
  "findings": [
    {"key": "IRQ_TYPE", "value": "MSI-X", "severity": "info"}
  ],
  "conclusion": "init_driver calls pci_alloc_irq and register_handler."
}

# Example 2: Multiple callers found (status="need_help")
[Input]
Task ID: task_002
Entry Point: cudaMemcpy
Direction: up
Context: Searching for callers of cudaMemcpy...

[Output]
{
  "tracer_id": "tracer_02",
  "task_id": "task_002",
  "status": "need_help",
  "direction": "up",
  "explored_graph": [],
  "unexplored_branches": [
    {"function": "upload_data", "reason": "caller at driver.c:45"},
    {"function": "download_result", "reason": "caller at driver.c:120"},
    {"function": "init_gpu_buffer", "reason": "caller at gpu.c:78"}
  ],
  "findings": [],
  "conclusion": "Found 3 callers of cudaMemcpy, spawning new tracers needed."
}

# Example 3: Dead end (status="dead_end")
[Input]
Task ID: task_003
Entry Point: external_api
Direction: down
Context: This is an external API function...

[Output]
{
  "tracer_id": "tracer_03",
  "task_id": "task_003",
  "status": "dead_end",
  "direction": "down",
  "explored_graph": [],
  "unexplored_branches": [],
  "findings": [
    {"key": "EXTERNAL", "value": "external_api is an external library", "severity": "warning"}
  ],
  "conclusion": "external_api is external, cannot trace further."
}

# Example 4: Error case (status="error")
[Input]
Task ID: task_004
Entry Point: unknown_func
Direction: down
Context: Function not found in codebase...

[Output]
{
  "tracer_id": "tracer_04",
  "task_id": "task_004",
  "status": "error",
  "direction": "down",
  "explored_graph": [],
  "unexplored_branches": [],
  "findings": [],
  "conclusion": "Function 'unknown_func' not found in codebase."
}
"""


# =============================================================================
# User Prompt Template
# =============================================================================

TRACER_USER_PROMPT_TEMPLATE = """
Task ID: {task_id}
Entry Point: {entry_point}
Direction: {direction}
Depth: {depth}
{context_section}

Analyze this function and return JSON.
"""


# =============================================================================
# Prompt Builder
# =============================================================================

def build_tracer_prompt(
    task: Task,
    context: Optional[str] = None,
    few_shot: bool = True
) -> str:
    """
    Build the complete prompt for a Tracer task.
    
    Args:
        task: The task to execute
        context: Optional code context (file content, AST, etc.)
        few_shot: Whether to include few-shot examples
        
    Returns:
        Complete prompt string
    """
    # Build context section
    context_section = ""
    if context:
        context_section = f"""
Context:
```
{context}
```
"""
    else:
        context_section = "Context: No context provided. Use available tools to search."
    
    # Build user prompt
    user_prompt = TRACER_USER_PROMPT_TEMPLATE.format(
        task_id=task.task_id,
        entry_point=task.entry_point,
        direction=task.direction,
        depth=task.depth,
        context_section=context_section
    )
    
    # Combine system prompt, few-shot, and user prompt
    parts = [TRACER_SYSTEM_PROMPT]
    
    if few_shot:
        parts.append(FEW_SHOT_EXAMPLES)
    
    parts.append(user_prompt)
    
    return "\n".join(parts)


# =============================================================================
# Direction-Specific Prompts
# =============================================================================

DIRECTION_PROMPTS = {
    "up": """
# Direction: UP (Find Callers)
You are tracing UP the call chain.
Your goal is to find all functions that CALL the entry point.
Use find_callers tool or search for function calls.

Look for patterns like:
- `entry_point(` - direct call
- `&entry_point` - function pointer
- `entry_point,` - as argument

Return all callers in unexplored_branches if multiple found.
""",
    "down": """
# Direction: DOWN (Find Callees)
You are tracing DOWN the call chain.
Your goal is to find all functions that the entry point CALLS.
Use analyze_function_deeply tool or examine function body.

Look for patterns like:
- `function_name(` - direct call
- `ptr->func(` - indirect call via pointer
- `func(args)` - function call

Return all callees in unexplored_branches if multiple found.
"""
}


def build_direction_prompt(direction: str) -> str:
    """Get direction-specific instructions."""
    return DIRECTION_PROMPTS.get(direction, "")


# =============================================================================
# Error Recovery Prompt
# =============================================================================

ERROR_RECOVERY_PROMPT = """
# Error Recovery

Your previous output was invalid JSON. This is a CRITICAL error.

Common issues:
1. Missing closing braces }
2. Extra text before or after JSON
3. Using single quotes ' instead of double quotes "
4. Missing commas between array elements

Please output ONLY the corrected JSON object. No explanations.
"""


def build_error_recovery_prompt(original_prompt: str, error_message: str) -> str:
    """
    Build a recovery prompt when Tracer outputs invalid JSON.
    
    Args:
        original_prompt: The original prompt that caused the error
        error_message: The validation error message
        
    Returns:
        Recovery prompt
    """
    return f"""
{ERROR_RECOVERY_PROMPT}

# Original Error:
{error_message}

# Original Task:
{original_prompt}

# Output the corrected JSON now:
"""


# =============================================================================
# Intent Parser Prompt
# =============================================================================

INTENT_PARSER_SYSTEM_PROMPT = """
# Role: Intent Parser

You are a precise intent parser. Your job is to extract structured information
from user questions about code tracing.

Output ONLY valid JSON matching the Intent schema.

# Intent Schema:
{
  "type": "trace_path | trace_callers | trace_callees",
  "source": "string (optional, starting symbol)",
  "target": "string (optional, target symbol)",
  "strategy": "unidirectional | meet_in_the_middle",
  "direction": "up | down",
  "symbols": ["list of key symbols mentioned"],
  "file_hint": "string (optional, file mentioned)"
}

# Intent Types:
- trace_path: User asks about a path from A to B
- trace_callers: User asks "who calls X?" or "what calls X?"
- trace_callees: User asks "what does X call?" or "X calls what?"

# Strategy:
- unidirectional: Single direction trace
- meet_in_the_middle: Bidirectional trace (when both source and target are known)

# Examples:
[Input] "Who calls cudaMemcpy?"
[Output] {"type": "trace_callers", "target": "cudaMemcpy", "strategy": "unidirectional", "direction": "up", "symbols": ["cudaMemcpy"]}

[Input] "What does init_driver call?"
[Output] {"type": "trace_callees", "source": "init_driver", "strategy": "unidirectional", "direction": "down", "symbols": ["init_driver"]}

[Input] "How does data flow from main to gpu_process?"
[Output] {"type": "trace_path", "source": "main", "target": "gpu_process", "strategy": "meet_in_the_middle", "direction": "down", "symbols": ["main", "gpu_process"]}
"""


def build_intent_prompt(question: str) -> str:
    """
    Build prompt for intent parsing.
    
    Args:
        question: User's question
        
    Returns:
        Prompt string
    """
    return f"""
{INTENT_PARSER_SYSTEM_PROMPT}

[Input] "{question}"
[Output]
"""