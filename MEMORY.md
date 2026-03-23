# MEMORY.md - 長期記憶

## 核心身份
- 我是 Jarvis，Tom 的 AI 助手
- Tom 在學習股票投資，偏好短線操作
- **專案相關人員：**
  - 希泉 (Discord ID: `911227262496571432`) — 專案主持人，指示同樣需要執行

**注意：專案索引已移至 PROJECTS.md**

## 教訓
- **2026-03-14**: 必須遵守 AGENTS.md 的「Gemini CLI for Coding」規則。寫程式碼修改時應該使用 `gemini "prompt"`，而不是直接自己寫。簡單任務直接執行，複雜任務用 `nohup` 背景執行。

## 專案索引
- **llm-cos-fun**: `/home/ubuntu/.openclaw/workspace/llm-cos-fun/` — LLM 角色扮演專案（主持：希泉）
  - 進度記錄：`PROGRESS.md`
  - 最新功能：Context Compression (15%/45% FIFO)、Trust Level 起始值優化、AJAX 聊天
- **stock_crawler**: `/home/ubuntu/.openclaw/workspace/stock_crawler/` — 記憶在 `PROGRESS.md`
- **codebase_rag**: `/home/ubuntu/workspace/crag/` — 完整進度記錄在 `/home/ubuntu/workspace/crag/PROGRESS.md`
  - 現正解決：LLM 持續嘗試调用已移除的工具 (`global_text_search`)，懷疑是模型固有行為
  - Symlink 已設定：`/home/ubuntu/.openclaw/workspace/crag -> /home/ubuntu/workspace/crag`