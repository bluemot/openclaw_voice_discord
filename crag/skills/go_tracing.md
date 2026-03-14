+++
name = "Go Code Tracing"
description = "Strategies for tracing Go goroutines, channels, and interfaces"
keywords = ["goroutine", "channel", "go func", "interface", "defer", "select", "mutex"]
project_types = ["go"]
priority = 15
+++

### Go Code Tracing Strategy

1. **Goroutine Spawning**:
   - `go func() { ... }()` - spawn goroutine
   - `go someFunc(args)` - spawn with function
   - Search for `go ` (with space) to find spawn points
   - Watch for closures capturing variables by reference!

2. **Channel Communication**:
   - `make(chan T)` - create channel
   - `ch <- value` - send
   - `value := <-ch` - receive
   - `close(ch)` - close channel (receivers get zero value + false)
   - Search for `<-` to find channel operations

3. **Interface Satisfaction**:
   - Go uses **structural typing** - any type with the right methods satisfies an interface
   - No explicit `implements` keyword
   - Search for `type InterfaceName interface` to find interface definition
   - Then search for methods matching the interface signature

4. **Defer Execution**:
   - `defer func()` - executes when surrounding function returns (LIFO order)
   - Common for cleanup: `defer file.Close()`
   - Arguments are evaluated at defer time, not execution time

5. **Error Handling**:
   - `func() (T, error)` - conventional return
   - `if err != nil { return err }` - error propagation
   - `errors.New("msg")` - create error
   - `fmt.Errorf("context: %w", err)` - wrap error

### Key Patterns

```go
// Goroutine with channel
go func() {
    for data := range ch {
        process(data)
    }
}()

// Interface - find implementations by method signature
type Reader interface {
    Read(p []byte) (n int, err error)
}

// Defer for cleanup
func processFile(path string) error {
    f, err := os.Open(path)
    if err != nil { return err }
    defer f.Close()
    // ...
}
```

### Search Strategy

- For goroutines: search for `go ` and `go func`
- For channels: search for `make(chan`, `<-`, and `close(`
- For interfaces: search for `type Name interface` and match method signatures