# Integration: Adding find_callers to hound_tools.py

## Step 1: Add find_callers function

Insert the `find_callers` function and `_extract_caller_function` helper after `hound_fast_search` in hound_tools.py.

## Step 2: Register the tool

Add to the return list in `create_hound_tools()`:

```python
return [
    # ... existing tools ...
    Tool(find_callers, name="find_callers", description="Find all functions that call this function (UPWARD direction)."),
    # ... existing tools ...
]
```

## Step 3: Update tool list

```python
return [
    Tool(analyze_function_deeply, name="analyze_function_deeply", description="Locate and analyze a function's callees in one step."),
    Tool(find_callers, name="find_callers", description="Find all functions that call this function (UPWARD direction)."),  # NEW
    Tool(resolve_async_dispatch, name="resolve_async_dispatch", description="Resolve async queue handlers by ID."),
    Tool(find_state_consumer, name="find_state_consumer", description="Find where a state/event is consumed."),
    Tool(get_function_callees, name="get_function_callees", description="Get all callees inside a function."),
    Tool(hound_fast_search, name="hound_fast_search", description="Fast deterministic symbol search."),
    Tool(global_text_search, name="global_text_search", description="Search the macro name globally to find the event handler or consumer."),
    Tool(backtrack_to, name="backtrack_to", description="Backtrack to a previous function in the call chain."),
    Tool(acknowledge_and_dismiss, name="acknowledge_and_dismiss", description="Dismiss a high-relevance branch to bypass Veto."),
    Tool(submit_final_answer, name="submit_final_answer", description="Signal potential completion of the task for verification."),
    Tool(confirm_completion, name="confirm_completion", description="Confirm completion after verification.")
]
```

## Usage Example

```python
# Find who calls cudaMalloc
result = find_callers("cudaMalloc")

# Expected output:
{
    "intent": "find_callers",
    "function": "cudaMalloc",
    "callers": [
        {
            "name": "init_gpu",
            "file": "src/gpu.c",
            "line": 45,
            "source": "hound"
        },
        {
            "name": "allocate_buffer",
            "file": "src/memory.c",
            "line": 120,
            "source": "graph"
        }
    ],
    "sources": ["hound", "graph"],
    "guidance": ">>> FOUND 2 CALLERS: init_gpu, allocate_buffer. Each needs separate tracing."
}
```

## Mixed Strategy Benefits

| Source | Pros | Cons |
|--------|------|------|
| Graph (Memgraph) | Fast, structured relationships | May be incomplete in lightweight mode |
| Hound (ripgrep) | Always works, finds all occurrences | Slower, may have false positives |

By using both, we get:
- **Speed**: Graph query when available
- **Completeness**: Hound search always catches everything
- **Deduplication**: Results merged by function name