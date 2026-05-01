# Release Notes

## v1.15.0 (2026-05-01)

### New Features
- **get_result (三层查询模式)** - 增强 `get_result` 工具，支持三种查询模式：任务摘要（省略 status）、失败主机列表（status="failed"）、成功主机列表（status="success"）
- **get_host_detail** - 新增 MCP 工具，通过 task_id + 主机 IP 查询单个主机的执行详情（rc、stdout、stderr、status）

### Improvements
- **异步工具轮询指导增强** - `ansible_shell`、`ansible_copy`、`ansible_fetch`、`check_host_status` 的 "running" 状态响应现在包含确切的 `get_result()` 调用语法和 30-60 秒轮询间隔建议
- **统一错误响应格式** - 所有错误响应均包含 task_id，便于追溯
- **API 文档更新** - 更新 `docs/API-REFERENCE.md`，补充 `get_result` 三种查询模式和 `get_host_detail` 完整文档

### Changes
- `lib/mcp_tools/task_results.py` - 重构 `get_result`，新增 `get_host_detail`
- `lib/task_result_store.py` - 新增 `get_host_result()` 方法，增强 `get_result()` 支持 status="success"
- `docs/API-REFERENCE.md` - 更新 MCP 工具表，新增 3.7/3.8 节，完善 Async Task Query API 章节

---

## v1.14.0 (2026-04-25)

### New Features
- **change_ssh_password** - 新增 MCP 工具，支持批量修改目标主机 SSH 密码

### Improvements
- **change_ssh_password 本地验证优化**
  - 移除了密码修改后从 MCP 服务器重新连接验证的逻辑
  - 改为在 playbook 执行成功后直接返回结果
  - 减少网络依赖，提高可靠性
  - 移除了旧密码回退测试逻辑
  - 简化了成功/失败处理流程

### Changes
- `lib/mcp_tools/change_ssh_password.py` - 移除 `_verify_connectivity` 函数，简化验证逻辑
- `playbooks/change_ssh_password.yml` - 移除本地验证步骤，依赖 playbook 执行结果判断

---

## v1.13.0

### Previous version
