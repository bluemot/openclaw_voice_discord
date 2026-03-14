# codebase_rag/services/json_sanitizer.py
"""
JSON Sanitizer - Extract and Validate JSON from LLM Output

Handles common LLM output issues:
- Markdown code blocks (```json ... ```)
- Preambles like "Here is the result:"
- Extra whitespace
- Incomplete JSON

Created: 2026-03-14
Branch: trace-manager-architecture
"""

import re
import json
from typing import Optional, Any, Dict
from loguru import logger

from .trace_protocol import TraceResult, validate_trace_result


class JSONSanitizationError(Exception):
    """Raised when JSON cannot be extracted or validated."""
    pass


def extract_json(raw_output: str) -> str:
    """
    Extract JSON from raw LLM output.
    
    Handles:
    - Markdown code blocks
    - Preambles
    - Extra text after JSON
    
    Args:
        raw_output: Raw output from LLM
        
    Returns:
        Extracted JSON string
        
    Raises:
        JSONSanitizationError: If no valid JSON found
    """
    # Remove markdown code blocks
    output = raw_output.strip()
    
    # Remove ```json or ``` at start
    output = re.sub(r'^```(?:json)?\s*\n?', '', output)
    
    # Remove ``` at end
    output = re.sub(r'\n?```\s*$', '', output)
    
    # Remove common preambles
    preambles = [
        r'^Here is (?:the )?(?:result|output|JSON|response)[:：]?\s*\n',
        r'^Output:?\s*\n',
        r'^Result:?\s*\n',
        r'^```json\s*',
        r'^```\s*',
    ]
    
    for pattern in preambles:
        output = re.sub(pattern, '', output, flags=re.IGNORECASE)
    
    # Find JSON object (outermost braces)
    match = re.search(r'\{[\s\S]*\}', output)
    
    if match:
        return match.group(0)
    
    raise JSONSanitizationError("No valid JSON object found in output")


def sanitize_and_parse(
    raw_output: str,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Sanitize and parse JSON from LLM output.
    
    Args:
        raw_output: Raw output from LLM
        max_retries: Not used, kept for API compatibility
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        JSONSanitizationError: If parsing fails
    """
    try:
        # Extract JSON
        json_str = extract_json(raw_output)
        
        # Parse JSON
        data = json.loads(json_str)
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"[JSONSanitizer] JSON parse error: {e}")
        logger.debug(f"[JSONSanitizer] Raw output: {raw_output[:500]}")
        raise JSONSanitizationError(f"Failed to parse JSON: {e}")
        
    except JSONSanitizationError:
        raise


def validate_trace_result_json(
    raw_output: str,
    tracer_id: str,
    task_id: str
) -> TraceResult:
    """
    Full pipeline: extract, parse, validate TraceResult.
    
    Args:
        raw_output: Raw output from LLM
        tracer_id: Tracer identifier for defaults
        task_id: Task identifier for defaults
        
    Returns:
        Validated TraceResult
        
    Raises:
        JSONSanitizationError: If validation fails
    """
    try:
        # Extract and parse
        data = sanitize_and_parse(raw_output)
        
        # Ensure required fields
        if "tracer_id" not in data:
            data["tracer_id"] = tracer_id
        if "task_id" not in data:
            data["task_id"] = task_id
        if "status" not in data:
            data["status"] = "error"
        
        # Validate
        result = validate_trace_result(data)
        
        if result is None:
            raise JSONSanitizationError("TraceResult validation failed")
        
        return result
        
    except JSONSanitizationError:
        raise
    except Exception as e:
        raise JSONSanitizationError(f"Unexpected error: {e}")


def attempt_recovery(
    raw_output: str,
    error_message: str,
    recovery_prompt: str
) -> Optional[TraceResult]:
    """
    Attempt to recover from invalid JSON.
    
    This is a placeholder for potential future implementation
    where we could use a smaller model to fix JSON.
    
    Args:
        raw_output: Original invalid output
        error_message: The validation error
        recovery_prompt: Prompt to send for recovery
        
    Returns:
        Recovered TraceResult or None
    """
    # Try basic fixes
    fixes = [
        # Add missing closing braces
        lambda s: s + "}",
        lambda s: s + "}}",
        # Remove trailing commas
        lambda s: re.sub(r',\s*}', '}', s),
        lambda s: re.sub(r',\s*]', ']', s),
        # Fix single quotes
        lambda s: s.replace("'", '"'),
    ]
    
    json_str = None
    try:
        json_str = extract_json(raw_output)
    except JSONSanitizationError:
        return None
    
    for fix in fixes:
        try:
            fixed = fix(json_str)
            data = json.loads(fixed)
            result = validate_trace_result(data)
            if result:
                logger.info("[JSONSanitizer] Recovery successful")
                return result
        except:
            continue
    
    return None


# =============================================================================
# Utility Functions
# =============================================================================

def is_valid_json(text: str) -> bool:
    """Check if text is valid JSON."""
    try:
        json.loads(text)
        return True
    except:
        return False


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Safely parse JSON with default fallback.
    
    Args:
        text: JSON string
        default: Default value if parsing fails
        
    Returns:
        Parsed JSON or default
    """
    try:
        return json.loads(text)
    except:
        return default


def truncate_for_logging(text: str, max_length: int = 500) -> str:
    """Truncate text for logging."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "...[truncated]"