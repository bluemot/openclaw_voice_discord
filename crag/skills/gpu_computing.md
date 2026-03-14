+++
name = "GPU Computing Analysis"
description = "Strategies for tracing GPU compute code (CUDA, Metal, Vulkan)"
keywords = ["gpu", "cuda", "metal", "vulkan", "opencl", "compute", "shader", "kernel", "memory", "buffer"]
project_types = ["c", "cpp", "rust"]
priority = 15
+++

### GPU Computing Analysis Strategy

1. **Memory Allocation Path**: GPU memory allocation usually follows:
   - `malloc` → `cudaMalloc`/`vkAllocateMemory`/`MTLBuffer`
   - Look for `create_buffer`, `alloc_buffer`, `new_buffer` patterns
   - The actual allocation often happens in a backend-specific implementation

2. **Kernel Launch**: Find how kernels are launched:
   - CUDA: `<<< >>>` syntax or `cudaLaunchKernel`
   - Vulkan: `vkCmdDispatch` or `vkCmdDispatchIndirect`
   - Metal: `dispatchThreadgroups`

3. **Data Transfer**: Look for copy functions:
   - Host → Device: `cudaMemcpy`, `vkCmdCopyBuffer`
   - Device → Host: Look for mapping or staging buffers

4. **Pipeline State**: GPU operations are often wrapped in pipelines:
   - Look for `create_pipeline`, `compile_pipeline`
   - Check for shader compilation and binding

### Key Patterns

- **Backend Abstraction**: Many projects abstract GPU backends. Look for:
  - `ggml_backend_*` (llama.cpp style)
  - `wgpu_*` (WebGPU native)
  - `Device` class patterns

- **Command Buffers**: Operations are often recorded:
  - `begin_command_buffer` → `cmd_*` → `end_command_buffer` → `submit`

- **Synchronization**: Look for fences, semaphores, events