# Gemini Answer: llama.cpp Model Loading and GPU Inference

## 問題
請問 llama.cpp 如何載入 model 處理運算子和模型參數，然後放入 GPU 進行推論？

## Gemini 回答

我將為您詳細分析 `llama.cpp`（核心基於 `ggml` 庫）從模型載入到 GPU 推論的完整技術流程。

### 1. GGUF 模型載入 (GGUF Model Loading)
GGUF (GGML Universal File Format) 是 `llama.cpp` 的專用格式，設計目標是「快速映射」與「版本相容」。

*   **Header 解析**：載入時，`llama.cpp` 首先讀取文件頭，獲取模型的超參數（Hyperparameters，如 `n_layer`, `n_head`, `n_embd` 等）以及 Tensor 的索引表。
*   **MMap (Memory Mapping)**：這步是關鍵。`llama.cpp` 預設使用 `mmap` 將模型文件直接映射到進程的虛擬地址空間。這意味著：
    *   不需要一次性將數 GB 的模型讀入記憶體。
    *   OS 會根據推論需求自動分頁載入。
    *   如果 Tensor 需要放入 GPU，則會從這個映射位址拷貝到 VRAM。

### 2. 運算子註冊與圖構建 (Operator Registration & Graph Building)
`ggml` 是一個張量運算庫，它將推論抽象為一個 **運算圖 (Computational Graph)**。

*   **c-graph 構建**：在推論開始前，`llama.cpp` 會根據 Transformer 架構建立一個 `ggml_cgraph`。
*   **運算子宣告**：例如 `ggml_mul_mat(ctx, a, b)`。這並不會立即執行運算，而是將一個「節點 (Node)」加入圖中。
*   **後端派發 (Backend Dispatch)**：每個運算子（如矩陣乘法 `MUL_MAT`）在 `ggml` 中都有多種實現（C 原生、AVX、CUDA、Metal 等）。系統會根據編譯選項和運行設備，在執行時選擇對應的 Kernel。

### 3. 模型參數處理 (Parameter Handling)
*   **量化處理**：GGUF 支持 Q4_K_M, Q8_0 等量化格式。在載入時，權重以量化狀態存在。
*   **Tensor 分配**：模型中的每個權重矩陣（如 `wq`, `wk`, `wv`）都被封裝為 `ggml_tensor` 結構，包含維度、步長 (stride) 和數據指標。
*   **權重轉換**：如果是 GPU 推論，部分量化權重會在傳輸到 GPU 前或在 GPU 內部的 Kernel 中進行解壓/轉換。

### 4. GPU 記憶體分配 (GPU Memory Allocation)
`llama.cpp` 使用了高效的快取機制來管理 VRAM：

*   **KV Cache 分配**：推論前會預先在 VRAM 分配一大塊空間作為 Key-Value Cache，用於儲存 Context 信息，避免重複計算。
*   **Scratch Buffer**：`ggml` 會分配一兩塊較大的連續 GPU 記憶體（稱為 Scratch），所有的中間計算結果（Activations）都會循環複用這塊空間，極大地減少了頻繁申請/釋放 VRAM 的開銷。
*   **Offloading (層遷移)**：用戶可以指定 `-n_gpu_layers`。`llama.cpp` 會按層將 Tensor 數據從系統內存拷貝到 GPU VRAM (`cudaMemcpy`)。

### 5. 推論執行流程 (Inference Execution)
當輸入一個 Token 時，執行路徑如下：

1.  **Token Embedding**：將 Input ID 轉換為向量。
2.  **Graph Setup**：針對目前的 Sequence Length 更新運算圖。
3.  **Backend Compute**：呼叫 `ggml_backend_graph_compute()`。
    *   **CUDA Kernel 啟動**：如果是矩陣乘法，會呼叫優化過的 CUDA Kernel（如 `cuBLAS` 或 `ggml` 自帶的 `dequantize + mul_mat` 融合算子）。
    *   **同步與串聯**：層與層之間依序執行，結果存回 Scratch Buffer。
4.  **Logits 提取**：最後一層輸出經過 Norm 後，計算出 Logits（各個詞的機率分佈）。
5.  **Sampling**：在 CPU 或 GPU 上進行採樣（Top-P, Temp 等），得到下一個 Token。

### 總結技術亮點
*   **Unified Buffer Management**：通過 `ggml_allocr` 統一管理 CPU/GPU 記憶體，實現了靈活的 Offloading。
*   **Dequantization Kernels**：其 CUDA Kernel 直接在 GPU 上邊解壓量化權重邊做運算，這讓低 VRAM 設備也能跑大模型。
*   **Zero-copy (部份)**：利用 `mmap` 配合 GPU 異步拷貝，極大化了加載速度。
