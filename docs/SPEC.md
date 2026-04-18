# Technical Specification (SPEC)

## 1. Technical Constraints

### 1.1 Runtime Environment

- **Python Version**: `3.13`. A virtual environment is provided at the project root: `.venv`(use `source .venv/bin/activate` to active it.).
- **Local Bash**: Version `5` or higher.
- **Target Host Bash**: Version `4` or higher.

### 1.2 Mandatory Requirements

- All documentation and code must use **half-width (ASCII)** punctuation.
- Python code must follow **Object-Oriented Programming (OOP)** principles.
- Python path operations must exclusively use the `pathlib` standard library.
- Logging must be managed via `loguru`. The logging module must be encapsulated in `tsc_logger.py` under the `lib` directory.
- Database management must utilize an **ORM**.
- Any API interface must provide **Swagger** documentation.
- Python `requests` usage must employ a persistent `Session` object.
- **MCP** tools must include explicit English `instructions` in their definitions.
- **LANGUAGE** Comments must use English.
- Python YAML parsing must strictly use `yaml.safe_load()` or `yaml.safe_load_all()`.
- Python code must use **Google-style Docstrings**.
- JavaScript code must use **JSDoc**.
- Shell scripts must use **Google-style function comments**.
- Python code must include **type hints**.
- A `README.md` file must exist at the project root, describing the project's functionality, installation, configuration, and usage.
- A `release-note.md` file must exist at the project root to describe version changes. The third line must explicitly state the current version using the format: `## Version=1.5.0` (replace with actual version).
- A `Dockerfile` must exist at the project root for containerization.
- A `compose.yml` file must exist for local development environment setup. (Use of `docker-compose.yml` is deprecated).

### 1.3 Prohibitions

- **No Emojis**: Forbidden in all documentation and code.
- **No ASCII Art**: Forbidden in all documentation and code. Use **Mermaid** flowchart syntax if diagrams are necessary.
- **No Procedural Python**: Object-Oriented Programming is mandatory; procedural style is forbidden.
- **No Raw SQL (Primary Rule)**: Database management and operations must primarily use an **ORM**. **Exception**: `Raw SQL` is allowed **only** for complex read-only analytics or when ORM performance proves insufficient, subject to **Code Review approval**.
- **No Pickle**: Python `pickle` serialization is forbidden.
- **No `os.path`**: Python path operations using `os.path` are forbidden (use `pathlib` instead).
- **No TypeScript**: TypeScript is forbidden.
- **No Full-width Punctuation**: Full-width characters are forbidden in all documentation and code.
- **No Complex Shell Logic**: Shell scripts must not use compound statements like multiple `||` or `&&`. Use explicit `if/else/elif` blocks instead.
- **No Insecure Deserialization**: Forbidden. Always validate and sanitize data from untrusted sources before processing (e.g., JSON payloads, YAML files from external sources).
- **No Hardcoded Secrets**: Forbidden. Secrets must be loaded from environment variables or secure vaults.

### 1.4 Preferred Choices

- **Backend Frameworks**:
  - **Django**: Default choice for projects requiring a complex built-in **admin interface**, **authentication system**, and rapid CRUD development. Leverages its "batteries-included" philosophy.
  - **FastAPI**: Preferred for high-concurrency APIs, microservices, or projects prioritizing minimal latency and asynchronous I/O. Suitable when a custom admin panel is preferred over Django's monolithic structure.
- **Interface Design**: `RESTful` > `RPC`; `Asynchronous` > `Synchronous`.
- **Database Operations**: `SQLAlchemy` (with `FastAPI`) or `Django ORM` (with `Django`) as the primary mechanism.
- **Configuration Files**: Priority order: `TOML` > `INI` > `YAML` > `JSON` > `Python Dict`.
- **MCP Transport**: Prefer `Streamable HTTP` over `SSE`.
- **MCP Tools**: All tool definitions must include explicit **English** `instructions` detailing preconditions, inputs, and expected outputs.
- **Security & Safety**: Avoid `eval()` in Python and Shell. If absolutely necessary, **must request manual human confirmation** before execution.
- **WebSockets**: Do not consider WebSockets unless bidirectional interaction is strictly required.
- **LOG**: Prefer more detailed logging (from debug to error levels). Whenever attempting to fix a bug, add additional logs directly within the malfunctioning code to aid diagnosis.

### 1.5 Code Formatting & Validation

If validation fails, prompt the user for manual intervention.

- **Python Scripts**:
  - Type checking via `mypy`.
  - Formatting via `black`.
  - Linting via `pylint`.
- **Shell Scripts**:
  - Formatting via `dev_tools/shfmt`.
  - Validation via `dev_tools/shellcheck`.
- **Ansible Playbooks**:
  - Validation via `ansible-lint`.
- **JavaScript**:
  - Linting via `eslint` (Google Style Guide).

## 2. 路径约束

- `.venv/`: 本工具 `python` 虚环境
- `bin/`: 本工具脚本, 可执行文件
- `docs/`: 设计文档
- `tmp`: 临时文件
- `logs/`: 日志文件
- `lib/`: 库/包文件
- `test/`: 测试文件
- `dev_tools/`: 开发辅助工具, 如 `shfmt`, `shellcheck`
- `roles`, `playbooks/`, `retries`, `ansible.cfg`: ansible 相关文件路径
- `pylintrc`: `pylint` 配置文件
- `pyproject.toml`: `mypy` 配置文件
- `.eslintrc.js`: `eslint` 配置文件
- `etc/inventory.yml`: inventory配置
- `etc/tsc_ansible_mcp.toml`: 主配置文件
- `etc/jwt_secret_key.txt`: JWT 密钥文件（不提交到 git）
- `etc/jwt_issued_tokens.json`: JWT 签发记录文件
- `logs/tsc_ansible_mcp.db`: SQLite 数据库

## 3. 目标服务器基础运行环境

### 3.1 tsc_tools

#### 3.1.1 tsc_tools 安装包

nginx `base_url`, `分发路径` 可在主配置文件配置

| 属性       | 值                                                 |
| ---------- | -------------------------------------------------- |
| 安装包格式 | `tsc_tools-{version}-{arch}-{date}.sh`             |
| 分发方式   | `nginx` 静态文件服务                               |
| nginx 服务 | 本机环境 `http://192.168.19.22` (主配置文件可配置) |
| 分发路径   | `/tsc_tools-2.0.3.beta10-noarch-20260210.sh`       |

**安装包 URL 示例**：

```text
http://192.168.19.22/tsc_python-0.9.5-Redhat-x86_64-20260330.sh
```

#### 3.1.2 安装后路径

| 路径            | 说明                                                            |
| --------------- | --------------------------------------------------------------- |
| 安装根目录      | `/home/tsc/tsc_tools/micromamba/envs/tsc_python`                |
| Python 解释器   | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`    |
| Python 版本链接 | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3.13` |

#### 3.1.3 幂等性检查顺序

执行 `tsc_tools` 安装前，按以下方法检查是否已安装：

1. `test -d /home/tsc/tsc_tools/`
2. `test -f /home/tsc/tsc_tools/release-note.md`

若任一检查通过，则跳过安装。

### 3.2. Python 环境规格

#### 3.2.1 tsc_python 安装包

| 属性        | 值                                                 |
| ----------- | -------------------------------------------------- | --- |
| 安装包格式  | `tsc_python-{version}-{distro}-{arch}-{date}.sh`   |
| python 版本 | `3.13`                                             |
| 分发方式    | `nginx` 静态文件服务                               |
| nginx 服务  | 本机环境 `http://192.168.19.22` (主配置文件可配置) |
| 分发路径    | `/tsc_python-0.9.5-redhat-x86_64-20260330.sh`      |     |

**安装包 URL 示例**：

```text
http://192.168.19.22/tsc_python-0.9.5-Redhat-x86_64-20260330.sh
```

### 3.2.2 安装后路径

| 路径            | 说明                                                            |
| --------------- | --------------------------------------------------------------- |
| 安装根目录      | `/home/tsc/tsc_tools/micromamba/envs/tsc_python`                |
| Python 解释器   | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`    |
| Python 版本链接 | `/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3.13` |

### 3.2.3 幂等性检查顺序

执行 Python 安装前，按以下顺序检查是否已安装：

1. 系统 Python：`command -v python3`
2. tsc_python：`test -x /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`

若任一检查通过，则跳过安装。

## 4. SSH 认证规格

### 4.1 认证方式优先级

依据优先级 fallback

| 优先级 | 认证方式      | 参数       | SSH 选项                                                              |
| ------ | ------------- | ---------- | --------------------------------------------------------------------- |
| 1      | 密码认证      | `password` | 增加`-o PreferredAuthentications=password -o PubkeyAuthentication=no` |
| 2      | ~/.ssh/config | 无需参数   | 操作系统默认行为                                                      |
| 3      | SSH 密钥      | 无需参数   | 操作系统默认行为                                                      |

### 4.2 SSH 连接参数

| 参数                  | 默认值           | 说明                   |
| --------------------- | ---------------- | ---------------------- |
| 端口                  | 继承操作系统默认 | 可通过 `port` 参数覆盖 |
| 用户                  | root             | 可通过 `user` 参数覆盖 |
| 超时                  | 600s             | 主配置文件 中          |
| StrictHostKeyChecking | no               | 禁用主机密钥检查       |
| ForwardX11            | no               | 禁用 X11 转发          |
| GSSAPIAuthentication  | no               | 禁用 GSS               |
| VerifyHostKeyDNS      | no               | 禁用dns检查            |
| StrictHostKeyChecking | no               | 禁用服务端指纹检查     |
| UserKnownHostsFile    | no               | 禁用指纹记录           |

### 4.3 密码认证特殊处理

当使用密码认证时，必须添加以下 SSH 选项以避免尝试密钥认证：

```bash
-o PreferredAuthentications=password -o PubkeyAuthentication=no
```

**原因**：开发机器可能存在需要密码的 SSH 密钥，默认会尝试密钥认证导致卡住。

## 5. 归一化映射规格

### 5.1 架构映射

| Original Value    | Normalized Value  |
| --------- | --------- |
| `aarch64` | `aarch64` |
| `arm64`   | `aarch64` |
| `x86_64`  | `x86_64`  |
| `amd64`   | `x86_64`  |

### 5.2 发行版映射

| Original Value           | Normalized Value |
| ---------------- | -------- |
| `rhel`           | `RedHat` |
| `centos`         | `RedHat` |
| `almalinux`      | `RedHat` |
| `rocky`          | `RedHat` |
| `fedora`         | `RedHat` |
| `ubuntu`         | `Debian` |
| `debian`         | `Debian` |
| `linuxmint`      | `Debian` |
| `arch`           | `Arch`   |
| `manjaro`        | `Arch`   |
| `alpine`         | `Alpine` |
| `suse`           | `Suse`   |
| `opensuse`       | `Suse`   |
| `openeuler`      | `Euler`  |
| `fitserveros`    | `Euler`  |
| `fitstarryskyos` | `Euler`  |
| `hce`            | `Euler`  |
| `ningos`         | `Euler`  |

### 5.3 Tool Package Name & Architecture Mapping
eg: `tsc_tools-2.0.3.beta9-noarch-20260323.sh`, `tsc_python-0.9.7-Euler-x86_64-20260408.sh`
explan: `package_name-version<-distro>-arch-release_date.sh`
map:

| Original Value | ormalized Value | target system |
| --- | --- | --- |
| arch | x86_64 | x86_64 |
| arch | aarch64 | aarch64/amd64 |
| arch | noarch | x86_64/amd64/aarch64/amd64 |

## 6. 执行参数规格

### 6.1 并发控制

| 参数    | 默认值 | 说明             |
| ------- | ------ | ---------------- |
| `forks` | 10     | 同时连接的主机数 |

### 6.2 超时控制

| 参数                 | 默认值 | 最大值 | 说明             |
| -------------------- | ------ | ------ | ---------------- |
| `default_timeout`    | 600s   | -      | 默认执行超时     |
| `max_timeout`        | 3600s  | -      | 最大允许超时     |
| `task_timeout`       | 600s   | -      | Ansible 任务超时 |
| `connection_timeout` | 30s    | -      | SSH 连接超时     |

### 6.3 重试策略

| 场景     | 重试次数 | 重试间隔 |
| -------- | -------- | -------- |
| 网络检查 | 3        | 5s       |

## 7. 输出格式规格

### 7.1 任务状态值

| 状态              | 说明         |
| ----------------- | ------------ |
| `pending`         | 任务待执行   |
| `running`         | 任务执行中   |
| `success`         | 任务成功完成 |
| `partial_success` | 部分主机成功 |
| `failed`          | 任务失败     |

### 7.2 主机状态值

| 状态        | 说明                     |
| ----------- | ------------------------ |
| `ready`     | 网络、SSH、Python 均正常 |
| `not_ready` | 至少一项检查失败         |
| `partial`   | 检查结果不完整           |
| `unknown`   | 无法确定状态             |

## 8. 高危命令黑名单

主配置文件配置命令黑名单, 拦截高危命令执行

- rm
- unlink
- halt
- shutdown
- mkfs
- parted
- reboot
- poweroff
- init
- dd
- format
- shred

**例外**：脚本中内含的这些操作无需屏蔽。

## 9. 依赖版本规格

| 依赖           | 版本要求   |
| -------------- | ---------- |
| Python         | >= 3.13    |
| ansible-core   | >= 2.15.0  |
| ansible-runner | >= 2.3.0   |
| FastAPI        | >= 0.100.0 |
| FastMCP        | >= 0.1.0   |
| SQLAlchemy     | >= 2.0.0   |
| PyJWT          | >= 2.8.0   |
| pydantic       | >= 2.0.0   |
| loguru         | >= 0.7.0   |

## 10. 动态 Playbook 工具生成机制

### 10.1 核心组件

**PlaybookScanner 类** (`lib/playbook_scanner.py`):

- 扫描 `playbooks/` 目录下的所有 `.yml` 和 `.yaml` 文件
- 解析 playbook 元数据（JSON 格式）
- 生成工具定义（名称、描述、参数）

### 10.2 工具生成规则

**命名规则**:

- 使用 `playbook_` 前缀 + playbook 文件名（不含扩展名）
- 例如: `collect_iaas_info.yml` -> 工具名 `playbook_collect_iaas_info`

**描述生成**:
基于元数据字段自动生成结构化描述:

- description: 功能描述
- parameters: 参数说明
- use_cases: 使用场景
- example: 使用示例
- notes: 注意事项

**参数定义**:
固定参数:

- targets: 目标主机列表
- user: SSH 用户名
- port: SSH 端口
- password: SSH 密码
- private_key: SSH 私钥路径
- extravars: 额外变量（根据元数据中的 parameters 字段）
- timeout: 超时时间

### 10.3 元数据要求

**必填字段**:

- description: playbook 功能描述

**可选字段**:

- author: 作者信息
- version: 版本号
- tags: 标签列表
- parameters: 参数定义
- use_cases: 使用场景列表
- example: 使用示例
- notes: 注意事项列表

**缺失元数据处理**:

- 跳过没有 description 字段的 playbook
- 在日志中记录警告信息

## 12. JWT 认证规格

### 12.1 认证库

使用 `PyJWT` 库实现 JWT 认证：

| 属性     | 值            |
| -------- | ------------- |
| 库名     | PyJWT         |
| 签名算法 | HS256         |
| 特性     | 标准 JWT 实现 |

### 12.2 JWT 结构

**Header**:

```json
{ "alg": "HS256", "typ": "JWT" }
```

**Payload**:
| 字段 | 类型 | 必填 | 说明 |
| ---- | ------ | ---- | ------------ |
| sub | string | 是 | 用户唯一标识 |
| name | string | 是 | 用户名称 |
| role | string | 是 | 用户角色 |
| iat | number | 是 | 签发时间戳 |
| exp | number | 否 | 过期时间戳 |

### 12.3 角色权限配置

**文件**: `etc/tsc_ansible_mcp.toml`

```toml
[auth]
enabled = true
jwt_secret_key_file = "etc/jwt_secret_key.txt"
jwt_issued_tokens_file = "etc/jwt_issued_tokens.json"

[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
```

**权限配置说明**:

- `*`: 表示所有工具
- `playbook_*`: 表示所有动态生成的 playbook 工具（如 playbook_collect_iaas_info）

**权限验证机制**:

- MCP 工具列表根据角色过滤（v1.6.0 新增）
- MCP 工具调用时验证用户权限
- LLM 获取工具列表时，根据角色暴露可用工具
- API 调用时验证用户权限
- 日志中记录每个操作的用户名

**MCP 工具角色过滤实现**（v1.6.0 新增）:

使用 MCP 授权中间件实现工具列表过滤：

| 组件             | 文件                  | 功能                          |
| ---------------- | --------------------- | ----------------------------- |
| 上下文传递       | `lib/context_vars.py` | 使用 contextvars 传递用户信息 |
| 授权中间件       | `lib/middleware.py`   | 拦截 MCP 请求，过滤工具列表   |
| 权限检查         | `lib/jwt_utils.py`    | check_permission 方法         |
| 工具函数权限检查 | `lib/permission.py`   | 工具函数内部的权限检查        |

**双重保护机制**（v1.6.0 新增）:

为了防止 LLM 通过其他方式（如历史对话、文档等）得知工具名称后尝试调用，实现了双重保护：

1. **第一层：MCP 协议层面**
   - 中间件拦截 `tools/list` 请求，过滤工具列表
   - 中间件拦截 `tools/call` 请求，检查权限

2. **第二层：工具函数内部**
   - 每个 admin 专用工具函数内部都有权限检查
   - 即使中间件失效，工具函数本身也会拒绝执行
   - 实现"深度防御"（Defense in Depth）原则

**工作流程**:

1. MCP Client 发送请求（携带 JWT Token）
2. 授权中间件提取并验证 JWT
3. 设置用户上下文（role, name, sub）
4. 拦截 `tools/list` 请求，根据角色过滤工具列表
5. 拦截 `tools/call` 请求，检查工具调用权限（第一层保护）
6. 工具函数内部再次检查权限（第二层保护）
7. 记录审计日志

### 12.4 密钥管理

**文件**: `etc/jwt_secret_key.txt`

- 单一密钥，简化管理
- 密钥长度建议 >= 32 字符
- 可通过更换密钥与其他认证系统对接

### 12.5 JWT 签发记录

**文件**: `etc/jwt_issued_tokens.json`

```json
{
  "tokens": [
    {
      "jwt_id": "jwt_001",
      "sub": "user_001",
      "name": "张三",
      "role": "admin",
      "issued_at": "2026-04-07T10:00:00Z",
      "expires_at": null,
      "description": "管理员 Token",
      "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    }
  ]
}
```

**字段说明**（v1.7.0 更新）:

- `jwt_id`: JWT 唯一标识
- `sub`: 用户唯一标识
- `name`: 用户名称
- `role`: 用户角色
- `issued_at`: 签发时间
- `expires_at`: 过期时间（null 表示永久有效）
- `description`: JWT 描述
- `token`: JWT token 字符串（v1.7.0 新增）

### 12.6 JWT 生成器

**文件**: `bin/generate_jwt.py`

| 命令                                           | 功能                |
| ---------------------------------------------- | ------------------- |
| --generate-key                                 | 生成新密钥          |
| --issue --sub <id> --name <name> --role <role> | 签发 JWT            |
| --issue ... --expires <duration>               | 签发带过期时间的JWT |
| --list                                         | 列出已签发 JWT      |
| --verify <token>                               | 验证 JWT            |

**撤销 JWT/密钥**：

- 撤销 JWT：直接编辑 `etc/jwt_issued_tokens.json`，删除对应记录，重启服务
- 更换密钥：直接编辑 `etc/jwt_secret_key.txt`，重启服务（会使所有已签发的 JWT 失效）

### 12.7 审计日志格式

```
2026-04-07 18:50:57 | INFO | 认证成功: IP=127.0.0.1, User=张三(user_001), Role=admin
```

## 13. 测试环境规格

### 13.1 测试主机

| 属性 | 值                      |
| ---- | ----------------------- |
| IP   | `192.168.19.35`         |
| 端口 | `3204`                  |
| 用户 | `root`                  |
| 系统 | `CentOS Linux 7`        |
| 内核 | `3.10.0-693.el7.x86_64` |
| 架构 | `x86_64`                |

### 13.2 测试连接命令样例

```bash
sshpass -vp JScz-320400 ssh root@192.168.19.35 -p 3204 -o 'PreferredAuthentications=password' -o 'PubkeyAuthentication=no'
```

## 14. 锁管理机制

### 14.1 锁管理概述

为了避免多个操作同时执行导致的冲突，系统实现了主机级别的锁管理机制。

### 14.2 核心组件

| 组件 | 文件 | 功能 |
| ---- | ---- | ---- |
| 锁管理 | `lib/executor.py` | 实现主机锁的获取和释放 |
| 锁存储 | `_active_hosts` | 存储当前活跃的主机列表 |
| 锁操作 | `_acquire_hosts`, `_release_hosts` | 实现锁的获取和释放逻辑 |

### 14.3 锁管理流程

1. **获取锁** - 执行前尝试获取主机锁
2. **执行操作** - 获取锁成功后执行相应的操作
3. **释放锁** - 使用 try-finally 块确保锁在任何情况下都会被释放
4. **死锁避免** - 在调用子方法时设置 `skip_lock=True`，避免死锁

### 14.4 锁管理日志

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

### 14.5 锁管理实现

所有执行方法现在都使用统一的锁管理机制：

- `ansible_shell()` - 添加锁的获取和释放逻辑
- `ansible_copy()` - 添加锁的获取和释放逻辑
- `ansible_fetch()` - 添加锁的获取和释放逻辑
- `run_playbook()` - 已有的锁管理逻辑

## 15. localhost 连接处理

### 15.1 问题描述

当目标主机是 localhost 时，代码仍然尝试通过 SSH 连接到 localhost:22，导致出现 "Connection refused" 错误。

### 15.2 解决方案

修改了 `_build_inventory` 方法，为 localhost 添加了特殊处理逻辑：

- 当目标是 "localhost" 时，使用 `ansible_connection: local` 而不是 SSH 连接
- 为 localhost 设置了默认的 Python 解释器路径 `/usr/bin/python3`

### 15.3 实现细节

```python
if target == "localhost":
    # 特殊处理 localhost，使用 local 连接方式
    host_data = {
        "ansible_host": "localhost",
        "ansible_connection": "local",
        "ansible_python_interpreter": "/usr/bin/python3",
    }
else:
    # 普通主机的处理逻辑
    host_data = {
        "ansible_host": target,
        "ansible_ssh_common_args": self.config.ssh_base_args,
        "ansible_python_interpreter": python_path,
    }
```

## 16. 相关文档

- [PRD 文档](./PRD.md)
- [架构设计文档](./ARCHITECTURE.md)
- [API 参考文档](./API-REFERENCE.md)
- [开发任务清单](./TODO.md)
