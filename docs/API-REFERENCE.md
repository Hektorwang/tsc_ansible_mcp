# TSC_ANSIBLE_MCP API 参考文档

## 1. API 概述

### 1.1 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **协议**: HTTP/HTTPS
- **数据格式**: JSON
- **字符编码**: UTF-8

## 2. REST API 接口

### 2.1 检查主机状态

检查目标主机状态，包括架构、发行版、Python 安装状态、tsc_tools 安装状态等。

**请求**:

```http
POST /api/v1/hosts/status
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明             |
| ----------- | ------------- | ---- | ---------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表 |
| credentials | object        | 否   | SSH 凭据         |

**请求示例**:

```json
{
  "targets": ["192.168.1.100"],
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  }
}
```

**响应示例**:

```json
{
  "task_id": "job_12347",
  "results": {
    "192.168.1.100": {
      "arch": "x86_64",
      "arch_raw": "x86_64",
      "distro": "RedHat",
      "distro_raw": "CentOS Linux release 7.9.2009",
      "python_installed": true,
      "python_version": "Python 3.9.5",
      "python_path": "/usr/bin/python3",
      "tsc_tools_installed": false
    }
  }
}
```

### 2.2 安装 tsc_tools

在目标主机安装 tsc_tools 环境。

**请求**:

```http
POST /api/v1/hosts/tsc_tools/install
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明             |
| ----------- | ------------- | ---- | ---------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表 |
| version     | string        | 否   | 版本号           |
| date        | string        | 否   | 日期标识         |
| credentials | object        | 否   | SSH 凭据         |

**请求示例**:

```json
{
  "targets": ["192.168.1.100"],
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  }
}
```

**响应示例**:

```json
{
  "task_id": "job_12348",
  "status": "success",
  "results": {
    "192.168.1.100": {
      "installed": true,
      "version": "2.0.3.beta10",
      "path": "/home/tsc/tsc_tools",
      "elapsed": "45.2s"
    }
  }
}
```

### 2.3 安装 Python

在目标主机安装 tsc_python 环境。

**请求**:

```http
POST /api/v1/hosts/python/install
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明             |
| ----------- | ------------- | ---- | ---------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表 |
| version     | string        | 否   | 版本号           |
| date        | string        | 否   | 日期标识         |
| credentials | object        | 否   | SSH 凭据         |

**请求示例**:

```json
{
  "targets": ["192.168.1.100"],
  "version": "0.9.5",
  "date": "20260330",
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  }
}
```

**响应示例**:

```json
{
  "task_id": "job_12346",
  "status": "success",
  "results": {
    "192.168.1.100": {
      "installed": true,
      "version": "Python 3.13",
      "path": "/home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3",
      "elapsed": "45.2s"
    }
  }
}
```

### 2.4 检查主机状态

检查目标主机的连接状态，包括网络连通性、SSH 可达性、Python 可用性、tsc_tools 安装状态。

**请求**:

```http
POST /api/v1/hosts/status
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明             |
| ----------- | ------------- | ---- | ---------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表 |
| credentials | object        | 否   | SSH 凭据         |

**响应示例**:

```json
{
  "task_id": "job_12349",
  "timestamp": "2026-04-05T10:30:00Z",
  "results": {
    "192.168.1.100": {
      "overall_status": "ready",
      "checks": [
        {"name": "network", "status": "pass", "message": "网络可达"},
        {"name": "ssh", "status": "pass", "message": "SSH 连接成功"},
        {"name": "python", "status": "pass", "message": "Python 3.9.5 已安装"},
        {"name": "tsc_tools", "status": "pass", "message": "tsc_tools 已安装"}
      ]
    }
  }
}
```

### 2.5 Ansible Shell 命令

执行远程 Shell 命令(仅支持 ad-hoc 模式)。

**请求**:

```http
POST /api/v1/shell
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明                                                     |
| ----------- | ------------- | ---- | -------------------------------------------------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表                                         |
| command     | string        | 是   | 命令内容                                                 |
| credentials | object        | 否   | SSH 凭据(user, password, private_key)                    |
| timeout     | int           | 否   | 超时时间(秒)                                             |

**请求示例**:

```json
{
  "targets": ["192.168.1.100", "192.168.1.101"],
  "command": "df -h",
  "credentials": {
    "user": "root",
    "private_key": "/root/.ssh/id_rsa"
  },
  "timeout": 300
}
```

**响应示例**:

```json
{
  "task_id": "job_12345",
  "status": "success",
  "summary": {
    "total": 2,
    "success": 2,
    "failed": 0
  },
  "results": {
    "192.168.1.100": {
      "rc": 0,
      "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       100G   50G   50G  50% /",
      "stderr": "",
      "elapsed": "2.5s"
    },
    "192.168.1.101": {
      "rc": 0,
      "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       200G   80G  120G  40% /",
      "stderr": "",
      "elapsed": "2.3s"
    }
  }
}
```

### 2.6 Ansible Copy 模块

调用 ansible copy 模块，将本地文件复制到远程主机。

**请求**:

```http
POST /api/v1/copy
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明             |
| ----------- | ------------- | ---- | ---------------- |
| targets     | array[string] | 是   | 目标主机 IP 列表 |
| src         | string        | 是   | 本地源文件路径   |
| dest        | string        | 是   | 远程目标路径     |
| credentials | object        | 否   | SSH 凭据         |
| mode        | string        | 否   | 文件权限         |
| owner       | string        | 否   | 文件所有者       |
| group       | string        | 否   | 文件所属组       |

**请求示例**:

```json
{
  "targets": ["192.168.1.100"],
  "src": "/local/path/to/file.sh",
  "dest": "/remote/path/to/file.sh",
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  },
  "mode": "0755",
  "owner": "root",
  "group": "root"
}
```

**响应示例**:

```json
{
  "task_id": "job_12349",
  "status": "success",
  "results": {
    "192.168.1.100": {
      "dest": "/remote/path/to/file.sh",
      "checksum": "abc123",
      "changed": true,
      "elapsed": "1.2s"
    }
  }
}
```

### 2.7 Ansible Fetch 模块

调用 ansible fetch 模块，从远程主机获取文件到本地。

**请求**:

```http
POST /api/v1/fetch
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明                           |
| ----------- | ------------- | ---- | ------------------------------ |
| targets     | array[string] | 是   | 目标主机 IP 列表               |
| src         | string        | 是   | 远程源文件路径                 |
| dest        | string        | 是   | 本地目标目录                   |
| credentials | object        | 否   | SSH 凭据                       |
| flat        | boolean       | 否   | 是否扁平化目录结构(默认 false) |

**请求示例**:

```json
{
  "targets": ["192.168.1.100"],
  "src": "/remote/path/to/file.log",
  "dest": "/local/path/to/fetch/",
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  },
  "flat": false
}
```

**响应示例**:

```json
{
  "task_id": "job_12350",
  "status": "success",
  "results": {
    "192.168.1.100": {
      "dest": "/local/path/to/fetch/192.168.1.100/remote/path/to/file.log",
      "checksum": "abc123",
      "changed": true,
      "elapsed": "1.5s"
    }
  }
}
```

### 2.8 列出 Playbook

列出 playbooks 目录下所有可用的 playbook 文件。

**请求**:

```http
GET /api/v1/playbooks
```

**响应示例**:

```json
{
  "playbooks": [
    {
      "name": "example.yml",
      "path": "playbooks/example.yml",
      "description": "示例 playbook - 用于演示 playbook 执行功能",
      "author": "tsc",
      "version": "1.0.0"
    }
  ]
}
```

### 2.9 执行 Playbook

执行指定的 playbook 文件。

**请求**:

```http
POST /api/v1/playbooks/execute
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型          | 必填 | 说明                  |
| ----------- | ------------- | ---- | --------------------- |
| playbook    | string        | 是   | playbook 文件名或路径 |
| targets     | array[string] | 是   | 目标主机 IP 列表      |
| credentials | object        | 否   | SSH 凭据              |
| extravars   | object        | 否   | 额外变量              |

**请求示例**:

```json
{
  "playbook": "example.yml",
  "targets": ["192.168.1.100"],
  "credentials": {
    "user": "root",
    "port": 22,
    "password": "secret"
  },
  "extravars": {
    "var1": "value1"
  }
}
```

**响应示例**:

```json
{
  "task_id": "job_12345",
  "status": "success",
  "results": {
    "192.168.1.100": {
      "rc": 0,
      "stdout": "Playbook executed successfully",
      "stderr": "",
      "elapsed": "10.5s"
    }
  }
}
```

### 2.10 添加主机到 Inventory

添加/更新主机到本地 Inventory 缓存。

**请求**:

```http
POST /api/v1/inventory
Content-Type: application/json
```

**请求参数**:

| 参数        | 类型   | 必填 | 说明         |
| ----------- | ------ | ---- | ------------ |
| host        | string | 是   | 主机 IP 地址 |
| credentials | object | 否   | SSH 凭据     |

**请求示例**:

```json
{
  "host": "192.168.1.200",
  "credentials": {
    "user": "admin",
    "port": 22,
    "private_key": "/root/.ssh/id_rsa"
  }
}
```

**响应示例**:

```json
{
  "status": "success",
  "message": "主机已添加/更新到 Inventory",
  "host": "192.168.1.200"
}
```

### 2.11 查询 Inventory

查询本地 Inventory 缓存中的所有主机。

**请求**:

```http
GET /api/v1/inventory
```

**响应示例**:

```json
{
  "all": {
    "hosts": {
      "192.168.1.100": {
        "ansible_host": "192.168.1.100",
        "ansible_user": "root",
        "ansible_port": 22
      }
    }
  }
}
```

### 2.12 删除 Inventory 主机

从本地 Inventory 缓存中删除指定主机。

**请求**:

```http
DELETE /api/v1/inventory/{host}
```

**路径参数**:

| 参数 | 类型   | 必填 | 说明         |
| ---- | ------ | ---- | ------------ |
| host | string | 是   | 主机 IP 地址 |

**响应示例**:

```json
{
  "status": "success",
  "message": "主机 192.168.1.100 已从 Inventory 删除"
}
```

### 2.13 查询任务状态

查询指定任务的执行状态。

**请求**:

```http
GET /api/v1/executor/tasks/{task_id}
```

**路径参数**:

| 参数    | 类型   | 必填 | 说明    |
| ------- | ------ | ---- | ------- |
| task_id | string | 是   | 任务 ID |

**响应示例**:

```json
{
  "task_id": "job_12345",
  "status": "running",
  "progress": {
    "total": 100,
    "completed": 45,
    "failed": 2,
    "pending": 53
  },
  "started_at": "2026-04-05T10:30:00Z",
  "elapsed": "125s"
}
```

### 2.14 查询任务列表

查询任务列表。

**请求**:

```http
GET /api/v1/executor/tasks
```

**查询参数**:

| 参数          | 类型   | 必填 | 说明               |
| ------------- | ------ | ---- | ------------------ |
| status_filter | string | 否   | 按状态过滤         |
| limit         | int    | 否   | 返回数量限制(默认 100) |

**响应示例**:

```json
[
  {
    "id": "job_12345",
    "type": "execute_command",
    "parameters": "{\"targets\": [\"192.168.1.100\"], \"command\": \"df -h\"}",
    "status": "success",
    "result": null,
    "created_at": "2026-04-05T10:30:00Z",
    "updated_at": "2026-04-05T10:30:05Z"
  }
]
```

### 2.15 删除任务

删除指定任务。

**请求**:

```http
DELETE /api/v1/executor/tasks/{task_id}
```

**路径参数**:

| 参数    | 类型   | 必填 | 说明    |
| ------- | ------ | ---- | ------- |
| task_id | string | 是   | 任务 ID |

**响应示例**:

```json
{
  "status": "success",
  "message": "任务 job_12345 已删除"
}
```

### 2.16 任务统计

获取任务统计信息。

**请求**:

```http
GET /api/v1/executor/stats
```

**响应示例**:

```json
{
  "total": 100,
  "pending": 10,
  "running": 5,
  "success": 80,
  "failed": 5
}
```

### 2.17 健康检查

检查服务健康状态。

**请求**:

```http
GET /health
```

**响应示例**:

```json
{
  "status": "healthy"
}
```

## 3. MCP 工具接口

MCP 工具与 REST API 功能一致，参数和输出格式相同，详见各 REST API 接口说明。

| 工具名称             | 功能描述                                       | 对应 REST API |
| -------------------- | ---------------------------------------------- | ------------- |
| `check_host_status`  | 检查主机状态（架构、发行版、Python、tsc_tools）| 2.1           |
| `install_tsc_tools`  | 安装 tsc_tools 环境                            | 2.2           |
| `install_python`     | 安装 tsc_python 环境                           | 2.3           |
| `ansible_shell`      | 执行远程 Shell 命令                            | 2.5           |
| `ansible_copy`       | 调用 ansible copy 模块，分发文件到远程主机     | 2.6           |
| `ansible_fetch`      | 调用 ansible fetch 模块，从远程主机获取文件    | 2.7           |
| `list_playbooks`     | 列出可用的 playbook 文件，包含元数据说明       | 2.8           |
| `ansible_playbook`   | 执行 playbook 文件                             | 2.9           |
| `get_task_status`    | 查询任务状态                                   | 2.13          |
| `set_context`        | 设置上下文键值对                               | -             |
| `get_context`        | 获取上下文值                                   | -             |
| `delete_context`     | 删除指定的上下文键值对                         | -             |
| `list_contexts`      | 列出所有上下文键值对                           | -             |
| `clear_contexts`     | 清空所有上下文数据                             | -             |

## 4. 错误码说明

### 4.1 HTTP 状态码

| 错误码 | 说明           | 处理建议             |
| ------ | -------------- | -------------------- |
| 200    | 请求成功       | -                    |
| 201    | 资源创建成功   | -                    |
| 400    | 请求参数错误   | 检查请求参数格式     |
| 401    | 认证失败       | 检查 Token 是否有效  |
| 403    | 权限不足       | 检查用户权限         |
| 404    | 资源不存在     | 检查目标主机是否存在 |
| 500    | 服务器内部错误 | 联系管理员           |
| 503    | 服务不可用     | 稍后重试             |

### 4.2 业务错误码

| 错误码            | 说明           | 处理建议               |
| ----------------- | -------------- | ---------------------- |
| TASK_NOT_FOUND    | 任务不存在     | 检查 task_id 是否正确  |
| HOST_UNREACHABLE  | 主机不可达     | 检查网络连接           |
| SSH_AUTH_FAILED   | SSH 认证失败   | 检查 SSH 密钥或密码    |
| COMMAND_TIMEOUT   | 命令执行超时   | 增加 timeout 参数      |
| HIGH_RISK_COMMAND | 高危命令被拦截 | 检查命令是否在黑名单中 |

## 5. 请求头说明

### 5.1 必需请求头

```http
Content-Type: application/json
```

### 5.2 认证请求头

所有 API 请求（除了健康检查端点）必须在请求头中携带 JWT Token：

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**认证说明**：

- 采用 JWT (JSON Web Token) 认证，支持身份识别和权限控制
- 使用 `PyJWT` 库实现 JWT 签发和验证
- 签名算法：HS256
- 认证功能可通过配置文件启用或禁用（`auth.enabled`）

**角色权限**：

| 角色  | 权限范围                                          |
| ----- | ------------------------------------------------- |
| admin | 可调用所有工具                                    |
| user  | 仅能调用 playbook 相关工具（list_playbooks, ansible_playbook, get_task_status, 以及所有动态生成的playbook工具） |

**权限验证机制**:
- LLM 获取工具列表时，根据角色暴露可用工具
- API 调用时验证用户权限
- 日志中记录每个操作的用户名

**示例请求**：

```bash
# 使用 curl 发送带认证的请求
curl -X POST http://localhost:8500/api/v1/shell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "targets": ["192.168.1.100"],
    "command": "ls -la"
  }'
```

**认证失败响应**：

```json
{
  "status": "error",
  "message": "Bearer Token required. Please provide Authorization: Bearer <token> header."
}
```

或

```json
{
  "status": "error",
  "message": "Invalid JWT Token"
}
```

**权限不足响应**：

```json
{
  "status": "error",
  "message": "Permission denied. Role 'user' cannot access tool 'ansible_shell'"
}
```

**生成 JWT**：

使用提供的工具生成 JWT：

```bash
# 生成新密钥
python bin/generate_jwt.py --generate-key

# 签发 JWT（永久有效）
python bin/generate_jwt.py --issue --sub user_001 --name "张三" --role admin

# 签发 JWT（24小时有效期）
python bin/generate_jwt.py --issue --sub user_002 --name "李四" --role user --expires 24h

# 列出已签发 JWT
python bin/generate_jwt.py --list

# 撤销 JWT
python bin/generate_jwt.py --revoke jwt_001

# 验证 JWT
python bin/generate_jwt.py --verify <token>
```

**配置示例**：

```toml
# etc/tsc_ansible_mcp.toml
[auth]
enabled = true
jwt_secret_key_file = "etc/jwt_secret_key.txt"
jwt_issued_tokens_file = "etc/jwt_issued_tokens.json"

[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
```

**密钥文件**：

创建 `etc/jwt_secret_key.txt`：

```
sk-jwt-secret-key-2026
```

**JWT 签发记录文件**：

创建 `etc/jwt_issued_tokens.json`：

```json
{
  "tokens": []
}
```

**注意**：
- `etc/jwt_secret_key.txt` 和 `etc/jwt_issued_tokens.json` 已添加到 `.gitignore`，不会被提交到 git
- JWT 默认永久有效，签发时可选设置过期时间
- 支持 JWT 撤销功能

## 6. 响应格式说明

### 6.1 成功响应

```json
{
  "status": "success",
  "data": {},
  "message": "操作成功"
}
```

### 6.2 错误响应

```json
{
  "status": "error",
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
  }
}
```

## 7. 相关文档

- [PRD 文档](./PRD.md)
- [架构设计文档](./ARCHITECTURE.md)
- [技术规格说明](./SPEC.md)
- [开发任务清单](./TODO.md)
