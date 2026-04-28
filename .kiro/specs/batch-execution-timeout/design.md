# 设计文档

## 概述

本次修复针对批量主机执行超时问题，涉及以下六个方向：

1. 移除执行方法中的隐式 `check_host_status` 前置调用
2. 在工具描述中显式提示 LLM 先调用 `check_host_status`
3. 后台线程执行 ansible-runner，MCP 超时后结果仍可查询
4. 修复 `execute_shell` 的 `finally` 块 `NameError`
5. 清理死配置 `execution.timeout`
6. 按任务 ID 拆分日志文件

---

## 架构变更

### 变更前

```text
MCP 工具调用
    -> ExecutionService
    -> Executor.ansible_shell()
        -> check_host_status()   # 隐式前置，耗时翻倍
        -> _run_ansible()        # 同步阻塞
    <- 返回结果（可能已超时）
变更后
MCP 工具调用
    -> ExecutionService
    -> Executor.ansible_shell()
        -> _run_ansible()        # 直接执行，无前置探测
    <- 返回结果

（后台线程保障：即使 MCP 超时，结果仍写入 DB）
详细设计
1. 移除隐式 check_host_status（对应需求 2.1）
涉及文件：
executor.py

变更方法：ansible_shell、ansible_copy、ansible_fetch、run_playbook

删除各方法开头的以下模式代码：

# 删除这段
if detect_result is None:
    detect_result = self.check_host_status(
        targets, timeout=timeout, skip_lock=True
    )
unreachable_hosts = [...]
hosts_need_python = [...]
各方法直接进入 _build_inventory 和 _run_ansible，不再做前置环境探测。

detect_result 参数保留但标记为废弃，兼容现有调用方。

2. 工具描述中显式提示（对应需求 2.2）
涉及文件：

ansible_shell.py
ansible_copy.py
ansible_fetch.py
server.py
（动态 playbook 工具的描述模板）
在每个工具 description 的 ## Prerequisites 部分增加：

## Prerequisites
- Target hosts must be added to inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH
  2. Python is installed (required for shell/copy/fetch modules)
  If Python is not installed, run playbook_bootstrap_tsc_environment first.
动态 playbook 工具在 _register_dynamic_playbook_tools 生成描述时，统一在描述头部追加同样的前置提示。

3. 后台线程保障结果可查（对应需求 2.3）
涉及文件：
execution_service.py

核心思路：ExecutionService 的各 execute_* 方法改为在独立线程中运行 executor，主线程立即将任务状态置为 running 并返回含 task_id 的响应；后台线程完成后更新 DB。

import threading

def execute_shell(self, targets, command, timeout, task_id):
    self.task_repo.update(task_id, "running")

    def _run():
        try:
            result = self.executor.ansible_shell(
                targets=targets,
                command=command,
                timeout=timeout,
                task_id=task_id,
            )
            self.task_repo.update(task_id, result["status"], result)
            self.result_store.save_result(task_id, result)
        except Exception as e:
            error_result = {"status": "failed", "error": str(e)}
            self.task_repo.update(task_id, "failed", error_result)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # 等待结果，但不超过 MCP 客户端超时
    # 若 thread 在合理时间内完成则同步返回，否则返回 pending 状态
    thread.join(timeout=55)  # 留 5s 余量给 MCP 响应

    if thread.is_alive():
        # 后台仍在跑，返回 pending 让 LLM 轮询
        return {
            "task_id": task_id,
            "status": "running",
            "message": "Task is running in background. Use get_task_status(task_id) to poll result."
        }

    # 线程已完成，从 DB 取最终结果
    task = self.task_repo.get(task_id)
    return task.get("result") or {"task_id": task_id, "status": task["status"]}
execute_playbook、ansible_copy、ansible_fetch、check_host_status 采用相同模式。

等待超时配置：55 秒硬编码（MCP 客户端通常 60s），后续可提取到配置文件 mcp.tool_wait_timeout。

4. 修复 execute_shell finally 块 NameError（对应需求 2.4）
涉及文件：
execution_service.py

当前问题：

def execute_shell(self, ...):
    try:
        result = self.executor.ansible_shell(...)  # 若此处抛异常
        ...
    finally:
        self.result_store.save_result(task_id, result)  # result 未定义 -> NameError
修复：删除 finally 块中的 save_result 调用，改为在 try 块成功路径中调用，异常路径由后台线程的 except 处理。

5. 清理死配置（对应需求 2.5）
涉及文件：

tsc_ansible_mcp.toml
 — 删除 [execution] 节的 timeout = 300
config.py
 — 删除 execution_timeout 属性
_run_ansible 中超时选择逻辑保持不变，继续使用 self.config.default_timeout（来自 [mcp] 节）。

6. 按任务 ID 拆分日志（对应需求 2.6）
涉及文件：
ansible_logger.py
、
tsc_logger.py

6.1 日志目录结构
logs/
├── tsc_ansible_mcp.log          # 主应用日志（不变）
├── ansible_execution.log        # ansible 汇总日志（不变）
└── tasks/                       # 任务独立日志目录（新增）
    ├── {task_id}.log
    └── ...
6.2 AnsibleExecutionLogger 变更
在 log_execution_start 时，为当前 task_id 动态添加一个 loguru sink：

def _get_task_log_path(self, task_id: str) -> Path:
    base_dir = Path(__file__).parent.parent.resolve()
    task_log_dir = base_dir / "logs" / "tasks"
    task_log_dir.mkdir(parents=True, exist_ok=True)
    return task_log_dir / f"{task_id}.log"

def log_execution_start(self, task_id, ...):
    log_path = self._get_task_log_path(task_id)
    handler_id = logger.add(
        str(log_path),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        encoding="utf-8",
        filter=lambda record, tid=task_id: record["extra"].get("task_id") == tid,
    )
    self._task_handlers[task_id] = handler_id
    # 后续所有该任务的日志通过 logger.bind(task_id=task_id) 写入
    ...

def log_execution_result(self, task_id, ...):
    # 写完结果后移除该任务的 handler
    handler_id = self._task_handlers.pop(task_id, None)
    if handler_id is not None:
        logger.remove(handler_id)
_task_handlers: Dict[str, int] 存储 task_id -> loguru handler id 的映射。

6.3 get_task_status 返回日志路径
TaskRepository.get 返回的字典中增加 log_file 字段：

log_file = str(base_dir / "logs" / "tasks" / f"{task_id}.log")
return {
    ...
    "log_file": log_file if Path(log_file).exists() else None,
}
6.4 配置项
tsc_ansible_mcp.toml
 新增：

[logging]
task_log_dir = "logs/tasks"
task_log_retention = "7 days"   # 任务日志保留时间，独立于主日志
文件变更清单
文件	变更类型	说明
executor.py
修改	删除 ansible_shell、ansible_copy、ansible_fetch、run_playbook 中的隐式 check_host_status 调用
execution_service.py
修改	改为后台线程执行，修复 finally NameError
ansible_shell.py
修改	工具描述增加前置提示
ansible_copy.py
修改	工具描述增加前置提示
ansible_fetch.py
修改	工具描述增加前置提示
server.py
修改	动态 playbook 工具描述模板增加前置提示
ansible_logger.py
修改	支持按 task_id 动态添加/移除 loguru sink
tsc_logger.py
修改	新增 task log 目录配置支持
config.py
修改	删除 execution_timeout 属性，新增 task_log_dir、task_log_retention
tsc_ansible_mcp.toml
修改	删除 execution.timeout，新增 logging.task_log_dir、logging.task_log_retention
正确性属性
以下属性用于验证修复的正确性：

P1（无隐式探测）：调用 ansible_shell 时，check_host_status 不应被调用，ansible-runner 事件中不应出现 Detect architecture 等探测任务名。

P2（后台持续执行）：MCP 工具返回 running 状态后，等待 ansible-runner 实际完成时间后，get_task_status 应返回 success 或 failed，不应仍为 running。

P3（日志隔离）：任务 A 和任务 B 并发执行时，logs/tasks/{task_id_A}.log 中不应出现任务 B 的事件，反之亦然。

P4（NameError 消除）：当 executor.ansible_shell 抛出任意异常时，execute_shell 应将该异常传播，不应抛出 NameError。

P5（配置一致）：Config 类不应存在 execution_timeout 属性，_run_ansible 使用的超时值应来自 mcp.default_timeout。



---

确认内容没问题后，我来生成任务列表（`tasks.md`）。