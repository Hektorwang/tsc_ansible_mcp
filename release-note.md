# Release Notes

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

### v1.1.0 (2026-04-06)

- 新增 Playbook 执行能力
- 新增 ansible_fetch 文件获取功能
- 重命名 MCP 工具（统一命名风格）
- 合并 detect_environment 到 check_host_status
- 改进错误处理和日志输出
- 更新文档

### v1.0.0 (2026-04-06)

- 首次发布
- 实现核心功能
- 提供双接口服务（MCP + REST API）
- 完整的 API 文档
