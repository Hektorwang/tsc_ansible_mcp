# Release Notes

## Version=1.3.0

2026-04-07

### 新功能

#### API 认证系统

- **Bearer Token 认证** - 实现标准的 HTTP Bearer Token 认证机制
- **Token 文件管理** - Token 独立存储在 `etc/tokens.txt`，不暴露在主配置文件中
- **认证开关** - 通过配置文件灵活控制认证启用/禁用
- **中间件保护** - 所有 API 端点和 MCP 端点统一受认证保护

#### 认证配置

```toml
[auth]
enabled = true
tokens_file = "etc/tokens.txt"
```

#### Token 管理

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

### 安全特性

- Token 使用加密安全的随机数生成器生成
- 支持 IP 白名单双重验证
- 详细的认证日志记录
- 标准的 HTTP 401/403 响应
- WWW-Authenticate 头支持

### 文档更新

- 新增 `docs/AUTH-GUIDE.md` - 完整的认证使用指南
- 更新 `README.md` - 添加认证说明和版本号更新
- 更新 `docs/API-REFERENCE.md` - 添加认证请求头说明
- 更新 `docs/PRD.md` - 添加认证需求

### 测试验证

- 无 Token 访问返回 401
- 错误 Token 访问返回 401
- 正确 Token 访问返回 200
- 健康检查端点无需认证
- API 文档端点无需认证

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
