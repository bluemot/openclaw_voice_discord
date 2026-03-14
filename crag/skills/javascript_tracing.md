+++
name = "JavaScript/TypeScript Tracing"
description = "Strategies for tracing JS/TS promises, events, and prototype chains"
keywords = ["promise", "async", "await", "callback", "event", "prototype", "this", "bind", "apply"]
project_types = ["javascript", "typescript", "js", "ts"]
priority = 15
+++

### JavaScript/TypeScript Code Tracing Strategy

1. **Promise Chain Tracing**:
   - `.then(fn)` - success handler
   - `.catch(fn)` - error handler
   - `.finally(fn)` - cleanup
   - `await promise` - pauses until resolved
   - Search for where the promise is **created** (`new Promise`, `resolve()`, `reject()`)

2. **Event Emitter Pattern**:
   - `emitter.on('event', handler)` - register listener
   - `emitter.emit('event', data)` - trigger
   - Search for `.emit('eventName')` to find where events fire

3. **Prototype Chain**:
   - `Class.prototype.method` - instance method
   - `Class.staticMethod` - static method
   - `Object.create(proto)` - prototypal inheritance
   - `__proto__` - dunder proto (avoid in production)

4. **`this` Binding Issues**:
   - Arrow functions inherit `this` from lexical scope
   - `.bind(thisArg)` - explicit binding
   - `.call(thisArg, ...args)`, `.apply(thisArg, args)` - immediate invocation

5. **Module System**:
   - `import { x } from 'module'` - ES modules
   - `require('module')` - CommonJS
   - Dynamic: `import('module')` - returns Promise

### Key Patterns

```javascript
// Promise - trace resolve/reject
new Promise((resolve, reject) => {
    // Where is resolve called?
});

// Event - find emit
eventBus.on('data', handler);
// Search: emit('data'

// Prototype
class Child extends Parent {
    method() { super.method(); }
}
```

### Search Strategy

- For promises: search for `new Promise` and `resolve(`
- For events: search for `.emit('eventName')` and `.on('eventName'`
- For classes: search for `class ClassName` and `extends`