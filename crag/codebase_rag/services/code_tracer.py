# codebase_rag/services/code_tracer.py
"""
CodeTracer Agent - Single-direction code path tracer

This module implements the Tracer (LLM) that:
- Traces code paths in a single direction (up or down)
- Uses tools to find callers/callees
- Returns structured JSON (TraceResult)

Architecture:
- Tracer is disposable (stateless)
- Output is always TraceResult schema
- Managed by Trace Manager

Created: 2026-03-14
"""

import asyncio
import json
import re
from typing import Optional, List, Dict, Any
from loguru import logger

from .trace_protocol import (
    Task,
    TraceResult,
    TraceStatus,
    GraphEdge,
    UnexploredBranch,
    Finding
)
from .tracer_prompts import build_tracer_prompt, build_direction_prompt
from .json_sanitizer import validate_trace_result_json


# =============================================================================
# Tracer Configuration
# =============================================================================

TRACER_CONFIG = {
    "max_retries": 3,
    "timeout_seconds": 60,
    "max_context_chars": 4000,
    "max_branches": 10,
}


# =============================================================================
# CodeTracer Class
# =============================================================================

class CodeTracer:
    """
    Single-direction code path tracer.
    
    A Tracer is:
    - Stateless (no session persistence)
    - Direction-aware (up = callers, down = callees)
    - JSON-output only (no prose)
    
    Usage:
        tracer = CodeTracer(tools_provider=tools)
        result = await tracer.trace(task)
        
    The result is always a TraceResult:
    - status: done | need_help | dead_end | error
    - explored_graph: edges discovered
    - unexplored_branches: branches needing other tracers
    """
    
    def __init__(
        self,
        tools_provider=None,
        llm_client=None,
        model: str = "gpt-4o-mini",
        config: dict = None
    ):
        """
        Initialize CodeTracer.
        
        Args:
            tools_provider: Provider for code tools (hound, search, etc.)
            llm_client: LLM client for generation
            model: Model to use
            config: Configuration overrides
        """
        self.tools_provider = tools_provider
        self.llm_client = llm_client
        self.model = model
        self.config = {**TRACER_CONFIG, **(config or {})}
        
        # Unique tracer ID
        self.tracer_id = f"tracer_{id(self)}"
    
    async def trace(self, task: Task, context: str = None) -> TraceResult:
        """
        Execute a trace task.
        
        This is the main entry point for tracing.
        
        Args:
            task: Task to execute
            context: Optional code context (file content, AST, etc.)
            
        Returns:
            TraceResult with status, explored_graph, unexplored_branches
        """
        logger.info(f"[CodeTracer] Starting trace: {task.entry_point} (direction={task.direction})")
        
        # Try tools-based tracing first
        result = await self._trace_with_tools(task, context)
        
        # If tools found results, return them
        if result and result.status != TraceStatus.ERROR:
            logger.info(f"[CodeTracer] Tools result: {result.status.value}")
            return result
        
        # Fall back to LLM-based tracing
        if self.llm_client:
            result = await self._trace_with_llm(task, context)
            logger.info(f"[CodeTracer] LLM result: {result.status.value}")
            return result
        
        # No tools and no LLM - return error
        return TraceResult(
            tracer_id=self.tracer_id,
            task_id=task.task_id,
            status=TraceStatus.ERROR,
            conclusion="No tools or LLM available for tracing"
        )
    
    async def _trace_with_tools(self, task: Task, context: str = None) -> Optional[TraceResult]:
        """
        Trace using code tools (non-LLM approach).
        
        Uses:
        - find_callers (for up direction)
        - analyze_function_deeply (for down direction)
        - hound_fast_search (for definitions)
        
        Args:
            task: Task to execute
            context: Optional context
            
        Returns:
            TraceResult or None if tools not available
        """
        if not self.tools_provider:
            return None
        
        try:
            explored_graph = []
            unexplored_branches = []
            findings = []
            
            if task.direction == "up":
                # Find callers
                callers = await self._find_callers(task.entry_point)
                
                if callers:
                    for caller in callers:
                        explored_graph.append(GraphEdge(
                            source=caller["name"],
                            relation="CALLS",
                            target=task.entry_point
                        ))
                        
                        # Add as unexplored branch
                        unexplored_branches.append(UnexploredBranch(
                            function=caller["name"],
                            reason="caller found",
                            location=caller.get("file"),
                            depth=task.depth + 1
                        ))
                    
                    findings.append(Finding(
                        key="CALLERS_COUNT",
                        value=str(len(callers)),
                        severity="info"
                    ))
                else:
                    findings.append(Finding(
                        key="NO_CALLERS",
                        value="No callers found",
                        severity="warning"
                    ))
            
            elif task.direction == "down":
                # Find callees
                callees = await self._find_callees(task.entry_point)
                
                if callees:
                    for callee in callees:
                        explored_graph.append(GraphEdge(
                            source=task.entry_point,
                            relation="CALLS",
                            target=callee["name"]
                        ))
                        
                        # Add as unexplored branch
                        unexplored_branches.append(UnexploredBranch(
                            function=callee["name"],
                            reason="callee found",
                            location=callee.get("file"),
                            depth=task.depth + 1
                        ))
                    
                    findings.append(Finding(
                        key="CALLEES_COUNT",
                        value=str(len(callees)),
                        severity="info"
                    ))
                else:
                    findings.append(Finding(
                        key="NO_CALLEES",
                        value="No callees found",
                        severity="warning"
                    ))
            
            # Determine status
            if len(unexplored_branches) > self.config["max_branches"]:
                # Too many branches - need help
                status = TraceStatus.NEED_HELP
            elif len(unexplored_branches) > 0:
                status = TraceStatus.NEED_HELP
            elif len(explored_graph) > 0:
                status = TraceStatus.DONE
            else:
                status = TraceStatus.DEAD_END
            
            return TraceResult(
                tracer_id=self.tracer_id,
                task_id=task.task_id,
                status=status,
                direction=task.direction,
                explored_graph=explored_graph,
                unexplored_branches=unexplored_branches,
                findings=findings,
                conclusion=f"Found {len(explored_graph)} edges via tools",
                depth_reached=task.depth
            )
            
        except Exception as e:
            logger.error(f"[CodeTracer] Tools trace failed: {e}")
            return TraceResult(
                tracer_id=self.tracer_id,
                task_id=task.task_id,
                status=TraceStatus.ERROR,
                conclusion=f"Tools error: {str(e)}"
            )
    
    async def _find_callers(self, func_name: str) -> List[Dict]:
        """
        Find callers of a function (up direction).
        
        Args:
            func_name: Function name
            
        Returns:
            List of caller dicts with name, file, line
        """
        # This would call the tools_provider's find_callers
        # For now, return empty - will be integrated with hound_tools
        return []
    
    async def _find_callees(self, func_name: str) -> List[Dict]:
        """
        Find callees of a function (down direction).
        
        Args:
            func_name: Function name
            
        Returns:
            List of callee dicts with name, file, line
        """
        # This would call the tools_provider's analyze_function_deeply
        # For now, return empty - will be integrated with hound_tools
        return []
    
    async def _trace_with_llm(self, task: Task, context: str = None) -> TraceResult:
        """
        Trace using LLM (fallback approach).
        
        Uses structured output to ensure JSON response.
        
        Args:
            task: Task to execute
            context: Optional context
            
        Returns:
            TraceResult
        """
        try:
            # Build prompt
            prompt = build_tracer_prompt(task, context=context)
            direction_prompt = build_direction_prompt(task.direction)
            
            full_prompt = f"{prompt}\n\n{direction_prompt}"
            
            # Call LLM
            response = await self._call_llm(full_prompt)
            
            # Parse response
            result = validate_trace_result_json(
                response,
                self.tracer_id,
                task.task_id
            )
            
            # Ensure direction is set
            result.direction = task.direction
            
            return result
            
        except Exception as e:
            logger.error(f"[CodeTracer] LLM trace failed: {e}")
            return TraceResult(
                tracer_id=self.tracer_id,
                task_id=task.task_id,
                status=TraceStatus.ERROR,
                conclusion=f"LLM error: {str(e)}"
            )
    
    async def _call_llm(self, prompt: str) -> str:
        """
        Call LLM with prompt.
        
        Args:
            prompt: Full prompt
            
        Returns:
            Raw LLM response
        """
        if not self.llm_client:
            raise ValueError("No LLM client available")
        
        # Handle different LLM client interfaces
        if hasattr(self.llm_client, "chat"):
            response = self.llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a code tracing expert. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            # Extract content
            if isinstance(response, dict):
                return response.get("content", "") or response.get("message", {}).get("content", "")
            return str(response)
        
        elif hasattr(self.llm_client, "complete"):
            response = self.llm_client.complete(
                model=self.model,
                prompt=prompt,
                temperature=0.0
            )
            if isinstance(response, dict):
                return response.get("text", "") or response.get("content", "")
            return str(response)
        
        else:
            raise ValueError(f"Unsupported LLM client: {type(self.llm_client)}")


# =============================================================================
# Tracer Factory
# =============================================================================

def create_tracer(
    tools_provider=None,
    llm_client=None,
    model: str = "gpt-4o-mini",
    config: dict = None
) -> CodeTracer:
    """
    Factory function to create a CodeTracer.
    
    Args:
        tools_provider: Provider for code tools
        llm_client: LLM client
        model: Model to use
        config: Configuration overrides
        
    Returns:
        CodeTracer instance
    """
    return CodeTracer(
        tools_provider=tools_provider,
        llm_client=llm_client,
        model=model,
        config=config
    )


# =============================================================================
# Sync Wrapper
# =============================================================================

def trace_sync(
    task: Task,
    tools_provider=None,
    llm_client=None,
    context: str = None
) -> TraceResult:
    """
    Synchronous wrapper for trace.
    
    Args:
        task: Task to execute
        tools_provider: Provider for code tools
        llm_client: LLM client
        context: Optional context
        
    Returns:
        TraceResult
    """
    tracer = CodeTracer(tools_provider=tools_provider, llm_client=llm_client)
    
    # Run async trace in event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(tracer.trace(task, context))


# =============================================================================
# Integration with Hound Tools
# =============================================================================

class HoundTracerAdapter:
    """
    Adapter to use Hound tools with CodeTracer.
    
    This class wraps the hound_tools to work with CodeTracer's
    tools_provider interface.
    """
    
    def __init__(self, hound_tools: list):
        """
        Initialize adapter with hound tools.
        
        Args:
            hound_tools: List of Tool objects from create_hound_tools
        """
        self.tools = {tool.name: tool for tool in hound_tools}
    
    async def find_callers(self, func_name: str, file_pattern: str = "*.[ch]") -> List[Dict]:
        """
        Find callers using hound_tools.
        
        Args:
            func_name: Function name
            file_pattern: File pattern to search
            
        Returns:
            List of caller dicts
        """
        if "find_callers" not in self.tools:
            return []
        
        tool = self.tools["find_callers"]
        # Tool is a pydantic-ai Tool, need to extract function
        func = tool.function if hasattr(tool, 'function') else tool
        
        try:
            result = func(func_name, file_pattern)
            
            # Parse JSON result
            if isinstance(result, str):
                data = json.loads(result)
                callers = data.get("results", {}).get("callers", [])
                return callers
            
            return []
        except Exception as e:
            logger.error(f"[HoundTracerAdapter] find_callers error: {e}")
            return []
    
    async def analyze_function_deeply(self, func_name: str) -> Dict:
        """
        Analyze function deeply using hound_tools.
        
        Args:
            func_name: Function name
            
        Returns:
            Analysis result dict
        """
        if "analyze_function_deeply" not in self.tools:
            return {}
        
        tool = self.tools["analyze_function_deeply"]
        func = tool.function if hasattr(tool, 'function') else tool
        
        try:
            result = func(func_name)
            
            # Parse JSON result
            if isinstance(result, str):
                data = json.loads(result)
                return data.get("results", {})
            
            return {}
        except Exception as e:
            logger.error(f"[HoundTracerAdapter] analyze_function_deeply error: {e}")
            return {}
    
    async def hound_fast_search(self, symbol: str) -> List[Dict]:
        """
        Fast symbol search using hound_tools.
        
        Args:
            symbol: Symbol to search
            
        Returns:
            List of search results
        """
        if "hound_fast_search" not in self.tools:
            return []
        
        tool = self.tools["hound_fast_search"]
        func = tool.function if hasattr(tool, 'function') else tool
        
        try:
            result = func(symbol)
            
            if isinstance(result, str):
                data = json.loads(result)
                return data.get("results", [])
            
            return []
        except Exception as e:
            logger.error(f"[HoundTracerAdapter] hound_fast_search error: {e}")
            return []