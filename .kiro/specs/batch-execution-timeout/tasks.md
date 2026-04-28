# 实现任务列表

## 任务

- [x] 1. 清理死配置 execution.timeout
  - [x] 1.1 删除 `etc/tsc_ansible_mcp.toml` 中 `[execution]` 节的 `timeout = 300`
  - [x] 1.2 删除 `lib/config.py` 中的 `execution_timeout` 属性及相关引用
  - [x] 1.3 在 `etc/tsc_ansible_mcp.toml` `[logging]` 节新增 `task_log_dir = "logs/tasks"` 和 `task_log_retention = "7 days"`
  - [x] 1.4 在 `lib/config.py` 新增 `task_log_dir` 和 `task_log_retention` 属性

- [x] 2. 移除执行方法中的隐式 check_host_status 前置调用
  - [x] 2.1 修改 `lib/executor.py` `ansible_shell` 方法，删除隐式 `check_host_status` 调用及 unreachable/python 检测逻辑
  - [x] 2.2 修改 `lib/executor.py` `ansible_copy` 方法，删除隐式 `check_host_status` 调用及 unreachable/python 检测逻辑
  - [x] 2.3 修改 `lib/executor.py` `ansible_fetch` 方法，删除隐式 `check_host_status` 调用及 unreachable/python 检测逻辑
  - [x] 2.4 修改 `lib/executor.py` `run_playbook` 方法，删除隐式 `check_host_status` 调用及 unreachable/python 检测逻辑

- [x] 3. 修复 execution_service.py 的 NameError 并改为后台线程执行
  - [x] 3.1 修复 `execute_shell` 的 `finally` 块 `NameError`，删除 `finally` 中的 `save_result` 调用
  - [x] 3.2 将 `execute_shell` 改为后台线程执行模式，主线程 `join(timeout=55)`，超时后返回 `running` 状态
  - [x] 3.3 将 `execute_playbook` 改为后台线程执行模式
  - [x] 3.4 将 `ansible_copy` 改为后台线程执行模式
  - [x] 3.5 将 `ansible_fetch` 改为后台线程执行模式
  - [x] 3.6 将 `check_host_status` 改为后台线程执行模式

- [x] 4. 工具描述中增加 check_host_status 前置提示
  - [x] 4.1 修改 `lib/mcp_tools/ansible_shell.py` 工具描述，在 Prerequisites 部分增加必须先调用 `check_host_status` 的说明
  - [x] 4.2 修改 `lib/mcp_tools/ansible_copy.py` 工具描述，增加同样的前置提示
  - [x] 4.3 修改 `lib/mcp_tools/ansible_fetch.py` 工具描述，增加同样的前置提示
  - [x] 4.4 修改 `lib/server.py` 动态 playbook 工具描述模板，在生成描述时统一追加前置提示

- [x] 5. 按任务 ID 拆分日志
  - [x] 5.1 修改 `lib/ansible_logger.py`，新增 `_task_handlers` 字典，在 `log_execution_start` 时为 task_id 动态添加 loguru sink，在 `log_execution_result` 时移除该 sink
  - [x] 5.2 修改 `lib/ansible_logger.py`，所有 `_log` 调用改为 `logger.bind(task_id=task_id)` 方式，确保日志写入对应任务文件
  - [x] 5.3 修改 `lib/database.py` `TaskRepository.get` 方法，在返回字典中增加 `log_file` 字段（若文件存在则返回路径，否则返回 `None`）
