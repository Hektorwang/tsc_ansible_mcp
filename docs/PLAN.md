# TSC_ANSIBLE_MCP v1.5.0 开发计划

## 版本概述

v1.5.0 的核心任务是 **JWT 认证系统升级**，将现有的简单 Bearer Token 认证替换为基于 JWT 的身份认证和权限控制系统。

## 需求确认结果

通过 14 个问题的调研，已确认以下关键决策：

### 1. 认证系统设计

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 认证方式迁移 | 完全替换为 JWT | 移除旧的 Token 认证代码和配置 |
| JWT 默认过期时间 | 永久有效 | 签发时可选设置过期时间 |
| JWT 撤销机制 | 重启服务生效 | 编辑 jwt_issued_tokens.json 删除记录后重启服务 |
| 密钥长度检查 | 自动生成 | 密钥长度不足时自动生成符合要求的密钥 |
| JWT 认证失败错误格式 | 专门格式 | 使用专门的 JWT 认证失败错误响应格式 |

### 2. 权限系统设计

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 角色权限扩展 | 支持自定义角色 | 在配置文件中定义角色和权限 |
| 权限通配符匹配 | 简单前缀匹配 | 只支持 playbook_* 这种简单前缀匹配 |
| 自定义角色定义方式 | 配置文件定义 | 在 etc/tsc_ansible_mcp.toml 中定义角色和权限 |

### 3. 动态工具命名

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 动态 Playbook 工具命名 | 添加 playbook_ 前缀 | 如 collect_iaas_info.yml -> playbook_collect_iaas_info |

### 4. 审计日志增强

记录以下信息：
- 请求参数（目标主机、命令等）
- 响应状态和结果摘要
- 完整的请求和响应数据

### 5. 清理范围

需要删除的文件和配置：
- etc/tokens.txt
- etc/tokens.txt.example
- bin/generate_api_key.py
- 配置文件中的 api_keys 配置项

### 6. 测试验收标准

- JWT 功能测试：验证 JWT 生成、验证、撤销等功能
- 权限控制测试：验证 admin、user 和自定义角色的权限控制

### 7. 文档更新范围

- README.md：认证说明、工具命名、MCP 工具列表、配置文件示例
- release-note.md：添加 v1.5.0 版本说明

## 文档自洽性分析

### 已发现的不一致问题

#### 1. 动态工具命名不一致 ✅ 已解决

**问题**：
- TODO.md 说要添加 `playbook_` 前缀
- README.md 第 366 行说工具名直接使用文件名（无前缀）

**解决方案**：统一使用 `playbook_` 前缀

#### 2. 认证配置不一致 ✅ 已解决

**问题**：
- SPEC.md 说权限配置在 `etc/tsc_ansible_mcp.toml`
- README.md 显示的是旧的 `api_keys` 配置方式

**解决方案**：完全替换为 JWT 认证，更新所有文档

#### 3. 审计日志格式不完整 ✅ 已解决

**问题**：
- SPEC.md 12.7 只定义了基本的审计日志格式（IP、用户名、角色）
- 用户要求记录更多信息

**解决方案**：增强审计日志，记录请求参数、响应状态、完整数据

## 开发任务清单

### 阶段一：基础设施准备

#### 1.1 依赖管理

- [ ] 添加 `PyJWT>=2.8.0` 到 `requirements.txt`（注意：不使用 fast-jwt-auth，使用标准的 PyJWT 库）
- [ ] 验证依赖安装

#### 1.2 文件创建

- [ ] 创建 `etc/jwt_secret_key.txt` 密钥文件（初始为空，启动时自动生成）
- [ ] 创建 `etc/jwt_issued_tokens.json` 签发记录文件（初始为空 JSON）
- [ ] 更新 `.gitignore` 添加 JWT 相关文件

### 阶段二：核心模块开发

#### 2.1 JWT 工具模块（lib/jwt_utils.py）

- [ ] 实现 JWT 生成函数
  - 支持 sub, name, role, iat, exp 字段
  - 默认永久有效，可选设置过期时间
  - 使用 HS256 算法
- [ ] 实现 JWT 验证函数
  - 验证签名有效性
  - 验证过期时间（如果有）
  - 返回 payload 信息
- [ ] 实现密钥管理功能
  - 自动生成符合长度要求的密钥（>= 32 字符）
  - 从文件加载密钥
  - 密钥长度检查和自动生成
- [ ] 实现 JWT 记录管理功能
  - 加载已签发 JWT 记录
  - 保存 JWT 记录
  - 删除 JWT 记录（撤销）
  - 列出所有 JWT 记录
- [ ] 实现通配符权限匹配功能
  - 支持 `*` 通配符（所有工具）
  - 支持 `playbook_*` 前缀匹配（所有动态 playbook 工具）
  - 简单前缀匹配实现

#### 2.2 动态工具命名调整（lib/playbook_scanner.py）

- [ ] 修改 `_process_playbook_file` 方法
  - 工具命名添加 `playbook_` 前缀
  - 例如：`collect_iaas_info.yml` -> `playbook_collect_iaas_info`
- [ ] 更新相关日志和错误信息

#### 2.3 认证中间件改造（lib/auth.py）

- [ ] 重构 `AuthMiddleware` 类
  - 移除旧的 Token 认证代码
  - 使用 JWT 验证替换
  - 从 JWT 中提取用户身份信息（sub, name, role）
  - 实现权限验证（工具注册时）
- [ ] 实现权限验证逻辑
  - 根据角色查询配置文件中的权限配置
  - 检查工具是否在允许列表中
  - 支持通配符匹配
- [ ] 实现审计日志增强
  - 记录请求参数
  - 记录响应状态
  - 记录完整数据
- [ ] 实现 JWT 认证失败的专门错误响应格式

#### 2.4 JWT 生成器开发（bin/generate_jwt.py）

- [ ] 实现 `--generate-key` 命令
  - 生成符合长度要求的密钥（>= 32 字符）
  - 保存到 etc/jwt_secret_key.txt
- [ ] 实现 `--issue` 命令
  - 接受 --sub, --name, --role 参数
  - 可选 --expires 参数设置过期时间
  - 生成 JWT 并保存记录
- [ ] 实现 `--list` 命令
  - 列出所有已签发的 JWT
- [ ] 实现 `--verify` 命令
  - 验证 JWT 有效性
  - 显示 payload 信息

#### 2.5 配置文件更新（etc/tsc_ansible_mcp.toml）

- [ ] 移除旧的 Token 配置
  - 删除 `tokens_file` 配置项
- [ ] 添加 JWT 配置
  ```toml
  [auth]
  enabled = true
  jwt_secret_key_file = "etc/jwt_secret_key.txt"
  jwt_issued_tokens_file = "etc/jwt_issued_tokens.json"
  
  [auth.tool_permissions]
  admin = ["*"]
  user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
  # 支持自定义角色
  # readonly = ["list_playbooks", "get_task_status"]
  ```

### 阶段三：清理工作

- [ ] 删除 `etc/tokens.txt`（如果存在）
- [ ] 删除 `etc/tokens.txt.example`
- [ ] 删除 `bin/generate_api_key.py`
- [ ] 清理配置文件中的 `api_keys` 配置（如果存在）

### 阶段四：测试验证

#### 4.1 JWT 功能测试

- [ ] 测试密钥自动生成
- [ ] 测试 JWT 生成（永久有效）
- [ ] 测试 JWT 生成（带过期时间）
- [ ] 测试 JWT 验证
- [ ] 测试 JWT 撤销（编辑文件 + 重启服务）
- [ ] 测试密钥更换（所有 JWT 失效）

#### 4.2 权限控制测试

- [ ] 测试 admin 角色权限（所有工具）
- [ ] 测试 user 角色权限（仅 playbook 相关）
- [ ] 测试自定义角色权限
- [ ] 测试 `playbook_*` 通配符匹配
- [ ] 测试权限不足的错误响应

#### 4.3 集成测试

- [ ] 测试 REST API 认证
- [ ] 测试 MCP 认证
- [ ] 测试动态工具命名（playbook_ 前缀）
- [ ] 测试审计日志记录

### 阶段五：文档更新

#### 5.1 README.md 更新

- [ ] 更新认证说明（JWT 替换 Token）
- [ ] 更新动态工具命名说明（添加 playbook_ 前缀）
- [ ] 更新 MCP 工具列表（添加 playbook_ 前缀）
- [ ] 更新配置文件示例（JWT 配置）
- [ ] 更新使用示例（JWT 生成和使用）

#### 5.2 release-note.md 更新

- [ ] 添加 v1.5.0 版本说明
- [ ] 列出所有新功能和变更
- [ ] 列出破坏性变更（认证方式迁移）

#### 5.3 其他文档验证

- [ ] 验证 SPEC.md 与实现一致
- [ ] 验证 PRD.md 与实现一致
- [ ] 验证 ARCHITECTURE.md 与实现一致
- [ ] 验证 API-REFERENCE.md 与实现一致

## 技术实现细节

### JWT Payload 结构

```json
{
  "sub": "user_001",
  "name": "张三",
  "role": "admin",
  "iat": 1712476800,
  "exp": null
}
```

### 权限配置示例

```toml
[auth.tool_permissions]
admin = ["*"]
user = ["list_playbooks", "ansible_playbook", "get_task_status", "playbook_*"]
readonly = ["list_playbooks", "get_task_status"]
operator = ["check_host_status", "ansible_shell", "ansible_copy", "ansible_fetch", "playbook_*"]
```

### 审计日志格式

```
2026-04-07 18:50:57 | INFO | 认证成功: IP=127.0.0.1, User=张三(user_001), Role=admin, Request={"targets": ["192.168.1.1"], "command": "ls -la"}, Response={"status": "success", "rc": 0}
```

### JWT 认证失败错误响应

```json
{
  "status": "error",
  "error": {
    "code": "JWT_AUTH_FAILED",
    "message": "JWT Token 无效或已过期",
    "details": {
      "reason": "token_expired",
      "expired_at": "2026-04-07T18:50:57Z"
    }
  }
}
```

## 风险评估

### 1. 破坏性变更

**风险**：认证方式从 Token 完全替换为 JWT，可能影响现有用户

**缓解措施**：
- 在 release-note.md 中明确标注破坏性变更
- 提供迁移指南
- 保留旧版本文档

### 2. 性能影响

**风险**：JWT 验证和权限检查可能增加请求延迟

**缓解措施**：
- JWT 验证使用高效的 PyJWT 库
- 权限检查使用简单的前缀匹配
- 避免每次请求都读取文件（缓存 JWT 记录）

### 3. 安全风险

**风险**：JWT 密钥泄露或管理不当

**缓解措施**：
- 密钥文件添加到 .gitignore
- 自动生成符合长度要求的密钥
- 提供密钥更换指南

## 时间估算

| 阶段 | 预计工作量 | 说明 |
|------|-----------|------|
| 阶段一：基础设施准备 | 0.5 天 | 依赖管理和文件创建 |
| 阶段二：核心模块开发 | 2 天 | JWT 工具、认证中间件、生成器 |
| 阶段三：清理工作 | 0.5 天 | 删除旧代码和文件 |
| 阶段四：测试验证 | 1 天 | 功能测试和集成测试 |
| 阶段五：文档更新 | 0.5 天 | 更新所有相关文档 |
| **总计** | **4.5 天** | - |

## 验收标准

### 功能验收

- [ ] JWT 生成和验证功能正常
- [ ] 权限控制按预期工作
- [ ] 动态工具命名正确（playbook_ 前缀）
- [ ] 审计日志记录完整
- [ ] 所有测试通过

### 文档验收

- [ ] 所有文档与实现一致
- [ ] README.md 更新完整
- [ ] release-note.md 包含所有变更

### 代码质量

- [ ] 通过 mypy 类型检查
- [ ] 通过 black 格式化
- [ ] 通过 pylint 校验
- [ ] 代码符合项目规范

## 后续优化方向（不在 v1.5.0 范围）

- 热更新优化：实现无需重启服务的工具更新
- 实时撤销：使用缓存实现 JWT 实时撤销
- 与其他认证系统对接：提供详细的对接文档
- 更细粒度的权限控制：支持资源级别的权限

---

**计划制定时间**：2026-04-08
**计划版本**：v1.0
**预计开始时间**：待确认
**预计完成时间**：待确认
