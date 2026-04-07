# 文档更新总结 - Version 1.3.0

## 更新日期

2026-04-07

## 更新内容

### 1. README.md

**更新内容**:
- 版本号：1.3.0（已更新）
- 新增章节：7. 上下文管理
  - 说明 5 个上下文管理工具
  - 持久化存储功能介绍

### 2. release-note.md

**更新内容**:
- 新增 Version=1.3.0 完整发布说明
- 详细记录 4 大新功能：
  1. API 认证系统
  2. 上下文管理工具（5 个新工具）
  3. Python 检测逻辑优化
  4. 代码质量改进
- 工具列表更新：从 9 个增加到 14 个
- 测试验证说明

### 3. docs/PRD.md

**更新内容**:
- MCP 工具列表更新
  - 新增 5 个上下文管理工具
  - 更新 `check_host_status` 描述（添加 tsc_python 字段）
  - 更新 `install_python` 描述（说明独立环境）
- 工具总数：从 9 个增加到 14 个

### 4. docs/API-REFERENCE.md

**更新内容**:
- MCP 工具接口表格更新
  - 新增 5 个上下文管理工具
  - 更新工具描述
- 新增章节：3.1 上下文管理工具
  - set_context - 设置上下文键值对
  - get_context - 获取上下文值
  - delete_context - 删除指定的上下文键值对
  - list_contexts - 列出所有上下文键值对
  - clear_contexts - 清空所有上下文数据
- 每个工具包含参数说明和返回示例

### 5. docs/SPEC.md

**更新内容**:
- 版本号标识：已更新为 Version=1.3.0（第 27 行）

### 6. 新增文档

**docs/PYTHON_DETECTION_FIX.md**:
- Python 检测逻辑修复说明
- tsc_python_installed 字段说明
- 使用场景和 LLM 建议

**docs/SYS_PATH_FIX.md**:
- sys.path.insert 代码质量修复说明
- 修复逻辑详解
- 场景分析和验证测试

## 版本 1.3.0 新功能总结

### 1. API 认证系统

- Bearer Token 认证
- Token 文件独立管理
- 认证开关控制
- 中间件保护

### 2. 上下文管理工具（5 个新工具）

- set_context - 设置上下文键值对
- get_context - 获取上下文值
- delete_context - 删除指定的上下文键值对
- list_contexts - 列出所有上下文键值对
- clear_contexts - 清空所有上下文数据

### 3. Python 检测逻辑优化

- 新增 tsc_python_installed 字段
- 区分系统 Python 和 tsc_python
- 修复 install_python 跳过逻辑

### 4. 代码质量改进

- sys.path.insert 优化
- 动态路径替代硬编码
- 高效判断逻辑

## MCP 工具列表（14 个）

1. ansible_shell
2. install_python
3. check_host_status
4. get_task_status
5. install_tsc_tools
6. ansible_copy
7. ansible_fetch
8. list_playbooks
9. ansible_playbook
10. **set_context** (新增)
11. **get_context** (新增)
12. **delete_context** (新增)
13. **list_contexts** (新增)
14. **clear_contexts** (新增)

## 相关文档

- [README.md](../README.md) - 项目主文档
- [release-note.md](../release-note.md) - 版本发布说明
- [docs/PRD.md](./PRD.md) - 产品需求文档
- [docs/API-REFERENCE.md](./API-REFERENCE.md) - API 参考文档
- [docs/SPEC.md](./SPEC.md) - 技术规格说明
- [docs/AUTH-GUIDE.md](./AUTH-GUIDE.md) - 认证使用指南
- [docs/PYTHON_DETECTION_FIX.md](./PYTHON_DETECTION_FIX.md) - Python 检测修复说明
- [docs/SYS_PATH_FIX.md](./SYS_PATH_FIX.md) - sys.path.insert 修复说明
