# Release Note — v1.15.0 (2026-05-01)

## 异步任务查询增强 / Async Task Query Enhancement

### 概述 / Overview

v1.15.0 引入了结构化的三层查询模式，为 LLM 代理提供清晰、渐进式的异步任务结果访问方式，避免上下文过载。

v1.15.0 introduces a structured three-layer query pattern that gives LLM agents clear, progressive access to async task results without context overload.

---

### 新功能 / New Features

#### 三层查询模式 / Three-Layer Query Pattern

| 层级 / Layer | 调用方式 / Call | 返回内容 / Returns |
| ------------ | --------------- | ------------------- |
| 第一层 / Layer 1 | `get_result(task_id)` | 任务摘要（total_hosts, success_count, failed_count）/ Task summary |
| 第二层 / Layer 2 | `get_result(task_id, status="failed")` | 所有失败主机详情 / All failed hosts with details |
| 第二层 / Layer 2 | `get_result(task_id, status="success")` | 所有成功主机详情 / All successful hosts with details |
| 第三层 / Layer 3 | `get_host_detail(task_id, host_ip)` | 单个主机详情 / Single host details |

#### 新增工具 / New Tool: `get_host_detail`

查询单个主机在指定任务中的执行详情（rc、stdout、stderr、status）。  
Query execution details for a specific host in a task (rc, stdout, stderr, status).

```json
// 请求 / Request
{"task_id": "job_abc123", "host": "192.168.1.10"}

// 响应 / Response
{
  "task_id": "job_abc123",
  "host": "192.168.1.10",
  "rc": 0,
  "stdout": "...",
  "stderr": "",
  "status": "success"
}
```

#### 增强轮询指导 / Enhanced Polling Guidance

所有异步工具（`ansible_shell`、`ansible_copy`、`ansible_fetch`、`check_host_status`）在返回 "running" 状态时，现在包含确切的 `get_result()` 调用语法和 30-60 秒轮询间隔建议。

All async tools now include exact `get_result()` call syntax and a 30-60 second polling interval recommendation in their "running" status responses.

---

### 向后兼容性 / Backward Compatibility

- ✅ `get_result(task_id, status="failed")` — 行为不变 / behavior unchanged
- ✅ TaskRepository 数据库架构不变 / database schema unchanged
- ✅ ResultStore JSON 文件格式不变 / result file format unchanged
- ✅ 所有现有异步工具核心逻辑不变 / all existing async tool core logic unchanged

---

### 变更文件 / Changed Files

| 文件 / File | 变更 / Change |
| ----------- | ------------- |
| `lib/mcp_tools/task_results.py` | 重构 `get_result`，新增 `get_host_detail` |
| `lib/task_result_store.py` | 新增 `get_host_result()`，增强 `get_result()` 支持 status="success" |
| `docs/API-REFERENCE.md` | 更新 MCP 工具表，新增 3.7/3.8 节，完善 Async Task Query API 章节 |

---

### 升级说明 / Upgrade Notes

无需任何配置变更或数据库迁移。重启服务后新工具即可使用。

No configuration changes or database migrations required. New tools are available immediately after service restart.
