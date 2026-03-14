# CRAG 專案進度記錄

**最後更新:** 2026-03-13 12:00 UTC

---

## 專案概述

CRAG (Code-Graph RAG) 是一個代碼理解工具，使用圖數據庫 + LLM 來分析代碼庫。

**位置:** `/home/ubuntu/workspace/crag`

**核心流程:**
```
用戶問題 → Orchestrator → Scheduler → Architect Agent
                ↓
           狀態機管理 (IDLE → EXPLORING → ANALYZING → VERIFYING → COMPLETED)
                ↓
           技能注入 (根據項目語言/關鍵詞)
                ↓
           工具調用 (hound_fast_search, analyze_function_deeply, etc.)
                ↓
           圖數據庫查詢 (Neo4j) + 文件讀取
                ↓
           結果匯總 → 驗證 → 返回答案
```

---

## 架構組件

### 1. 索引器 (Indexer)
- **位置:** `indexer/` 目錄
- **功能:** 解析代碼文件，提取符號定義/引用/調用關係
- **支持語言:** C, C++, JavaScript, TypeScript, Python, Rust, Go, Scala, Java, Lua, **Objective-C** (2026-03-13 新增)
- **後端:** 使用 tree-sitter 解析語法，Hound (ripgrep) 做符號搜索

### 2. 圖數據庫 (Neo4j)
- **位置:** Neo4j Docker 容器
- **端口:** 7474 (HTTP), 7687 (Bolt)
- **存儲:** 節點 (文件/符號/定義/引用) + 關係 (CONTAINS/CALLS/REFERENCES)

### 3. 查詢引擎 (Query Engine)
- **位置:** `query_engine/` 目錄
- **功能:** 
  - `hound_fast_search`: 符號搜索
  - `global_text_search`: 文本搜索
  - `graph_query`: 圖遍歷查詢

### 4. Orchestrator (調度器)
- **位置:** `orchestrator/` 目錄
- **功能:** 管理 Agent 會話，處理狀態機
- **狀態:** IDLE → EXPLORING → ANALYZING → NAVIGATING → VERIFYING_COMPLETION → COMPLETED

### 5. Agent (分析器)
- **位置:** `agent/` 目錄
- **模型:** 支持 Ollama 本地模型 + 雲端 API
- **功能:** 分析代碼結構，生成調用鏈

### 6. Scheduler (核心組件)
- **位置:** `codebase_rag/services/scheduler.py`
- **功能:** 
  - 狀態機管理 (AnalysisState)
  - 上下文壓縮 (ContextCompressor)
  - 循環檢測 (JunctionLedger)
  - 技能注入 (SkillsRegistry)
  - 驗證攔截 (VERIFICATION CHECKPOINT)

---

## 階段性功能路線圖

### Phase 1: Foundation ✅ 已完成
- [x] 1.1 Environment & CLI
- [x] 1.2 CFG Visualization

### Phase 2: C Driver Intelligence ✅ 已完成
- [x] 2.1 Schema & Isolation (Multi-Repo Support)
- [x] 2.2 Indirect Dispatch (MLTA for Function Pointers)
- [x] 2.3 UX Polish
- [x] 2.4 Data-Flow (Reaching Definitions)
- [x] 2.5 Hybrid Search & Router

### Phase 2.5: Skeleton Optimization ✅ 已完成
- [x] Massive Repo Ingestion (8852BU)
- [x] O(N*M) Tree-sitter Hang Fixes
- [x] 120b Model Prompt Pruning
- [x] Full Repo Backup/Restore

### Phase 3: Multi-Agent Orchestration ✅ 已完成
- [x] Task 3.1: The "Hound" (Caller Finder Agent)
- [x] Task 3.2: The "Architect" (Logic Interpreter Agent)
- [x] Task 3.3: Role-Based Communication Protocol
- [x] Task 3.4: Performance Tuning & Parallelism

### Phase 4: Cognitive Hardening ✅ 已完成
- [x] 4.0: State Machine & Interceptor
- [x] 4.1: Unstructured Exploration, Callbacks, & Context Resilience
- [x] 4.2: Robust Semantic Branch Guard
- [x] 4.3: GPU Driver Analysis & Timeout Investigation
- [x] 4.4: Minimum Model Size Testing (8B+ viable)

---

## 技能系統 ✅ (2026-03-12 完成)

### 架構

```
codebase_rag/skills/
├── __init__.py      # 導出 SkillsRegistry
├── schemas.py       # SkillMetadata, Skill 數據模型
└── manager.py       # SkillsRegistry 類 (加載/匹配/格式化)

skills/              # 技能文件目錄 (TOML frontmatter + Markdown)
├── linux_wifi_driver.md    # priority: 20
├── gpu_computing.md        # priority: 15
├── c_cpp_tracing.md        # priority: 15
├── python_tracing.md       # priority: 15
├── python_async.md         # priority: 15
├── javascript_tracing.md   # priority: 15
├── go_tracing.md           # priority: 15
├── rust_tracing.md         # priority: 15
├── java_tracing.md         # priority: 15
├── csharp_tracing.md       # priority: 15
├── swift_tracing.md        # priority: 15
└── ruby_tracing.md         # priority: 15
```

### 技能文件格式

```markdown
+++
name = "Skill Name"
description = "What this skill helps with"
keywords = ["keyword1", "keyword2"]
project_types = ["c", "cpp", "python"]
priority = 20
+++

### Analysis Strategy
(實際內容...)
```

### 匹配邏輯

```python
# 檢測順序:
1. ingestor.language (如果已設置)
2. path_tracker 中最近分析的文件擴展名
3. 項目配置文件 (pyproject.toml, Cargo.toml, package.json, etc.)

# 匹配規則:
- 關鍵詞匹配: query 中包含技能關鍵詞
- 項目類型匹配: project_type 在技能的 project_types 列表中
- 按優先級排序，最多返回 3 個技能
```

### 已創建的技能 (12 個)

| 技能 | Priority | 項目類型 | 關鍵技術 |
|------|----------|----------|----------|
| Linux WiFi Driver Analysis | 20 | c, cpp | TX/RX 分離、事件分發器、回調發現、container_of |
| GPU Computing Analysis | 15 | c, cpp, rust | 內存分配、Kernel 啟動、數據傳輸、Pipeline |
| C/C++ Code Tracing | 15 | c, cpp | 指針賦值、宏展開、函數指針表、container_of |
| Python Code Tracing | 15 | python | 裝飾器、動態屬性、元類、import |
| Python Async Analysis | 15 | python | async/await、事件循環、Task |
| JavaScript/TypeScript Tracing | 15 | js, ts | Promise、事件、原型鏈、this 綁定 |
| Go Code Tracing | 15 | go | Goroutine、Channel、Interface、Defer |
| Rust Code Tracing | 15 | rust | 所有權、生命週期、Result/Option、async |
| Java Code Tracing | 15 | java | 類繼承、Interface、Executor、Stream |
| C#/.NET Code Tracing | 15 | csharp | async/Task、LINQ、Event、Extension |
| Swift Code Tracing | 15 | swift | async/await、Protocol、Optional、Extension |
| Ruby Code Tracing | 15 | ruby | Block、Mixin、元編程、method_missing |

### 添加新技能

在 `skills/` 目錄創建 `.md` 文件：

```markdown
+++
name = "My New Skill"
keywords = ["keyword1", "keyword2"]
project_types = ["python", "rust"]
priority = 15
+++

### Analysis Strategy

1. **Pattern 1**: Description...
2. **Pattern 2**: Description...

### Key Patterns

\`\`\`language
// Example code
\`\`\`

### Search Strategy

- For X: search for `pattern`
- For Y: search for `pattern2`
```

---

## 已解決的問題

### 問題 1: Scheduler 驗證挑戰導致上下文丟失 ✅ 已修復
- **現象:** Architect 說"我看完了"，Scheduler 推送驗證挑戰後方向走偏
- **原因:** 驗證 prompt 沒有保留原始問題上下文
- **修復:**
  - `VERIFICATION CHECKPOINT` prompt 現在包含 `ORIGINAL TASK`
  - 添加 `_last_notified_state` 避免重複注入狀態指令
  - 添加 `_readme_injected` 重置確保新問題獲得乾淨上下文

### 問題 2: 硬編碼技能注入導致上下文污染 ✅ 已修復
- **現象:** 問 GPU 問題卻注入 Linux WiFi 驅動技能
- **原因:** `linux_wifi_driver.md` 被硬編碼無條件注入
- **修復:** 
  - 創建 `SkillsRegistry` 動態匹配系統
  - 根據關鍵詞 + 項目類型自動匹配技能
  - 新增 12 個語言技能

### 問題 3: 新問題開始時上下文不乾淨 ✅ 已修復
- **現象:** 新問題帶有上一個問題的上下文殘留
- **原因:** `reset()` 方法不完整
- **修復:**
  - `reset()` 現在重置 `_readme_injected = False`
  - `reset()` 現在重置 `_last_notified_state = None`
  - 動態技能注入替代硬編碼

### 問題 4: Metal 後端索引 (Objective-C) ✅ 已修復 (2026-03-13)
- **現象:** `ggml-metal.m` 文件中的符號未被正確索引
- **原因:** `.m` (Objective-C) 文件未被 tree-sitter 支持
- **修復:**
  1. 安裝 `tree-sitter-objc` 依賴
  2. 在 `language_config.py` 新增 `objective-c` 配置
  3. 在 `parser_loader.py` 新增 Objective-C 載入器

---

## 技術設計規範

### Phase 2.1: Multi-Repo Stability (node_hash Strategy)

**問題:** 多倉庫數據污染，節點 ID 碰撞

**解決方案:** `node_hash` 策略
```python
node_hash = sha256(f"{repo_id}:{label}:{business_key}")
```

**Schema 更新:**
- 每個節點添加 `node_hash` 屬性
- 使用 `CONSTRAINT ON (n:Label) ASSERT n.node_hash IS UNIQUE`
- `MERGE` 語句使用 `node_hash` 作為主鍵

### Phase 2.2: MLTA (Multi-Layer Type Analysis)

**問題:** 間接調用（函數指針）無法追蹤

**解決方案:** Struct-Field Matching 算法
```c
// 索引階段：掃描 struct initializer
static const struct file_operations my_ops = {
    .read = my_driver_read,  // 建立 ("file_operations", "read") -> "my_driver_read"
};

// 查詢階段：匹配調用點
filp->f_op->read(...)  // 匹配到 my_driver_read
```

**Graph Schema:**
```cypher
(:Function)-[:POSSIBLE_CALL {reason: "MLTA", field: "read"}]->(:Function)
```

### Phase 2.4: Data-Flow Analysis

**新增邊類型:**
- `[:REACHES]` - Intra-procedural Data Flow
- `[:ASYNC_FLOW]` - Inter-procedural Async Queue (Producer/Consumer)

### Phase 2.5: Hybrid Search & Router

**架構:**
```
用戶查詢 → SearchRouter (Python API)
                ↓
           判斷意圖 (Vector/Graph/Hybrid)
                ↓
           Vector: Qdrant 語義搜索
           Graph: Memgraph 圖遍歷
           Hybrid: 組合查詢
                ↓
           返回結構化結果 (Pydantic Models)
```

**禁止:**
- Agent 直接使用原始 Cypher 查詢

### Phase 3: Multi-Agent Orchestration

**兩個 Agent:**
1. **The Hound** (Caller Finder)
   - 快速本地模型 (Qwen-Coder)
   - 僅搜索工具，不解釋代碼
   - 輸出 JSON 格式

2. **The Architect** (Logic Interpreter)
   - 大型智能模型 (GPT-4o/DeepSeek-V3)
   - 任務規劃和結果解釋
   - 委託搜索任務給 Hound

**通信協議:**
- `consult_hound` 工具作為橋樑
- JSON 報告格式標準化
- 角色分離日誌 (`architect_io.log`, `hound_io.log`)

### Phase 4: Cognitive Hardening

**核心組件:**

1. **StateMachineScheduler**
   - 狀態: IDLE → EXPLORING → ANALYZING → NAVIGATING → VERIFYING → COMPLETED
   - 強制狀態轉換，防止無限循環

2. **ContextCompressor**
   - 使用 tiktoken 監控上下文限制
   - 摘要舊內容，保留 `## ANALYTICAL ANCHOR`

3. **JunctionLedger**
   - 狀態指紋 (hashing)
   - 自動回溯到未探索的分支點

4. **Verification Interceptor**
   - `submit_final_answer` + `confirm_completion` 雙工具機制
   - 強制驗證原始目標

---

## 驗證成功的案例

### llama.cpp GPU 內存管理分析 ✅
**問題:** "How does llama.cpp manage GPU memory for tensors?"
**結果:** CRAG 成功追蹤完整流程:
1. Backend 註冊: `ggml_backend_cuda_buffer_type()`
2. Tensor 分配: `ggml_backend_cuda_alloc_tensor` → `cudaMalloc`
3. 數據傳輸: `cudaMemcpyAsync` (host ↔ device)
4. Memory Pooling: 每個 buffer 維護 free-list

### ONNX Runtime 測試 ✅
**問題:** GPU 執行提供者如何註冊？
**結果:** 成功分析出註冊流程

### NVIDIA GPU Kernel Module 分析 ✅
**結果:** Agent 正確追蹤:
```
用戶空間 → DRM GEM import ioctl → ImportMemory (KAPI) → nvRmApiControl → GPU
```

---

## 模型大小測試結果

| 模型 | 大小 | 使用核心工具 | 正確追蹤 | 備註 |
|------|------|--------------|----------|------|
| rnj-1:8b (本地) | 8B | ❌ | ❌ | 無法理解複雜 prompt |
| rnj-1:8b-cloud | 8B | ✅ | ✅ | **最小可用模型** |
| gpt-oss:20b-cloud | 20B | ✅ | ✅ | 推薦配置 |
| gpt-oss:120b-cloud | 120B | ✅ | ✅ | 最佳性能 |

**結論:** 8B 參數模型在雲端版本可以使用，關鍵是模型質量/微調。

---

## 關鍵文件路徑

```
/home/ubuntu/workspace/crag/
├── crag                    # 主入口腳本
├── indexer/                # 索引器模塊
├── query_engine/           # 查詢引擎
├── orchestrator/           # 調度器
├── agent/                  # Agent 模塊
├── codebase_rag/
│   ├── main.py            # 主程式
│   ├── config.py          # 配置
│   ├── scheduler.py       # 狀態機調度器
│   ├── skills/            # 技能系統
│   │   ├── manager.py     # SkillsRegistry
│   │   └── schemas.py     # 數據模型
│   └── ...
├── config/
│   └── orchestrator.json   # orchestrator 配置
├── log/                    # 日誌目錄
│   ├── session.log        # 會話日誌
│   ├── architect_io.log   # Architect 日誌
│   └── hound_io.log       # Hound 日誌
├── repos/                  # 代碼倉庫
│   └── llama.cpp/         # llama.cpp 源碼
└── skills/                 # 技能文件目錄
    ├── python_tracing.md
    ├── c_cpp_tracing.md
    └── ... (12 個技能)
```

---

## 測試命令參考

```bash
# 建立 llama.cpp 索引
cd /home/ubuntu/workspace/crag
./crag index /home/ubuntu/workspace/repos/llama.cpp

# 測試問題
./crag chat llama.cpp -q "GPU memory allocation" --orchestrator ollama:gpt-oss:20b-cloud --no-confirm

# 查看日誌
tail -f log/session.log

# 檢查 orchestrator 配置
cat config/orchestrator.json
```

---

## 待解決問題

### 問題 A: 雲端模型 API 錯誤後恢復
- **現象:** API 返回錯誤後，Agent 可能走向無關搜索
- **狀態:** 需要更多測試

### 問題 B: 廣泛問題處理
- **現象:** 問「主要功能組件有哪些？」時，Agent 無法理解任務
- **原因:** Agent 的系統 prompt 設計為深度追蹤，非高層架構概覽
- **建議:** 需要不同的 prompt 或專門的「架構分析」模式

---

## 待辦事項

- [ ] 正式 Data-Flow Pass (從 regex/heuristic 到 reaching-definitions)
- [ ] Producer-Consumer Queue Tracing (enqueue → thread worker)
- [ ] 測試更多邊緣案例

---

## 歷史版本記錄

| 日期 | 版本 | 主要變更 |
|------|------|----------|
| 2026-03-13 | 1.0 | 整合所有記憶文件到 PROGRESS_GLOBAL.md |
| 2026-03-12 | 0.9 | 完成 12 個語言技能系統 |
| 2026-03-10 | 0.8 | GPU 內存管理分析驗證成功 |
| 2026-03-02 | 0.7 | 模型大小測試，8B 可用 |
| 2026-02-28 | 0.6 | Phase 4.2 語義分支保護 |
| 2026-02-27 | 0.5 | Phase 4.1 上下文壓縮 |
| 2026-02-24 | 0.4 | Phase 4.0 狀態機調度器 |
| 2026-02-21 | 0.3 | Phase 3.8 循環檢測 |
| 2026-02-17 | 0.2 | Phase 3 Multi-Agent 架構 |
| 2026-02-01 | 0.1 | Phase 1 Foundation |