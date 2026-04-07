# Bearer Token 认证使用指南

## 1. 概述

TSC Ansible MCP 服务现在支持标准的 HTTP Bearer Token 认证，保护所有 API 端点和 MCP 端点。

## 2. 启用/禁用认证

### 2.1 配置文件

编辑 `etc/tsc_ansible_mcp.toml`：

```toml
[auth]
enabled = true  # true 启用认证，false 禁用认证
api_keys = ["sk-tsc-ansible-mcp-2026"]
whitelist_ips = ["127.0.0.1", "192.168.19.0/24"]
```

### 2.2 认证开关

- `enabled = true`：启用认证，所有请求需要 Bearer Token
- `enabled = false`：禁用认证，所有请求无需 Token

## 3. 生成 Token

### 3.1 使用生成工具

```bash
# 使用 venv 环境
venv/bin/python bin/generate_api_key.py
```

输出示例：
```
============================================================
TSC Ansible MCP API Key 生成工具
============================================================

生成的 API Key: sk-PUZFOUwjAMIg9X59A5na89lEFscKNx0n

使用说明:
1. 将此 Key 添加到配置文件 etc/tsc_ansible_mcp.toml
2. 在 [auth] 部分的 api_keys 列表中添加此 Key
...
```

### 3.2 手动生成

也可以使用 Python 生成：

```python
import secrets
import string

def generate_token(length=32):
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(length))
    return f"sk-{token}"

print(generate_token())
```

## 4. REST API 使用

### 4.1 请求示例

```bash
# 健康检查（无需认证）
curl http://localhost:8500/health

# 查询任务统计（需要认证）
curl -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  http://localhost:8500/api/v1/executor/stats

# 执行 Shell 命令（需要认证）
curl -X POST http://localhost:8500/api/v1/shell \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-tsc-ansible-mcp-2026" \
  -d '{
    "targets": ["192.168.1.100"],
    "command": "ls -la"
  }'
```

### 4.2 认证失败响应

```json
{
  "status": "error",
  "message": "Bearer Token required. Please provide Authorization: Bearer <token> header."
}
```

或

```json
{
  "status": "error",
  "message": "Invalid Bearer Token"
}
```

## 5. MCP 客户端使用

### 5.1 MCP 客户端配置

MCP 客户端需要通过 HTTP 连接时，必须在请求头中携带 Bearer Token。

#### Claude Desktop 配置

编辑 Claude Desktop 配置文件：

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

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

#### 其他 MCP 客户端

如果 MCP 客户端支持自定义请求头，添加：

```
Authorization: Bearer sk-tsc-ansible-mcp-2026
```

### 5.2 MCP 工具调用示例

MCP 工具调用时，客户端会自动携带认证信息：

```python
# MCP 客户端会自动添加认证头
ansible_shell(
    targets=["192.168.1.100"],
    command="ls -la"
)
```

## 6. IP 白名单（可选）

### 6.1 配置 IP 白名单

```toml
[auth]
enabled = true
api_keys = ["sk-tsc-ansible-mcp-2026"]
whitelist_ips = [
    "127.0.0.1",           # 本地
    "192.168.19.0/24",     # 内网网段
    "10.0.0.100"           # 特定 IP
]
```

### 6.2 白名单规则

- 支持 CIDR 格式（如 `192.168.19.0/24`）
- 支持单个 IP（如 `127.0.0.1`）
- 如果不配置白名单，则不检查 IP
- 白名单 + API Key 双重验证

## 7. 安全建议

### 7.1 API Key 管理

1. **定期轮换**：建议每季度更换一次 API Key
2. **多 Key 支持**：可配置多个 Key，便于轮换
3. **权限分离**：不同用途使用不同的 Key
4. **安全存储**：不要将 Key 提交到版本控制

### 7.2 网络安全

1. **限制监听**：不要监听 `0.0.0.0`，使用内网 IP
2. **防火墙**：使用防火墙限制访问
3. **HTTPS**：生产环境建议使用 HTTPS

### 7.3 配置示例

```toml
[mcp]
host = "192.168.19.22"  # 使用内网 IP，而不是 0.0.0.0
port = 8500

[auth]
enabled = true
api_keys = [
    "sk-tsc-ansible-mcp-2026-production",  # 生产环境
    "sk-tsc-ansible-mcp-2026-dev"          # 开发环境
]
header_name = "X-API-Key"
whitelist_ips = [
    "127.0.0.1",
    "192.168.19.0/24"
]
```

## 8. 故障排查

### 8.1 认证失败

**问题**：返回 401 错误

**检查**：
1. 确认 API Key 是否正确
2. 确认请求头名称是否为 `X-API-Key`
3. 检查配置文件中的 `api_keys` 列表

### 8.2 IP 白名单失败

**问题**：返回 403 错误

**检查**：
1. 确认客户端 IP 是否在白名单中
2. 检查白名单配置格式是否正确
3. 查看日志中的 IP 地址

### 8.3 查看日志

```bash
# 查看服务日志
tail -f logs/server.log

# 查看认证日志
grep "认证" logs/tsc_ansible_mcp.log
```

## 9. 测试认证

### 9.1 测试脚本

```bash
#!/bin/bash

API_KEY="sk-tsc-ansible-mcp-2026"
BASE_URL="http://localhost:8500"

echo "测试 1: 无 API Key（应返回 401）"
curl -s "$BASE_URL/api/v1/executor/stats"
echo -e "\n"

echo "测试 2: 错误的 API Key（应返回 401）"
curl -s -H "X-API-Key: wrong-key" "$BASE_URL/api/v1/executor/stats"
echo -e "\n"

echo "测试 3: 正确的 API Key（应返回 200）"
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/executor/stats"
echo -e "\n"

echo "测试 4: 健康检查（无需认证）"
curl -s "$BASE_URL/health"
echo -e "\n"
```

### 9.2 运行测试

```bash
# 启动服务
./run.sh start

# 运行测试
bash test_auth.sh
```

## 10. 常见问题

### Q1: MCP 客户端如何传递 API Key？

**A**: MCP 客户端通过 HTTP 请求头传递 API Key。在客户端配置中添加 `headers` 字段。

### Q2: 可以禁用认证吗？

**A**: 可以。在配置文件中设置 `auth.enabled = false` 即可禁用认证。

### Q3: 如何支持多个 API Key？

**A**: 在配置文件的 `api_keys` 列表中添加多个 Key：

```toml
api_keys = ["sk-key1", "sk-key2", "sk-key3"]
```

### Q4: API Key 可以随时更换吗？

**A**: 可以。修改配置文件后重启服务即可生效。建议保留旧 Key 一段时间，便于平滑过渡。

### Q5: 如何查看当前有效的 API Key？

**A**: 查看配置文件 `etc/tsc_ansible_mcp.toml` 中的 `auth.api_keys` 列表。

## 11. 相关文档

- [API 参考文档](./API-REFERENCE.md)
- [架构设计文档](./ARCHITECTURE.md)
- [技术规格说明](./SPEC.md)
