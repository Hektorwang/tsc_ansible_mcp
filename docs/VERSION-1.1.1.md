# 版本 1.1.1 更新说明

**发布日期：2026-04-07**

## 🎉 主要更新

### 1. 智能 Inventory 管理 ✨

实现了智能的 inventory 验证和 fallback 机制，确保主机凭据的可靠性。

**核心功能：**
- ✅ **智能验证** - LLM 提供的凭据会先验证，验证成功才更新 inventory
- ✅ **自动 Fallback** - 新凭据失败时自动使用缓存凭据
- ✅ **Inventory 保护** - 错误凭据不会覆盖已有凭据
- ✅ **详细日志** - 完整的验证和 fallback 过程日志

**新增方法：**
- `_test_connectivity()` - 独立的连接性测试方法
- `update_host_credentials()` - 仅在验证成功后更新凭据
- `_build_inventory(use_cached)` - 支持强制使用缓存 inventory

**工作流程：**
```
LLM 提供凭据 → 测试连接 → 成功 → 更新 inventory
                      ↓
                     失败 → 尝试缓存凭据 → 成功 → 使用缓存（不更新）
                                          ↓
                                         失败 → 连接失败
```

### 2. 持久化上下文存储 💾

新增上下文存储功能，支持跨会话保存配置信息。

**新增 MCP 工具：**
- `set_mcp_context(key, value)` - 保存上下文
- `get_mcp_context(key)` - 获取上下文
- `list_mcp_context()` - 列出所有上下文
- `delete_mcp_context(key)` - 删除上下文

**数据库变更：**
- 新增 `context` 表
- 新增 `ContextRepository` 类

**使用场景：**
- 记住常用的主机地址
- 保存配置信息（端口、路径等）
- 跨会话复用配置
- 团队知识共享

### 3. JSON 注释格式的 Playbook 元数据 📝

采用 LLM 最友好的 JSON 注释格式编写 Playbook 元数据。

**优势：**
- ✅ LLM 原生支持 JSON
- ✅ 可以提供完整的调用示例
- ✅ 类型信息丰富（type、default、description）
- ✅ 保持单文件（元数据和代码在一起）
- ✅ 通过 ansible-lint 验证
- ✅ 向后兼容旧格式

**示例：**
```yaml
# @meta: {
#   "description": "Collect IaaS infrastructure information",
#   "version": "1.1.1",
#   "parameters": [
#     {"name": "runtime", "type": "bool", "default": false}
#   ],
#   "example": {
#     "playbook": "collect_iaas_info.yml",
#     "targets": ["192.168.1.10"],
#     "extravars": {"runtime": true}
#   }
# }
---
- name: Collect IaaS information
  ...
```

### 4. IaaS 信息采集 Playbook 🖥️

新增专用的 IaaS 信息采集 playbook。

**功能：**
- 采集处理器信息（型号、核心数、架构）
- 采集内存信息（容量、类型、使用率）
- 采集存储信息（磁盘、RAID 配置）
- 采集操作系统信息（发行版、内核版本）
- 采集包管理器信息
- 可选的实时资源使用状态采集（`--runtime` 参数）

**文件：**
- `playbooks/collect_iaas_info.yml`

**使用：**
```python
# 基础信息采集
ansible_playbook(
    playbook="collect_iaas_info.yml",
    targets=["192.168.1.10"]
)

# 包含实时资源使用状态
ansible_playbook(
    playbook="collect_iaas_info.yml",
    targets=["192.168.1.10"],
    extravars={"runtime": true}
)
```

## 🐛 Bug 修复

### Inventory 管理逻辑修复
- **问题** - 错误凭据会覆盖正确凭据
- **修复** - 只有新凭据验证成功才更新 inventory
- **改进** - Fallback 时不再修改 `test_result`，避免误更新

### Playbook 执行修复
- **问题** - `Save IaaS information to file` 任务失败（`ansible_date_time` 未定义）
- **修复** - 移除保存文件任务，简化流程
- **改进** - Playbook 只负责采集和显示信息

## 📚 文档完善

### 新增文档
- `docs/inventory_management.md` - Inventory 管理逻辑详细说明
- `playbooks/README.md` - Playbook 编写指南（JSON 元数据规范）
- `CHANGELOG.md` - 版本更新日志

### 文档更新
- `README.md` - 添加版本号，更新功能说明
- `lib/server.py` - 更新 MCP_INSTRUCTIONS，增加 Playbook 使用指南

## 🧹 代码清理

### 删除示例文件
- 删除 `install_nginx.yml`
- 删除 `deploy_docker_container.yml`
- 删除 `monitor_system.yml`
- 删除 `install_nginx_v2.yml`
- 删除 `install_nginx_v3.yml`

### 保留文件
- `system_check.yml`（原有示例）
- `collect_iaas_info.yml`（生产使用）

## 🔧 技术细节

### 代码结构变更
```
lib/
├── executor.py
│   ├── _test_connectivity()          # 新增
│   ├── _build_inventory(use_cached)  # 改进
│   └── check_host_status()           # 改进
├── inventory_manager.py
│   └── update_host_credentials()     # 新增
├── models.py
│   └── Context                        # 新增
├── database.py
│   └── ContextRepository              # 新增
└── server.py
    ├── set_mcp_context()              # 新增
    ├── get_mcp_context()              # 新增
    ├── list_mcp_context()             # 新增
    └── delete_mcp_context()           # 新增
```

### 数据库变更
```sql
CREATE TABLE context (
    key VARCHAR(255) PRIMARY KEY,
    value TEXT NOT NULL,
    created_at VARCHAR(30) NOT NULL,
    updated_at VARCHAR(30) NOT NULL
);
```

## ✅ 测试验证

### 功能测试
- ✅ 使用正确凭据连接成功并更新 inventory
- ✅ 使用错误凭据自动 fallback 到缓存凭据
- ✅ Inventory 文件保持正确密码，未被错误密码覆盖
- ✅ 持久化上下文存储和读取
- ✅ JSON 元数据解析
- ✅ IaaS 信息采集

### 兼容性测试
- ✅ 通过 ansible-lint production 级别验证
- ✅ Python 3.13 兼容
- ✅ 向后兼容旧版元数据格式

## 📊 版本对比

| 功能 | v1.1.0 | v1.1.1 |
|------|--------|--------|
| 智能 Inventory 验证 | ❌ | ✅ |
| 自动 Fallback | ❌ | ✅ |
| 持久化上下文存储 | ❌ | ✅ |
| JSON 元数据格式 | ❌ | ✅ |
| IaaS 信息采集 | ❌ | ✅ |
| 详细日志 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Inventory 保护 | ❌ | ✅ |

## 🎯 升级建议

### 从 v1.1.0 升级
1. 拉取最新代码
2. 重启服务（数据库会自动创建 `context` 表）
3. 无需修改现有配置

### 兼容性
- ✅ 完全向后兼容 v1.1.0
- ✅ 现有 inventory 文件无需修改
- ✅ 现有 playbook 无需修改

## 📝 后续计划

- [ ] 添加更多运维常用 playbook
- [ ] 支持动态加载 playbook
- [ ] 添加硬件发现功能
- [ ] 添加安全扫描功能
- [ ] 支持多租户管理

---

**完整更新日志请查看：** [CHANGELOG.md](CHANGELOG.md)
