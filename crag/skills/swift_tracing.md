+++
name = "Swift Code Tracing"
description = "Strategies for tracing Swift async/await, protocols, and optionals"
keywords = ["async", "await", "protocol", "optional", "guard", "extension", "closure", "task"]
project_types = ["swift"]
priority = 15
+++

### Swift Code Tracing Strategy

1. **Async/Await (Swift 5.5+)**:
   - `async func()` - async function
   - `await expression` - suspend until complete
   - `Task { }` - spawn async task
   - `TaskGroup` - structured concurrency
   - `@MainActor` - run on main thread

2. **Protocol-Oriented Programming**:
   - `protocol Name { }` - protocol definition
   - `extension Protocol where Self: Class` - default implementation
   - `struct/enum: Protocol` - conformance
   - Protocol conformance may be in extension file

3. **Optional Handling**:
   - `Type?` - optional type
   - `if let x = optional { }` - safe unwrap
   - `guard let x = optional else { return }` - early return
   - `optional?.property` - optional chaining
   - `optional ?? default` - nil coalescing
   - `try!`, `try?` - error handling variants

4. **Closure Syntax**:
   - `{ param in body }` - closure
   - `@escaping` - stored closure
   - `[weak self]` - capture list (avoid retain cycle)
   - `.map { }`, `.filter { }` - functional

5. **Extensions**:
   - `extension Type { }` - add functionality
   - Protocol conformance often in separate extension
   - Extensions can't override existing methods

### Key Patterns

```swift
// Async/await
func fetchData() async throws -> Data {
    let result = try await network.request()
    return result
}

// Optional handling
func process(user: User?) {
    guard let user = user else { return }
    // user is now unwrapped
}

// Protocol conformance
struct MyModel: Codable { ... }
// Search for extension for conformance
```

### Search Strategy

- For async: search for `async `, `await `, `Task {`
- For protocols: search for `protocol ` and `extension *: Protocol`
- For optionals: search for `if let`, `guard let`, `?`