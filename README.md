# TSC Ansible MCP

基于 Ansible 的远程主机自动化管理工具，提供 MCP (Model Context Protocol) 和 REST API 双接口服务。

## 项目简介

TSC Ansible MCP 是一个远程主机自动化管理平台，支持通过 MCP 服务调度 Ansible 实现对多台主机的批量管理操作。支持环境探测、软件安装、命令执行、文件分发、Playbook 执行等核心功能。

## 核心功能

### 1. 主机状态检查

- 网络连通性检测
- SSH 连接状态检查
- Python 环境检测
- tsc_tools 工具集安装状态
- CPU 架构和操作系统发行版识别

### 2. Software Installation

- **bootstrap_tsc_environment Playbook** - Bootstraps tsc_tools and tsc_python environment using API (no nginx required)
- **tsc_tools Toolkit Installation** - Downloads and installs from configured package repository
- **tsc_python Environment Installation** - Automatically selects installation package based on host architecture and distribution

### 3. 命令执行

- 批量在多台主机上执行 shell 命令
- 支持高危命令拦截
- 实时返回执行结果和状态

### 4. 文件操作

- **文件分发 (ansible_copy)** - 将本地文件传输到远程主机
- **文件获取 (ansible_fetch)** - 从远程主机获取文件到本地
- 支持批量操作多台主机
- 自动创建目标目录

### 5. Playbook 执行

- 列出可用的 playbook 文件（含元数据说明）
- 执行指定的 playbook 文件
- 支持传入额外变量
- **动态工具生成**: 每个 playbook 自动生成独立的 MCP 工具，LLM 可直接调用

### 6. API 认证

- 支持 JWT (JSON Web Token) 认证
- 支持角色权限控制（admin, user, 自定义角色）
- 密钥自动生成和管理
- 审计日志记录
- **JWT Token 字符串保存**（v1.7.0 新增）
  - 签发的 JWT token 字符串保存到 `etc/jwt_issued_tokens.json`
  - 方便查看和管理已签发的 token
- **MCP 工具列表角色过滤**（v1.6.0 新增）
  - admin 角色：可以看到所有 MCP 工具
  - user 角色：只能看到 playbook 相关工具
  - 工具列表在 MCP 协议层面进行过滤
  - 工具调用时进行二次权限检查
- **双重保护机制**（v1.6.0 新增）
  - 第一层：MCP 协议层面权限检查（中间件拦截）
  - 第二层：工具函数内部权限检查（防止绕过）
  - 实现"深度防御"（Defense in Depth）原则
- **中间件重构**（v1.7.0 新增）
  - 使用 BaseHTTPMiddleware 简化代码
  - 支持 SSE 格式响应
  - 详细的日志记录（每个请求分配唯一 request_id）
  - 记录请求的完整生命周期和每个步骤的耗时
### 6. SSH Port Management

- **change_ssh_port** - Change SSH port on target hosts with automatic rollback on failure
  - Validates host count (max 50) and port range (22 or 1024-65535)
  - Three-step approach: check status, execute playbook, verify connectivity
  - Supports fallback to old port if new port fails
  - Automatic inventory updates with old port backup
  - rc code based status: 0=success, 1=config test failed, 2=reload failed, 3=new port not listening, 4=old port still listening, 99=other error
- **主机锁管理优化**（v1.11.0 新增）
  - 为所有执行方法添加完整的锁管理逻辑
  - 使用 try-finally 块确保锁在任何情况下都会被释放
  - 增加详细的锁管理日志，便于诊断和解决锁相关的问题
  - 避免死锁和主机永久锁定的问题
- **localhost 连接修复**（v1.11.0 新增）
  - 为 localhost 添加特殊处理逻辑，使用 `ansible_connection: local`
  - 避免 localhost 连接被拒绝的问题
- **Python 安装状态修复**（v1.11.0 新增）
  - 修复 `install_python` 方法中 `installed` 字段的返回值问题
  - 确保当 tsc_python 已经安装时，返回的 `installed` 字段为 True
- **响应日志增强**（v1.11.0 新增）
  - 为所有 MCP 工具添加响应日志，记录执行结果
  - 便于跟踪服务是否正确返回了响应
- **SSH 配置优化**（v1.11.0 新增）
  - 确保 `PubkeyAuthentication=no` 参数被正确包含在 SSH 命令中
  - 避免因公钥认证失败导致的连接延迟

### 7. 上下文管理

- 支持在会话间持久化存储数据
- 提供 5 个上下文管理工具：set_context, get_context, delete_context, list_contexts, clear_contexts
- 支持键值对操作，便于保存配置、状态信息等

## 技术架构

```text
tsc_ansible_mcp/
├── bin/
│   └── server.py          # 服务入口
├── lib/
│   ├── config.py          # 配置管理
│   ├── database.py        # 数据库操作
│   ├── executor.py        # Ansible 执行引擎
│   ├── inventory_manager.py # 主机清单管理
│   ├── logger.py          # 日志管理
│   ├── models.py          # 数据模型
│   └── server.py          # 统一服务（MCP + REST API）
├── etc/
│   └── tsc_ansible_mcp.toml # 配置文件
├── playbooks/
│   └── system_check.yml   # 示例 playbook
└── logs/
    ├── tsc_ansible_mcp.db # SQLite 数据库
    └── package_cache.yml  # 软件包缓存
```

## 安装部署

### 环境要求

- Python 3.13
- Ansible Runner
- FastAPI
- FastMCP

### 安装依赖

```bash
pip install ansible-runner fastapi fastmcp uvicorn sqlalchemy pydantic pyyaml
```

### 配置文件

配置文件位于 `etc/tsc_ansible_mcp.toml`，主要配置项：

```toml
[mcp]
transport = "http"
host = "0.0.0.0"
port = 8500
path = "/mcp"
default_timeout = 600
max_timeout = 3600

[tsc_repo]
base_url = "http://192.168.19.22/tsc_install"
local_path = "/home/tsc/cicd/html/tsc_install"

[execution]
timeout = 300
forks = 10
serial = 10

[playbooks]
path = "playbooks"

[auth]
enabled = true
jwt_secret_key_file = "etc/jwt_secret_key.txt"
jwt_issued_tokens_file = "etc/jwt_issued_tokens.json"

[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
```

### 启动服务

```bash
python bin/server.py
```

服务启动后：

- MCP 端点: `http://localhost:8500/mcp`
- REST API 文档: `http://localhost:8500/docs`

## 使用指南

### MCP 工具使用

#### 1. 检查主机状态

```python
check_host_status(
    targets=["192.168.1.1", "192.168.1.2"],
    user="root",
    password="your_password"
)
```

#### 2. 安装 tsc_tools（必须先安装）

```python
install_tsc_tools(
    targets=["192.168.1.1"],
    user="root",
    password="your_password"
)
```

#### 3. 安装 Python

```python
install_python(
    targets=["192.168.1.1"],
    user="root",
    password="your_password"
)
```

#### 4. 执行命令

```python
ansible_shell(
    targets=["192.168.1.1"],
    command="ls -la",
    user="root",
    password="your_password"
)
```

#### 5. 分发文件

```python
ansible_copy(
    targets=["192.168.1.1"],
    src="/local/path/file.txt",
    dest="/remote/path/file.txt",
    user="root",
    password="your_password"
)
```

#### 6. 获取文件

```python
ansible_fetch(
    targets=["192.168.1.1"],
    src="/remote/path/file.log",
    dest="/local/path/",
    user="root",
    password="your_password"
)
```

#### 7. 列出 Playbook

```python
list_playbooks()
```

#### 8. 执行 Playbook

```python
ansible_playbook(
    playbook="system_check.yml",
    targets=["192.168.1.1"],
    user="root",
    password="your_password"
)
```

#### 9. 修改 SSH 端口

```python
change_ssh_port(
    hosts=["192.168.1.1", "192.168.1.2"],
    new_port=2222
)
```

### REST API 使用

#### 认证

所有 REST API 请求需要在请求头中携带 JWT Token：

**生成 JWT**:

```bash
# 签发 JWT（永久有效）
python bin/generate_jwt.py --issue --sub user_001 --name "张三" --role admin

# 签发 JWT（24小时有效期）
python bin/generate_jwt.py --issue --sub user_002 --name "李四" --role user --expires 24h

# 列出已签发的 JWT
python bin/generate_jwt.py --list

# 验证 JWT
python bin/generate_jwt.py --verify <token>
```

**使用 JWT**:

```bash
curl -H "Authorization: Bearer <your_jwt_token>" \
  http://localhost:8500/api/v1/executor/stats
```

#### 执行命令

```bash
curl -X POST http://localhost:8500/api/v1/shell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "targets": ["192.168.1.1"],
    "command": "ls -la",
    "credentials": {
      "user": "root",
      "password": "your_password"
    }
  }'
```

#### 检查主机状态

```bash
curl -X POST http://localhost:8500/api/v1/hosts/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "targets": ["192.168.1.1"],
    "credentials": {
      "user": "root",
      "password": "your_password"
    }
  }'
```

#### 列出 Playbook

```bash
curl -H "Authorization: Bearer <your_jwt_token>" \
  http://localhost:8500/api/v1/playbooks
```

#### 执行 Playbook

```bash
curl -X POST http://localhost:8500/api/v1/playbooks/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_jwt_token>" \
  -d '{
    "playbook": "system_check.yml",
    "targets": ["192.168.1.1"],
    "credentials": {
      "user": "root",
      "password": "your_password"
    }
  }'
```

## Important Notes

### Installation Order

When installing software, you must follow this order, do not reverse:

1. **Install tsc_tools first** - Call `install_tsc_tools` or `playbook_bootstrap_tsc_environment`
2. **Then install tsc_python** - Call `install_python` or `playbook_bootstrap_tsc_environment`

### Recommended Workflow

1. Call `check_host_status` to check host status
2. If host is unreachable (returns error field) → Stop further operations on this host
3. If tsc_tools is not installed → Use `playbook_bootstrap_tsc_environment`
4. If tsc_python is not installed → Use `playbook_bootstrap_tsc_environment`
5. After successful installation → Perform other operations

### Important

If check_host_status reports that tsc_tools or tsc_python are not installed, use the bootstrap_tsc_environment playbook tool to install them.

### 认证方式

支持两种 SSH 认证方式：

- **密码认证**：传递 `user`、`password` 参数
- **私钥认证**：传递 `user`、`private_key` 参数

### 错误处理

- 安装失败时，返回结果包含 `action_required` 字段，提示停止流程
- `install_output` 字段包含完整的安装日志，用于排查问题
- 请将错误信息和安装日志反馈给用户

### Playbook 元数据规范

Playbook 文件应包含元数据，供 LLM 理解用途：

```yaml
# @description: 本 playbook 用于安装和配置 Nginx 服务
# @author: tsc
# @version: 1.0.0
# @tags: nginx, web, install
# @parameters:
#   - nginx_version: Nginx 版本号 (默认: 1.24.0)
---
- name: Install Nginx
  hosts: all
  ...
```

## 支持的操作系统

- **RedHat 系列**: RHEL, CentOS, AlmaLinux, Rocky Linux, Fedora
- **Debian 系列**: Ubuntu, Debian, Linux Mint
- **Arch 系列**: Arch Linux, Manjaro
- **其他**: Alpine, openSUSE, openEuler, HCE, NingOS, Euler

## MCP 工具列表

### Basic Tools

| Tool Name           | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `check_host_status` | Check host status (architecture, distribution, Python, tsc_tools) |
| `install_tsc_tools` | Install tsc_tools environment                        |
| `install_python`    | Install tsc_python environment                       |
| `ansible_shell`     | Execute remote Shell commands                        |
| `ansible_copy`      | Distribute files to remote hosts                     |
| `ansible_fetch`     | Retrieve files from remote hosts                     |
| `list_playbooks`    | List available playbook files                        |
| `ansible_playbook`  | Execute playbook files                               |
| `get_task_status`   | Query task status                                    |
| `set_context`       | Set context key-value pairs                          |
| `get_context`       | Get context value                                    |
| `delete_context`    | Delete specified context key-value pairs             |
| `list_contexts`     | List all context key-value pairs                     |
| `clear_contexts`    | Clear all context data                               |
| `change_ssh_port`   | Change SSH port with automatic rollback on failure   |

### 动态 Playbook 工具

服务启动时会自动扫描 `playbooks/` 目录，为每个包含元数据的 playbook 文件动态生成独立的 MCP 工具。

**命名规则**: 工具名使用 `playbook_` 前缀 + playbook 文件名（不含扩展名）

**示例**: 如果存在 `playbooks/collect_iaas_info.yml`，将自动生成 `playbook_collect_iaas_info` 工具：

```python
playbook_collect_iaas_info(
    targets=["192.168.1.10"],
    user="root",
    password="your_password",
    extravars={"runtime": True}
)
```

**元数据要求**: playbook 必须包含 `description` 字段才能生成工具。

**权限控制**:

- `admin` 角色可以调用所有工具
- `user` 角色只能调用 `playbook_*` 工具和 playbook 相关工具
- 可在配置文件中自定义角色权限
