# TSC_ANSIBLE_MCP 架构设计文档

## 1. 系统架构概览

### 1.1 单机部署架构

```text
MCP_Service -> Ansible-runner -> SSH -> Hosts
```

### 1.2 组件说明

| 组件        | 职责                     | 技术栈                        |
| ----------- | ------------------------ | ----------------------------- |
| Nginx       | 提供文件服务，分发安装包 | 独立提供, 无需包在本项目中    |
| MCP Service | 提供 LLM 调用接口        | Python 3.13, FastMCP, FastAPI |
| Ansible     | 实际执行远程操作的引擎   | ansible-core, ansible-runner  |
| SQLite      | 保存任务执行状态         | sqlite3                       |

## 2. 数据流向

### 2.1 请求处理流程

```text
LLM/CLI/API
    ↓
MCP Service (接收请求)
    ↓
TaskManager (创建和管理任务)
    ↓
Ansible (执行任务)
    ↓
目标主机 (执行命令)
    ↓
结果回收 (TaskManager)
    ↓
结果返回 (MCP Service)
    ↓
LLM/CLI/API (返回结果)
```

### 2.2 环境自举流程

使用一个预置的 playbook 实现

```text
目标主机 (无Python)
    ↓
detect_environment (检测环境)
    ↓
选择安装包 (根据架构/发行版)
    ↓
Nginx (提供安装包)
    ↓
目标主机 (下载并安装Python)
    ↓
验证安装 (install_python)
```

## 3. 数据存储设计

### 3.1 任务状态存储 (SQLite)

**存储路径**：`logs/tsc_semaphore.db`

**表结构**：

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    parameters TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 3.2 Inventory 缓存 (YAML)

**存储路径**：`etc/inventory.yml`

**格式**（Ansible 标准格式）：

```yaml
all:
  hosts:
    192.168.1.100:
      ansible_host: 192.168.1.100
      ansible_user: root
      ansible_port: 22
      ansible_ssh_private_key_file: /root/.ssh/id_rsa
    192.168.1.101:
      ansible_host: 192.168.1.101
      ansible_user: admin
      ansible_port: 22
      ansible_password: secret
```

## 4. MCP 工具实现设计

### 4.1 detect_environment

**功能**：探测目标主机环境信息

**实现方式**：Ansible `raw` 模块（无需目标主机安装 Python）

**执行流程**：

```text
1. SSH 连接目标主机
2. 执行 uname -m 获取架构
3. 执行 cat /etc/os-release 获取发行版
4. 执行 bash --version 获取 bash 版本
5. 检查 tsc_tools 是否已安装
6. 检查 python3 是否存在
7. 归一化架构和发行版信息
8. 返回汇总结果
```

**关键命令**：

| 检查项      | 命令                                                                                                           |
| ----------- | -------------------------------------------------------------------------------------------------------------- |
| 架构        | `uname -m`                                                                                                     |
| 发行版      | `cat /etc/os-release`                                                                                          |
| bash 版本   | `bash --version \| head -1`                                                                                    |
| tsc_tools   | `test -f /home/tsc/tsc_tools/release-note.md`                                                                  |
| python 路径 | `(command -v python3 \|\| test -x /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3) \|\|echo "not_found"` |

### 4.2 install_tsc_tools

**功能**：在目标主机安装 tsc_tools 环境

**实现方式**：Ansible `raw` 模块

**执行流程**：

```text
1. 幂等性检查: test -d /home/tsc/tsc_tools/ && tsc -f /home/tsc/tsc_tools/tsc
2. 若已存在则跳过
3. 若不存在从 nginx 下载安装包
4. 执行安装脚本
5. 验证安装结果
```

**关键命令**：

```bash
curl -o /tmp/tsc_tools.sh {nginx_url}/{package_name}
bash /tmp/tsc_tools.sh
```

### 4.3 install_python

**功能**：在目标主机安装 tsc_python 环境

**实现方式**：Ansible `raw` 模块

**执行流程**：

```text
1. 幂等性检查: which python3
2. 检查 tsc_python: test -f /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3
3. 若已存在则跳过
4. 调用 detect_environment 获取架构和发行版
5. 根据归一化结果选择安装包
6. 从 nginx 下载安装包
7. 执行安装脚本
8. 验证安装结果
```

**安装包选择逻辑**：

```text
包名格式: tsc_python-{version}-{distro}-{arch}-{date}.sh
示例: tsc_python-0.9.5-Redhat-x86_64-20260330.sh
```

### 4.4 ansible_shell

**功能**：在目标主机执行 Shell 命令

**实现方式**：Ansible `shell` 模块（需要目标主机有 Python）

**执行流程**：

```text
1. 高危命令黑名单检查
2. 若命中黑名单则拒绝执行
3. 构建 ansible ad-hoc 命令
4. 执行并捕获 stdout, stderr, rc
5. 返回执行结果
```

**安全检查**：

- 执行前检查命令是否包含黑名单关键词
- 脚本内含的黑名单命令不拦截

### 4.5 ansible_copy

**功能**：分发本地文件到远程主机

**实现方式**：Ansible `copy` 模块

**执行流程**：

```text
1. 验证本地文件存在
2. 构建 ansible copy 任务
3. 执行文件传输
4. 验证目标文件存在
5. 返回传输结果
```

### 4.6 ansible_fetch

**功能**: 采集远程文件到本地

**实现方式**：Ansible `fetch` 模块

**执行流程**：

```text
1. 构建 ansible fetch 任务
2. 执行文件传输(本地文件命名中需带 inventory_hostname或ansible_host)
3. 验证本地文件存在
4. 返回传输结果
```

### 4.7 add_inventory

**功能**：添加/更新主机到本地 Inventory 缓存

**实现方式**：Python 操作 YAML 文件

**执行流程**：

```text
1. 读取 etc/inventory.yml
2. 更新或添加主机信息
3. 写回 YAML 文件
4. 返回操作结果
```

### 4.8 get_task_status

**功能**：查询任务执行状态

**实现方式**：查询 SQLite 数据库

**执行流程**：

```text
1. 根据 task_id 查询 tasks 表
2. 返回任务状态和结果
```

### 4.9 list_playbooks

**功能**: 查询 playbooks 目录下的剧本, 并提取其元数据

**实现方式**: Python 读取 yaml 文件

**执行流程**:

```text
1. 遍历 `playbooks` 目录下第一级所有的 yml 文件
2. 读取每个 yml 文件的元数据信息 (yaml.safe_load())
3. 返回 剧本文件路径和剧本元数据信息
```

### 4.10 ansible_playbook

**功能**: 执行 playbooks 目录下剧本文件

**实现方式**: ansible-runner

**执行流程**:

```text
1. 接受接口传来的 playbook 剧本名, 和剧本的变量参数, 以及要运行的主机
2. 生成临时 inventory 文件
3. 将主机也更新到 etc/inventory.yml
4. 使用临时 inventory 文件来运行具备
5. 返回各主机运行结果
```

### 4.11 动态 Playbook 工具生成

**功能**: 服务启动时自动扫描 playbooks 目录，为每个 playbook 动态生成独立的 MCP 工具

**实现方式**: PlaybookScanner 类 + FastMCP 动态工具注册

**核心组件**:

- `lib/playbook_scanner.py`: PlaybookScanner 类
- `lib/server.py`: `_register_dynamic_playbook_tools()` 方法

**执行流程**:

```text
1. 服务启动时创建 PlaybookScanner 实例
2. 扫描 playbooks 目录下所有 .yml/.yaml 文件
3. 解析每个 playbook 的元数据（JSON 格式）
4. 生成工具定义（名称、描述、参数）
5. 使用 @mcp.tool() 装饰器动态注册工具
6. 启动 watchdog 文件监控
```

**工具命名规则**:

- 使用 `playbook_` 前缀 + playbook 文件名（不含扩展名）
- 例如: `collect_iaas_info.yml` -> 工具名 `playbook_collect_iaas_info`

**元数据要求**:

- 必须包含 `description` 字段
- 建议包含 `parameters`、`use_cases`、`example`、`notes` 字段
- 缺少元数据的 playbook 将被跳过并在日志中告警

**文件监控**:

- 使用 watchdog 库实现跨平台文件监控
- 监控事件: 文件创建、修改、删除
- 热更新限制: 需要重启服务才能使新的工具生效

### 4.12 JWT 认证架构

**功能**: 实现 JWT 身份认证和角色权限控制

**核心组件**:

- `lib/jwt_utils.py`: JWT 工具模块
- `lib/auth.py`: 认证中间件
- `bin/generate_jwt.py`: JWT 生成器

**认证流程**:

```text
客户端请求
    ↓
认证中间件 (auth.py)
    ↓
JWT 验证 (PyJWT)
    ↓
提取用户身份 (sub, name, role)
    ↓
权限验证 (工具注册时)
    ↓
执行请求
```

**权限验证流程**:

```text
工具调用请求
    ↓
提取 JWT 中的 role
    ↓
查询配置文件中的权限配置
    ↓
检查工具是否在允许列表中
    ↓
允许/拒绝执行
```

**权限验证机制**:
- MCP 工具列表根据角色过滤（v1.6.0 新增）
- MCP 工具调用时验证用户权限
- LLM 获取工具列表时，根据角色暴露可用工具
- API 调用时验证用户权限
- 日志中记录每个操作的用户名

**MCP 工具角色过滤架构**（v1.6.0 新增）:

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

**双重保护机制**（v1.6.0 新增）:

```
第一层保护：MCP 协议层面
├── tools/list 过滤：user 只能看到 playbook 相关工具
└── tools/call 检查：拒绝 user 调用 admin 工具

第二层保护：工具函数内部
├── check_host_status：内部权限检查
├── install_tsc_tools：内部权限检查
├── install_python：内部权限检查
├── ansible_shell：内部权限检查
├── ansible_copy：内部权限检查
└── ansible_fetch：内部权限检查
```

**核心组件**:
- `lib/context_vars.py`: 上下文变量管理
- `lib/middleware.py`: MCP 授权中间件
- `lib/jwt_utils.py`: 权限检查逻辑
- `lib/permission.py`: 工具函数权限检查

**角色权限设计**:

| 角色  | 权限配置        | 说明             |
| ----- | --------------- | ---------------- |
| admin | ["*"]           | 可调用所有工具   |
| user  | ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"] | 仅 playbook 相关 |

**权限配置说明**:
- `*`: 表示所有工具
- `playbook_*`: 表示所有动态生成的 playbook 工具

**JWT 签发流程**:

```text
运行 generate_jwt.py --issue
    ↓
读取密钥文件 (jwt_secret_key.txt)
    ↓
生成 JWT (PyJWT)
    ↓
记录到签发记录 (jwt_issued_tokens.json)
    ↓
输出 JWT Token
```

**JWT 撤销流程**:

```text
运行 generate_jwt.py --revoke <jwt_id>
    ↓
读取签发记录文件
    ↓
标记 JWT 为已撤销
    ↓
写回签发记录文件
```

**与其他认证系统对接**:

通过更换密钥文件，可以与其他认证系统对接：

1. 外部认证系统签发 JWT（使用相同密钥和 payload 结构）
2. 系统自动验证外部签发的 JWT
3. 支持单点登录（SSO）场景

## 5. 技术选型说明

### 5.1 为什么选择 FastMCP？

- LLM 友好：专为 LLM 工具调用设计
- 简单易用：Python 装饰器方式定义工具
- 类型安全：支持类型注解和验证
- 文档自动生成：自动生成工具文档

### 5.2 为什么选择 ansible-runner？

- 无代理：无需在目标主机安装客户端
- 幂等性：支持幂等操作
- 模块丰富：提供大量内置模块
- 社区活跃：庞大的社区支持

## 6. 系统边界

### 6.1 系统职责

- 远程命令执行
- 环境自举（Python 安装）
- 任务调度和管理
- 审计日志记录
- LLM 工具接口

### 6.2 系统不负责

- 目标主机监控
- 配置管理（非 Python 环境）
- 安全合规检查

## 7. 性能考量

### 7.1 性能指标

- 单台执行延迟（含探测）不超过 60 秒
- 支持至少 100 台机器同时触发（队列排队，分批执行）
- 在完全移除目标机 Python 情况下，`raw` 模式指令执行成功率 100%

### 7.2 性能优化

- 并发控制：forks=10（详见 SPEC.md 执行参数规格）
- 连接复用：SSH 连接复用
- 缓存机制：Fact 缓存
- 异步执行：异步任务执行

## 8. 相关文档

- [PRD 文档](./PRD.md)
- [API 参考文档](./API-REFERENCE.md)
- [技术规格说明](./SPEC.md)
- [开发任务清单](./TODO.md)
