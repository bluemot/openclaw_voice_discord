+++
name = "Rust Code Tracing"
description = "Strategies for tracing Rust ownership, lifetimes, and async"
keywords = ["ownership", "borrow", "lifetime", "async", "await", "trait", "impl", "Result", "Option"]
project_types = ["rust"]
priority = 15
+++

### Rust Code Tracing Strategy

1. **Ownership & Borrowing**:
   - `let x = value;` - owned
   - `let ref_x = &value;` - borrowed (immutable)
   - `let mut_ref = &mut value;` - borrowed (mutable)
   - `.clone()` - explicit copy
   - Look for `.into()`, `.as_ref()`, `.to_owned()` for conversions

2. **Result/Option Handling**:
   - `Result<T, E>` - success or error
   - `Option<T>` - Some or None
   - `?` operator - early return on error/None
   - `.unwrap()`, `.expect("msg")` - panics on failure
   - `.map()`, `.and_then()` - functional chaining

3. **Trait Implementation**:
   - `impl TraitName for Type` - trait implementation
   - `trait TraitName { fn method(); }` - trait definition
   - Search for `impl TraitName` to find all implementations

4. **Async/Await (Tokio/async-std)**:
   - `async fn` - async function
   - `.await` - suspend until complete
   - `async move` - capture ownership
   - `tokio::spawn()` - spawn async task
   - Search for `.spawn` to find task creation

5. **Pattern Matching**:
   - `match expr { pattern => body }` - exhaustive matching
   - `if let pattern = expr` - conditional extraction
   - `let pattern = expr` - destructuring

### Key Patterns

```rust
// Ownership transfer
fn process(data: Vec<u8>) { /* data is moved */ }
fn borrow(data: &Vec<u8>) { /* data is borrowed */ }

// Result handling
fn fallible() -> Result<T, E> {
    let value = some_operation()?;  // Early return on error
    Ok(value)
}

// Async
async fn fetch() -> Result<Data, Error> {
    let response = client.get(url).await?;
    Ok(response.json().await?)
}
```

### Search Strategy

- For ownership: look for `.clone()`, `.into()`, `.as_ref()`
- For errors: search for `impl Error` and `enum ErrorKind`
- For async: search for `.await` and `tokio::spawn`