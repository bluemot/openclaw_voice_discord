+++
name = "Python Async Analysis"
description = "Strategies for tracing Python async/await code paths"
keywords = ["async", "await", "asyncio", "coroutine", "event loop", "future", "task"]
project_types = ["python"]
priority = 15
+++

### Python Async Analysis Strategy

1. **Coroutine Chain**: Follow `async def` → `await` chains:
   - `await func()` suspends execution
   - Look for where the coroutine is actually awaited (not just created)
   - Check if it's wrapped in `asyncio.create_task()` or `asyncio.gather()`

2. **Event Loop Entry**: Find the loop start:
   - `asyncio.run()` (Python 3.7+)
   - `loop.run_until_complete()`
   - `loop.run_forever()`

3. **Callback Conversion**: Old code uses callback style:
   - `add_done_callback()` on Futures
   - Check `loop.call_soon()`, `loop.call_later()`
   - Look for where callbacks transition to async/await

4. **Task Scheduling**: Understand task creation:
   - `asyncio.create_task()` schedules immediately
   - `asyncio.gather()` runs concurrently
   - `asyncio.wait_for()` adds timeout

### Key Patterns

- **Queue Pattern**: Many async systems use queues:
  - `asyncio.Queue` → `await queue.get()` → `await queue.put()`
  - Look for producer/consumer separation

- **Stream Pattern**: Network/file I/O:
  - `reader.read(n)` → `writer.write(data)` → `await writer.drain()`

- **Context Managers**: Async context managers for resources:
  - `async with lock:` for synchronization
  - `async with pool:` for connection pooling