# Release Notes

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
