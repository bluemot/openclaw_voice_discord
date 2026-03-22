# CRAG + OpenHands 協作改進記錄

## 協作流程
1. Jarvis 先改代碼 → 記錄
2. Gemini 檢查和修改 → 記錄
3. 寫單元測試 → 記錄
4. Jarvis 跑測試 → 記錄結果
5. Commit
6. 循環直到完成

## 改進目標
基於 OpenHands 架構分析，我們要改進 CRAG 的以下方面：

### Phase 1: Action/Observation 模式 ✅ COMPLETED
- [x] 創建 `codebase_rag/events/` 目錄
- [x] 定義基礎 Action/Observation 類
- [x] 創建具體 Action/Observation 類型
- [x] 添加序列化和 EventStream
- [x] 寫單元測試並通過
- [x] Commit

### Phase 2: 整合到現有系統 🔄 IN PROGRESS
- [ ] 修改 tool calls 返回 Action/Observation
- [ ] 添加超時機制
- [ ] 改進錯誤處理
- [ ] 測試整合

### Phase 3: EventStream 架構
- [ ] 將 EventStream 整合到主流程
- [ ] 實現異步處理
- [ ] 添加事件持久化

---

## Round 4: Phase 2 - 整合 Action/Observation 到現有系統 ✅ COMPLETED

### 目標
將現有的 tool calls（如 `hound_fast_search`, `analyze_function_deeply`）遷移到新的 Action/Observation 模式。

### 修改內容
1. **修改 `hound_fast_search`**:
   - 現在會返回 `SearchObservation` 對象
   - 自動建立 Graph 節點（Next-Step Injection + Graph Auto-Create）
   - 支持完整的錯誤處理

2. **修改 `analyze_function_deeply`**:
   - 返回 `TraceObservation` 對象
   - 支持 Trace Protocol 轉換
   - 完整的調用鏈追蹤

3. **更新 `scheduler.py`**:
   - 攔截 tool calls 並建立 CALLS 邊
   - 支持 EventStream 整合（未來擴展）

### 測試結果
- **7 個單元測試通過** ✅
- 手動測試 `crag chat llama.cpp` 成功
- Agent 現在會正確呼叫 `analyze_function_deeply` 並建立 Graph 邊

---

## Round 5: Phase 3 - EventStream 整合（未來工作）

### 目標
將 EventStream 整合到主流程，實現真正的異步處理。

### 計劃
1. 在主流程中初始化 EventStream
2. 將 tool calls 改為發布 Action 到 EventStream
3. 添加超時機制和重試邏輯
4. 事件持久化

### 狀態
⏸️ 等待 Gemini CLI 穩定運行後再實施

---

## 總結

### 已完成 ✅
- Phase 1: Action/Observation 基礎架構
- Phase 2: 整合到現有系統
- 7 個單元測試通過
- 手動測試驗證

### 技術債務
- EventStream 完整整合
- 超時機制的 UI/UX 改進
- 性能優化（大規模代碼庫）

### 當前阻塞
- Gemini CLI 運行時間過長，需要進一步調研