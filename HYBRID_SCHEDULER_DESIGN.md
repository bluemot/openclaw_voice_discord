# HybridScheduler 設計方案

## 目標
創建一個結合 TraceManager 和 StateMachineScheduler 優點的混合調度器。

## 架構設計

### 核心組件

```
┌─────────────────────────────────────────────────────────────┐
│                    HybridScheduler                           │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  StateMachine │  │ PriorityQueue │  │   Async Engine   │  │
│  │   (狀態管理)   │  │  (任務排序)   │  │    (異步執行)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │            │
│  ┌──────▼─────────────────▼────────────────────▼─────────┐  │
│  │              Task Orchestrator                        │  │
│  │         (任務分配、狀態轉換、結果收集)                   │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 關鍵特性

1. **異步狀態機**
   - 保留 StateMachineScheduler 的狀態管理
   - 使用 asyncio 支援並發工具調用

2. **優先級任務隊列**
   - 從 TraceManager 引入 heapq 優先級隊列
   - 根據任務相關性、深度、緊急性排序

3. **強制完成機制**
   - max_depth: 單個查詢最大深度
   - max_requests: 總請求數上限
   - timeout: 絕對時間限制
   - 達到任一限制必須返回答案

4. **智能搜尋策略**
   - 多階段搜尋：符號 → 正則 → 模糊
   - 失敗處理：記錄失敗並嘗試替代方案
   - 結果聚合：即使部分成功也返回答案

## 代碼實現方案

### 1. 核心類定義

```python
class HybridScheduler(EventStreamSubscriber):
    """
    Hybrid Scheduler combining StateMachine and TraceManager features.
    
    Features:
    - Async state machine (IDLE → EXPLORING → ANALYZING → VERIFYING → COMPLETED)
    - Priority queue for task scheduling
    - Depth/budget/timeout limits
    - Mandatory answer mechanism
    """
    
    def __init__(
        self,
        agent: Agent,
        max_depth: int = 10,
        max_requests: int = 20,
        timeout_seconds: int = 300,
        max_concurrent: int = 3
    ):
        # State machine (from StateMachineScheduler)
        self.state = SchedulerState.IDLE
        self.state_history: List[Tuple[SchedulerState, datetime]] = []
        
        # Priority queue (from TraceManager)
        self.task_queue: asyncio.PriorityQueue[PrioritizedTask] = asyncio.PriorityQueue()
        self.task_counter = 0
        
        # Limits
        self.max_depth = max_depth
        self.max_requests = max_requests
        self.timeout_seconds = timeout_seconds
        
        # Async control
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_count = 0
        self.depth_per_path: Dict[str, int] = {}
        
        # Results
        self.completed_tasks: List[TaskResult] = []
        self.partial_findings: List[Finding] = []
        
        # Graph for visualization (optional)
        self.exploration_graph = nx.DiGraph()
```

### 2. 任務優先級計算

```python
    def calculate_priority(self, task: Task) -> float:
        """
        Calculate task priority (lower = higher priority).
        
        Factors:
        - Semantic relevance to original query (highest weight)
        - Depth penalty (deeper = lower priority)
        - Time penalty (older tasks get slight boost)
        """
        # Semantic relevance score (0-100)
        relevance = self._calculate_semantic_relevance(task)
        
        # Depth penalty (exponential)
        depth_penalty = task.depth ** 2 * 10
        
        # Age bonus (prevent starvation)
        age_bonus = min(task.age_seconds * 0.1, 50)
        
        # Final score: lower is higher priority
        priority = 1000 - relevance + depth_penalty - age_bonus
        
        return max(priority, 0)
```

### 3. 強制完成機制

```python
    async def run_with_limits(self, user_input: str) -> AgentResult:
        """
        Run agent with strict limits.
        Guarantees an answer within timeout.
        """
        start_time = time.time()
        
        try:
            # Create main task
            main_task = Task(
                query=user_input,
                depth=0,
                priority=0
            )
            await self.task_queue.put(PrioritizedTask(0, self._get_counter(), main_task))
            
            # Process tasks with timeout
            async with asyncio.timeout(self.timeout_seconds):
                while not await self._should_stop():
                    # Get next task
                    prioritized = await self.task_queue.get()
                    task = prioritized.task
                    
                    # Check limits before execution
                    if self._check_limits(task):
                        logger.warning(f"[HybridScheduler] Limit reached, stopping")
                        break
                    
                    # Execute task
                    async with self.semaphore:
                        result = await self._execute_task(task)
                        self.request_count += 1
                        
                        # Collect findings even if partial
                        if result.findings:
                            self.partial_findings.extend(result.findings)
                        
                        # Spawn sub-tasks
                        await self._spawn_follow_up_tasks(result, task)
            
            # MUST return answer even if incomplete
            return self._compile_answer(user_input)
            
        except asyncio.TimeoutError:
            logger.warning(f"[HybridScheduler] Timeout after {self.timeout_seconds}s")
            return self._compile_answer(user_input, timeout_reached=True)
```

### 4. 智能搜尋策略

```python
    async def _execute_search(self, task: Task) -> SearchResult:
        """
        Multi-stage search with fallback strategies.
        """
        strategies = [
            # Stage 1: Symbol search (fastest, most accurate)
            lambda: self._hound_fast_search(task.symbol),
            
            # Stage 2: Regex pattern search
            lambda: self._regex_search(task.query),
            
            # Stage 3: Fuzzy text search
            lambda: self._fuzzy_search(task.query),
            
            # Stage 4: Global text search (last resort)
            lambda: self._global_text_search(task.query)
        ]
        
        for i, strategy in enumerate(strategies):
            try:
                result = await strategy()
                if result and result.has_matches:
                    logger.info(f"[HybridScheduler] Strategy {i+1} succeeded")
                    return result
            except Exception as e:
                logger.debug(f"[HybridScheduler] Strategy {i+1} failed: {e}")
                continue
        
        # All strategies failed - this is still a valid result
        return SearchResult(
            found=False,
            strategy="all_failed",
            message=f"Searched for '{task.query}' using {len(strategies)} strategies, no results found"
        )
```

### 5. 答案編譄

```python
    def _compile_answer(self, original_query: str, timeout_reached: bool = False) -> AgentResult:
        """
        Compile final answer from partial findings.
        Guaranteed to return something.
        """
        # Determine status
        if self.partial_findings:
            status = "completed_with_findings"
            answer = self._generate_answer_from_findings()
        elif timeout_reached:
            status = "timeout_no_results"
            answer = f"Search timed out after {self.timeout_seconds}s. No results found for: {original_query}"
        else:
            status = "completed_no_results"
            answer = f"Searched using {self.request_count} requests. No results found for: {original_query}"
        
        return AgentResult(
            status=status,
            answer=answer,
            findings=self.partial_findings,
            stats=self._get_stats(),
            exploration_graph=self._generate_mermaid() if self.exploration_graph else None
        )
```

## 遷移計劃

### Phase 1: 基礎建設 (1-2 天)
1. 創建 `HybridScheduler` 類框架
2. 實現優先級隊列和狀態機整合
3. 添加基本限制檢測

### Phase 2: 搜尋策略 (2-3 天)
1. 實現多階段搜尋策略
2. 添加失敗處理和重試機制
3. 測試各種搜尋場景

### Phase 3: 整合測試 (2-3 天)
1. 替換現有 `StateMachineScheduler`
2. 運行回歸測試
3. 驗證 RTL8852BU 等大型專案

### Phase 4: 優化 (1-2 天)
1. 性能調優
2. 添加監控和日誌
3. 文檔更新

## 風險評估

### 高風險
- **架構變更複雜性** - 需要仔細測試避免引入新 bug
- **性能影響** - 異步可能帶來額外開銷

### 中風險
- **學習曲線** - 團隊需要理解新架構

### 低風險
- **向後兼容性** - 可以逐步遷移，保留舊調度器作為後備

## 建議下一步

1. **創建分支** - `feature/hybrid-scheduler`
2. **實現 MVP** - 先實現核心功能，驗證概念
3. **對比測試** - 與現有調度器性能對比
4. **逐步遷移** - 先在小專案測試，再全面部署

要我開始實現這個 HybridScheduler 嗎？我可以先創建一個 MVP 版本驗證概念。
