# Design: Tracer Implementation Details

**Created:** 2026-03-14
**Status:** Draft
**Related:** CRAG_DESIGN_TRACE_MANAGER.md

---

## Overview

這份文件記錄 Tracer 的具體實作細節，包括：
- 方向感知（find_callers vs find_callees）
- System Prompt 設計
- Fallback 策略
- 測試案例設計

---

## 1. 方向感知（Direction Awareness）

### 問題
一個問題可能同時需要往上找調用者（find_callers）和往下找被調用者（analyze_function_deeply）。

### 解決方案：Manager 意圖分解

**架構：Hybrid（LLM + Python）**
- **LLM 層 (Intent Parser)**：判斷用戶問題是否涉及路徑追蹤，提取關鍵實體
- **Python 層 (Orchestrator)**：狀態管理、任務派發、路徑比對

**Intent Schema:**
```json
{
  "type": "trace_path",
  "source": {"symbol": "A", "file": "main.c"},
  "target": {"symbol": "B", "file": "driver.c"},
  "strategy": "meet_in_the_middle"
}
```

### Tracer 保持原子化

Tracer 工具設計為單向且專注：
- `find_callers(func_name)`：往上找
- `find_callees(func_name)`：往下找

**不建議**：讓 Tracer 同時處理雙向

### Meet-in-the-middle 策略

當問題包含明確的「起點」和「終點」時：

```python
class TraceManager:
    def meet_in_the_middle(self, source: str, target: str):
        # 維護兩個邊界集合
        self.forward_frontier = set([source])
        self.backward_frontier = set([target])
        
        while True:
            # 派發正向追蹤
            forward_task = Task(entry_point=source, direction="down")
            forward_result = await self.run_tracer(forward_task)
            self.forward_frontier.update(forward_result.explored_nodes)
            
            # 派發反向追蹤
            backward_task = Task(entry_point=target, direction="up")
            backward_result = await self.run_tracer(backward_task)
            self.backward_frontier.update(backward_result.explored_nodes)
            
            # 碰撞檢測
            intersection = self.forward_frontier & self.backward_frontier
            if intersection:
                return self.reconstruct_path(intersection)
            
            # 更新邊界
            source = forward_result.furthest_node
            target = backward_result.furthest_node
```

---

## 2. System Prompt 設計

### 目標
確保 LLM **只輸出 JSON**，不要輸出解釋性文字。

### 完整範例

```markdown
# Role: Codebase Trace Expert
You are a highly precise tool for tracing code execution paths and dependencies. Your goal is to analyze a specific symbol or task and return a structured JSON response.

# Input Context:
- Current File: {{current_file}}
- Task: {{task_description}}
- Available Skills: {{skills}}

# Constraints:
- Output MUST be a single, valid JSON object following the TraceResult schema.
- Do NOT provide conversational filler.
- Do NOT include markdown blocks (like ```json).
- If you encounter a macro or dynamic call you cannot resolve, mark it in `unexplored_branches`.

# TraceResult Schema:
{
  "tracer_id": "string",
  "task_id": "string",
  "status": "done | need_help | dead_end | error",
  "explored_graph": [{"source": "string", "relation": "CALLS | DEFINES | USES", "target": "string"}],
  "unexplored_branches": [{"symbol": "string", "reason": "string", "location": "string"}],
  "findings": [{"key": "string", "value": "string", "severity": "info | warning"}],
  "conclusion": "string"
}

# Few-shot Example:
[Input] Trace function `init_driver` in `main.c`.
[Output]
{
  "tracer_id": "tracer_01",
  "task_id": "task_456",
  "status": "done",
  "explored_graph": [
    {"source": "main", "relation": "CALLS", "target": "init_driver"},
    {"source": "init_driver", "relation": "CALLS", "target": "pci_alloc_irq"}
  ],
  "unexplored_branches": [
    {"symbol": "pci_alloc_irq", "reason": "External library call, need L2 grep", "location": "pci.h"}
  ],
  "findings": [
    {"key": "IRQ_TYPE", "value": "MSI-X", "severity": "info"}
  ],
  "conclusion": "init_driver initiates PCI IRQ allocation and stops at library boundary."
}

# Error Handling:
- If the symbol is not found: set status="dead_end" and list attempted searches in findings.
- If the code is too complex: set status="need_help" and describe the obstacle.
```

### 後處理過濾器

```python
import re
import json

def sanitize_json_output(raw_output: str) -> dict:
    """Extract JSON from LLM output that may include prefixes/suffixes."""
    # Remove markdown blocks
    raw_output = re.sub(r'^```json\s*', '', raw_output)
    raw_output = re.sub(r'\s*```$', '', raw_output)
    
    # Find outermost braces
    match = re.search(r'\{.*\}', raw_output, re.DOTALL)
    if match:
        json_str = match.group(0)
        return json.loads(json_str)
    
    raise ValueError("No valid JSON found in output")
```

---

## 3. Fallback 策略（L1 → L2 → L3）

### 分層回退機制

| 層級 | 方法 | 優先級 | 描述 |
|------|------|--------|------|
| L1 | AST/LSP | 高 | 精準解析，Tree-sitter 或 clang |
| L2 | Heuristic Grep | 中 | 正則匹配函數名出現位置 |
| L3 | Knowledge Gap | 低 | 標記為 ambiguous，列出候選者 |

### Tracer 內部執行

```python
class CodeTracer:
    def execute(self, task: Task) -> TraceResult:
        # L1: AST Analysis
        result = self.run_ast_tool(task.symbol)
        
        # 判斷 L1 是否足夠
        if not result.found or result.has_dynamic_calls:
            # L2: Heuristic Grep
            heuristic_results = self.run_grep_tool(task.symbol)
            result.merge(heuristic_results)
            result.analysis_type = "heuristic_grep"
        
        if not result.found:
            result.status = "dead_end"
            result.warnings.append("Symbol not found in AST or grep")
        
        return result
    
    def run_ast_tool(self, symbol: str) -> AnalysisResult:
        """L1: Try precise AST parsing"""
        # 使用 Tree-sitter 或 clang-query
        pass
    
    def run_grep_tool(self, symbol: str) -> AnalysisResult:
        """L2: Fallback to grep/ripgrep"""
        import subprocess
        result = subprocess.run(
            ['rg', '-n', symbol, '--type', 'c'],
            capture_output=True, text=True
        )
        # 解析 grep 結果
        pass
```

### L1 失敗判斷條件

1. **AST 解析失敗**：語法錯誤或工具無法處理
2. **結果為空**：符號是宏生成或外部庫
3. **動態調用**：函數指針 `ops->start()` 無法靜態解析

### L3 (Knowledge Gap) 處理

當 L1 和 L2 都失敗時，返回：

```json
{
  "status": "need_help",
  "unexplored_branches": [
    {
      "symbol": "ops->start",
      "reason": "Dynamic dispatch via function pointer",
      "location": "driver.c:45",
      "candidates": ["nvme_start", "sata_start", "usb_start"]
    }
  ]
}
```

---

## 4. 測試案例設計

### 目錄結構

```
C-Trace-Benchmark/
├── basic_call/           # A -> B -> C 線性調用
│   └── main.c
├── cyclic_dependency/    # A -> B -> A 循環
│   └── cycle.c
├── macro_hidden/         # D_CALL(func) 宏隱藏
│   └── macro.c
├── function_pointer/     # struct.ops->start 函數指針
│   └── fptr.c
└── expected_results.json # 預期結果
```

### 測試案例定義

#### basic_call（線性調用）

```c
// main.c
void C() {}
void B() { C(); }
void A() { B(); }
int main() { A(); }
```

**預期行為：**
- `find_callees("A")` 返回 `[B]`
- `find_callees("B")` 返回 `[C]`
- `find_callees("C")` 返回 `[]`

#### cyclic_dependency（循環檢測）

```c
// cycle.c
void B();
void A() { B(); }
void B() { A(); }
```

**預期行為：**
- Tracer 從 A 開始，追蹤到 B
- B 調用 A，發現 A 已在路徑中
- 標記 `{"key": "cycle_detected", "value": "A->B->A"}`
- `status = "done"`

#### macro_hidden（宏處理）

```c
// macro.c
#define CALL_FUNC(f) f()
void helper() { /* ... */ }
void main() { CALL_FUNC(helper); }
```

**預期行為：**
- L1 AST 找不到 `CALL_FUNC` 的調用目標
- L2 Grep 找到 `helper()` 被調用
- 標記 `{"key": "source_type", "value": "macro_expansion"}`

#### function_pointer（函數指針）

```c
// fptr.c
struct ops {
    void (*start)(void);
};
void nvme_start() {}
void sata_start() {}
void init(struct ops* o) { o->start(); }
```

**預期行為：**
- L1 AST 只看到 `o->start()`
- 無法確定具體函數
- 標記 `candidates: ["nvme_start", "sata_start"]`

### 通過判斷標準

| 標準 | 描述 |
|------|------|
| Recall | `explored_graph` 包含所有預期節點 |
| Schema Validity | 輸出能被 `TraceResult.parse_obj()` 解析 |
| Cycle Detection | 循環路徑被正確標記 |
| Efficiency | Tool Calls 次數 ≤ 預期 |

---

## 5. 完整實作流程

```
用戶問題
    │
    ▼
┌─────────────────────────┐
│  Intent Parser (LLM)    │
│  - 提取 source, target  │
│  - 判斷 strategy        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  Trace Manager (Python) │
│  - 建立 Task Queue      │
│  - 派發給 Tracer        │
│  - 碰撞檢測             │
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐   ┌─────────┐
│Tracer#1 │   │Tracer#2 │
│(Forward)│   │(Backward)│
│         │   │         │
│L1: AST  │   │L1: AST  │
│L2: Grep │   │L2: Grep │
│L3: Gap  │   │L3: Gap  │
└────┬────┘   └────┬────┘
     │             │
     └──────┬──────┘
            │
            ▼
┌─────────────────────────┐
│  Manager 合併結果       │
│  - NetworkX 圖合併      │
│  - 衝突標記             │
│  - 生成 Mermaid 圖      │
└─────────────────────────┘
```