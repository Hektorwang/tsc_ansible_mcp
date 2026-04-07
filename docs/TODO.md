# TSC_ANSIBLE_MCP 开发任务清单

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

### API 认证系统

- [x] 实现 Bearer Token 认证机制
- [x] Token 文件管理 (`etc/tokens.txt`)
- [x] 认证中间件保护所有端点
- [x] 审计日志记录

### 上下文管理工具

- [x] set_context / get_context / delete_context
- [x] list_contexts / clear_contexts

### Python 检测逻辑优化

- [x] 新增 tsc_python_installed 字段
- [x] 修复 install_python 判断逻辑

---

## v1.1.0 已完成任务

## 版本概述

版本 1.1.0 主要增加 playbook 执行能力和 ansible 模块直接调用能力。

---

## 大项一：文档更新

### 1.1 更新 API-REFERENCE.md

- [x] 1.1.1 修改接口名称（execute_command -> ansible_shell, dispatch_file -> ansible_copy）
- [x] 1.1.2 添加 `list_playbooks` 接口文档
- [x] 1.1.3 添加 `ansible_playbook` 接口文档
- [x] 1.1.4 添加 `ansible_fetch` 接口文档
- [x] 1.1.5 补充缺失的 REST API 接口（任务列表、删除任务、统计、健康检查等）
- [x] 1.1.6 更新 REST API 路径

### 1.2 更新 PRD.md

- [x] 1.2.1 更新 MCP 工具列表（改名模块）
- [x] 1.2.2 添加 Playbook 元数据规范

### 1.3 更新其他文档

- [x] 1.3.1 修正 SPEC.md 中的依赖（Flask -> FastAPI）
- [x] 1.3.2 修正 ARCHITECTURE.md 中的技术栈（Flask -> FastAPI）
- [x] 1.3.3 修正 PRD.md 中的技术栈（Flask -> FastAPI）

---

## 大项二：基础设施准备

### 2.1 创建 playbooks 目录

- [x] 2.1.1 创建 `playbooks/` 目录
- [x] 2.1.2 创建示例 playbook 文件（含元数据）

### 2.2 更新配置

- [x] 2.2.1 在 `lib/config.py` 中添加 playbooks 路径配置属性
- [x] 2.2.2 在 `etc/tsc_ansible_mcp.toml` 中添加 playbooks 相关配置项

---

## 大项三：核心功能实现

### 3.1 实现执行引擎方法（lib/executor.py）

- [x] 3.1.1 实现 `list_playbooks()` 方法 - 列出 playbooks 目录下的文件，读取元数据
- [x] 3.1.2 实现 `run_playbook()` 方法 - 执行指定的 playbook 文件
- [x] 3.1.3 实现 `ansible_fetch()` 方法 - 调用 ansible fetch 模块
- [x] 3.1.4 重命名 `execute_command` -> `ansible_shell`
- [x] 3.1.5 重命名 `dispatch_file` -> `ansible_copy`

### 3.2 实现 MCP 工具接口（lib/server.py）

#### 3.2.1 重命名现有工具

- [x] 3.2.1.1 重命名 `execute_command` -> `ansible_shell`
- [x] 3.2.1.2 重命名 `dispatch_file` -> `ansible_copy`

#### 3.2.2 新增 MCP 工具

- [x] 3.2.2.1 实现 `list_playbooks` 工具 - 列出可用的 playbook 文件（含元数据）
- [x] 3.2.2.2 实现 `ansible_playbook` 工具 - 执行指定的 playbook
- [x] 3.2.2.3 实现 `ansible_fetch` 工具 - 调用 ansible fetch 模块

### 3.3 实现 REST API 接口（lib/server.py）

#### 3.3.1 更新现有 API

- [x] 3.3.1.1 修改 `POST /api/v1/executor/execute` -> `POST /api/v1/shell`
- [x] 3.3.1.2 修改 `POST /api/v1/files/dispatch` -> `POST /api/v1/copy`

#### 3.3.2 新增 REST API

- [x] 3.3.2.1 实现 `GET /api/v1/playbooks` - 列出 playbook 文件
- [x] 3.3.2.2 实现 `POST /api/v1/playbooks/execute` - 执行 playbook
- [x] 3.3.2.3 实现 `POST /api/v1/fetch` - Ansible fetch 模块

---

## 大项四：测试与验证

### 4.1 功能测试

- [x] 4.1.1 代码语法检查通过
- [ ] 4.1.2 测试 `list_playbooks` 功能（含元数据读取）
- [ ] 4.1.3 测试 `ansible_playbook` 功能
- [ ] 4.1.4 测试 `ansible_fetch` 功能
- [ ] 4.1.5 验证 `ansible_shell` 重命名
- [ ] 4.1.6 验证 `ansible_copy` 重命名

### 4.2 文档验证

- [x] 4.2.1 验证 API 文档准确性
- [x] 4.2.2 验证 PRD 文档完整性

---

## Playbook 元数据规范

### 元数据格式

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

### 元数据字段说明

| 字段         | 必填 | 说明                           |
| ------------ | ---- | ------------------------------ |
| @description | 是   | playbook 功能描述，供 LLM 理解 |
| @author      | 否   | 作者信息                       |
| @version     | 否   | playbook 版本号                |
| @tags        | 否   | 标签，便于分类和搜索           |
| @parameters  | 否   | 可传入的参数说明               |

---

## 接口变更对照表

### MCP 工具

| 原名称            | 新名称           | 说明   |
| ----------------- | ---------------- | ------ |
| detect_environment | check_host_status | 重命名，合并功能 |
| execute_command   | ansible_shell    | 重命名 |
| dispatch_file     | ansible_copy     | 重命名 |
| -                 | list_playbooks   | 新增   |
| -                 | ansible_playbook | 新增   |
| -                 | ansible_fetch    | 新增   |
| add_temp_host     | -                | 删除（内部使用） |

### REST API

| 原路径                          | 新路径                         | 说明   |
| ------------------------------- | ------------------------------ | ------ |
| POST /api/v1/hosts/environment  | POST /api/v1/hosts/status      | 重命名 |
| POST /api/v1/executor/execute   | POST /api/v1/shell             | 重命名 |
| POST /api/v1/files/dispatch     | POST /api/v1/copy              | 重命名 |
| -                               | GET /api/v1/playbooks          | 新增   |
| -                               | POST /api/v1/playbooks/execute | 新增   |
| -                               | POST /api/v1/fetch             | 新增   |

---

## 风险评估

1. **向后兼容性**：接口重命名可能影响现有调用方
2. **安全性**：playbook 执行需要考虑安全限制
3. **性能**：playbook 执行可能需要更长的超时时间
