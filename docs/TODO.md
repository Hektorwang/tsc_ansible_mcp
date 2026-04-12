# TSC_ANSIBLE_MCP 开发任务清单

## v1.9.0 已完成任务

### 结果摘要模式

#### 基础设施

- [x] 创建 `lib/task_result_store.py` 模块
- [x] 实现 `TaskResultStore` 类
  - [x] 实现 `save_result()` 方法
  - [x] 实现 `get_result()` 方法
  - [x] 实现 `get_host_result()` 方法
  - [x] 实现 `get_failed_hosts()` 方法
  - [x] 实现 `get_all_results()` 方法
- [x] 在 `lib/config.py` 中添加配置属性
- [x] 在 `etc/tsc_ansible_mcp.toml` 中添加配置项

#### 核心功能开发

- [x] 修改 `lib/executor.py`
  - [x] 实现 `_build_summary_result()` 方法
  - [x] 修改 `ansible_shell()` 返回格式
  - [x] 修改 `run_playbook()` 返回格式
  - [x] 修改 `dispatch_file()` 返回格式
  - [x] 修改 `ansible_fetch()` 返回格式
  - [x] 修改 `check_host_status()` 返回格式
  - [x] 修改 `install_python()` 返回格式
  - [x] 修改 `install_tsc_tools()` 返回格式

#### MCP 查询工具

- [x] 在 `lib/server.py` 中添加查询工具
  - [x] 实现 `get_task_detail` 工具
  - [x] 实现 `get_failed_hosts` 工具
  - [x] 实现 `get_all_results` 工具

#### 文档更新

- [x] 更新 PRD.md - 添加结果摘要模式说明
- [x] 更新 SPEC.md - 添加返回格式规格
- [x] 更新 ARCHITECTURE.md - 添加存储架构说明
- [x] 更新 TODO.md - 添加任务清单
- [x] 更新 release-note.md - 添加版本更新说明

---

## v1.8.0 已完成任务

### Ansible 执行详细日志记录

#### 基础设施

- [x] 创建 `lib/ansible_logger.py` 模块
- [x] 实现 `AnsibleExecutionLogger` 类
  - [x] 实现 `_setup_logger()` 方法
  - [x] 实现 `log_execution_start()` 方法
  - [x] 实现 `log_execution_event()` 方法
  - [x] 实现 `log_execution_result()` 方法
  - [x] 实现 `log_execution_error()` 方法
- [x] 在 `lib/config.py` 中添加 ansible 日志配置属性
- [x] 在 `etc/tsc_ansible_mcp.toml` 中添加配置项

#### 核心功能开发

- [x] 修改 `lib/executor.py`
  - [x] 在 `_run_ansible()` 方法中集成日志记录
  - [x] 在执行前记录完整的 playbook 和 inventory
  - [x] 遍历所有事件并记录详细信息
  - [x] 在执行后记录结果汇总

#### 文档更新

- [x] 更新 PRD.md - 添加 ansible 执行日志需求
- [x] 更新 SPEC.md - 添加 ansible 执行日志规格
- [x] 更新 ARCHITECTURE.md - 添加日志架构说明
- [x] 更新 TODO.md - 添加任务清单
- [x] 更新 release-note.md - 添加版本更新说明

---

## v1.6.0 已完成任务

### MCP 工具列表角色过滤

#### 基础设施

- [x] 创建 `lib/context_vars.py` 上下文变量管理模块
- [x] 创建 `lib/middleware.py` MCP 授权中间件
- [x] 创建 `lib/permission.py` 权限检查模块

#### 核心功能开发

- [x] 实现 MCP 授权中间件
  - [x] JWT Token 提取和验证
  - [x] 用户上下文设置
  - [x] tools/list 请求拦截和过滤
  - [x] tools/call 请求权限检查
  - [x] 审计日志记录

- [x] 实现双重保护机制
  - [x] 第一层：MCP 协议层面权限检查
  - [x] 第二层：工具函数内部权限检查
  - [x] 为所有 admin 专用工具添加权限检查
    - [x] check_host_status
    - [x] install_tsc_tools
    - [x] install_python
    - [x] ansible_shell
    - [x] ansible_copy
    - [x] ansible_fetch

#### 服务集成

- [x] 修改 `lib/server.py`
  - [x] 集成新的授权中间件
  - [x] 替换旧的认证中间件
  - [x] 添加权限检查导入

#### 文档更新

- [x] 更新 PRD.md - 添加 MCP 工具角色过滤说明
- [x] 更新 SPEC.md - 添加技术规格和双重保护机制
- [x] 更新 ARCHITECTURE.md - 添加架构图和核心组件
- [x] 更新 API-REFERENCE.md - 添加工具列表
- [x] 更新 README.md - 添加功能说明
- [x] 更新 release-note.md - 添加版本更新说明
- [x] 更新 TODO.md - 添加任务清单

#### 测试验证

- [x] 测试 admin 用户工具列表
- [x] 测试 user 用户工具列表过滤
- [x] 测试工具调用权限检查
- [x] 测试双重保护机制

---

## v1.5.0 已完成任务

### JWT 认证系统升级

#### 基础设施

- [x] 添加 `PyJWT>=2.8.0` 依赖到 `requirements.txt`
- [x] 创建 `etc/jwt_secret_key.txt` 密钥文件
- [x] 创建 `etc/jwt_issued_tokens.json` 签发记录文件
- [x] 更新 `.gitignore` 添加 JWT 相关文件

#### 核心模块开发

- [x] 创建 `lib/jwt_utils.py` JWT 工具模块
  - [x] 实现 JWT 生成函数
  - [x] 实现 JWT 验证函数
  - [x] 实现密钥管理功能
  - [x] 实现 JWT 记录管理功能
  - [x] 实现通配符权限匹配功能

#### 动态工具命名调整

- [x] 修改 `lib/playbook_scanner.py`
  - [x] 工具命名添加 `playbook_` 前缀
  - [x] 例如: `collect_iaas_info.yml` -> `playbook_collect_iaas_info`

#### 认证中间件改造

- [x] 修改 `lib/auth.py` 认证中间件
  - [x] 使用 PyJWT 替换现有认证逻辑
  - [x] 从 JWT 中提取用户身份信息
  - [x] 实现权限验证（工具注册时）
  - [x] 移除单一 Token 认证代码
  - [x] 实现审计日志增强

#### JWT 生成器开发

- [x] 创建 `bin/generate_jwt.py` JWT 生成器
  - [x] 实现 `--generate-key` 命令
  - [x] 实现 `--issue` 命令
  - [x] 实现 `--list` 命令
  - [x] 实现 `--verify` 命令
  - [x] 实现 `--revoke` 命令

#### 配置文件更新

- [x] 更新 `etc/tsc_ansible_mcp.toml`
  - [x] 添加 JWT 配置项
  - [x] 添加角色权限配置
  - [x] 移除旧 Token 配置

#### 清理工作

- [x] 删除 `etc/tokens.txt`（如果存在）
- [x] 删除 `etc/tokens.txt.example`
- [x] 删除 `bin/generate_api_key.py`

#### 测试验证

- [x] 测试 JWT 生成和验证
- [x] 测试权限控制
- [x] 测试密钥自动生成

#### 文档更新

- [x] 更新 PRD.md
- [x] 更新 SPEC.md
- [x] 更新 API-REFERENCE.md
- [x] 更新 ARCHITECTURE.md
- [x] 更新 README.md
- [x] 更新 release-note.md

---

## v1.4.0 已完成任务

### 动态 Playbook 工具生成

- [x] 创建 PlaybookScanner 类 (`lib/playbook_scanner.py`)
- [x] 实现 playbook 元数据解析（JSON 格式）
- [x] 实现动态工具注册机制
- [x] 添加 watchdog 文件监控
- [x] 更新文档（PRD.md, SPEC.md, ARCHITECTURE.md）
- [x] 代码格式化和类型检查

---

## v1.3.0 已完成任务

### REST API 增强

- [x] 添加 FastAPI REST API 支持
- [x] 实现任务管理 API（创建、查询、删除）
- [x] 实现主机管理 API（添加、删除、查询）
- [x] 实现健康检查端点
- [x] 添加 API 认证中间件
- [x] 更新文档

---

## v1.2.0 已完成任务

### 上下文管理

- [x] 实现上下文存储（SQLite）
- [x] 添加上下文管理工具（set, get, delete, list, clear）
- [x] 支持会话间数据持久化

---

## v1.1.0 已完成任务

### 基础功能

- [x] MCP 服务器实现
- [x] Ansible 集成
- [x] 主机管理
- [x] Playbook 执行
- [x] 任务状态跟踪
