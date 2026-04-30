# Async Task Query Enhancement — Usage Guide
# 异步任务查询增强系统 — 使用指南

---

## English

### Overview

The async task query system provides a **three-layer progressive query pattern** for retrieving execution results from async tools (`ansible_shell`, `ansible_copy`, `ansible_fetch`, `check_host_status`). Each layer reveals more detail, letting LLM agents avoid context overload by fetching only what they need.

---

### Layer Architecture

```
Layer 1 — Task Summary
  Input : task_id
  Source: SQLite (TaskRepository)
  Output: status, total_hosts, success_count, failed_count

Layer 2 — Host List (filtered by status)
  Input : task_id + status ("failed" | "success")
  Source: JSON file (ResultStore)
  Output: per-host rc, stdout, stderr, status

Layer 3 — Single Host Detail
  Input : task_id + host_ip
  Source: JSON file (ResultStore)
  Output: rc, stdout, stderr, status for one host
```

---

### Decision Tree — Which Layer to Use?

```
Start: I have a task_id
│
├─ Do I need to know if the task finished and how many hosts failed?
│   └─ YES → Layer 1: get_result(task_id)
│
├─ Do I need to see which specific hosts failed (or succeeded)?
│   └─ YES → Layer 2: get_result(task_id, status="failed")
│                      get_result(task_id, status="success")
│
└─ Do I need the full stdout/stderr for one specific host?
    └─ YES → Layer 3: get_host_detail(task_id, host_ip)
```

---

### Polling Workflow

```
1. Submit async task
   → Receive: {"task_id": "abc-123", "status": "running", "message": "..."}

2. Wait 30–60 seconds

3. Poll: get_result("abc-123")
   → If status == "running": wait another 30–60 s, repeat step 3
   → If status == "completed": proceed to step 4

4. Check summary counts
   → If failed_count > 0: use Layer 2 to list failed hosts
   → If all succeeded: done

5. (Optional) Drill into a specific host
   → get_host_detail("abc-123", "192.168.1.10")
```

Recommended polling interval: **30–60 seconds**. Do not poll more frequently than every 30 seconds.

---

### Layer 1 — Task Summary

**When to use:** First check after polling. Understand overall task health without loading host details.

**Call:**
```python
get_result(task_id="abc-123")
```

**Success response:**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "total_hosts": 10,
  "success_count": 8,
  "failed_count": 2,
  "message": "Task completed with 2 failed host(s). Use get_result('abc-123', status='failed') to see failed hosts"
}
```

**Task still running:**
```json
{
  "task_id": "abc-123",
  "status": "running",
  "message": "Task is still running. Poll again in 30-60 seconds using get_result('abc-123')"
}
```

**Task not found:**
```json
{
  "task_id": "abc-123",
  "status": "not_found",
  "message": "Task abc-123 not found in database"
}
```

---

### Layer 2 — Host List (Filtered by Status)

**When to use:** After Layer 1 shows failures (or to confirm successes). Lists all matching hosts with their output.

**Call — failed hosts:**
```python
get_result(task_id="abc-123", status="failed")
```

**Response:**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "failed_hosts": {
    "192.168.1.10": {
      "rc": 1,
      "stdout": "",
      "stderr": "bash: command not found",
      "status": "failed"
    },
    "192.168.1.11": {
      "rc": 2,
      "stdout": "",
      "stderr": "permission denied",
      "status": "failed"
    }
  },
  "total_failed": 2,
  "message": "Use get_host_detail(task_id, host_ip) to investigate specific host"
}
```

**Call — successful hosts:**
```python
get_result(task_id="abc-123", status="success")
```

**Response:**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "success_hosts": {
    "192.168.1.12": {
      "rc": 0,
      "stdout": "OK",
      "stderr": "",
      "status": "success"
    }
  },
  "total_success": 8
}
```

**No matching hosts:**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "failed_hosts": {},
  "total_failed": 0,
  "message": "No failed hosts"
}
```

---

### Layer 3 — Single Host Detail

**When to use:** Deep-dive into one specific host without loading all results.

**Call:**
```python
get_host_detail(task_id="abc-123", host="192.168.1.10")
```

**Success response:**
```json
{
  "task_id": "abc-123",
  "host": "192.168.1.10",
  "rc": 1,
  "stdout": "",
  "stderr": "bash: mycommand: command not found",
  "status": "failed"
}
```

**Host not found:**
```json
{
  "task_id": "abc-123",
  "host": "192.168.1.99",
  "status": "not_found",
  "message": "Host 192.168.1.99 not found in task abc-123 results"
}
```

**Task still running:**
```json
{
  "task_id": "abc-123",
  "status": "running",
  "message": "Task is still running. Wait and try again in 30-60 seconds"
}
```

---

### Error Reference

| Error `status` | Cause | Resolution |
|---|---|---|
| `not_found` | `task_id` does not exist in the database | Verify the task_id is correct |
| `running` | Task has not finished yet | Wait 30–60 s and retry |
| `error` (invalid status) | `status` value is not `"failed"` or `"success"` | Use only `"failed"` or `"success"` |
| `error` (missing file) | Result JSON file deleted or never written | Check server logs; task may have crashed |

All error responses include `task_id` for traceability.

---

---

## 中文

### 概述

异步任务查询系统为从异步工具（`ansible_shell`、`ansible_copy`、`ansible_fetch`、`check_host_status`）获取执行结果提供了**三层渐进式查询模式**。每一层揭示更多细节，让 LLM 代理只获取所需信息，避免上下文过载。

---

### 层级架构

```
第一层 — 任务摘要
  输入：task_id
  数据源：SQLite（TaskRepository）
  输出：status、total_hosts、success_count、failed_count

第二层 — 主机列表（按状态过滤）
  输入：task_id + status（"failed" | "success"）
  数据源：JSON 文件（ResultStore）
  输出：每个主机的 rc、stdout、stderr、status

第三层 — 单个主机详情
  输入：task_id + host_ip
  数据源：JSON 文件（ResultStore）
  输出：单个主机的 rc、stdout、stderr、status
```

---

### 决策树 — 应该使用哪一层？

```
开始：我有一个 task_id
│
├─ 我需要知道任务是否完成以及有多少主机失败？
│   └─ 是 → 第一层：get_result(task_id)
│
├─ 我需要查看哪些具体主机失败（或成功）？
│   └─ 是 → 第二层：get_result(task_id, status="failed")
│                      get_result(task_id, status="success")
│
└─ 我需要某个特定主机的完整 stdout/stderr？
    └─ 是 → 第三层：get_host_detail(task_id, host_ip)
```

---

### 轮询工作流

```
1. 提交异步任务
   → 收到：{"task_id": "abc-123", "status": "running", "message": "..."}

2. 等待 30–60 秒

3. 轮询：get_result("abc-123")
   → 如果 status == "running"：再等 30–60 秒，重复步骤 3
   → 如果 status == "completed"：进入步骤 4

4. 检查摘要计数
   → 如果 failed_count > 0：使用第二层列出失败主机
   → 如果全部成功：完成

5. （可选）深入查看特定主机
   → get_host_detail("abc-123", "192.168.1.10")
```

推荐轮询间隔：**30–60 秒**。请勿每 30 秒以内频繁轮询。

---

### 第一层 — 任务摘要

**使用时机：** 轮询后的第一次检查。在不加载主机详情的情况下了解任务整体状态。

**调用：**
```python
get_result(task_id="abc-123")
```

**成功响应：**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "total_hosts": 10,
  "success_count": 8,
  "failed_count": 2,
  "message": "Task completed with 2 failed host(s). Use get_result('abc-123', status='failed') to see failed hosts"
}
```

**任务仍在运行：**
```json
{
  "task_id": "abc-123",
  "status": "running",
  "message": "Task is still running. Poll again in 30-60 seconds using get_result('abc-123')"
}
```

**任务未找到：**
```json
{
  "task_id": "abc-123",
  "status": "not_found",
  "message": "Task abc-123 not found in database"
}
```

---

### 第二层 — 主机列表（按状态过滤）

**使用时机：** 第一层显示有失败（或需要确认成功）后使用。列出所有匹配主机及其输出。

**调用 — 失败主机：**
```python
get_result(task_id="abc-123", status="failed")
```

**响应：**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "failed_hosts": {
    "192.168.1.10": {
      "rc": 1,
      "stdout": "",
      "stderr": "bash: command not found",
      "status": "failed"
    },
    "192.168.1.11": {
      "rc": 2,
      "stdout": "",
      "stderr": "permission denied",
      "status": "failed"
    }
  },
  "total_failed": 2,
  "message": "Use get_host_detail(task_id, host_ip) to investigate specific host"
}
```

**调用 — 成功主机：**
```python
get_result(task_id="abc-123", status="success")
```

**响应：**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "success_hosts": {
    "192.168.1.12": {
      "rc": 0,
      "stdout": "OK",
      "stderr": "",
      "status": "success"
    }
  },
  "total_success": 8
}
```

**无匹配主机：**
```json
{
  "task_id": "abc-123",
  "status": "completed",
  "failed_hosts": {},
  "total_failed": 0,
  "message": "No failed hosts"
}
```

---

### 第三层 — 单个主机详情

**使用时机：** 深入查看某个特定主机，无需加载所有结果。

**调用：**
```python
get_host_detail(task_id="abc-123", host="192.168.1.10")
```

**成功响应：**
```json
{
  "task_id": "abc-123",
  "host": "192.168.1.10",
  "rc": 1,
  "stdout": "",
  "stderr": "bash: mycommand: command not found",
  "status": "failed"
}
```

**主机未找到：**
```json
{
  "task_id": "abc-123",
  "host": "192.168.1.99",
  "status": "not_found",
  "message": "Host 192.168.1.99 not found in task abc-123 results"
}
```

**任务仍在运行：**
```json
{
  "task_id": "abc-123",
  "status": "running",
  "message": "Task is still running. Wait and try again in 30-60 seconds"
}
```

---

### 错误参考

| 错误 `status` | 原因 | 解决方案 |
|---|---|---|
| `not_found` | `task_id` 在数据库中不存在 | 验证 task_id 是否正确 |
| `running` | 任务尚未完成 | 等待 30–60 秒后重试 |
| `error`（无效 status） | `status` 值不是 `"failed"` 或 `"success"` | 仅使用 `"failed"` 或 `"success"` |
| `error`（文件缺失） | 结果 JSON 文件被删除或从未写入 | 检查服务器日志；任务可能已崩溃 |

所有错误响应均包含 `task_id` 以便追溯。


---

## Polling Workflow Reference / 轮询工作流参考

### English

#### Recommended Polling Intervals

| Task Type | Typical Duration | Recommended First Poll | Subsequent Polls |
|---|---|---|---|
| `check_host_status` | 5–15 s | 15 s | 15 s |
| `ansible_shell` (simple) | 10–30 s | 30 s | 30 s |
| `ansible_shell` (complex) | 30–120 s | 45 s | 60 s |
| `ansible_copy` / `ansible_fetch` | 15–60 s | 30 s | 30 s |

**Rule of thumb:** Never poll more frequently than every 30 seconds. The server returns `status: "running"` until the task completes.

#### Polling Example (Python pseudocode)

```python
import time

# Step 1: Submit task
result = ansible_shell(targets=["192.168.1.10", "192.168.1.11"], command="uptime")
task_id = result["task_id"]

if result["status"] == "completed":
    # Fast path: task finished within 55 seconds
    process_results(result)
else:
    # Slow path: poll until done
    max_attempts = 10
    poll_interval = 30  # seconds

    for attempt in range(max_attempts):
        time.sleep(poll_interval)

        summary = get_result(task_id=task_id)

        if summary["status"] == "running":
            print(f"Still running... attempt {attempt + 1}/{max_attempts}")
            continue

        if summary["status"] == "completed":
            # Check for failures
            if summary["failed_count"] > 0:
                failed = get_result(task_id=task_id, status="failed")
                for host, detail in failed["failed_hosts"].items():
                    print(f"FAILED {host}: {detail['stderr']}")
            break

        if summary["status"] == "not_found":
            raise RuntimeError(f"Task {task_id} not found")

    else:
        raise TimeoutError(f"Task {task_id} did not complete after {max_attempts} polls")
```

#### Timeout Handling Strategy

1. **Set a maximum poll count** (e.g., 10 attempts × 60 s = 10 minutes max wait).
2. **Exponential backoff** is not necessary — the server is non-blocking and 30–60 s fixed intervals work well.
3. **On timeout:** Log the `task_id` and check server logs. The task may still be running in the background.
4. **Do not re-submit** the same task if it times out on your side — it may still complete and write results.

---

### 中文

#### 推荐轮询间隔

| 任务类型 | 典型耗时 | 建议首次轮询 | 后续轮询 |
|---|---|---|---|
| `check_host_status` | 5–15 秒 | 15 秒 | 15 秒 |
| `ansible_shell`（简单） | 10–30 秒 | 30 秒 | 30 秒 |
| `ansible_shell`（复杂） | 30–120 秒 | 45 秒 | 60 秒 |
| `ansible_copy` / `ansible_fetch` | 15–60 秒 | 30 秒 | 30 秒 |

**经验法则：** 轮询频率不要超过每 30 秒一次。服务器在任务完成前会持续返回 `status: "running"`。

#### 轮询示例（Python 伪代码）

```python
import time

# 步骤 1：提交任务
result = ansible_shell(targets=["192.168.1.10", "192.168.1.11"], command="uptime")
task_id = result["task_id"]

if result["status"] == "completed":
    # 快速路径：任务在 55 秒内完成
    process_results(result)
else:
    # 慢速路径：轮询直到完成
    max_attempts = 10
    poll_interval = 30  # 秒

    for attempt in range(max_attempts):
        time.sleep(poll_interval)

        summary = get_result(task_id=task_id)

        if summary["status"] == "running":
            print(f"仍在运行中... 第 {attempt + 1}/{max_attempts} 次")
            continue

        if summary["status"] == "completed":
            # 检查失败情况
            if summary["failed_count"] > 0:
                failed = get_result(task_id=task_id, status="failed")
                for host, detail in failed["failed_hosts"].items():
                    print(f"失败 {host}: {detail['stderr']}")
            break

        if summary["status"] == "not_found":
            raise RuntimeError(f"任务 {task_id} 未找到")

    else:
        raise TimeoutError(f"任务 {task_id} 在 {max_attempts} 次轮询后仍未完成")
```

#### 超时处理策略

1. **设置最大轮询次数**（例如：10 次 × 60 秒 = 最多等待 10 分钟）。
2. **无需指数退避** — 服务器是非阻塞的，30–60 秒固定间隔效果良好。
3. **超时后：** 记录 `task_id` 并检查服务器日志。任务可能仍在后台运行。
4. **不要重新提交**超时的任务 — 它可能仍会完成并写入结果。
