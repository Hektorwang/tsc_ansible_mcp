# Release Notes

## Version=1.17.0

2026-05-18

1. 修复 debug 模式时, 未保存 inventory.json 文件问题
2. 修复 bootstrap_tsc_environment.yml 中的 python 安装验证逻辑问题

## Version=1.16.0

2026-05-01

### Bug Fixes

#### 1. ansible_shell Returns Incorrect Results (rc: -1, status: failed)

When `ansible_shell` executed successfully, the MCP client received all hosts as failed with `rc: -1` and empty stdout/stderr. Root cause: `ansible_shell` bypassed `_build_summary_result` and `_parse_result` defaulted to `rc: -1` when `runner_on_ok` events were not matched.

Fix: `ansible_shell` now uses `_build_summary_result` for consistent result structure, and adds a `result.stats` fallback to correct `rc` when event matching fails.

#### 2. Debug Playbook Cache Shows Unsubstituted Variables

`logs/debug/{task_id}/playbook.yml` showed raw `{{ var_name }}` placeholders instead of actual `extravars` values. Fix: extravars are now substituted into the cached content before writing.

### Improvements

#### 3. Tool Descriptions and Instructions Externalized to Markdown

All MCP tool `description` strings and `MCP_INSTRUCTIONS` are now loaded from `etc/instructions.md` and `etc/tool_descriptions/*.md` at startup via `lib/tool_description_loader.py`. A shared `_polling_rules.md` fragment is injected via `{{POLLING_RULES}}` placeholder, eliminating duplication across tools.

#### 4. Strict LLM Polling Behavior Rules

All async tools now include explicit MUST/MUST NOT rules for `status: "running"` handling. The same rules are added to `MCP_INSTRUCTIONS` as global behavior rules with highest priority. Key rules: poll every 60 seconds, never ask the user, never change the interval, never stop polling due to unchanged status.

#### 5. Startup Warning for Missing ansible-playbook in PATH

`bin/server.py` now prints a warning to stderr at startup if `ansible-playbook` is not found in PATH, preventing silent `rc=127` failures at runtime.

### Files Changed

- `lib/executor.py` - ansible_shell fix, debug cache extravars substitution
- `lib/execution_service.py` - polling message update
- `lib/tool_description_loader.py` (new)
- `etc/instructions.md` (new)
- `etc/tool_descriptions/` (new directory, 10 files)
- `lib/mcp_tools/ansible_shell.py`, `ansible_copy.py`, `ansible_fetch.py`, `check_host_status.py`, `task_results.py`, `change_ssh_password.py`, `change_ssh_port.py`
- `lib/server.py`
- `bin/server.py`

---

## Version=1.15.0

2026-05-01

### 新功能

#### 1. 异步任务查询增强系统（三层查询模式）

实现了结构化的三层查询模式，为 LLM 代理提供清晰、渐进式的任务结果访问方式，避免上下文过载。

**三层查询架构：**

```
第一层：任务摘要查询
├─ 调用：get_result(task_id)
├─ 数据源：TaskRepository (SQLite)
└─ 返回：task_id, status, total_hosts, success_count, failed_count

第二层：主机列表查询（按状态过滤）
├─ 调用：get_result(task_id, status="failed"|"success")
├─ 数据源：ResultStore (JSON 文件)
└─ 返回：filtered_hosts {host_ip: {rc, stdout, stderr, status}}

第三层：单个主机详情查询
├─ 调用：get_host_detail(task_id, host_ip)
├─ 数据源：ResultStore (JSON 文件)
└─ 返回：host_ip, rc, stdout, stderr, status
```

**新增 MCP 工具：**

- `get_host_detail(task_id, host)` - 查询单个主机在指定任务中的执行详情

**增强 MCP 工具：**

- `get_result(task_id, status=None)` - 支持三种查询模式（摘要/失败主机/成功主机）

**向后兼容性：**

- `get_result(task_id, status="failed")` 保持现有行为
- TaskRepository 数据库架构未变更
- ResultStore 文件格式未变更
- 所有现有异步工具核心逻辑未变更

#### 2. 异步工具轮询指导增强

所有异步工具（`ansible_shell`、`ansible_copy`、`ansible_fetch`、`check_host_status`）在返回 "running" 状态时，现在包含：

- 确切的 `get_result(task_id)` 调用语法
- 建议的 30-60 秒轮询间隔

#### 3. 统一错误响应格式

所有错误响应均包含 `task_id` 字段，便于追溯。错误类型包括：

- `status: "not_found"` - 任务或主机不存在
- `status: "running"` - 任务仍在运行
- `status: "error"` - 无效参数或结果文件缺失

### 改进

#### 1. TaskResultStore 增强

- 新增 `get_host_result(task_id, host)` 方法，支持读取单个主机结果
- 增强 `get_result(task_id, status)` 支持 `status="success"` 过滤，返回 `success_hosts` 和 `total_success`

#### 2. 性能优化

- 任务摘要查询（第一层）仅读取 SQLite 数据库，不读取 JSON 结果文件
- 主机列表查询（第二层）读取 JSON 文件一次并在内存中过滤
- 单主机查询（第三层）读取 JSON 文件一次并仅提取请求的主机数据

### 文件变更

#### 修改文件

- `lib/mcp_tools/task_results.py` - 重构 `get_result`，新增 `get_host_detail`，更新工具描述
- `lib/task_result_store.py` - 新增 `get_host_result()` 方法，增强 `get_result()` 支持 status="success"
- `docs/API-REFERENCE.md` - 更新 MCP 工具表（替换旧工具名），新增 3.7/3.8 节，完善 Async Task Query API 章节，修正 `get_host_detail` 成功响应示例

### 测试验证

- ✅ TaskResultStore `get_host_result()` 单元测试（成功/主机不存在/任务不存在）
- ✅ `get_result` 三种查询模式单元测试（摘要/失败主机/成功主机/无效参数/任务不存在/运行中）
- ✅ `get_host_detail` 单元测试（成功/主机不存在/任务不存在/运行中）
- ✅ 错误响应格式单元测试（所有错误场景）

---

## Version=1.14.0

2026-04-26

### Bug 修复

#### 1. 批量主机执行超时问题修复

修复了通过 MCP 工具对批量主机（约 10 台）执行操作时，LLM 客户端收到 `MCP error -32001: Request timed out` 错误，以及 LLM 超时后后台任务状态悬空的问题。

**问题原因：**

- `ansible_shell`、`run_playbook`、`ansible_copy`、`ansible_fetch` 在执行前会隐式调用 `check_host_status` 作为前置探测，相当于串行执行两轮 ansible，总耗时翻倍
- 所有执行方法同步阻塞 HTTP 请求，MCP 客户端超时后后台进程仍在运行，结果无法查询
- `execution_service.execute_shell` 的 `finally` 块存在 `NameError` 隐患
- `[execution]` 节的 `timeout` 配置项从未被使用，与 `[mcp].default_timeout` 并存造成混淆

**修复内容：**

- 移除 4 个执行方法中的隐式 `check_host_status` 前置调用，直接执行操作
- 所有执行方法改为后台线程模式：主线程等待 55 秒，超时后返回 `running` 状态，后台继续执行并将结果写入 DB，LLM 可通过 `get_task_status(task_id)` 查询最终结果
- 在 `ansible_shell`、`ansible_copy`、`ansible_fetch` 及所有 playbook 工具描述中明确提示 LLM 调用前必须先执行 `check_host_status`
- 修复 `execute_shell` `finally` 块的 `NameError`
- 删除无效的 `[execution].timeout` 配置项，统一使用 `[mcp].default_timeout`
- 新增按任务 ID 拆分日志：每个任务创建独立日志文件 `logs/tasks/{task_id}.log`，`get_task_status` 返回 `log_file` 字段

---

## Version=1.13.0

### Bug 修复

#### 1. change_ssh_port MCP 超时问题修复

修复了通过 MCP 调用 `change_ssh_port` 工具修改 SSH 端口时，客户端收到 `MCP error -32001: Request timed out` 错误。

**问题原因：**

- 旧实现中每个步骤（备份、修改配置、测试、重启、验证等）都独立调用 `execute_shell()`
- 每次调用都会触发 `check_host_status` 进行环境检测和主机锁获取/释放
- 对于 2 台主机、9 个步骤的场景，总共会执行约 18 次 `check_host_status` + 18 次 ansible shell playbook
- 每次 playbook 执行都有启动开销，累积时间极易超过 MCP 客户端的默认超时时间（通常 30-60 秒）

**修复内容：**

- 将 `change_ssh_port` 的实现从 Python 多步骤串行调用改为三步方案
- 第一步：执行 `check_host_status` 获取当前端口（每台主机 1 次）
- 第二步：调用外联 playbook `change_ssh_port.yml` 执行完整的端口变更流程（每台主机 1 次）
- 第三步：验证新端口连通性，支持 fallback 到旧端口
- 每台主机只需 1 次 `check_host_status` + 1 次 playbook + 1 次验证，大幅减少 ansible 调用次数

**新增文件：**

- `playbooks/change_ssh_port.yml` - 外联 playbook，使用 `raw` 模块执行 Python 脚本
- `scripts/change_ssh_port_on_target.py` - 目标主机上执行的 Python 脚本

**改进内容：**

- 新增主机数量限制：超过 50 台直接失败返回
- 新增端口范围校验：目的端口必须为 22 或在 1024-65535 范围内
- 全程持有主机锁，避免中间被其他任务抢占
- 使用 rc 码区分失败状态：0=成功，1=配置测试失败，2=reload失败，3=新端口未监听，4=旧端口仍监听，99=其他错误
- 支持新端口失败时 fallback 到旧端口验证连通性
- 修复结果解析 Bug（`backup_result.get(host, {})` 应为 `backup_result.get("results", {}).get(host, {})`）

**影响范围：**

- `change_ssh_port` MCP 工具 - 重构为三步方案
- `playbooks/change_ssh_port.yml` - 新增外联 playbook
- `scripts/change_ssh_port_on_target.py` - 新增 Python 脚本

### 改进

#### 1. 代码质量

- 所有 Python 脚本的中文注释和 docstrings 改为英文
- 添加完整的 Google-style Docstrings 和 type hints

### 技术实现

#### 三步方案架构

```
change_ssh_port MCP 工具
    |
    +-- 前置校验（主机数 <= 50，端口范围检查）
    |
    +-- 第一步：check_host_status（获取当前端口）
    |
    +-- 第二步：execute_playbook("change_ssh_port.yml")
    |       |
    |       +-- ansible.builtin.copy（上传 Python 脚本）
    |       +-- ansible.builtin.raw（执行 Python 脚本）
    |               |
    |               +-- 备份 sshd_config
    |               +-- 修改 Port 行
    |               +-- 测试配置（sshd -t）
    |               +-- 重载 sshd（systemctl reload）
    |               +-- 等待新端口监听（循环检测，超时 15 秒）
    |               +-- 失败时自动回滚
    |
    +-- 第三步：验证和更新 inventory
            |
            +-- 更新 inventory（ansible_port = new_port）
            +-- 验证新端口连通性（echo 测试）
            +-- 失败时 fallback 到旧端口
            +-- 根据结果最终调整 inventory
```

### 文档更新

- 更新 `docs/SPEC.md` - 添加 change_ssh_port 三步方案说明
- 更新 `README.md` - 添加 change_ssh_port 工具说明

---

## Version=1.12.1

2026-04-22

### Bug 修复

#### 1. 包版本排序问题修复

修复了包管理器中使用字符串字典序排序版本号，导致 beta10 被错误识别为比 beta9 旧的问题。

**问题原因：**

- `lib/package_manager/scanner.py` 中 `get_latest_package()` 方法使用字符串比较排序版本
- 字典序比较时，`"beta9" > "beta10"` 因为 `'9' > '1'`
- 导致 `/api/v1/packages/download` 接口返回旧版本 beta9 而非最新 beta10

**修复内容：**

- 引入 `packaging.version.parse` 进行语义化版本比较
- 将字符串排序替换为语义化版本排序
- 正确识别 `beta10 > beta9`、`rc > beta`、`正式版 > 预发布版`

**影响范围：**

- `GET /api/v1/packages/download` - 现在正确返回最新版本
- `GET /api/v1/packages/list/{pkg_type}` - 列表顺序正确

### 测试验证

- ✅ beta10 正确识别为比 beta9 新
- ✅ 正式版正确识别为比预发布版新
- ✅ rc 正确识别为比 beta 新
- ✅ 现有 7 个包管理器测试全部通过

---

## Version=1.12.0

2026-04-16

### New Features

#### 1. Package Manager and API

Eliminates nginx dependency by implementing a direct API-based package transfer system.

- **Package Scanner** - Scans and filters installation packages, supporting noarch packages
- **Package Manager** - Core package management logic with normalization and caching
- **API Endpoints** - Integrated package download, list, and cache refresh endpoints
- **No nginx Required** - Direct file transfer from MCP server to target hosts

#### 2. Bootstrap Playbook

New `bootstrap_tsc_environment.yml` playbook that automates environment bootstrapping.

- **Automatic Detection** - Detects system distro and architecture automatically
- **API Integration** - Downloads packages via API endpoints
- **HTTPS Support** - Uses `curl -k` for HTTPS compatibility
- **Installation Status Check** - Verifies existing installations before proceeding

#### 3. English Documentation

All MCP tool descriptions and documentation have been updated to English.

- **MCP_INSTRUCTIONS** - Complete English rewrite with improved clarity
- **README.md** - Updated with English descriptions and new feature documentation
- **Tool Descriptions** - All MCP tool descriptions are now in English

### Improvements

#### 1. Workflow Optimization

Added clear guidance on using bootstrap_tsc_environment playbook.

- **check_host_status Integration** - Check host status first
- **Bootstrap Recommendation** - Use bootstrap_tsc_environment when packages are missing
- **Simplified Process** - One playbook handles both tsc_tools and tsc_python

#### 2. Package Management

Generic package filtering method that matches arch and distro before sorting by version.

- **Noarch Support** - Special handling for noarch packages
- **Distro/Arch Normalization** - Consistent handling across different systems
- **Version Sorting** - Proper version-based package selection

### Technical Implementation

#### Package Manager Architecture

```
lib/package_manager/
├── scanner.py    - Package scanning and filtering
├── manager.py    - Core package management logic
└── normalizer.py - Distro and arch normalization

lib/api/routes/
└── packages.py   - API endpoints for package management
```

#### API Endpoints

- `GET /api/v1/packages/download` - Download latest package
- `GET /api/v1/packages/list/{pkg_type}` - List available packages
- `POST /api/v1/packages/refresh` - Refresh package cache

### Documentation Updates

- Updated `README.md` - Added v1.12.0 feature descriptions
- Updated `MCP_INSTRUCTIONS` - Complete English rewrite
- Updated `check_host_status.py` - Added English note about bootstrap_tsc_environment
- Updated `bootstrap_tsc_environment.yml` - Added proper metadata and English description

---

## Version=1.11.0

2026-04-14

### Bug 修复

#### 1. 主机锁管理问题修复

修复了主机锁未正确释放导致的死锁问题，确保所有执行方法都能正确管理主机锁。

**问题原因：**

- `ansible_shell`、`ansible_copy` 和 `ansible_fetch` 方法缺少锁管理逻辑
- 当这些方法执行时，主机锁被获取但未在所有情况下释放
- 导致主机被永久锁定，无法执行后续操作

**修复内容：**

为所有执行方法添加了完整的锁管理逻辑：

- `ansible_shell()` - 添加锁的获取和释放逻辑
- `ansible_copy()` - 添加锁的获取和释放逻辑
- `ansible_fetch()` - 添加锁的获取和释放逻辑
- 所有方法都使用 try-finally 块确保锁在任何情况下都会被释放
- 在调用 `install_python` 时设置 `skip_lock=True`，避免死锁

#### 2. 锁管理日志增强

增加了详细的锁管理日志，便于诊断和解决锁相关的问题。

**修复内容：**

- 在 `_acquire_hosts` 方法中增加了详细的日志，包括尝试获取锁、获取成功和失败的情况
- 在 `_release_hosts` 方法中增加了详细的日志，包括尝试释放锁、释放成功和跳过的情况
- 将一些 debug 级别的日志提升为 info 级别，以便在正常日志中也能看到锁的操作情况

#### 3. localhost 连接问题修复

修复了 localhost 连接被拒绝的问题，为 localhost 添加了特殊处理逻辑。

**问题原因：**

- 当目标主机是 localhost 时，代码仍然尝试通过 SSH 连接到 localhost:22
- 导致出现 "Connection refused" 错误

**修复内容：**

- 修改了 `_build_inventory` 方法，为 localhost 添加了特殊处理逻辑
- 当目标是 "localhost" 时，使用 `ansible_connection: local` 而不是 SSH 连接
- 为 localhost 设置了默认的 Python 解释器路径 `/usr/bin/python3`

#### 4. Python 安装状态返回值修复

修复了 `install_python` 方法中 `installed` 字段的返回值问题。

**问题原因：**

- 当 tsc_python 已经安装时，`install_python` 方法返回的 `installed` 字段为 False
- 导致 LLM 认为 Python 未安装，重复尝试安装

**修复内容：**

- 修改了 `install_python` 方法中的逻辑，当 tsc_python 已经安装时，返回的 `installed` 字段为 True
- 确保 LLM 能够正确理解 Python 安装状态

### 改进

#### 1. 响应日志增强

为所有 MCP 工具添加了响应日志，以便更好地跟踪服务是否正确返回了响应。

**改进内容：**

- `ansible_shell.py` - 添加了响应日志，记录执行结果
- `ansible_copy.py` - 添加了响应日志，记录文件分发结果
- `ansible_fetch.py` - 添加了响应日志，记录文件获取结果
- `ansible_playbook.py` - 添加了响应日志，记录 playbook 执行结果
- `check_host_status.py` - 添加了响应日志，记录主机状态检查结果
- `install_python.py` - 添加了响应日志，记录 Python 安装结果
- `install_tsc_tools.py` - 添加了响应日志，记录 tsc_tools 安装结果

#### 2. SSH 配置优化

优化了 SSH 配置，确保当使用密码认证时，Ansible 会直接使用密码而不尝试公钥认证。

**改进内容：**

- 确保 `PubkeyAuthentication=no` 参数被正确包含在 SSH 命令中
- 避免因公钥认证失败导致的连接延迟
- 提高 SSH 连接的可靠性

### 技术实现

#### 锁管理机制

所有执行方法现在都使用统一的锁管理机制：

1. **获取锁** - 执行前尝试获取主机锁
2. **执行操作** - 获取锁成功后执行相应的操作
3. **释放锁** - 使用 try-finally 块确保锁在任何情况下都会被释放
4. **死锁避免** - 在调用子方法时设置 `skip_lock=True`，避免死锁

#### 日志记录

增强的锁管理日志格式：

```
2026-04-14 02:30:00 | INFO     | [LOCK] Attempting to acquire locks for hosts: ['192.168.19.35']
2026-04-14 02:30:00 | INFO     | [LOCK] Acquired lock for host: 192.168.19.35
2026-04-14 02:30:00 | INFO     | [LOCK] _acquire_hosts SUCCESS: hosts=['192.168.19.35'], new_active=['192.168.19.35']
...
2026-04-14 02:30:05 | INFO     | [LOCK] Attempting to release locks for hosts: ['192.168.19.35']
2026-04-14 02:30:05 | INFO     | [LOCK] Released host lock: 192.168.19.35
2026-04-14 02:30:05 | INFO     | [LOCK] _release_hosts done: released=['192.168.19.35'], skipped=[], remaining_active=[]
```

### 文档更新

- 更新 `README.md` - 添加 v1.11.0 功能说明
- 更新 `docs/SPEC.md` - 添加锁管理和 localhost 连接处理说明
- 更新 `docs/ARCHITECTURE.md` - 添加锁管理机制说明

---

## Version=1.10.0

2026-04-12

### Bug 修复

#### 1. Task ID 不一致问题修复

修复了 `task_id` 在 server.py 和 executor.py 中不一致的问题，导致 `get_task_detail` 查询失败。

**问题原因：**

- `server.py` 创建了一个 `task_id`
- `executor` 内部又创建了新的 `task_id`
- `task_result_store.save_result` 保存的是 executor 内部的 task_id
- 但返回给用户的是 server.py 的 task_id
- 两个 task_id 不一致导致查询失败

**修复内容：**

修改了以下函数，添加 `task_id` 可选参数，确保整个调用链使用相同的 task_id：

- `executor.py`:
  - `check_host_status()` - 添加 task_id 参数
  - `install_python()` - 添加 task_id 参数
  - `install_tsc_tools()` - 添加 task_id 参数
  - `dispatch_file()` - 添加 task_id 参数
  - `ansible_fetch()` - 添加 task_id 参数
  - `ansible_shell()` - 添加 task_id 参数
  - `run_playbook()` - 添加 task_id 参数

- `server.py`:
  - 所有 MCP 工具调用传递 task_id 给 executor
  - 所有 REST API 调用传递 task_id 给 executor
  - 移除 `result["task_id"] = task_id` 覆盖操作

#### 2. Extravars 参数类型修复

修复了 CherryStudio 传递 extravars 为 JSON 字符串时验证失败的问题。

**问题原因：**

- CherryStudio 将 extravars 作为 JSON 字符串传递
- Pydantic 验证期望字典类型，导致验证错误

**修复内容：**

- `extravars` 参数类型改为 `Optional[Union[Dict[str, Any], str]]`
- 添加字符串解析逻辑，自动将 JSON 字符串转换为字典

### 移除功能

#### 1. 移除 Playbook 实时文件监控

移除了 watchdog 库实现的实时文件监控功能。

**移除原因：**

- FastMCP 的工具注册机制限制，文件变化后需要重启服务才能使新的工具生效
- 实时监控功能实际无意义，反而增加系统复杂度

**移除内容：**

- 移除 `PlaybookScanner.start_watching()` 方法
- 移除 `PlaybookScanner.stop_watching()` 方法
- 移除 `PlaybookScanner.on_file_created/modified/deleted()` 方法
- 移除 `PlaybookEventHandler` 类
- 移除 `lib/server.py` 中的 lifespan 监控代码
- Playbooks 改为启动时加载一次

### 改进

#### 1. Playbook 参数可选性优化

- 移除元数据中的 `default` 字段
- 添加 `required: false` 标识
- 在描述中明确说明参数是可选的
- 添加 notes 提示 LLM 不要传递默认值

---

## Version=1.9.0

2026-04-11

### 新功能

#### 1. 结果摘要模式

解决大规模主机执行时返回结果超过 LLM 上下文长度限制的问题。

- **摘要返回** - 默认只返回执行摘要和失败主机详情（限制数量）
- **混合存储** - 摘要存 SQLite，详情存 JSON 文件
- **永久保留** - 详细结果永久保留，支持手动清理
- **查询工具** - 提供三个查询工具获取详细信息

#### 2. 新增 MCP 查询工具

- `get_task_detail(task_id, host)` - 查询特定主机执行详情
- `get_failed_hosts(task_id, limit, offset)` - 查询失败主机详情
- `get_all_results(task_id, limit, offset)` - 分页查询所有结果

#### 3. 返回格式变更

所有执行类工具的返回格式统一为摘要格式：

```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "partial_success",
  "summary": {
    "total": 100,
    "success": 95,
    "failed": 5
  },
  "failed_hosts": ["host1", "host2", ...],
  "failed_detail": {
    "host1": {"rc": 1, "stdout": "...", "stderr": "..."}
  },
  "has_more_failed": false,
  "elapsed": "10.50s",
  "message": "执行完成，5 台主机失败。使用 get_task_detail('xxx', host) 查看详情"
}
```

#### 4. 适用工具

以下工具已支持结果摘要模式：

- `ansible_shell` - Shell 命令执行
- `ansible_playbook` - Playbook 执行
- `ansible_copy` - 文件分发
- `ansible_fetch` - 文件获取
- `check_host_status` - 主机状态检查
- `install_python` - Python 安装
- `install_tsc_tools` - tsc_tools 安装

### 配置变更

#### 执行配置

在 `etc/tsc_ansible_mcp.toml` 中添加：

```toml
[execution]
max_failed_detail = 10
max_output_length = 1000
result_store_dir = "logs/task_results"
```

### 文件变更

#### 新增文件

- `lib/task_result_store.py` - 任务结果存储模块

#### 修改文件

- `lib/executor.py` - 添加摘要返回格式
- `lib/server.py` - 添加查询工具
- `lib/config.py` - 添加配置属性
- `etc/tsc_ansible_mcp.toml` - 添加配置项

### 文档更新

- 更新 `docs/PRD.md` - 添加结果摘要模式说明
- 更新 `docs/SPEC.md` - 添加返回格式规格
- 更新 `docs/ARCHITECTURE.md` - 添加存储架构说明

---

## Version=1.8.0

2026-04-11

### 新功能

#### 1. Ansible 执行详细日志记录

- **独立日志文件** - 创建独立的 ansible 执行日志文件 `logs/ansible_execution.log`
- **详细记录** - 记录完整的 playbook、inventory、执行参数
- **事件追踪** - 记录每个执行事件的详细信息（stdout, stderr, rc 等）
- **结果汇总** - 记录执行结果汇总（成功/失败主机数、总耗时）
- **配置灵活** - 支持启用/禁用、日志保留时间、轮转策略配置

#### 2. 日志内容

每次 ansible 执行都会记录以下详细信息：

- 执行开始：Task ID、用户、超时、目标主机、playbook 内容、inventory 内容
- 执行事件：事件类型、主机名、任务名、执行结果（stdout, stderr, rc, changed）
- 执行结果：状态、成功/失败主机数、耗时

#### 3. 日志格式

使用 loguru 标准文本格式，清晰易读：

```
2026-04-11 10:00:00 | INFO | ========== ANSIBLE EXECUTION START ==========
2026-04-11 10:00:00 | INFO | Task ID: xxx-xxx-xxx
2026-04-11 10:00:00 | INFO | Timeout: 600s
2026-04-11 10:00:00 | INFO | Targets: [host1, host2]
2026-04-11 10:00:00 | INFO | Playbook:
2026-04-11 10:00:00 | INFO |   ---
2026-04-11 10:00:00 | INFO |   - name: Check host status
...
2026-04-11 10:00:01 | INFO | [EVENT] Task: Check host status | Host: host1 | Status: OK
2026-04-11 10:00:01 | DEBUG | [EVENT DETAIL] stdout: x86_64
2026-04-11 10:00:01 | DEBUG | [EVENT DETAIL] rc: 0
...
2026-04-11 10:00:05 | INFO | ========== ANSIBLE EXECUTION RESULT ==========
2026-04-11 10:00:05 | INFO | Status: success
2026-04-11 10:00:05 | INFO | Elapsed: 5.23s
```

### 配置变更

#### 日志配置

在 `etc/tsc_ansible_mcp.toml` 中添加 ansible 执行日志配置：

```toml
[logging]
dir = "logs"
level = "DEBUG"
ansible_execution_log = "ansible_execution.log"
ansible_execution_enabled = true
ansible_execution_retention = "30 days"
ansible_execution_rotation = "50 MB"
```

### 文件变更

#### 新增文件

- `lib/ansible_logger.py` - Ansible 执行详细日志记录器

#### 修改文件

- `lib/config.py` - 添加 ansible 日志配置属性
- `lib/executor.py` - 集成 ansible 执行日志记录
- `etc/tsc_ansible_mcp.toml` - 添加 ansible 日志配置
- `docs/PRD.md` - 添加 ansible 执行日志需求
- `docs/SPEC.md` - 添加 ansible 执行日志规格
- `docs/ARCHITECTURE.md` - 添加日志架构说明
- `docs/TODO.md` - 添加任务清单

### 文档更新

- 更新 `docs/PRD.md` - 添加 Ansible 执行日志需求
- 更新 `docs/SPEC.md` - 添加 Ansible 执行日志规格
- 更新 `docs/ARCHITECTURE.md` - 添加日志架构说明
- 更新 `README.md` - 添加 v1.8.0 功能说明

---

## Version=1.7.0

2026-04-09

### 新功能

#### 1. JWT Token 字符串保存

- **Token 字符串保存** - 签发的 JWT token 字符串现在会保存到 `etc/jwt_issued_tokens.json`
- **方便管理** - 可以直接查看已签发的 token 字符串，无需重新生成
- **记录完整** - JWT 记录包含完整的 token 字符串和元数据

#### 2. 中间件重构

- **BaseHTTPMiddleware** - 使用 Starlette 的 `BaseHTTPMiddleware` 基类重写中间件
- **代码简化** - 无需手动处理 ASGI 规范，代码更简洁
- **自动处理** - 自动处理请求体和响应体

#### 3. SSE 格式支持

- **SSE 响应解析** - 支持 Server-Sent Events (SSE) 格式的响应
- **自动检测** - 自动检测响应格式（SSE 或纯 JSON）
- **正确返回** - 正确解析和返回 SSE 格式的响应

#### 4. 详细日志记录

- **唯一 request_id** - 每个请求分配唯一的 request_id
- **完整生命周期** - 记录请求的完整生命周期
- **关键步骤** - 记录 JWT 验证、权限检查、工具过滤等关键步骤
- **耗时统计** - 记录每个步骤的耗时

### 技术改进

#### 中间件架构

```
旧架构（v1.6.0）：
手动实现 ASGI 规范
├── 处理 scope, receive, send
├── 手动读取请求体
└── 手动发送响应

新架构（v1.7.0）：
使用 BaseHTTPMiddleware
├── 自动处理 ASGI 规范
├── 自动处理请求体和响应体
└── 简化代码逻辑
```

#### SSE 格式处理

```
检测响应格式
├── 判断是否以 "event:" 开头
├── SSE 格式：提取 "data:" 行
└── 纯 JSON：直接解析

返回响应
├── SSE 格式：返回 "event: message\ndata: {JSON}\n\n"
└── 纯 JSON：返回标准 JSON 响应
```

### 文件变更

#### 修改文件

- `lib/middleware.py` - 重写中间件，使用 BaseHTTPMiddleware
- `lib/jwt_utils.py` - JWT token 字符串保存到记录文件
- `bin/server.py` - 从配置文件读取日志级别

### 配置变更

#### 日志级别配置

现在可以在配置文件中设置日志级别：

```toml
[logging]
dir = "logs"
level = "DEBUG"  # 支持 DEBUG, INFO, WARNING, ERROR
```

### 文档更新

- 更新 `docs/PRD.md` - 添加 JWT token 字符串保存说明
- 更新 `docs/SPEC.md` - 添加 JWT 记录字段说明
- 更新 `docs/ARCHITECTURE.md` - 添加中间件技术实现细节
- 更新 `README.md` - 添加 v1.7.0 功能说明

### 测试验证

- ✅ JWT token 字符串正确保存到记录文件
- ✅ 中间件正确处理 SSE 格式响应
- ✅ 工具列表过滤功能正常
- ✅ 详细日志正确记录
- ✅ Cherry Studio 客户端兼容性测试通过

---

## Version=1.6.0

2026-04-09

### 新功能

#### 1. MCP 工具列表角色过滤

- **工具列表过滤** - 根据用户角色过滤 MCP 工具列表
  - admin 角色：可以看到所有 MCP 工具
  - user 角色：只能看到 playbook 相关工具
- **双重保护机制** - 实现"深度防御"原则
  - 第一层：MCP 协议层面权限检查（中间件拦截）
  - 第二层：工具函数内部权限检查（防止绕过）
- **上下文传递** - 使用 contextvars 传递用户信息
- **审计日志增强** - 记录工具列表过滤和权限检查

#### 2. 核心组件

- **lib/context_vars.py** - 上下文变量管理模块
- **lib/middleware.py** - MCP 授权中间件
- **lib/permission.py** - 工具函数权限检查模块

### 技术实现

#### MCP 授权中间件

拦截 MCP 协议请求，实现工具列表过滤和权限检查：

```
MCP Client 请求
    ↓
JWT 认证中间件（提取角色信息）
    ↓
授权中间件（过滤工具列表）
    ↓
工具执行（权限检查）
    ↓
返回结果
```

#### 双重保护机制

防止 LLM 通过其他方式（如历史对话、文档等）得知工具名称后尝试调用：

1. **第一层保护**：MCP 协议层面
   - 中间件拦截 `tools/list` 请求，过滤工具列表
   - 中间件拦截 `tools/call` 请求，检查权限

2. **第二层保护**：工具函数内部
   - 每个 admin 专用工具函数内部都有权限检查
   - 即使中间件失效，工具函数本身也会拒绝执行

### 安全增强

- **防止权限绕过** - LLM 无法通过任何方式调用无权限的工具
- **深度防御** - 多层保护确保安全
- **审计追踪** - 所有权限检查都有日志记录

### 文档更新

- 更新 PRD.md - 添加 MCP 工具角色过滤说明
- 更新 SPEC.md - 添加技术规格和双重保护机制
- 更新 ARCHITECTURE.md - 添加架构图和核心组件
- 更新 API-REFERENCE.md - 添加工具列表
- 更新 README.md - 添加功能说明

---

## Version=1.5.0

2026-04-08

### 新功能

#### 1. JWT 认证系统

- **JWT 身份认证** - 使用 JWT (JSON Web Token) 替换简单的 Bearer Token 认证
- **角色权限控制** - 支持 admin、user 和自定义角色
- **权限通配符匹配** - 支持 `*` 和 `playbook_*` 等通配符匹配
- **密钥自动生成** - 密钥长度不足时自动生成符合要求的密钥
- **JWT 生成器工具** - 提供 `bin/generate_jwt.py` 工具管理 JWT

#### 2. 动态工具命名调整

- **统一命名规则** - 动态生成的 playbook 工具添加 `playbook_` 前缀
- **示例**: `collect_iaas_info.yml` -> `playbook_collect_iaas_info`

#### 3. 审计日志增强

- **请求参数记录** - 记录目标主机、命令等参数
- **响应状态记录** - 记录操作结果摘要
- **完整数据记录** - 支持记录完整的请求和响应数据

### 破坏性变更

#### 认证方式迁移

v1.5.0 完全替换了认证系统，旧的 Token 认证已移除：

- 移除 `etc/tokens.txt` 文件
- 移除 `etc/tokens.txt.example` 文件
- 移除 `bin/generate_api_key.py` 工具
- 移除配置文件中的 `api_keys` 配置项

**迁移步骤**:

1. 使用 `python bin/generate_jwt.py --issue --sub <user_id> --name <name> --role admin` 签发新的 JWT
2. 更新客户端代码，使用新的 JWT Token
3. 更新配置文件，使用 JWT 配置项

### JWT 使用指南

#### 生成 JWT

```bash
# 签发 JWT（永久有效）
python bin/generate_jwt.py --issue --sub user_001 --name "张三" --role admin

# 签发 JWT（24小时有效期）
python bin/generate_jwt.py --issue --sub user_002 --name "李四" --role user --expires 24h

# 列出已签发的 JWT
python bin/generate_jwt.py --list

# 验证 JWT
python bin/generate_jwt.py --verify <token>

# 撤销 JWT
python bin/generate_jwt.py --revoke <jwt_id>
```

#### 使用 JWT

```bash
curl -H "Authorization: Bearer <your_jwt_token>" \
  http://localhost:8500/api/v1/executor/stats
```

### 角色权限配置

在 `etc/tsc_ansible_mcp.toml` 中配置角色权限：

```toml
[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
# 支持自定义角色
# readonly = ["list_playbooks", "get_task_status"]
```

**权限说明**:

- `*`: 表示所有工具
- `playbook_*`: 表示所有动态生成的 playbook 工具

### 配置变更

旧配置（v1.4.0）:

```toml
[auth]
enabled = true
tokens_file = "etc/tokens.txt"
```

新配置（v1.5.0）:

```toml
[auth]
enabled = true
jwt_secret_key_file = "etc/jwt_secret_key.txt"
jwt_issued_tokens_file = "etc/jwt_issued_tokens.json"

[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
```

### 文件变更

#### 新增文件

- `lib/jwt_utils.py` - JWT 工具模块
- `bin/generate_jwt.py` - JWT 生成器工具
- `etc/jwt_secret_key.txt` - JWT 密钥文件（自动生成）
- `etc/jwt_issued_tokens.json` - JWT 签发记录文件

#### 删除文件

- `etc/tokens.txt.example` - 旧 Token 示例文件
- `bin/generate_api_key.py` - 旧 API Key 生成工具

### 依赖变更

- 新增 `PyJWT>=2.8.0` 依赖

### 文档更新

- 更新 `README.md` - JWT 认证说明、工具命名规则、配置示例
- 更新 `docs/SPEC.md` - JWT 认证规格
- 更新 `docs/PRD.md` - JWT 认证需求
- 更新 `docs/ARCHITECTURE.md` - JWT 认证架构
- 更新 `docs/API-REFERENCE.md` - JWT 认证 API 说明
- 更新 `docs/TODO.md` - v1.5.0 任务清单

---

## Version=1.4.0

2026-04-07

### 新功能

#### 1. 动态 Playbook 工具生成

- **自动工具注册** - 服务启动时自动扫描 playbooks 目录，为每个 playbook 动态生成独立的 MCP 工具
- **工具命名** - 使用 playbook 文件名（不含扩展名）作为工具名称
- **元数据解析** - 支持 JSON 格式的元数据解析，自动生成工具描述
- ~~**文件监控** - 使用 watchdog 库监控 playbook 文件变化（需重启服务生效）~~ (已在 v1.10.0 移除)
- **LLM 体验提升** - LLM 无需先调用 list_playbooks，可直接调用 playbook 工具

#### 2. 技术改进

- ~~**新增依赖** - 添加 watchdog>=3.0.0 用于文件监控~~ (已在 v1.10.0 移除)
- **PlaybookScanner 类** - 新增 `lib/playbook_scanner.py` 模块
- **元数据规范** - playbook 必须包含 description 字段才能生成工具

## Version=1.3.0

2026-04-07

### 新功能

#### 1. API 认证系统

- **Bearer Token 认证** - 实现标准的 HTTP Bearer Token 认证机制
- **Token 文件管理** - Token 独立存储在 `etc/tokens.txt`，不暴露在主配置文件中
- **认证开关** - 通过配置文件灵活控制认证启用/禁用
- **中间件保护** - 所有 API 端点和 MCP 端点统一受认证保护

#### 2. 上下文管理工具

新增 5 个上下文管理 MCP 工具，支持在会话间持久化存储数据：

- **set_context** - 设置上下文键值对
- **get_context** - 获取上下文值
- **delete_context** - 删除指定的上下文键值对
- **list_contexts** - 列出所有上下文键值对
- **clear_contexts** - 清空所有上下文数据

#### 3. Python 检测逻辑优化

- **新增字段** - `tsc_python_installed` 字段，区分系统 Python 和 tsc_python
- **逻辑修复** - `install_python` 现在正确判断是否需要安装 tsc_python
- **语义明确** - 即使主机有系统 Python，也可以安装独立的 tsc_python 环境

#### 4. 代码质量改进

- **sys.path.insert 优化** - 修复路径插入逻辑，确保优先级正确
- **动态路径** - 使用 `Path(__file__).parent` 替代硬编码路径
- **高效判断** - 只在必要时才进行路径操作

### 认证配置

```toml
[auth]
enabled = true
tokens_file = "etc/tokens.txt"
```

### Token 管理

- **生成工具** - 提供 `bin/generate_api_key.py` 生成安全的随机 Token
- **文件格式** - 每行一个 Token，支持注释
- **安全存储** - `etc/tokens.txt` 已添加到 `.gitignore`
- **示例文件** - 提供 `etc/tokens.txt.example` 作为模板

### 使用方式

#### REST API 认证

```bash
curl -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  http://localhost:8500/api/v1/executor/stats
```

#### MCP 客户端认证

```json
{
  "mcpServers": {
    "tsc-ansible": {
      "url": "http://localhost:8500/mcp",
      "headers": {
        "Authorization": "Bearer sk-tsc-ansible-mcp-2026"
      }
    }
  }
}
```

### 工具列表更新

MCP 工具总数从 9 个增加到 14 个：

1. ansible_shell
2. install_python
3. check_host_status
4. get_task_status
5. install_tsc_tools
6. ansible_copy
7. ansible_fetch
8. list_playbooks
9. ansible_playbook
10. **set_context** (新增)
11. **get_context** (新增)
12. **delete_context** (新增)
13. **list_contexts** (新增)
14. **clear_contexts** (新增)

### 安全特性

- Token 使用加密安全的随机数生成器生成
- 详细的认证日志记录
- 标准的 HTTP 401 响应
- WWW-Authenticate 头支持

### 文档更新

- 新增 `docs/AUTH-GUIDE.md` - 完整的认证使用指南
- 新增 `docs/PYTHON_DETECTION_FIX.md` - Python 检测逻辑修复说明
- 新增 `docs/SYS_PATH_FIX.md` - sys.path.insert 修复说明
- 更新 `README.md` - 添加认证说明和版本号更新
- 更新 `docs/API-REFERENCE.md` - 添加认证请求头说明
- 更新 `docs/PRD.md` - 添加认证需求和上下文管理工具

### 测试验证

- 无 Token 访问返回 401
- 错误 Token 访问返回 401
- 正确 Token 访问返回 200
- 健康检查端点无需认证
- API 文档端点无需认证
- 上下文管理工具功能正常
- Python 检测逻辑正确区分系统 Python 和 tsc_python

---

## Version=1.1.2

2026-04-07

### 改进

#### 智能 Inventory 管理

- **Playbook 支持** - 所有方法（ansible_shell, ansible_copy, ansible_fetch, ansible_playbook）现在都使用智能 inventory 管理
- **Python 解释器缓存** - Playbook 执行时正确使用缓存的 Python 解释器
- **日志增强** - 添加详细的缓存使用日志，包括 Python 解释器信息

#### MCP_INSTRUCTIONS 优化

- **优先级说明** - 在开头添加"重要：优先使用 Playbook"的说明
- **使用场景对比** - 添加 Playbook vs ansible_shell 使用场景对比表
- **优先级顺序** - 明确了3级优先级顺序：
  1. 优先级 1 - 调用 `list_playbooks()` 查看可用的 playbook
  2. 优先级 2 - 如果有合适的 playbook，使用 `ansible_playbook()` 执行
  3. 优先级 3 - 如果没有合适的 playbook，才使用 `ansible_shell()`
- **理由说明** - 列出了5个优先使用 Playbook 的理由

### 修复

#### Inventory 管理

- **修复 Bug** - Playbook 执行时未使用缓存的 inventory
- **修复 Bug** - Python 解释器未正确传递给 Playbook
- **优化逻辑** - 所有方法统一使用 `use_cached=True` 参数

### 文档更新

- 更新 `MCP_INSTRUCTIONS` - 强调优先使用 Playbook
- 更新日志级别 - 将缓存使用日志从 DEBUG 改为 INFO

### 测试验证

#### 功能测试

- ✅ Playbook 执行使用缓存的 inventory
- ✅ Python 解释器正确识别并保存
- ✅ 后续操作自动使用缓存的 Python 解释器
- ✅ 日志正确显示缓存使用情况

---

## Version=1.1.1

2026-04-07

### 新功能

#### 智能 Inventory 管理

- **智能验证机制** - LLM 提供的凭据会先进行连接测试，验证成功后才更新主 inventory 文件
- **自动 Fallback** - 当新凭据连接失败时，自动尝试使用缓存的凭据，确保服务连续性
- **Inventory 保护** - 错误凭据不会覆盖已有的正确凭据，保持 inventory 的可靠性
- **新增方法**：
  - `_test_connectivity()` - 独立的连接性测试方法
  - `update_host_credentials()` - 仅在验证成功后更新凭据
  - `_build_inventory(use_cached)` - 支持强制使用缓存 inventory

#### 持久化上下文存储

- **Context 数据模型** - 新增 `Context` 表用于存储键值对
- **ContextRepository** - 新增上下文仓库类，提供 CRUD 操作
- **MCP 工具** - 新增 4 个上下文管理工具：
  - `set_mcp_context(key, value)` - 保存上下文
  - `get_mcp_context(key)` - 获取上下文
  - `list_mcp_context()` - 列出所有上下文
  - `delete_mcp_context(key)` - 删除上下文
- **使用场景** - 记住常用主机地址、保存配置信息、跨会话共享

#### Playbook 元数据增强

- **JSON 注释格式** - 支持 LLM 最友好的 JSON 注释格式元数据
- **完整调用示例** - 元数据中可包含完整的函数调用示例
- **类型信息** - 参数支持类型、默认值、详细描述
- **新增方法** - `_extract_json_metadata()` 解析 JSON 格式元数据
- **向后兼容** - 同时支持 JS 风格和 Pythonic 风格

#### IaaS 信息采集 Playbook

- **collect_iaas_info.yml** - 新增专用的 IaaS 信息采集 playbook
- **功能** - 采集处理器、内存、存储（RAID）、操作系统、包管理器信息
- **可选参数** - `runtime` 参数支持采集实时资源使用状态
- **输出格式** - 使用 `jq` 格式化 JSON 输出

### 改进

#### 文档完善

- **inventory_management.md** - 新增智能 Inventory 管理完整文档
  - 工作流程说明
  - 使用示例
  - 故障排查指南
  - 最佳实践
- **playbooks/README.md** - 更新 Playbook 编写指南
  - JSON 元数据规范
  - 最佳实践
  - 使用示例

#### 日志增强

- **详细日志** - 增加连接测试、凭据验证、fallback 过程的详细日志
- **日志分类** - 使用 INFO、WARNING、DEBUG 等级别区分日志重要性
- **可追溯性** - 每个关键操作都有日志记录

### 修复

#### Inventory 管理逻辑

- **修复 Bug** - 修复错误凭据会覆盖正确凭据的问题
- **优化逻辑** - 只有新凭据验证成功才更新 inventory
- **Fallback 改进** - 新凭据失败时不再修改 `test_result`，避免误更新

#### Playbook 执行

- **移除问题任务** - 移除 `Save IaaS information to file` 任务（因 `ansible_date_time` 未定义）
- **简化流程** - Playbook 只负责采集和显示信息，不保存文件

### 变更

#### 清理示例文件

- 删除 `install_nginx.yml`
- 删除 `deploy_docker_container.yml`
- 删除 `monitor_system.yml`
- 删除 `install_nginx_v2.yml`
- 删除 `install_nginx_v3.yml`
- 保留 `system_check.yml`（原有示例）
- 新增 `collect_iaas_info.yml`（生产使用）

### 数据库变更

新增 `context` 表：

```sql
CREATE TABLE context (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    created_at VARCHAR(30) NOT NULL,
    updated_at VARCHAR(30) NOT NULL
);
```

### 文档更新

- 新增 `CHANGELOG.md` - 详细的版本更新日志
- 新增 `docs/inventory_management.md` - Inventory 管理逻辑详细说明
- 新增 `docs/VERSION-1.1.1.md` - v1.1.1 版本详细说明
- 更新 `README.md` - 添加版本号，更新功能说明
- 更新 `playbooks/README.md` - Playbook 编写指南

### 测试验证

#### 功能测试

- ✅ 使用正确凭据连接成功并更新 inventory
- ✅ 使用错误凭据自动 fallback 到缓存凭据
- ✅ Inventory 文件保持正确密码，未被错误密码覆盖
- ✅ 持久化上下文存储和读取
- ✅ JSON 元数据解析
- ✅ IaaS 信息采集

#### 兼容性测试

- ✅ 通过 ansible-lint production 级别验证
- ✅ Python 3.13 兼容
- ✅ 向后兼容旧版元数据格式

---

## Version=1.1.0

2026-04-06

### 新功能

#### Playbook 执行能力

- **list_playbooks** - 列出 playbooks 目录下所有可用的 playbook 文件
- **ansible_playbook** - 执行指定的 playbook 文件，支持传入额外变量
- **Playbook 元数据支持** - 支持读取 playbook 文件顶部的元数据（description, author, version, tags, parameters）

#### 文件操作增强

- **ansible_fetch** - 从远程主机获取文件到本地，支持扁平化目录结构选项

#### 主机状态检查增强

- **check_host_status** - 合并了原来的 detect_environment 功能
- 自动保存主机凭据到 Inventory
- 自动检测并保存 Python 解释器路径
- 主机不可达时跳过后续操作

### 接口变更

#### MCP 工具重命名

| 原名称               | 新名称              | 说明                 |
| -------------------- | ------------------- | -------------------- |
| `execute_command`    | `ansible_shell`     | 重命名，统一命名风格 |
| `dispatch_file`      | `ansible_copy`      | 重命名，统一命名风格 |
| `detect_environment` | `check_host_status` | 合并功能             |

#### MCP 工具删除

| 工具名称        | 说明               |
| --------------- | ------------------ |
| `add_temp_host` | 删除，改为内部使用 |

#### REST API 路径变更

| 原路径                           | 新路径                      |
| -------------------------------- | --------------------------- |
| `POST /api/v1/executor/execute`  | `POST /api/v1/shell`        |
| `POST /api/v1/files/dispatch`    | `POST /api/v1/copy`         |
| `POST /api/v1/hosts/environment` | `POST /api/v1/hosts/status` |

#### 新增 REST API

| 路径                             | 说明               |
| -------------------------------- | ------------------ |
| `GET /api/v1/playbooks`          | 列出 playbook 文件 |
| `POST /api/v1/playbooks/execute` | 执行 playbook      |
| `POST /api/v1/fetch`             | 获取远程文件       |

### 改进

#### 错误处理

- 主机不可达时自动跳过后续操作，返回明确的错误信息
- 安装失败时提供详细的错误原因和建议
- 所有操作返回统一的 task_id，支持通过 get_task_status 查询

#### 日志输出

- check_host_status 增加详细的执行日志
- 记录每个检测步骤的结果
- 记录主机状态汇总信息

#### Python 检测优化

- 优先检测 tsc_python 环境
- 支持多个 Python 路径检测
- 自动选择最优的 Python 解释器

#### Inventory 管理

- 自动保存主机凭据（user, port, password, private_key）
- 自动保存 Python 解释器路径
- 支持增量更新，不覆盖已有信息

### 配置变更

新增 `[playbooks]` 配置段：

```toml
[playbooks]
path = "playbooks"
```

### 目录结构变更

新增 `playbooks/` 目录，用于存放 playbook 文件。

### 文档更新

- 更新 README.md，反映 v1.1.0 变更
- 更新 API-REFERENCE.md，补充完整的 REST API 文档
- 更新 PRD.md，添加 Playbook 元数据规范
- 更新 TODO.md，记录开发任务

### 已知问题

- 部分边缘发行版可能需要手动适配
- Playbook 执行超时时间可能需要根据复杂度调整

---

## Version=1.0.0

2026-04-06

### 新功能

#### 核心功能

- **主机状态检查** - 支持检查网络连通性、SSH 连接、Python 环境、tsc_tools 安装状态
- **环境探测** - 自动识别主机架构（x86_64, aarch64）和操作系统发行版
- **软件安装** - 支持远程安装 tsc_tools 工具集和 tsc_python 环境
- **命令执行** - 批量在多台主机上执行 shell 命令
- **文件分发** - 将本地文件传输到远程主机的指定路径

#### 接口服务

- **MCP 接口** - 提供 Model Context Protocol 接口，支持 AI 助手集成
- **REST API** - 提供完整的 RESTful API，支持 Swagger 文档
- **统一服务** - MCP 和 REST API 共享同一服务端口

#### 管理功能

- **任务管理** - 支持任务创建、查询、删除和统计
- **主机清单** - 支持临时主机缓存，简化认证流程
- **软件包缓存** - 自动扫描和缓存可用软件包信息

### 技术特性

#### 架构设计

- 基于 Ansible Runner 的执行引擎
- FastAPI + FastMCP 统一服务架构
- SQLite 数据库存储任务信息
- YAML 格式的软件包缓存

#### 安全特性

- 高危命令拦截机制
- SSH 密钥和密码双重认证支持
- 严格的安装顺序控制

#### 性能优化

- 支持批量主机并行操作
- 可配置的执行超时和并发数
- 智能的软件包版本选择

### 支持的操作系统

#### RedHat 系列

- RHEL (Red Hat Enterprise Linux)
- CentOS
- AlmaLinux
- Rocky Linux
- Fedora

#### Debian 系列

- Ubuntu
- Debian
- Linux Mint

#### Arch 系列

- Arch Linux
- Manjaro

#### 其他

- Alpine Linux
- openSUSE
- openEuler
- HCE (Huawei Cloud Euler)
- NingOS
- Euler

---

## 版本历史

### v1.1.2 (2026-04-07)

- 修复 Playbook 未使用缓存 inventory 的 Bug
- 所有方法统一使用智能 inventory 管理
- Python 解释器正确缓存并传递给 Playbook
- 优化 MCP_INSTRUCTIONS，强调优先使用 Playbook
- 增强日志输出，显示缓存使用情况

### v1.1.1 (2026-04-07)

- 新增智能 Inventory 管理（验证 + Fallback）
- 新增持久化上下文存储功能
- 新增 JSON 注释格式的 Playbook 元数据
- 新增 IaaS 信息采集 Playbook
- 修复 Inventory 管理逻辑 Bug
- 完善文档和日志

### v1.0.0 (2026-04-06)

- 首次发布
- 实现核心功能
- 提供双接口服务（MCP + REST API）
- 完整的 API 文档
