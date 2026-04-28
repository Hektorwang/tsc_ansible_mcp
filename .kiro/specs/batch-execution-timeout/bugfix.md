# 缺陷修复需求文档

## 概述

当通过 MCP 工具对批量主机（约 10 台）执行操作时，LLM 客户端会收到响应超时错误（通常为 `MCP error -32001: Request timed out`），而此时后台的 ansible-runner 进程仍在继续运行。这导致 LLM 无法获取执行结果，任务状态悬空，用户体验严重受损。

根本原因有两点：

1. `ansible_shell`、`run_playbook`、`ansible_copy`、`ansible_fetch` 在执行前会隐式调用 `check_host_status` 作为前置探测（5 个 raw 任务 x 10 台主机），相当于每次操作串行执行两轮 ansible，使总耗时翻倍，极易超过 MCP 客户端默认超时（30-60 秒）。
2. MCP 工具超时后，后台 ansible-runner 进程仍在运行，但没有任何机制让 LLM 事后查询结果，任务状态永久悬空。

此外，`execution_service.py` 的 `execute_shell` 方法存在 `NameError` 隐患，`[execution]` 节的超时配置未被实际使用，以及所有任务日志混合写入主日志导致排查困难。

## 缺陷分析

### 当前行为（缺陷）

1.1 当调用 `ansible_shell`、`run_playbook`、`ansible_copy` 或 `ansible_fetch` 时，系统内部会以 `skip_lock=True` 方式隐式调用 `check_host_status` 作为前置检测，相当于串行执行两轮完整的 ansible 任务，使总耗时翻倍，批量执行 10 台主机时极易触发 MCP 客户端超时。

1.2 当 MCP 客户端超时、LLM 认为任务失败后，系统仍在后台继续运行 ansible-runner 进程，且没有任何机制让 LLM 事后查询该任务的执行结果，任务状态永久悬空。

1.3 当 `executor.ansible_shell` 在 `execution_service.execute_shell` 内部抛出异常时，系统会在 `finally` 块中因 `result` 变量未赋值而触发 `NameError`，掩盖原始异常。

1.4 配置文件中 `[execution]` 节的 `timeout`（300s）从未被代码引用，是一个死配置，与实际生效的 `[mcp]` 节 `default_timeout`（600s）并存，造成配置语义混乱。

1.5 当任务执行时，所有任务的日志（包括 ansible 执行事件、结果、错误信息）均混合写入主日志文件 `logs/tsc_ansible_mcp.log`，无法按任务 ID 快速检索某次执行的完整日志，排查问题效率低下。

1.6 当 LLM 调用 `ansible_shell`、`ansible_copy`、`ansible_fetch` 或 playbook 工具时，工具描述中未明确要求 LLM 在调用前先执行 `check_host_status`，导致 LLM 可能跳过环境检测直接执行操作，在目标主机无 Python 环境时失败。

### 预期行为（修复目标）

2.1 当调用 `ansible_shell`、`run_playbook`、`ansible_copy` 或 `ansible_fetch` 时，系统不应执行隐式的 `check_host_status` 前置调用，直接对目标主机执行操作；主机状态检测应作为独立的显式工具调用，由 LLM 根据工具描述的提示主动发起。

2.2 当 `ansible_shell`、`ansible_copy`、`ansible_fetch` 及所有 playbook 工具的描述（`description`）中，应在 Prerequisites 部分明确注明：调用本工具前，必须先调用 `check_host_status` 确认目标主机环境就绪（Python 已安装、主机可达），以引导 LLM 主动执行前置检测。

2.3 当 MCP 客户端超时后，系统后台的 ansible-runner 进程应继续执行至完成，执行结果（成功或失败）应写入 SQLite 任务表和 `TaskResultStore`；LLM 可在超时后通过 `get_task_status(task_id)` 查询最终结果。

2.4 当 `executor.ansible_shell` 在 `execution_service.execute_shell` 内部抛出异常时，系统应干净地传播原始异常，不在 `finally` 块中触发二次 `NameError`。

2.5 删除配置文件中 `[execution]` 节的 `timeout` 配置项及代码中对应的 `execution_timeout` 属性，统一使用 `mcp.default_timeout` 作为 ansible-runner 的执行超时，消除配置歧义。

2.6 当任务开始执行时，系统应为该任务创建独立的日志文件（路径格式：`logs/tasks/{task_id}.log`），将该任务的所有执行日志（ansible 事件、结果、错误）写入该文件；任务完成后，日志文件保留供事后查询，`get_task_status` 的返回结果中应包含日志文件路径字段 `log_file`。

### 不变行为（回归防护）

3.1 当 `check_host_status` 作为独立 MCP 工具被显式调用时，系统应继续执行完整的 5 任务 raw 探测，并返回主机环境详情（架构、发行版、Python、tsc_tools）。

3.2 当任务成功完成时，系统应继续将完整结果保存到 `TaskResultStore`（JSON 文件），并更新 SQLite 中的任务状态。

3.3 当 `ansible_shell` 检测到高危命令时，系统应继续在执行前拒绝该命令。

3.4 当执行期间持有主机锁时，系统应继续阻止对同一主机的并发操作，并在完成或失败时释放锁。

3.5 当使用有效的 `task_id` 调用 `get_task_status` 时，系统应继续从 SQLite 返回已存储的任务状态和结果。

3.6 当调用 `ansible_copy` 或 `ansible_fetch` 时，系统应继续以相同的参数和返回格式执行文件分发或获取操作。

3.7 当调用方显式传入执行超时时间时，系统应继续遵守该值（上限为 `mcp.max_timeout`）。
