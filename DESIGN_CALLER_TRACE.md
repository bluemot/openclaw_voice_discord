# Design: Caller Tracing & Mixed Strategy

**Created:** 2026-03-14
**Status:** Draft
**Project:** CRAG (Code-Graph RAG)

---

## Problem Statement

When users ask Architect to "find callers" (who calls this function), the Agent often incorrectly finds "callees" (what this function calls).

### Root Causes

1. **Missing Tool**: All existing tools are "downward" direction:
   - `analyze_function_deeply`: Finds callees
   - `hound_fast_search`: Finds definitions
   - `get_function_callees`: Extracts callees via AST

2. **Incomplete Graph in Lightweight Mode**: 
   - `lightweight=True` skips `CALLS` edge creation
   - Graph query `MATCH (caller)-[:CALLS]->(target)` returns empty

---

## Solution: Mixed Strategy for `find_callers`

### Layer 1: Graph Query (Fast but Incomplete)

```cypher
MATCH (caller:Function)-[:CALLS]->(target:Function {name: $func_name})
RETURN caller.name, caller.file, caller.line
```

- Works when graph has data
- Empty in lightweight mode

### Layer 2: Hound Search (Always Accurate)

```bash
rg "target_func\s*\(" --type c -n
```

- Works regardless of ingestion mode
- Returns raw text matches (file:line:context)

### Implementation Pattern

```python
def find_callers(func_name: str) -> str:
    """
    Find all functions that call this function (REVERSE direction).
    Uses mixed strategy: graph + hound search.
    """
    
    # Layer 1: Graph (fast, may be empty in lightweight)
    graph_callers = []
    if ingestor and hasattr(ingestor, 'graph_service'):
        try:
            query = """
            MATCH (caller:Function)-[:CALLS]->(target:Function {name: $name})
            RETURN caller.name as name, caller.file as file
            """
            graph_callers = ingestor.execute_read(query, {"name": func_name})
        except Exception:
            pass
    
    # Layer 2: Hound Search (always works)
    hound_results = searcher.search_text_in_codebase(
        query=f"{func_name}\\s*\\(",
        file_extension=".c,.cpp,.h",
        is_regex=True
    )
    
    # Parse hound results to extract callers
    hound_callers = parse_callers_from_search(hound_results, func_name)
    
    # Merge and dedupe
    merged = merge_callers(graph_callers, hound_callers)
    
    return format_callers_json(merged)

def find_callees(func_name: str) -> str:
    """
    Find all functions called by this function (FORWARD direction).
    Also uses mixed strategy for consistency.
    """
    # Similar implementation, but CALLS direction reversed
    # MATCH (f:Function {name: $name})-[:CALLS]->(callee:Function)
    pass
```

### Enhanced `analyze_function_deeply`

```python
def analyze_function_deeply(func_name: str) -> str:
    """
    Deep analysis of a function - BOTH directions.
    Now includes callers (up) and callees (down).
    """
    # Existing: Find callees (downward)
    callees = analyze_function_deeply_logic(func_name)
    
    # NEW: Find callers (upward)
    callers = find_callers(func_name)
    
    # NEW: Graph context
    graph_context = fetch_graph_context(func_name)
    
    return {
        "function": func_name,
        "callers": callers,      # NEW - upward direction
        "callees": callees,      # existing - downward
        "graph_context": graph_context  # neighboring nodes
    }
```

---

## Tool Suite Summary

| Tool | Direction | Strategy |
|------|-----------|----------|
| `find_callers` | Up (Caller) | Graph + Hound |
| `analyze_function_deeply` | Both | Enhanced with callers |
| `hound_fast_search` | Definition | Hound only |
| `resolve_async_dispatch` | Down | Heuristic + Graph |

---

## Prompt Strategy

Add to Architect system prompt:

```
## Direction Awareness

When user asks to "find callers" or "who calls this":
- Use `find_callers` tool (UPWARD direction)
- This finds functions that CALL the target

When user asks to "trace downstream" or "what does this call":
- Use `analyze_function_deeply` tool (DOWNWARD direction)
- This finds functions that the target CALLS

CRITICAL: Do NOT confuse these directions!
```

---

## Files to Modify

1. `codebase_rag/tools/hound_tools.py` - Add `find_callers` tool
2. `codebase_rag/parsers/heuristic_resolvers.py` - Add caller parsing logic
3. `codebase_rag/services/scheduler.py` - Update prompts for direction awareness

---

## Testing

```bash
# Test: Find who calls ggml_backend_alloc_tensor
./crag chat llama.cpp -q "Who calls ggml_backend_alloc_tensor?"

# Expected: Should return callers, NOT callees
```