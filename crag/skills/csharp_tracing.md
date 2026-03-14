+++
name = "C#/.NET Code Tracing"
description = "Strategies for tracing C# async/await, LINQ, and delegates"
keywords = ["async", "await", "Task", "LINQ", "delegate", "event", "property", "extension"]
project_types = ["csharp", "cs", "dotnet"]
priority = 15
+++

### C#/.NET Code Tracing Strategy

1. **Async/Await Pattern**:
   - `async Task<T>` - async method returns Task
   - `await expression` - suspend until complete
   - `Task.Run(() => ...)` - queue to thread pool
   - `Task.WhenAll(tasks)` - wait for multiple
   - Search for `async` and `await` to trace async flow

2. **Task Parallel Library (TPL)**:
   - `Parallel.For()`, `Parallel.ForEach()` - parallel loops
   - `PLINQ` - `.AsParallel()` for parallel LINQ
   - `CancellationToken` - cooperative cancellation

3. **LINQ Tracing**:
   - `.Where()`, `.Select()`, `.OrderBy()` - standard operators
   - `.GroupBy()`, `.Join()` - grouping/joining
   - Deferred execution: query runs when enumerated
   - `.ToList()`, `.ToArray()` - force immediate execution

4. **Delegate & Event Pattern**:
   - `delegate` - function pointer type
   - `event EventHandler<T>` - publish/subscribe
   - `+=` subscribe, `-=` unsubscribe
   - Search for `Invoke(` or `?.Invoke(` for event firing

5. **Extension Methods**:
   - `public static T Method(this T source)` - extension method
   - Appears as instance method but defined in static class
   - Search for `this ` in method signatures

### Key Patterns

```csharp
// Async chain
public async Task<User> GetUserAsync(int id) {
    var user = await _repository.FindByIdAsync(id);
    return user;
}

// Event pattern
public event EventHandler<string> OnMessage;
OnMessage?.Invoke(this, "hello");  // Fire event

// LINQ
var result = users
    .Where(u => u.IsActive)
    .Select(u => u.Name)
    .ToList();  // Immediate execution
```

### Search Strategy

- For async: search for `async `, `await `, `Task<`
- For events: search for `event `, `?.Invoke(`
- For LINQ: search for `.Where(`, `.Select(`, `.AsParallel(`