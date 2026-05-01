# TSC_ANSIBLE_MCP API 参考文档

## 1. API 概述

### 1.1 基础信息

- **Base URL**: `http://localhost:8500/api/v1`
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



### 2.4 Ansible Shell 命令

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

### 2.5 Ansible Copy 模块

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

### 2.6 Ansible Fetch 模块

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

### 2.7 列出 Playbook

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

### 2.8 执行 Playbook

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

### 2.17 包管理接口

包管理接口用于提供安装包的下载、列表和缓存刷新功能。这些端点**无需认证**，供目标主机在 bootstrap 过程中使用。

#### 2.17.1 下载安装包

下载指定类型的最新安装包，支持按发行版和架构过滤。

**请求**:

```http
GET /api/v1/packages/download?pkg_type={pkg_type}&distro={distro}&arch={arch}
```

**查询参数**:

| 参数     | 类型   | 必填 | 说明                           |
| -------- | ------ | ---- | ------------------------------ |
| pkg_type | string | 是   | 包类型（如 tsc_tools, tsc_python） |
| distro   | string | 否   | 发行版 ID（如 RedHat, Debian, Euler） |
| arch     | string | 否   | 架构（如 x86_64, aarch64）     |

**请求示例**:

```bash
curl -O -J "http://localhost:8500/api/v1/packages/download?pkg_type=tsc_tools&distro=FitServerOS&arch=x86_64"
```

**响应**:

- 成功：返回包文件内容（Content-Type: application/x-sh）
- 404：未找到匹配的包
- 500：服务器内部错误

**版本选择逻辑**:

系统使用**语义化版本比较**自动选择最新版本：
- `2.0.3.beta10` > `2.0.3.beta9`（数字比较，非字符串）
- `2.0.3` > `2.0.3.beta10`（正式版 > 预发布版）
- `2.0.3.rc1` > `2.0.3.beta10`（rc > beta）

#### 2.17.2 列出可用包

列出指定类型的所有可用包。

**请求**:

```http
GET /api/v1/packages/list/{pkg_type}
```

**路径参数**:

| 参数     | 类型   | 必填 | 说明                           |
| -------- | ------ | ---- | ------------------------------ |
| pkg_type | string | 是   | 包类型（如 tsc_tools, tsc_python） |

**响应示例**:

```json
{
  "packages": [
    {
      "filename": "tsc_tools-2.0.3.beta10-noarch-20260421.sh",
      "path": "/path/to/tsc_tools-2.0.3.beta10-noarch-20260421.sh"
    },
    {
      "filename": "tsc_tools-2.0.3.beta9-noarch-20260415.sh",
      "path": "/path/to/tsc_tools-2.0.3.beta9-noarch-20260415.sh"
    }
  ],
  "message": "Success"
}
```

#### 2.17.3 刷新包缓存

刷新包缓存，重新扫描包目录。

**请求**:

```http
POST /api/v1/packages/refresh
```

**响应示例**:

```json
{
  "message": "Cache refreshed successfully",
  "packages": {
    "tsc_tools": [
      {
        "filename": "tsc_tools-2.0.3.beta10-noarch-20260421.sh",
        "path": "/path/to/tsc_tools-2.0.3.beta10-noarch-20260421.sh"
      }
    ],
    "tsc_python": [
      {
        "filename": "tsc_python-0.9.7-Euler-x86_64-20260408.sh",
        "path": "/path/to/tsc_python-0.9.7-Euler-x86_64-20260408.sh"
      }
    ]
  }
}
```

### 2.18 健康检查

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

| 工具名称             | 功能描述                                                                 | 对应 REST API |
| -------------------- | ------------------------------------------------------------------------ | ------------- |
| `check_host_status`  | 检查主机状态（架构、发行版、Python、tsc_tools）                          | 2.1           |
| `install_tsc_tools`  | 安装 tsc_tools 环境                                                      | 2.2           |
| `install_python`     | 安装 tsc_python 环境                                                     | 2.3           |
| `ansible_shell`      | 执行远程 Shell 命令                                                      | 2.5           |
| `ansible_copy`       | 调用 ansible copy 模块，分发文件到远程主机                               | 2.6           |
| `ansible_fetch`      | 调用 ansible fetch 模块，从远程主机获取文件                              | 2.7           |
| `get_result`         | 查询任务执行结果，支持三种模式：任务摘要、失败主机列表、成功主机列表     | -             |
| `get_host_detail`    | 查询单个主机在指定任务中的执行详情（rc、stdout、stderr、status）         | -             |
| `set_context`        | 设置上下文键值对                                                         | -             |
| `get_context`        | 获取上下文值                                                             | -             |
| `delete_context`     | 删除指定的上下文键值对                                                   | -             |
| `list_contexts`      | 列出所有上下文键值对                                                     | -             |
| `clear_contexts`     | 清空所有上下文数据                                                       | -             |

### 3.1 check_host_status

检查目标主机状态。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `credentials` (optional): SSH 凭据信息

### 3.2 install_tsc_tools

在目标主机安装 tsc_tools 环境。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `credentials` (optional): SSH 凭据信息
- `timeout` (optional): 超时时间（秒）
- `task_id` (optional): 任务 ID

### 3.3 install_python

在目标主机安装 tsc_python 环境。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `credentials` (optional): SSH 凭据信息
- `timeout` (optional): 超时时间（秒）
- `task_id` (optional): 任务 ID

### 3.4 ansible_shell

执行远程 Shell 命令。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `command` (required): 命令内容
- `credentials` (optional): SSH 凭据信息
- `timeout` (optional): 超时时间（秒）

### 3.5 ansible_copy

分发文件到远程主机。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `src` (required): 本地源文件路径
- `dest` (required): 远程目标路径
- `credentials` (optional): SSH 凭据信息
- `mode` (optional): 文件权限
- `owner` (optional): 文件所有者
- `group` (optional): 文件所属组

### 3.6 ansible_fetch

从远程主机获取文件。

**参数：**
- `targets` (required): 目标主机 IP 列表
- `src` (required): 远程源文件路径
- `dest` (required): 本地目标目录
- `credentials` (optional): SSH 凭据信息
- `flat` (optional): 是否扁平化目录结构（默认 false）

### 3.7 get_result

查询任务执行结果，支持三种查询模式。  
Retrieve task execution results with three query modes.

**参数 / Parameters：**
- `task_id` (required): 任务 ID / Task ID
- `status` (optional): 状态过滤器，有效值：`"failed"` 或 `"success"`。省略时返回任务摘要。  
  Status filter. Valid values: `"failed"` or `"success"`. Omit to get task summary.

**三种查询模式 / Three Query Modes：**

| 调用方式 / Call | 返回内容 / Returns |
| --------------- | ------------------- |
| `get_result(task_id)` | 任务摘要（total_hosts, success_count, failed_count）/ Task summary |
| `get_result(task_id, status="failed")` | 所有失败主机列表及详情 / All failed hosts with details |
| `get_result(task_id, status="success")` | 所有成功主机列表及详情 / All successful hosts with details |

详细说明见 [Async Task Query API](#async-task-query-api) 章节。  
See the [Async Task Query API](#async-task-query-api) section for full documentation.

### 3.8 get_host_detail

查询单个主机在指定任务中的执行详情（第三层查询）。  
Query execution details for a specific host in a task (Layer 3 query).

**参数 / Parameters：**
- `task_id` (required): 任务 ID / Task ID
- `host` (required): 主机 IP 地址 / Host IP address

**返回字段 / Return Fields：**
- `rc`: 命令返回码（0 = 成功）/ Return code (0 = success)
- `stdout`: 标准输出 / Standard output
- `stderr`: 标准错误 / Standard error
- `status`: `"success"` 或 `"failed"`

详细说明见 [Async Task Query API](#async-task-query-api) 章节。  
See the [Async Task Query API](#async-task-query-api) section for full documentation.

## Async Task Query API

异步任务查询 API 提供三层查询模式，用于查询异步任务的执行结果。

Async Task Query API provides a three-layer query pattern for retrieving async task execution results.

---

### get_result

**用途 / Purpose**: 查询任务执行结果，支持三种查询模式。  
Retrieve task execution results with three query modes.

#### 参数 / Parameters

| 参数 / Parameter | 类型 / Type | 必填 / Required | 说明 / Description |
| ---------------- | ----------- | --------------- | ------------------- |
| `task_id`        | string      | 是 / Yes        | 任务 ID / Task ID   |
| `status`         | string      | 否 / No         | 状态过滤，有效值：`"failed"` 或 `"success"`。省略时返回摘要。<br>Status filter. Valid values: `"failed"` or `"success"`. Omit for summary. |

#### 查询模式 / Query Modes

##### 模式一：任务摘要（省略 status）/ Mode 1: Task Summary (status omitted)

返回高层统计信息，不包含主机详情。  
Returns high-level statistics without per-host details.

**请求示例 / Request Example**:
```json
{"task_id": "job_abc123"}
```

**响应示例 / Response Example**:
```json
{
  "task_id": "job_abc123",
  "status": "partial_success",
  "total_hosts": 10,
  "success_count": 8,
  "failed_count": 2,
  "message": "Task completed with 2 failed host(s). Use get_result('job_abc123', status='failed') to see failed hosts"
}
```

**字段说明 / Field Description**:

| 字段 / Field    | 说明 / Description |
| --------------- | ------------------- |
| `task_id`       | 任务 ID / Task ID |
| `status`        | 任务状态 / Task status |
| `total_hosts`   | 目标主机总数 / Total number of target hosts |
| `success_count` | 成功主机数 / Number of successful hosts |
| `failed_count`  | 失败主机数 / Number of failed hosts |
| `message`       | 操作指引 / Guidance message |

##### 模式二：失败主机列表（status="failed"）/ Mode 2: Failed Hosts List

返回所有失败主机及其详情。  
Returns all failed hosts with execution details.

**请求示例 / Request Example**:
```json
{"task_id": "job_abc123", "status": "failed"}
```

**响应示例 / Response Example**:
```json
{
  "task_id": "job_abc123",
  "status": "partial_success",
  "failed_hosts": {
    "192.168.1.10": {
      "rc": 1,
      "stdout": "",
      "stderr": "bash: command not found"
    },
    "192.168.1.11": {
      "rc": 2,
      "stdout": "",
      "stderr": "Permission denied"
    }
  },
  "total_failed": 2,
  "message": "Use get_host_detail(task_id, host_ip) to investigate specific host"
}
```

##### 模式三：成功主机列表（status="success"）/ Mode 3: Success Hosts List

返回所有成功主机及其详情。  
Returns all successful hosts with execution details.

**请求示例 / Request Example**:
```json
{"task_id": "job_abc123", "status": "success"}
```

**响应示例 / Response Example**:
```json
{
  "task_id": "job_abc123",
  "status": "partial_success",
  "success_hosts": {
    "192.168.1.1": {
      "rc": 0,
      "stdout": "Hello from 192.168.1.1",
      "stderr": ""
    },
    "192.168.1.2": {
      "rc": 0,
      "stdout": "Hello from 192.168.1.2",
      "stderr": ""
    }
  },
  "total_success": 8
}
```

#### 任务运行中响应 / Running Task Response

当任务仍在执行时，返回以下格式：  
When the task is still running:

```json
{
  "task_id": "job_abc123",
  "status": "running",
  "message": "Task is still running. Poll again in 30-60 seconds using get_result('job_abc123')"
}
```

#### 错误响应 / Error Responses

**任务不存在 / Task not found**:
```json
{
  "task_id": "job_abc123",
  "status": "not_found",
  "message": "Task job_abc123 not found in database"
}
```

**无效 status 参数 / Invalid status parameter**:
```json
{
  "task_id": "job_abc123",
  "status": "error",
  "message": "Invalid status parameter 'xyz'. Valid values: 'failed' or 'success'"
}
```

**结果文件缺失 / Result file missing**:
```json
{
  "task_id": "job_abc123",
  "status": "error",
  "message": "Result file for task job_abc123 is missing. The task exists in database but detailed results are not available."
}
```

---

### get_host_detail

**用途 / Purpose**: 查询单个主机的执行详情（第三层查询）。  
Query execution details for a specific host (Layer 3 query).

#### 参数 / Parameters

| 参数 / Parameter | 类型 / Type | 必填 / Required | 说明 / Description |
| ---------------- | ----------- | --------------- | ------------------- |
| `task_id`        | string      | 是 / Yes        | 任务 ID / Task ID   |
| `host`           | string      | 是 / Yes        | 主机 IP 地址 / Host IP address |

#### 请求示例 / Request Example

```json
{"task_id": "job_abc123", "host": "192.168.1.10"}
```

#### 成功主机示例 / Successful Host Example

当主机执行成功时（rc=0）：  
When the host executed successfully (rc=0):

```json
{
  "task_id": "job_abc123",
  "host": "192.168.1.10",
  "rc": 0,
  "stdout": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1       100G   50G   50G  50% /",
  "stderr": "",
  "status": "success"
}
```

#### 失败主机示例 / Failed Host Example

当主机执行失败时（rc≠0）：  
When the host execution failed (rc≠0):

```json
{
  "task_id": "job_abc123",
  "host": "192.168.1.10",
  "rc": 1,
  "stdout": "",
  "stderr": "bash: df: command not found",
  "status": "failed"
}
```

**字段说明 / Field Description**:

| 字段 / Field | 说明 / Description |
| ------------ | ------------------- |
| `task_id`    | 任务 ID / Task ID |
| `host`       | 主机 IP / Host IP |
| `rc`         | 命令返回码（0 = 成功）/ Return code (0 = success) |
| `stdout`     | 标准输出 / Standard output |
| `stderr`     | 标准错误 / Standard error |
| `status`     | `"success"` 或 `"failed"` |

#### 错误响应 / Error Responses

**任务不存在 / Task not found**:
```json
{
  "task_id": "job_abc123",
  "status": "not_found",
  "message": "Task job_abc123 not found in database"
}
```

**主机不存在 / Host not found**:
```json
{
  "task_id": "job_abc123",
  "host": "192.168.1.99",
  "status": "not_found",
  "message": "Host 192.168.1.99 not found in task job_abc123 results"
}
```

**任务运行中 / Task running**:
```json
{
  "task_id": "job_abc123",
  "status": "running",
  "message": "Task is still running. Wait and try again in 30-60 seconds"
}
```

**结果文件缺失 / Result file missing**:
```json
{
  "task_id": "job_abc123",
  "status": "error",
  "message": "Result file for task job_abc123 is missing. The task exists in database but detailed results are not available."
}
```

---

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

大多数 API 请求（除了健康检查端点和包管理端点）必须在请求头中携带 JWT Token：

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**无需认证的端点**：
- `/health` - 健康检查
- `/api/v1/packages/*` - 包管理接口（供目标主机在 bootstrap 过程中使用）

**认证说明**：

- 采用 JWT (JSON Web Token) 认证，支持身份识别和权限控制
- 使用 `PyJWT` 库实现 JWT 签发和验证
- 签名算法：HS256
- 认证功能可通过配置文件启用或禁用（`auth.enabled`）

**角色权限**：

| 角色  | 权限范围                                          |
| ----- | ------------------------------------------------- |
| admin | 可调用所有工具                                    |
| user  | 仅能调用 playbook 相关工具（get_task_status, 以及所有动态生成的playbook工具） |

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
user = ["get_task_status", "playbook_*"]
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
- 撤销 JWT：编辑 `etc/jwt_issued_tokens.json` 删除对应记录后重启服务即可

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
