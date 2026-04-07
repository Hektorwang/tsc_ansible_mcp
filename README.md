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

### 2. 软件安装

- **tsc_tools 工具集安装** - 自动从配置的 Nginx 服务器下载并安装
- **tsc_python 环境安装** - 根据主机架构和发行版自动选择安装包

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

### 6. API 认证

- 支持标准的 HTTP Bearer Token 认证
- Token 文件独立管理，不暴露在配置文件中
- 认证开关灵活控制

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
api_keys = ["sk-tsc-ansible-mcp-2026"]
whitelist_ips = ["127.0.0.1", "192.168.19.0/24"]
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

### REST API 使用

#### 认证

所有 REST API 请求需要在请求头中携带 Bearer Token：

```bash
curl -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  http://localhost:8500/api/v1/executor/stats
```

#### 执行命令

```bash
curl -X POST http://localhost:8500/api/v1/shell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
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
  -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
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
curl -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  http://localhost:8500/api/v1/playbooks
```

#### 执行 Playbook

```bash
curl -X POST http://localhost:8500/api/v1/playbooks/execute \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  -d '{
    "playbook": "system_check.yml",
    "targets": ["192.168.1.1"],
    "credentials": {
      "user": "root",
      "password": "your_password"
    }
  }'
```

## 重要说明

### 安装顺序

安装软件时必须遵循以下顺序，不可颠倒：

1. **先安装 tsc_tools** - 调用 `install_tsc_tools`
2. **再安装 tsc_python** - 调用 `install_python`

### 推荐工作流程

1. 调用 `check_host_status` 检查主机状态
2. 如果主机不可达（返回 error 字段）→ 停止对该主机的后续操作
3. 如果 tsc_tools 未安装 → 调用 `install_tsc_tools`
4. 如果 Python 未安装 → 调用 `install_python`
5. 安装成功后 → 执行其他操作

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

| 工具名称            | 功能描述                                        |
| ------------------- | ----------------------------------------------- |
| `check_host_status` | 检查主机状态（架构、发行版、Python、tsc_tools） |
| `install_tsc_tools` | 安装 tsc_tools 环境                             |
| `install_python`    | 安装 tsc_python 环境                            |
| `ansible_shell`     | 执行远程 Shell 命令                             |
| `ansible_copy`      | 分发文件到远程主机                              |
| `ansible_fetch`     | 从远程主机获取文件                              |
| `list_playbooks`    | 列出可用的 playbook 文件                        |
| `ansible_playbook`  | 执行 playbook 文件                              |
| `get_task_status`   | 查询任务状态                                    |
