+++
name = "Python Code Tracing"
description = "Strategies for tracing Python async, decorators, and dynamic imports"
keywords = ["decorator", "async", "await", "import", "getattr", "setattr", "metaclass", "classmethod"]
project_types = ["python"]
priority = 15
+++

### Python Code Tracing Strategy

1. **Decorator Chain**: `@decorator` is syntactic sugar for `func = decorator(func)`. The decorator may wrap, modify, or replace the function. Search for the decorator definition to understand behavior.

2. **Async/Await Tracing**:
   - `async def` defines a coroutine
   - `await expr` suspends until `expr` completes
   - Look for where coroutines are **actually started**: `asyncio.run()`, `await`, `asyncio.create_task()`
   - A coroutine that's never awaited never runs!

3. **Dynamic Attribute Access**:
   - `getattr(obj, 'method')` - dynamic method lookup
   - `__getattr__` / `__getattribute__` - custom attribute access
   - `@property` - computed attributes

4. **Import Machinery**:
   - `importlib.import_module(name)` - dynamic imports
   - `__import__` - low-level import
   - Check `sys.path` for module search locations

5. **Metaclass Magic**:
   - `class Meta(type):` - metaclass that controls class creation
   - `__new__`, `__init__`, `__call__` - customization points

### Key Patterns

```python
# Decorator - find the definition
@some_decorator
def func(): pass

# Async - trace where this is awaited
async def process():
    result = await some_operation()

# Dynamic - search for string usage
func = getattr(module, func_name)
```

### Search Strategy

- For decorators: search for `def decorator_name`
- For async: search for `await func_name` and `asyncio.create_task`
- For dynamic: search for string literals used in getattr/importlib