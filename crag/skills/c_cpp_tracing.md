+++
name = "C/C++ Code Tracing"
description = "Strategies for tracing C/C++ code with pointers, macros, and callbacks"
keywords = ["pointer", "macro", "callback", "struct", "function pointer", "inline", "static"]
project_types = ["c", "cpp"]
priority = 15
+++

### C/C++ Code Tracing Strategy

1. **Pointer Assignment Pattern**: When you see `obj->handler = func_name`, this is a callback assignment. Use `global_text_search` to find where `func_name` is defined and where `obj->handler` is invoked.

2. **Macro Expansion**: If you encounter `SOME_MACRO(var)`, search for `#define SOME_MACRO` in header files. Macros often hide complex logic.

3. **Function Pointer Tables**: Look for struct members like `.read = func`, `.write = func`. These are usually VFS-style interfaces. The actual function is called via `ops->read(...)`.

4. **Static Inline Detection**: `static inline` functions are defined in headers. Use `global_text_search` with pattern `*.[ch]` to find them.

5. **Container_of Macro**: Common in Linux kernel code. `container_of(ptr, type, member)` gets the parent struct from a member pointer. This is crucial for understanding object relationships.

### Key Patterns

```c
// Callback assignment - trace where this is called
struct->callback = my_handler;

// Macro - search for definition
CALLBACK(wrapper, data);

// Function pointer table - virtual dispatch
static const struct ops my_ops = {
    .init = my_init,
    .exit = my_exit,
};
```

### Search Strategy

- Always search `*.[ch]` for macro definitions
- Look for `&func_name` when tracing callback assignments
- Check `static` definitions in the same file first