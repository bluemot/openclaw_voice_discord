# RTL8852BU WiFi Station 連線流程測試記錄

**測試日期:** 2026-03-21 ~ 2026-03-22  
**測試目標:** 驗證 CRAG 能否回答困難的技術問題  
**問題:** "請告訴我當 RTL8852BU 作為 station 角色時，driver 怎麼完成一個完整的連線流程。請從接到上層來的連線請求開始，一直追蹤到如何控制頻道切換，以發出連線請求，完成認證程序。回答內容必須包含硬體和 firmware 控制的部分。"

---

## 測試步驟執行情況

### ✅ 步驟 1: Gemini 回答問題
**狀態:** 完成  
**時間:** 2026-03-22 00:06  
**結果:** Gemini 提供了非常詳細的答案，包含：
- 上層連線請求入口點（`rtw89_ops_add_interface`）
- 頻道切換流程（`rtw89_chan_switch`）
- Firmware H2C 命令（`rtw89_fw_h2c_connect`）
- 硬體寄存器操作（`REG_BB_SEL_CH`, `REG_MAC_CTRL` 等）
- 認證流程（Authentication Frame → Association → EAPOL）

**答案位置:** `/home/ubuntu/.openclaw/workspace/8852bu_gemini_answer.md`

---

### ⏳ 步驟 2: CRAG RAG 索引
**狀態:** 進行中（從 2026-03-22 00:07 開始）  
**模式:** `--lightweight`  
**進度:** 正在解析 PHY 層相關文件（`halbb_ch_info.h`, `halbb_rua_tbl.h` 等）

**觀察:**
- RTL8852BU 驅動非常大，索引需要較長時間
- 即使使用 `--lightweight` 模式，仍然需要數小時
- 這是一個真實的 Linux WiFi 6 驅動，包含數千個函數

---

### ⏳ 步驟 3-7: CRAG Chat 測試
**狀態:** 等待 RAG 索引完成  
**預計超時:** 30 分鐘  

---

### ⏳ 步驟 8: 記錄和 Commit
**狀態:** 等待測試完成  

---

## 發現的問題

### 問題 #1: Agent 搜尋策略缺陷
**描述:** CRAG 在之前的測試中無法在 Timeout 內返回答案  
**測試案例:**
- 簡單問題（如 "Find rtl8852bu_probe"）也會導致無限搜尋
- Agent 重複調用 `global_text_search` 但不收斂
- 沒有調用 `submit_final_answer`

**解決方案:**
- 設計並實現 HybridScheduler
- 添加優先級隊列、深度限制、強制答案機制
- 位置：`codebase_rag/services/hybrid_scheduler.py`

---

## 相關文件

1. **Gemini 答案:** `/home/ubuntu/.openclaw/workspace/8852bu_gemini_answer.md`
2. **CRAG 答案:** `/home/ubuntu/.openclaw/workspace/8852bu_crag_answer.md` (待創建)
3. **設計文檔:** `/home/ubuntu/.openclaw/workspace/HYBRID_SCHEDULER_DESIGN.md`
4. **測試代碼:** `/home/ubuntu/.openclaw/workspace/hybrid_scheduler_test.py`

---

## 測試結果

待測試完成後更新...

---

**最後更新:** 2026-03-22 07:50 UTC  
**狀態:** 進行中
