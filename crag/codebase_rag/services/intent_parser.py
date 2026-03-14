# codebase_rag/services/intent_parser.py
"""
Intent Parser - Extract structured intent from user questions

This module implements the Intent Parser using LLM:
- Parse user question to extract tracing intent
- Determine trace direction (up/down)
- Identify source/target symbols
- Choose strategy (unidirectional/meet_in_the_middle)

Architecture:
- Intent Parser is a thin LLM layer
- Output is Intent schema (Pydantic model)
- Used by Trace Manager to create initial Tasks

Created: 2026-03-14
"""

import json
import re
from typing import Optional, Tuple
from loguru import logger
from pydantic import BaseModel, Field

from .trace_protocol import Intent


# =============================================================================
# Intent Types
# =============================================================================

INTENT_TYPES = {
    "trace_callers": "Find who calls a function (upward trace)",
    "trace_callees": "Find what a function calls (downward trace)",
    "trace_path": "Find path from A to B (bidirectional trace)",
    "find_definition": "Find where a symbol is defined",
    "find_usage": "Find where a symbol is used",
}

DIRECTION_KEYWORDS = {
    "up": ["who calls", "what calls", "caller", "invoker", "where is .* called", "where is .* used"],
    "down": ["what does", "calls what", "callees", "invoke", "trace from", "follow"],
}

PATH_KEYWORDS = [
    "from .* to",
    "how does .* get to",
    "path from .* to",
    "flow from .* to",
]


# =============================================================================
# Pattern-Based Parser (Fast Path)
# =============================================================================

def parse_intent_patterns(question: str) -> Optional[Intent]:
    """
    Fast path: Parse intent using regex patterns.
    
    This avoids LLM calls for simple, well-structured questions.
    
    Args:
        question: User's question
        
    Returns:
        Intent if matched, None otherwise
    """
    question_lower = question.lower().strip()
    
    # Pattern: "Who calls X?" or "What calls X?"
    callers_patterns = [
        r"who calls (\w+)",
        r"what calls (\w+)",
        r"where is (\w+) called",
        r"find (?:the )?callers of (\w+)",
        r"callers of (\w+)",
    ]
    
    for pattern in callers_patterns:
        match = re.search(pattern, question_lower)
        if match:
            symbol = match.group(1)
            return Intent(
                type="trace_callers",
                target=symbol,
                direction="up",
                symbols=[symbol],
                strategy="unidirectional"
            )
    
    # Pattern: "What does X call?" or "X calls what?"
    callees_patterns = [
        r"what does (\w+) call",
        r"what (\w+) calls",
        r"find (?:the )?callees of (\w+)",
        r"callees of (\w+)",
        r"trace (\w+)",
        r"analyze (\w+)",
    ]
    
    for pattern in callees_patterns:
        match = re.search(pattern, question_lower)
        if match:
            symbol = match.group(1)
            return Intent(
                type="trace_callees",
                source=symbol,
                direction="down",
                symbols=[symbol],
                strategy="unidirectional"
            )
    
    # Pattern: "How does X get to Y?" or "Path from X to Y"
    path_patterns = [
        r"(?:how does|path from|flow from)\s+(\w+)\s+(?:to|get to)\s+(\w+)",
        r"trace from (\w+) to (\w+)",
        r"from (\w+) to (\w+)",
    ]
    
    for pattern in path_patterns:
        match = re.search(pattern, question_lower)
        if match:
            source = match.group(1)
            target = match.group(2)
            return Intent(
                type="trace_path",
                source=source,
                target=target,
                direction="down",  # Primary direction
                symbols=[source, target],
                strategy="meet_in_the_middle"
            )
    
    # Pattern: "Find definition of X" or "Where is X defined?"
    definition_patterns = [
        r"(?:find )?definition of (\w+)",
        r"where is (\w+) defined",
        r"define (\w+)",
    ]
    
    for pattern in definition_patterns:
        match = re.search(pattern, question_lower)
        if match:
            symbol = match.group(1)
            return Intent(
                type="find_definition",
                target=symbol,
                direction="down",
                symbols=[symbol],
                strategy="unidirectional"
            )
    
    return None


# =============================================================================
# Symbol Extraction
# =============================================================================

def extract_symbols(question: str) -> list:
    """
    Extract potential symbol names from question.
    
    Uses heuristics:
    - Quoted strings
    - CamelCase/snake_case identifiers
    - Function-like patterns (name followed by parentheses)
    
    Args:
        question: User's question
        
    Returns:
        List of potential symbol names
    """
    symbols = []
    
    # Quoted strings
    quoted = re.findall(r'["\'](\w+)["\']', question)
    symbols.extend(quoted)
    
    # CamelCase and snake_case
    identifiers = re.findall(r'\b([a-z_][a-z0-9_]*|[A-Z][a-zA-Z0-9]*)\b', question)
    # Filter out common words
    common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'who', 
                    'how', 'where', 'when', 'why', 'which', 'this', 'that', 'it',
                    'to', 'from', 'in', 'on', 'at', 'by', 'for', 'with', 'of'}
    symbols.extend([w for w in identifiers if w.lower() not in common_words])
    
    # Function patterns: word followed by parentheses
    func_patterns = re.findall(r'\b(\w+)\s*\(', question)
    symbols.extend(func_patterns)
    
    # Dedupe while preserving order
    seen = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    
    return unique


# =============================================================================
# Direction Detection
# =============================================================================

def detect_direction(question: str) -> str:
    """
    Detect trace direction from question.
    
    Args:
        question: User's question
        
    Returns:
        "up", "down", or "bidirectional"
    """
    question_lower = question.lower()
    
    # Check for upward keywords
    for pattern in DIRECTION_KEYWORDS["up"]:
        if re.search(pattern, question_lower):
            return "up"
    
    # Check for downward keywords
    for pattern in DIRECTION_KEYWORDS["down"]:
        if re.search(pattern, question_lower):
            return "down"
    
    # Check for path keywords (bidirectional)
    for pattern in PATH_KEYWORDS:
        if re.search(pattern, question_lower):
            return "bidirectional"
    
    # Default: down (most common)
    return "down"


# =============================================================================
# File Hint Extraction
# =============================================================================

def extract_file_hint(question: str) -> Optional[str]:
    """
    Extract file hint from question.
    
    Looks for:
    - Explicit file mentions (in.c, main.py)
    - Path patterns (src/foo.c)
    
    Args:
        question: User's question
        
    Returns:
        File hint or None
    """
    # Explicit file mentions
    file_patterns = [
        r'\b(\w+\.[ch])\b',           # C files: main.c, utils.h
        r'\b(\w+\.py)\b',              # Python files: main.py
        r'\b(\w+\.js)\b',              # JavaScript files: app.js
        r'\b(\w+\.rs)\b',              # Rust files: main.rs
        r'\b(\w+\.java)\b',           # Java files: Main.java
        r'([a-zA-Z0-9_/]+\.[a-z]{1,4})\b',  # General paths
    ]
    
    for pattern in file_patterns:
        match = re.search(pattern, question)
        if match:
            return match.group(1)
    
    return None


# =============================================================================
# Main Intent Parser
# =============================================================================

class IntentParser:
    """
    Intent Parser for code tracing questions.
    
    Usage:
        parser = IntentParser(llm_client=None)  # Pattern-based only
        intent = parser.parse("Who calls cudaMemcpy?")
        
        # Or with LLM for complex questions
        parser = IntentParser(llm_client=client)
        intent = parser.parse("How does the data flow from init to gpu?")
    """
    
    def __init__(
        self,
        llm_client=None,
        model: str = "gpt-4o-mini",
        use_patterns_first: bool = True
    ):
        """
        Initialize Intent Parser.
        
        Args:
            llm_client: LLM client for complex parsing (optional)
            model: Model to use for LLM parsing
            use_patterns_first: Try pattern-based parsing before LLM
        """
        self.llm_client = llm_client
        self.model = model
        self.use_patterns_first = use_patterns_first
    
    def parse(self, question: str) -> Intent:
        """
        Parse user question into structured Intent.
        
        Args:
            question: User's question
            
        Returns:
            Intent with type, source, target, direction, etc.
        """
        # Fast path: Try pattern-based parsing first
        if self.use_patterns_first:
            intent = parse_intent_patterns(question)
            if intent:
                logger.info(f"[IntentParser] Pattern match: {intent.type} -> {intent.symbols}")
                return intent
        
        # Extract metadata regardless of parsing method
        symbols = extract_symbols(question)
        direction = detect_direction(question)
        file_hint = extract_file_hint(question)
        
        # If no LLM, return a generic intent
        if not self.llm_client:
            # Try to guess intent type from direction
            if direction == "up":
                intent_type = "trace_callers"
                target = symbols[0] if symbols else None
                return Intent(
                    type=intent_type,
                    target=target,
                    direction=direction,
                    symbols=symbols,
                    file_hint=file_hint,
                    strategy="unidirectional"
                )
            else:
                intent_type = "trace_callees"
                source = symbols[0] if symbols else None
                return Intent(
                    type=intent_type,
                    source=source,
                    direction=direction,
                    symbols=symbols,
                    file_hint=file_hint,
                    strategy="unidirectional"
                )
        
        # LLM-based parsing for complex questions
        return self._parse_with_llm(question, symbols, direction, file_hint)
    
    def _parse_with_llm(
        self,
        question: str,
        symbols: list,
        direction: str,
        file_hint: Optional[str]
    ) -> Intent:
        """
        Use LLM to parse complex questions.
        
        Args:
            question: User's question
            symbols: Pre-extracted symbols
            direction: Pre-detected direction
            file_hint: Pre-extracted file hint
            
        Returns:
            Parsed Intent
        """
        from .tracer_prompts import build_intent_prompt
        
        prompt = build_intent_prompt(question)
        
        try:
            # Call LLM
            response = self.llm_client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a precise intent parser. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0
            )
            
            # Parse JSON response
            content = response.get("content", "") or response.get("message", {}).get("content", "")
            
            # Extract JSON
            from .json_sanitizer import sanitize_and_parse
            data = sanitize_and_parse(content)
            
            # Build Intent
            return Intent(
                type=data.get("type", "trace_callees"),
                source=data.get("source"),
                target=data.get("target"),
                strategy=data.get("strategy", "unidirectional"),
                direction=data.get("direction", direction),
                symbols=data.get("symbols", symbols),
                file_hint=data.get("file_hint", file_hint)
            )
            
        except Exception as e:
            logger.warning(f"[IntentParser] LLM parsing failed: {e}")
            
            # Fallback to heuristics
            if len(symbols) >= 2:
                return Intent(
                    type="trace_path",
                    source=symbols[0],
                    target=symbols[1],
                    strategy="meet_in_the_middle",
                    direction=direction,
                    symbols=symbols,
                    file_hint=file_hint
                )
            elif direction == "up":
                return Intent(
                    type="trace_callers",
                    target=symbols[0] if symbols else None,
                    strategy="unidirectional",
                    direction=direction,
                    symbols=symbols,
                    file_hint=file_hint
                )
            else:
                return Intent(
                    type="trace_callees",
                    source=symbols[0] if symbols else None,
                    strategy="unidirectional",
                    direction=direction,
                    symbols=symbols,
                    file_hint=file_hint
                )


# =============================================================================
# Convenience Functions
# =============================================================================

def parse_intent(question: str, llm_client=None) -> Intent:
    """
    Convenience function to parse intent.
    
    Args:
        question: User's question
        llm_client: Optional LLM client for complex parsing
        
    Returns:
        Parsed Intent
    """
    parser = IntentParser(llm_client=llm_client)
    return parser.parse(question)


def is_trace_question(question: str) -> bool:
    """
    Check if question is a code tracing question.
    
    Args:
        question: User's question
        
    Returns:
        True if it's a tracing question
    """
    question_lower = question.lower()
    
    # Keywords that indicate tracing
    trace_keywords = [
        "calls", "callers", "callees", "invokes",
        "trace", "follow", "flow", "path",
        "where is", "what does", "who calls",
        "from", "to", "how does"
    ]
    
    for keyword in trace_keywords:
        if keyword in question_lower:
            # Check if there's a potential symbol
            symbols = extract_symbols(question)
            if symbols:
                return True
    
    return False