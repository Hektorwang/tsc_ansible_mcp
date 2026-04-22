# TSC_ANSIBLE_MCP 产品需求文档

## 1. 产品概述

本工具的目的: 可通过 LLM 传入目标服务器 `IP`, `要执行的操作`，通过 `FastMCP`, `FastAPI`, `ansible-runner` 作为基础设施对目标服务器进行操作.

## 2. 核心功能需求

### 2.1 远程指令执行 (Ad-hoc Mode)

- 支持通过 LLM 或 REST API 传入任意 Shell 指令并在目标机执行
- 支持批量执行(分批模式，每批 10 台, 主配置文件可配置默认值)
- 具备指令超时控制(预设 300s，主配置文件可配置默认值)
- 完整捕获 `stdout`, `stderr` 及退出码 (`RC`)

### 2.2 Playbook 执行能力

- 支持执行存放在 `playbooks/` 目录下的 Ansible playbook 文件
- 支持列出可用的 playbook 文件
- 支持传入额外变量（extravars）
- 支持指定目标主机执行 playbook
- 支持批量执行和超时控制

### 2.3 Ansible 模块直接调用

- 支持直接调用 Ansible `copy` 模块进行文件分发
- 支持直接调用 Ansible `fetch` 模块从远程获取文件
- 支持设置文件权限、所有者等属性
- 支持扁平化目录结构选项

### 2.4 环境自举与感知 (Bootstrapping)

- 无 Python 执行能力: Playbook 设置 `gather_facts: false`，仅使用 `raw` 模块
- 自动识别架构(`uname -m`)和发行版(`cat /etc/os-release`)
- 归一化映射(主配置文件): 架构 `arm64` -> `aarch64`, `amd64` -> `x86_64`; 发行版 `rhel/centos -> RedHat`，`ubuntu/debian -> Debian`
- Python 安装包格式: `tsc_python-{version}-{distro}-{arch}-{date}.sh`
- 幂等性检查: 安装前先 `test -f /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3`
- **包管理 API**: 内置包下载接口

### 2.5 包管理

#### 2.5.1 功能描述

系统提供内置的包管理功能，通过 REST API 向目标主机分发安装包，替代外部 Nginx 文件服务。

#### 2.5.2 核心功能

1. **包扫描**
   - 自动扫描指定目录下的 `.sh` 安装包文件
   - 从文件名提取包类型、版本、发行版、架构信息
   - 维护内存缓存，支持手动刷新

2. **包过滤**
   - 按包类型过滤（如 `tsc_tools`, `tsc_python`）
   - 按发行版过滤（如 `RedHat`, `Debian`, `Euler`）
   - 按架构过滤（如 `x86_64`, `aarch64`）
   - `noarch` 包特殊处理：匹配任何架构
   - 若包名不含发行版或 `allsystem`, 则匹配任意 distro

3. **版本选择**
   - 使用**语义化版本比较**自动选择最新版本
   - 支持预发布版本（alpha, beta, rc）
   - 正式版优先级高于预发布版
   - 正确比较数字版本（`beta10` > `beta9`）

4. **API 接口**
   - `GET /api/v1/packages/download` - 下载最新包（无需认证）
   - `GET /api/v1/packages/list/{pkg_type}` - 列出可用包
   - `POST /api/v1/packages/refresh` - 刷新包缓存

#### 2.5.3 包文件名格式

```
{pkg_type}-{version}-{distro}-{arch}-{date}.sh

示例:
tsc_tools-2.0.3.beta10-noarch-20260421.sh
tsc_python-0.9.7-Euler-x86_64-20260408.sh
```

#### 2.5.4 版本比较规则

| 场景                            | 结果        | 说明               |
| ------------------------------- | ----------- | ------------------ |
| `2.0.3.beta10` vs `2.0.3.beta9` | beta10 更新 | 数字 10 > 9        |
| `2.0.3` vs `2.0.3.beta10`       | 正式版更新  | 预发布版 < 正式版  |
| `2.0.3.rc1` vs `2.0.3.beta10`   | rc 更新     | rc 优先级高于 beta |
| `2.0.10` vs `2.0.3`             | 2.0.10 更新 | 数字 10 > 3        |

#### 2.5.5 非功能需求

1. **性能**
   - 包扫描应在服务启动时完成，不影响 API 响应速度
   - 包文件读取使用流式传输，支持大文件

2. **可靠性**
   - 缓存机制避免重复扫描文件系统
   - 支持手动刷新缓存应对包文件变化

3. **安全性**
   - 包下载接口无需认证（供目标主机 bootstrap 使用）
   - 包列表和缓存刷新接口受认证保护

### 2.6 SSH 认证

按如下优先级, 失败后 fallback 到下一项:

- 操作系统默认行为(`~/.ssh/config`, 密钥)
- TODO: 支持密码认证, 对接 cmdb

### 2.7 安全控制

- 高危指令黑名单预拦截(`rm -rf /` 等)

### 2.8 API 认证

#### 2.7.1 认证机制

- 采用 JWT (JSON Web Token) 认证，支持身份识别和权限控制
- 使用 `PyJWT` 库实现 JWT 签发和验证
- 签名算法：HS256
- 认证开关可通过配置文件灵活控制

#### 2.7.2 JWT 结构

```json
{
  "header": { "alg": "HS256", "typ": "JWT" },
  "payload": {
    "sub": "user_001",
    "name": "张三",
    "role": "admin",
    "iat": 1712476800
  }
}
```

**Payload 字段说明**:

- `sub`: 用户唯一标识
- `name`: 用户名称
- `role`: 用户角色（admin, user）
- `iat`: 签发时间

#### 2.7.3 角色权限控制

| 角色  | 权限范围                                                                                                        |
| ----- | --------------------------------------------------------------------------------------------------------------- |
| admin | 可调用所有工具                                                                                                  |
| user  | 仅能调用 playbook 相关工具（list_playbooks, ansible_playbook, get_task_status, 以及所有动态生成的playbook工具） |

**权限控制的好处**:

- 减少 LLM 幻觉导致的误操作
- playbook 经过审查和测试，操作可控
- 避免执行未经验证的命令

**权限验证机制**:

- MCP 工具列表根据角色过滤（新增）
- MCP 工具调用时验证用户权限
- LLM 获取工具列表时，根据角色暴露可用工具
- API 调用时验证用户权限
- 日志中记录每个操作的用户名

**MCP 工具角色过滤**（v1.6.0 新增）:

- admin 角色：可以看到所有 MCP 工具
- user 角色：只能看到 playbook 相关工具（list*playbooks, ansible_playbook, get_task_status, playbook*\*）
- 工具列表在 MCP 协议层面进行过滤
- 工具调用时进行二次权限检查，确保安全

#### 2.7.4 密钥管理

- 密钥文件：`etc/jwt_secret_key.txt`
- 单一密钥，简化管理
- 可通过更换密钥与其他认证系统对接
- 建议定期更换密钥（如每 3 个月）

#### 2.7.5 **JWT 签发记录**

- 记录文件：`etc/jwt_issued_tokens.json`
- 记录所有已签发的 JWT 信息，包括 JWT token 字符串
- 撤销方式：直接从记录文件中删除对应 JWT 信息，然后重启服务
- 默认永久有效，签发时可选设置过期时间
- **Token 字符串保存**（v1.7.0 新增）：签发的 JWT token 字符串也会保存到记录文件中，方便查看和管理

#### 2.7.6 JWT 生成器

提供 `bin/generate_jwt.py` 工具：

- 生成新密钥：`--generate-key`
- 签发 JWT：`--issue --sub user_001 --name "张三" --role admin`
- 签发带过期时间的 JWT：`--issue --sub user_001 --name "张三" --role admin --expires 24h`
- 列出已签发 JWT：`--list`
- 验证 JWT：`--verify <token>`

**撤销 JWT/密钥**：

- 撤销 JWT：直接编辑 `etc/jwt_issued_tokens.json`，删除对应记录，重启服务
- 更换密钥：直接编辑 `etc/jwt_secret_key.txt`，重启服务（会使所有已签发的 JWT 失效）

#### 2.7.7 认证范围

- 所有 REST API 端点需要认证（健康检查除外）
- 所有 MCP 端点需要认证
- API 文档端点（`/docs`, `/redoc`）无需认证

#### 2.7.8 认证失败响应

- Token 缺失：返回 HTTP 401，提示需要 Bearer Token
- Token 无效：返回 HTTP 401，提示 Token 无效
- 权限不足：返回 HTTP 403，提示权限不足
- 响应包含 `WWW-Authenticate: Bearer` 头

#### 2.7.9 审计日志

- 记录所有认证尝试（成功和失败）
- 记录用户身份信息（用户名、角色）
- 记录客户端 IP 和请求路径

## 3. MCP 工具列表

| 工具名称            | 功能描述                                      | 对应 ansible 功能 |
| ------------------- | --------------------------------------------- | ----------------- |
| `check_host_status` | 检查主机状态(架构, 发行版, Python, tsc_tools) | raw               |
| `ansible_shell`     | 执行远程 Shell 命令                           | shell             |
| `ansible_copy`      | 调用 ansible copy 模块，分发文件到远程主机    | copy              |
| `ansible_fetch`     | 调用 ansible fetch 模块，从远程主机获取文件   | fetch             |
| `list_playbooks`    | 列出可用的 playbook 文件，包含元数据说明      | -                 |
| `ansible_playbook`  | 执行 playbook 文件                            | ansible-playbook  |
| `get_task_status`   | 查询任务状态                                  | 无                |

## 4. Playbook 元数据规范

为支持 LLM 理解 playbook 用途，所有 playbook 文件必须包含以下元数据：

### 4.1 元数据格式

在 playbook 文件顶部使用 YAML 注释声明元数据：

```yaml
# @description: 本 playbook 用于安装和配置 Nginx 服务
# @author: tsc
# @version: 1.0.0
# @tags: nginx, web, install
# @parameters:
#   - nginx_version: Nginx 版本号 (默认: 1.24.0)
#   - nginx_port: Nginx 监听端口 (默认: 80)
---
- name: Install and configure Nginx
  hosts: all
  ...
```

### 4.2 元数据字段说明

| 字段         | 必填 | 说明                           |
| ------------ | ---- | ------------------------------ |
| @description | 是   | playbook 功能描述，供 LLM 理解 |
| @author      | 否   | 作者信息                       |
| @version     | 否   | playbook 版本号                |
| @tags        | 否   | 标签，便于分类和搜索           |
| @parameters  | 否   | 可传入的参数说明               |

### 4.3 list_playbooks 返回格式

```json
{
  "playbooks": [
    {
      "name": "install_nginx.yml",
      "path": "playbooks/install_nginx.yml",
      "description": "本 playbook 用于安装和配置 Nginx 服务",
      "author": "tsc",
      "version": "1.0.0",
      "tags": ["nginx", "web", "install"],
      "parameters": [
        {
          "name": "nginx_version",
          "description": "Nginx 版本号",
          "default": "1.24.0"
        },
        {
          "name": "nginx_port",
          "description": "Nginx 监听端口",
          "default": "80"
        }
      ]
    }
  ]
}
```

## 5. 数据存储

- 任务状态: SQLite(`logs/tsc_ansible_mcp.db`)
- Inventory 缓存: YAML(`etc/inventory.yml`，Ansible 标准格式)

## 6. Ansible 执行日志

### 6.1 功能描述

系统应提供详细的 ansible 执行日志记录功能，将每次 ansible 执行的完整详细信息记录到独立的日志文件中。日志应包含完整的执行过程、每个任务的详细结果、错误信息等。

### 6.2 功能需求

1. **独立日志文件**
   - 创建独立的 ansible 执行日志文件
   - 日志文件路径：`logs/ansible_execution.log`
   - 支持日志轮转和压缩
   - 使用 loguru 的标准文本格式

2. **日志内容（详细）**
   - 执行时间戳
   - 任务 ID
   - 用户信息
   - 执行的完整 playbook 内容（YAML 格式）
   - 目标主机列表
   - Inventory 内容（完整记录）
   - 执行参数（timeout, extravars 等）
   - **每个执行事件的详细信息**：
     - 事件类型（runner_on_ok, runner_on_failed, runner_on_unreachable 等）
     - 主机名
     - 任务名
     - 执行结果（stdout, stderr, rc）
     - 是否改变状态（changed）
   - 执行结果汇总（成功/失败主机数、总耗时等）
   - 错误详情（如果有）

3. **日志格式**
   - 使用 loguru 的标准文本格式
   - 结构化但可读性强
   - 使用分隔线区分不同的执行记录
   - 包含任务 ID，便于追踪

4. **配置支持**
   - 支持启用/禁用 ansible 执行日志
   - 支持配置日志保留时间
   - 支持配置日志轮转策略

### 6.3 非功能需求

1. **性能要求**
   - 日志记录不应显著影响 ansible 执行性能
   - 日志写入应异步进行（如果可能）

2. **存储要求**
   - 日志文件应支持轮转，避免占用过多磁盘空间
   - 日志文件应支持压缩存储

3. **可读性要求**
   - 日志格式应清晰易读
   - 使用分隔线区分不同的执行记录
   - 重要信息使用不同的日志级别（INFO, WARNING, ERROR）

## 7. 结果摘要模式

### 7.1 功能描述

当执行 playbook 或命令的目标主机数量较多时，返回结果可能超过 LLM 上下文长度限制。结果摘要模式通过默认返回摘要信息，将详细结果存储到文件，支持按需查询。

### 7.2 核心特性

1. **摘要返回**
   - 默认只返回执行摘要（总数、成功数、失败数）
   - 返回失败主机列表和详细信息（限制数量）
   - 返回任务 ID，支持后续查询

2. **混合存储**
   - 摘要信息存储在 SQLite 数据库
   - 详细结果存储在 JSON 文件（`logs/task_results/`）
   - 永久保留，支持手动清理

3. **查询工具**
   - `get_task_detail(task_id, host)` - 查询特定主机详情
   - `get_failed_hosts(task_id, limit, offset)` - 查询失败主机
   - `get_all_results(task_id, limit, offset)` - 分页查询所有结果

### 7.3 返回格式示例

```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "partial_success",
  "summary": {
    "total": 100,
    "success": 95,
    "failed": 5
  },
  "failed_hosts": ["host1", "host2", "host3", "host4", "host5"],
  "failed_detail": {
    "host1": { "rc": 1, "stdout": "...", "stderr": "..." },
    "host2": { "rc": 1, "stdout": "...", "stderr": "..." }
  },
  "has_more_failed": false,
  "elapsed": "10.50s",
  "message": "执行完成，5 台主机失败。使用 get_task_detail('xxx-xxx-xxx', host) 查看详情"
}
```

### 7.4 适用工具

- `ansible_shell` - Shell 命令执行
- `ansible_playbook` - Playbook 执行
- `ansible_copy` - 文件分发
- `ansible_fetch` - 文件获取
- `check_host_status` - 主机状态检查

## 8. 验证标准

- 单台执行延迟(含探测)不超过 60 秒
- 支持至少 100 台机器同时触发(分批执行)
- 无 Python 环境下 `raw` 模式执行成功率 100%

## 9. 相关文档

- [架构设计文档](./ARCHITECTURE.md)
- [API 参考文档](./API-REFERENCE.md)
- [技术规格说明](./SPEC.md)
- [开发任务清单](./TODO.md)
