+++
name = "Ruby Code Tracing"
description = "Strategies for tracing Ruby blocks, mixins, and metaprogramming"
keywords = ["block", "proc", "lambda", "mixin", "module", "include", "extend", "yield", "send"]
project_types = ["ruby"]
priority = 15
+++

### Ruby Code Tracing Strategy

1. **Block & Yield Pattern**:
   - `method { |arg| body }` - block argument
   - `yield` - invoke block
   - `&block` - explicit block parameter
   - `block_given?` - check if block passed
   - Search for `yield` to find where blocks are invoked

2. **Proc & Lambda**:
   - `Proc.new { }` - create Proc
   - `lambda { }` or `->(arg) { }` - create Lambda
   - `&proc` - convert Proc to block
   - Lambda checks arity, Proc doesn't

3. **Mixin Pattern**:
   - `include Module` - add instance methods
   - `extend Module` - add class methods
   - `prepend Module` - insert before class in ancestry
   - Search for `include`/`extend`/`prepend` to find mixins

4. **Metaprogramming**:
   - `send(:method, args)` - dynamic dispatch
   - `define_method(:name) { }` - define method dynamically
   - `method_missing` - catch undefined method calls
   - `class_eval`, `instance_eval` - evaluate in context
   - Search for `send(`, `define_method`, `method_missing`

5. **Method Visibility**:
   - `private`, `protected`, `public`
   - Can be set per-method: `private :method_name`
   - Methods after keyword have that visibility

### Key Patterns

```ruby
# Block with yield
def with_file(path)
  f = File.open(path)
  yield f
ensure
  f.close
end

# Mixin
module Logging
  def log(msg) puts msg end
end
class Service
  include Logging  # Now has #log
end

# Dynamic dispatch
obj.send(:method_name, arg)  # Call private method
```

### Search Strategy

- For blocks: search for `yield`, `{ |`, `do |`
- For mixins: search for `include `, `extend `, `prepend `
- For metaprogramming: search for `send(`, `define_method`, `method_missing`