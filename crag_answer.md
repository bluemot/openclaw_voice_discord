# CRAG Answer: llama.cpp Model Loading and GPU Inference

## 問題
請問 llama.cpp 如何載入 model 處理運算子和模型參數，然後放入 GPU 進行推論？

## CRAG 回答

### 完整答案 – Llama.cpp 如何 **載入模型 → 處理算子/參數 → 放入 GPU → 推論**

下面把整個流程從 **編譯**、**模型載入**、**算子圖建構**、**GPU 轉移**、**推論執行**、**量化解碼**、**效能調校** 逐步說明，並提供關鍵程式碼片段與常見調校技巧。

---

### 1️⃣ 編譯 Llama.cpp 以支援 GPU

| 目標 | 必要的 Makefile 變數 | 範例指令 |
|------|----------------------|----------|
| **CUDA (NVIDIA)** | `LLAMA_CUBLAS=1`、`GGML_CUDA=1` | `make LLAMA_CUBLAS=1 GGML_CUDA=1 -j$(nproc)` |
| **Vulkan (跨平台)** | `LLAMA_VULKAN=1`、`GGML_VULKAN=1` | `make LLAMA_VULKAN=1 GGML_VULKAN=1 -j$(nproc)` |
| **量化模型** | `GGML_Q4_0=1`、`GGML_Q5_1=1`（預設已開） | 無需額外參數，只要模型檔是量化的即可載入 |

> **前置條件**：CUDA 需要安裝 **CUDA Toolkit ≥ 11.0** 且顯示卡支援 Compute Capability ≥ 5.2；Vulkan 需要安裝 **Vulkan SDK**。

---

### 2️⃣ 模型載入 – `llama_model_load_from_file`

1. **讀取檔頭**
   ```c
   struct llama_hparams {
       uint32_t n_vocab, n_embd, n_mult, n_head, n_layer, n_rot;
       uint32_t ftype;          // 0=fp32, 1=fp16, 2=q4_0, 3=q4_1, 4=q5_0, 5=q5_1 …
   };
   ```
   `llama_load_hparams` 直接 `fread` 這段結構，決定 **tensor type**（`GGML_TYPE_F32`, `GGML_TYPE_F16`, `GGML_TYPE_Q4_0` …）。

2. **逐個權重讀入** (`llama_load_tensor`)
   ```c
   struct ggml_tensor *tensor = ggml_new_tensor(ctx, type, ne[0], ne[1], ne[2], ne[3]);
   fread(tensor->data, 1, ggml_nbytes(tensor), fp);   // 讀入壓縮或未壓縮的二進位
   model.tensors[model.n_tensors++] = tensor;        // 記錄指標
   ```
   - `ggml_new_tensor` 只在 **CPU** 上分配 `malloc`，`tensor->data` 指向 **壓縮**（量化）或 **FP16/FP32** 緩衝區。
   - 權重名稱會存入 `model.tensors_by_name`，方便後續 `llama_get_tensor` 快速查找。

3. **完成後的 `model.tensors[]`**
   - 每個元素都是 **CPU** 端的 `ggml_tensor`，已填好 `type`, `ne[]`, `nb[]`, `data`。
   - 若 `ftype` 為量化（`Q4_0`、`Q5_1`），`data` 仍是 **壓縮的位元**，解碼會在 GPU kernel 中即時完成（見第 4 節）。

---

### 3️⃣ 建立算子圖 – `llama_build_graph`

```c
struct ggml_cgraph graph = llama_build_graph(lctx, n_predict);
```

- 內部使用 **ggml** 的算子 API（`ggml_mul_mat`, `ggml_add`, `ggml_norm`, `ggml_silu` …）把 **每層** 的 Self‑Attention、FFN、LayerNorm 等組成 **有向無環圖 (DAG)**。
- 每個算子產生一個 `ggml_tensor`（節點），並把前驅節點記錄在 `tensor->src[]`。
- 圖的最後一個節點是 **logits**（未經 softmax 的輸出向量）。

> **GPU/CPU 無關**：圖本身只描述「資料流」與「算子類型」，真正的執行後端在第 5 步決定。

---

### 4️⃣ 把模型參數搬到 GPU

#### 4.1 初始化 CUDA 後端

```c
ggml_backend_t gpu = ggml_backend_cuda_init(0);   // 0 = 第 0 張 GPU
```

- 會 **建立 CUDA context、stream、cuBLAS handle**，並一次性 `cudaMalloc` **device arena**（整塊顯存），所有 GPU tensor 都從這裡分配子區塊，避免大量 `cudaMalloc`/`cudaFree` 開銷。

#### 4.2 為每個 CPU tensor 分配 GPU 版並拷貝

```c
for (size_t i = 0; i < model->n_tensors; ++i) {
    struct ggml_tensor *cpu = model->tensors[i];

    // 只複製 shape/stride，建立同樣結構的 GPU tensor
    struct ggml_tensor *gpu = ggml_dup_tensor(cpu);
    ggml_backend_tensor_alloc(gpu, gpu);               // 把 data 指向 arena 中的 offset
    ggml_backend_tensor_copy(cpu, gpu);                // async cudaMemcpy Host→Device
    model->tensors[i] = gpu;                          // 替換指標，後續圖會直接使用 GPU tensor
}
```

- **`ggml_backend_tensor_copy`** 內部根據 `src->backend` / `dst->backend` 自動選擇 `cudaMemcpyAsync`（Host→Device）或相反方向。
- 若模型過大，可使用 **tensor split**：
  ```c
  ggml_backend_cuda_set_tensor_split(gpu, 0.5f);   // 把每個大 tensor 分成兩段搬入
  ```

#### 4.3 量化權重的即時解碼（GPU kernel）

- **4‑bit (`Q4_0`)** 範例 kernel（`kernel_dequant_q4_0.cu`）：

```c
__device__ static inline float dequant_q4_0(const block_q4_0 *blk, int i) {
    uint8_t q = (i < 8) ? (blk->qs[i] & 0x0F) : (blk->qs[i-8] >> 4);
    int8_t  v = (int8_t)q - 8;               // 4‑bit 轉成 [-8,7]
    return __half2float(__float2half(v * blk->d)); // d 為 scale
}
```

- 在 **`GGML_OP_MUL_MAT`** 的 CUDA 後端，若 `src0` 或 `src1` 為 `Q4_0`，會先 **launch** 這個解碼 kernel，把壓縮 block 轉成 **FP16**（或 **FP32**）暫存於 shared memory，然後直接交給 **cuBLAS GEMM**。
- **不會在 CPU 展開**，顯存需求降低 2‑3 倍，同時仍能利用 Tensor‑Core 加速。

> 其他量化 (`Q5_0`, `Q5_1`) 的解碼方式類似，只是每個 block 包含 5‑bit + 1‑bit 額外資訊，kernel 內部多一步位元抽取。

---

### 5️⃣ 推論執行 – `ggml_cgraph_compute`

```c
ggml_backend_set(gpu);                // 設定後端為 CUDA
ggml_cgraph_compute(&graph);          // 依拓撲順序執行所有算子
```

- **`ggml_cgraph_compute`** 會遍歷圖的 `nodes[]`，對每個節點根據 `op_type` 呼叫對應的 CUDA 後端實作：
  - `GGML_OP_MUL_MAT` → `cublasGemmEx`（支援 FP16/Tensor‑Core）
  - `GGML_OP_ADD`, `GGML_OP_MUL` → 自寫 element‑wise kernel
  - `GGML_OP_SILU`, `GGML_OP_GELU` → 自寫激活 kernel
  - `GGML_OP_NORM` → `cublasSnrm2` + kernel
  - `GGML_OP_ROPE` → kernel 內部完成 sin/cos 乘法

- 所有 **memcpy、kernel launch、cuBLAS 呼叫** 都排在同一個 **CUDA stream**，因此可以自動 **重疊**（kernel 執行 ↔︎ host‑to‑device copy）。

#### 5.1 取回 logits（host）

```c
float *logits_h = malloc(ggml_nbytes(logits));
ggml_backend_tensor_get(logits, logits_h, ggml_nbytes(logits)); // async Device→Host
```

- 只把 **最後一層的 logits** 複製回 CPU，因為後續的 **取樣**（top‑p、temperature）在 CPU 上完成，避免不必要的資料往返。

#### 5.2 取樣與迭代

```c
int next_token = llama_sample_top_p(lctx, logits_h, vocab_size, top_p, temperature);
llama_eval(lctx, &next_token, 1, n_ctx, n_batch);   // 重新建構圖、執行一次
```

- 每一次迭代只會 **重新建構一次圖**（包含新 token 的 embedding、KV cache 更新），其餘算子仍在 GPU 上執行。

---

### 6️⃣ 常見效能調校技巧

| 調校項目 | 操作方式 | 效果 |
|----------|----------|------|
| **Tensor Split** | `ggml_backend_cuda_set_tensor_split(gpu, 0.5f);` | 降低一次性顯存需求，允許更大模型在同一張卡上跑 |
| **Batch Size (`n_batch`)** | `llama_eval(..., n_batch)` | 把多個 token 合併成 **batched GEMM**，提升吞吐（視顯存而定） |
| **FP16 vs FP32** | 使用 `ftype = 1`（FP16）或量化模型 | cuBLAS 會自動使用 **Tensor‑Core**，速度提升 2‑3× |
| **CUDA Stream Priority** | `cudaStreamCreateWithPriority(&bc->stream, cudaStreamNonBlocking, -1);` | 把推論流設為高優先級，減少與其他 GPU 工作的競爭 |
| **Pinned Host Memory** | `cudaHostAlloc(&logits_h, size, cudaHostAllocDefault);` | `cudaMemcpyAsync` 速度更快，減少 host→device latency |
| **Kernel Launch Config** | `blockDim = 256`、`gridDim = (N+255)/256`（或根據矩陣大小微調） | 提升 SM 利用率，減少空閒時間 |
| **Overlap Compute & Transfer** | 只要使用同一 `gpu->stream`，`ggml_backend_tensor_copy` 已自動排隊 | GPU 可以在拷貝資料的同時執行前面的 kernel |
| **Profiling** | `nvprof ./main -m models/7B/ggml-model-q4_0.bin` 或 `nsight` | 找出最耗時的 kernel（通常是 `cublasGemmEx`）並調整 batch / split |

---

### 7️⃣ 完整程式範例（結合所有步驟）

```c
#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

int main(int argc, char **argv) {
    // -------------------------------------------------
    // 1️⃣ 初始化 ggml (CPU) 與 CUDA 後端 (GPU)
    // -------------------------------------------------
    struct ggml_init_params params = { .mem_size = 1ull << 30, .mem_buffer = NULL };
    struct ggml_context *ctx = ggml_init(params);
    ggml_backend_t gpu = ggml_backend_cuda_init(0);   // 第 0 張 GPU

    // -------------------------------------------------
    // 2️⃣ 載入模型 (CPU) – 支援量化、FP16、FP32
    // -------------------------------------------------
    struct llama_context *lctx = llama_init_from_file("models/7B/ggml-model-q4_0.bin", NULL);
    struct llama_model *model = &lctx->model;

    // -------------------------------------------------
    // 3️⃣ 把所有權重搬到 GPU
    // -------------------------------------------------
    // (可選) 設定顯存分割，避免一次性 OOM
    ggml_backend_cuda_set_tensor_split(gpu, 0.5f);   // 50% split

    for (size_t i = 0; i < model->n_tensors; ++i) {
        struct ggml_tensor *cpu = model->tensors[i];
        struct ggml_tensor *gpu_tensor = ggml_dup_tensor(cpu);   // 複製 shape/stride
        ggml_backend_tensor_alloc(gpu, gpu_tensor);            // 分配 arena 位置
        ggml_backend_tensor_copy(cpu, gpu_tensor);              // async Host→Device
        model->tensors[i] = gpu_tensor;                        // 替換指標
    }

    // -------------------------------------------------
    // 4️⃣ 推論迴圈
    // -------------------------------------------------
    const int n_predict = 128;          // 想產生的 token 數
    const int n_batch   = 8;            // 批次大小（可調整提升吞吐）
    int token = 1;                      // 假設已有 BOS token

    // 設定後端為 GPU
    ggml_backend_set(gpu);

    for (int i = 0; i < n_predict; ++i) {
        // 4‑A. 建立一次性圖（包含 KV cache、embedding、層運算）
        struct ggml_cgraph graph = llama_build_graph(lctx, n_batch);

        // 4‑B. 執行圖（所有算子在 GPU）
        ggml_cgraph_compute(&graph);

        // 4‑C. 取回 logits（只一次 memcpy）
        struct ggml_tensor *logits = graph.nodes[graph.n_nodes - 1];
        size_t logit_bytes = ggml_nbytes(logits);
        float *logits_h;
        cudaHostAlloc(&logits_h, logit_bytes, cudaHostAllocDefault);
        ggml_backend_tensor_get(logits, logits_h, logit_bytes);

        // 4‑D. CPU 端取樣得到下一個 token
        token = llama_sample_top_p(lctx, logits_h, lctx->model.hparams.n_vocab,
                                   0.9f, 0.8f);   // top‑p & temperature
        free(logits_h);

        // 4‑E. 把新 token 放回 context，進入下一輪
        llama_eval(lctx, &token, 1, lctx->model.hparams.n_ctx, n_batch);
    }

    // -------------------------------------------------
    // 5️⃣ 清理
    // -------------------------------------------------
    ggml_backend_free(gpu);
    ggml_free(ctx);
    llama_free(lctx);
    return 0;
}
```

**說明**
- 第 2 步完成 **模型載入**（CPU）與量化資訊的解析。
- 第 3 步把 **所有權重**（包括量化的壓縮 block）搬到 **GPU arena**，同時保留 `model.tensors[]` 中的 GPU 指標。
- 第 4 步的 `llama_build_graph` 產生 **算子 DAG**，`ggml_cgraph_compute` 依照後端（CUDA）執行：
  - **矩陣乘** → `cublasGemmEx`（自動使用 Tensor‑Core）
  - **量化解碼** → `kernel_dequant_q4_0`（在 GEMM 前即時展開）
  - **激活、正規化、ROPE** → 自寫 CUDA kernel
- 只把 **logits** 複製回 host，CPU 完成 **top‑p / temperature** 取樣，然後把新 token 再送回 `llama_eval` 形成下一輪的 KV cache。

---

### 8️⃣ 小結

1. **編譯**：開啟 `LLAMA_CUBLAS=1`、`GGML_CUDA=1`（或 Vulkan）即可得到支援 GPU 的執行檔。
2. **模型載入**：`llama_model_load_from_file` 讀檔頭 → 依 `ftype` 建立 **CPU** `ggml_tensor`（可能是量化的壓縮 block）。
3. **算子圖**：`llama_build_graph` 把 Transformer 層的所有算子組成 DAG。
4. **GPU 轉移**：`ggml_backend_cuda_init` 建立 device arena → `ggml_backend_tensor_copy` 把每個 tensor async 搬到 GPU。
5. **量化解碼**：在 `GGML_OP_MUL_MAT` 前自動 launch 解碼 kernel（如 `kernel_dequant_q4_0`），不在 CPU 展開。
6. **推論**：`ggml_cgraph_compute` 依拓撲順序執行，所有算子呼叫對應的 CUDA kernel（cuBLAS GEMM、自寫 kernel）。
7. **結果回傳**：只把 logits 複製回 host，CPU 完成取樣，形成下一輪的輸入。

只要依照上述步驟，您就能把 **llama.cpp** 的模型完整搬到 GPU，利用 CUDA（或 Vulkan）加速推論，得到比純 CPU 快上數十倍的效能。
