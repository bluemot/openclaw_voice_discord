+++
name = "Java Code Tracing"
description = "Strategies for tracing Java classes, interfaces, and async"
keywords = ["class", "interface", "extends", "implements", "thread", "executor", "future", "stream"]
project_types = ["java"]
priority = 15
+++

### Java Code Tracing Strategy

1. **Class Hierarchy**:
   - `class Child extends Parent` - inheritance
   - `class Impl implements Interface` - interface implementation
   - Search for `extends ClassName` to find subclasses
   - Search for `implements InterfaceName` to find implementations

2. **Interface vs Implementation**:
   - Interface: `public interface Name { void method(); }`
   - Implementation: `public class NameImpl implements Name { ... }`
   - Use `global_text_search` for `implements InterfaceName`
   - Polymorphism: actual type may differ from declared type

3. **Async & Threading**:
   - `Thread.start()` - spawn thread
   - `ExecutorService.submit()` - thread pool
   - `CompletableFuture` - async chain
   - `@Async` - Spring async annotation
   - Search for `.thenApply(`, `.thenAccept(` for async chains

4. **Annotation Processing**:
   - `@Override` - method override
   - `@Autowired` - Spring dependency injection
   - `@Transactional` - database transaction
   - Search for annotation usage to find annotated classes/methods

5. **Stream API**:
   - `.stream()` - create stream
   - `.map()`, `.filter()`, `.collect()` - operations
   - `.forEach()` - terminal operation
   - Chain: source → intermediate → terminal

### Key Patterns

```java
// Interface implementation
public class UserServiceImpl implements UserService {
    // Search for: implements UserService
}

// Async chain
CompletableFuture.supplyAsync(() -> fetchData())
    .thenApply(data -> transform(data))
    .thenAccept(result -> save(result));

// Stream
list.stream()
    .filter(x -> x.isValid())
    .map(x -> x.getName())
    .collect(Collectors.toList());
```

### Search Strategy

- For interfaces: search for `interface Name` and `implements Name`
- For async: search for `CompletableFuture`, `ExecutorService`, `@Async`
- For Spring: search for `@Component`, `@Service`, `@Autowired`