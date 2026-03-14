# Gemini CLI 討論摘要

**日期:** 2026-03-14
**主題:** Trace Manager 架構設計決策

---

## 討論概覽

與 Gemini CLI 進行了四輪討論，涵蓋以下議題：

1. Max Workers（併發 Tracer 數量）
2. Priority Queue（任務優先級）
3. Termination Conditions（終止條件）
4. Timeout 與錯誤處理
5. Graph 結構存儲
6. 錯誤節點處理
7. JSON Schema 驗證
8. 並行 Tracer 結果衝突
9. 開發優先級與 MVP 範圍
10. 測試策略

---

## 第一輪：核心問題

### 1. Max Workers
**Gemini 建議:** 動態 Worker Pool (Elastic Concurrency)
- `min_workers=1`, `max_workers=5~10`
- 根據 API Rate Limit (TPM/RPM) 動態調整
- 使用 `asyncio.Semaphore` 控制

**風險:** 併發過高觸發 HTTP 429
**緩解:** TokenBucket + Exponential Backoff

### 2. Priority Queue
**Gemini 建議:** Best-First Search (啟發式優先級)
- 公式: `Score = (Depth_Weight * Depth) - (Semantic_Relevance) + Penalty`
- 語義相關性: 目標關鍵字在分支出現的頻率
- 深度懲罰: 越深越不優先，防止 DFS 陷阱

**風險:** 評分函數設計不良導致關鍵路徑被埋沒
**緩解:** 發現高價值 finding 時動態提升子分支優先級

### 3. Termination Conditions
**Gemini 建議:** 多重防線終止策略
1. **完成條件**: findings 足以回答問題
2. **最大深度限制**: `MAX_DEPTH = 15`
3. **循環檢測**: 節點或邊已訪問
4. **全局限制**: `MAX_API_CALLS = 50`
5. **找不到終點**: Priority Queue 為空時返回 Partial_Trace

### 4. Timeout & 錯誤處理
- **超時**: 45-60 秒
- **重試**: `MAX_RETRIES = 2`，Exponential Backoff
- **無效 JSON**: 使用 LLM API 的 Structured Output / JSON Mode
- **失敗兩次**: 標記為 `Error_Node`，繼續其他分支

### 5. 結果合併
- **節點合併**: 使用 `Filepath:Function` 作為唯一鍵
- **衝突處理**: 保留原始文本，標記 `conflict: true`
- **呈現**: Manager 修剪圖 → Mermaid.js 視覺化 → Summarizer LLM 摘要

---

## 第二輪：追問細節

### Q1: 語義相關性評分
**問題:** 方案 A (embedding) vs B (正則) vs C (不做)
**Gemini 建議:** **方案 B + C 混合**
- 不用 embedding，開銷太大
- 用「字符串匹配 + 深度懲罰」，零 Token 消耗
- 關鍵字匹配給權重加分，深度給懲罰

### Q2: 循環檢測實作
**問題:** 基於節點、邊還是路徑？
**Gemini 建議:** **雙重檢測機制**
- **Global Seen Nodes (去重)**: 避免重複探索
- **Path History (斷環)**: 防止無限循環
- 「節點」用於不浪費 Token，「路徑」用於保證不陷入死循環

### Q3: Summarizer 必要性
**問題:** 何時使用 LLM 摘要？
**Gemini 建議:** **默認 Mermaid 圖，按需激活 Summarizer**
- 工程師更信任原始調用路徑圖
- LLM 摘要容易幻覺
- 只有用戶問「解釋」「總結」時才激活

### Q4: Token 預算追蹤
**問題:** Token 計數 vs API 次數計數？
**Gemini 建議:** **方案 B (API 總調用次數)**
- Token 計數要等 API 回傳，實作複雜
- API 次數簡單直觀
- 設 `max_total_requests = 50`，剩餘 < 20% 時停止探索新分支

---

## 第三輪：實作細節

### Q5: Graph 存儲
**問題:** NetworkX vs Memgraph？
**Gemini 建議:** **混合方案**
- **Runtime**: NetworkX (內存，快速)
- **Persistence**: 異步鏡像到 Memgraph
- Memgraph 定位為「專案百科全書」，Trace 過程用 NetworkX

### Q6: 錯誤節點處理
**問題:** Error_Node 是關鍵節點怎麼辦？
**Gemini 建議:** **標記阻斷 + Fallback**
1. 擴大上下文重試
2. 換模型重試
3. 改用 grep 模糊搜索
4. 最終報告包含 `Uncertainties` 章節

### Q7: JSON Schema 驗證
**問題:** Pydantic 驗證 vs 修復 Agent？
**Gemini 建議:** **方案 C (Pydantic AI 內建 Result Schema)**
- 框架已封裝結構化輸出處理
- 驗證失敗自動丟回 LLM 修正
- 超過重試次數才標記 `Schema_Error`

### Q8: 結果衝突處理
**問題:** 不同 Tracer 對同一代碼有不同「事實」？
**Gemini 建議:** **方案 B + C (細節優先 + 證據保留)**
- 信息量大的優先 (`Buffer*` > `void*`)
- 完全矛盾時保留兩個版本，加 `conflict: true` 標籤
- 關鍵路徑有衝突時啟動「仲裁者 Agent」

---

## 第四輪：開發優先級

### Q1: Priority Queue 何時實作？
**Gemini 建議:** **與 NetworkX 同步實作**
- PQ 是搜索算法核心驅動，不是額外功能
- 邏輯簡單，直接在 NetworkX 整合時加入

### Q2: 循環檢測何時實作？
**Gemini 建議:** **第一版 MVP 必須包含**
- 循環是常態，無去重會無窮迴圈
- 屬於「穩定性基礎」

### Q3: MVP 核心功能（1 週內）

**必須有:**
1. Schema 定義 (Pydantic)
2. NetworkX + Priority Queue
3. 循環檢測 (Global Set + Path Stack)
4. Knowledge Gap 回報

**可以延後:**
1. 衝突處理 (先用 Last-write-wins)
2. 持久化存儲 (先在內存執行)
3. 視覺化圖表 (先輸出 JSON/Markdown)

### Q4: 測試策略優先級
1. **單元測試** (Priority 1): NetworkX、PQ、循環檢測
2. **整合測試** (Priority 2): Tracer + Manager JSON 交換
3. **端到端測試** (Priority 3): 完整追蹤流程

---

## 最終開發順序

```
Schema 定義 (Pydantic TraceResult)
       ↓
NetworkX + Priority Queue + 循環檢測 (核心包)
       ↓
Knowledge Gap 邏輯
       ↓
單元測試
       ↓
MVP 發布
```

---

## 關鍵代碼片段

```python
class TraceManager:
    def __init__(self, max_concurrent: int = 5, max_depth: int = 15):
        self.graph = nx.DiGraph()
        self.visited_nodes: Set[str] = set()
        self.pending_queue: List[Tuple[float, int, Task]] = []  # heapq
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_depth = max_depth
        self.request_count = 0
        self.max_requests = 50
    
    def calculate_priority(self, task: Task) -> float:
        """Lower score = higher priority"""
        keyword_score = 0  # 簡單字符串匹配
        depth_score = task.depth * 5  # 深度懲罰
        return depth_score - keyword_score
    
    def is_cycle(self, node: str, path: List[str]) -> bool:
        """Path-based cycle detection"""
        return node in path
    
    async def process_result(self, result: TraceResult):
        # 1. Sync to NetworkX
        for edge in result.explored_graph:
            self.graph.add_edge(edge.source, edge.target)
        
        # 2. Dedupe and queue new tasks
        for branch in result.unexplored_branches:
            if branch.function not in self.visited_nodes:
                if branch.depth < self.max_depth:
                    priority = self.calculate_priority(branch)
                    heapq.heappush(self.pending_queue, (priority, self.task_counter, branch))
```

---

## 總結

Gemini CLI 的核心觀點：
1. **Manager = 狀態庫**，LLM = 探測器
2. **簡單啟發式優先**，不用複雜 embedding
3. **雙重循環檢測**，節點去重 + 路徑斷環
4. **API 次數計數**，簡單有效
5. **MVP 先求穩**，進階功能延後