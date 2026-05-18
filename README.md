# tsc_ansible_mcp

## 说明

将 Ansible 的 shell、copy、fetch、playbook 功能 MCP 化, 通过 LLM 客户端对受控主机执行远程操作.

## 安装条件

1. MCP 主机需持有受控主机的 SSH 信任私钥文件(如 `id_rsa`).
2. MCP 主机的 8500 端口未被占用.
3. 运行环境需使用 tsc_python(`source /home/tsc/tsc_profile`).

## 安装

将安装包解压到 `/home/tsc/tsc_ansible_mcp/`, 并进入该目录.

注意必须遵循 Ansible 的 YAML 配置格式.

### 1. 配置主配置文件

编辑 `etc/tsc_ansible_mcp.toml`, 一般仅需将 `mcp.host` 改为本机 IP：

```toml
[mcp]
host = "192.168.3.252"  # 改为本机 IP
port = 8500
```

### 2. 编辑受控主机配置文件

参考 `etc/inventory.yml.sample` 编辑 `etc/inventory.yml`, 在做好 SSH 信任的情况下一般仅需配置 `ansible_port`：

```yaml
all:
  hosts:
    192.168.19.106:
      ansible_host: 192.168.19.106
      ansible_user: root
      ansible_port: 22
```

### 3. 导入受控主机配置到数据库

```bash
source /home/tsc/tsc_ansible_mcp/.venv/bin/activate
python3 bin/inventory.py import
```

后续若要增加主机或调整配置, 修改 `etc/inventory.yml` 后重新运行以上命令.

### 4. 将 tsc_tools 和 tsc_python 安装包放到 `tsc_install` 目录下, 本次已经带上这些文件

## 运行

```bash
source /home/tsc/tsc_ansible_mcp/.venv/bin/activate
python3 bin/server.py & disown
```

服务启动后：

- MCP 端点：`http://本机IP:8500/mcp`
- REST API 文档：`http://本机IP:8500/docs`

## MCP 客户端配置

在 CherryStudio、Dify 等 MCP 客户端中配置：

- **URL**: `http://MCP服务器IP:8500/mcp`
- **类型**: `streamableHttp`

## MCP 工具介绍

1. **`ansible_shell`** — 在受控主机上执行指定命令. 命令黑名单中的高危命令不可执行.
   调度样例：`在 192.168.19.106 上执行 ls /tmp`

2. **`ansible_copy`** — 将 MCP 主机的文件分发到受控主机.
   调度样例：`把本机 /home/tsc/tsc_ansible_mcp/files/config.yml 拷贝到 192.168.19.106 的 /etc/myapp/ 下`

3. **`ansible_fetch`** — 将受控主机的文件采集到 MCP 主机.
   调度样例：`把 192.168.19.106 的 /tmp/result.log 拷贝到本机 /home/tsc/tsc_ansible_mcp/files/ 下`

4. **`check_host_status`** — 检查受控主机的架构、发行版、Python 和 tsc_tools 安装状态.

5. **`playbook_bootstrap_tsc_environment`** — 在受控主机上安装 tsc_tools 和 tsc_python.

6. **`change_ssh_port`** — 修改受控主机的 SSH 服务端口(允许范围：22 或 1024-65535), 失败自动回滚.
   调度样例：`修改 192.168.19.106 的 SSH 端口为 12345`

7. **`change_ssh_password`** — 修改受控主机的 root 用户密码(**8 位以上, 含数字、字母、特殊字符**).
   调度样例：`修改 192.168.19.106 的 SSH 密码为 !@#QWE123`

8. **`get_result`** — 查询异步任务结果(任务超过 55 秒时会返回 running 状态, 需轮询此工具).

9. **`playbook_*`** — 动态生成的 playbook 工具, 服务启动时自动扫描 `playbooks/` 目录生成.

## 维护

### 受控主机管理

```bash
# 验证 inventory.yml 配置是否正确
ansible -i etc/inventory.yml all -m ping

# 导入 inventory.yml 到数据库
python3 bin/inventory.py import

# 查看数据库中的受控主机信息
python3 bin/inventory.py list

# 移除指定主机
python3 bin/inventory.py remove --host 192.168.19.106

# 更新指定主机配置
python3 bin/inventory.py update --host 192.168.19.106 --port 32321
```

### 高危命令黑名单

修改 `etc/tsc_ansible_mcp.toml` 中 `[ansible]` 节：

```toml
[ansible]
high_risk_commands = ["rm", "unlink", "halt", "shutdown", "mkfs", "parted", "reboot", "poweroff", "init", "dd", "format", "wipefs", "eval", "drop"]
```

### 安全控制

本工具可在受控主机上执行命令、采集和分发文件, 建议使用 iptables 限制可连入本服务的客户端 IP. **防火墙或下方的用户认证鉴权机制, 建议至少启用一个.**

```bash
# 在 MCP 主机上执行, 顺序不可颠倒
iptables -t filter -I INPUT -p tcp --dport 8500 -j DROP
iptables -t filter -I INPUT -s 可信任的客户端IP -p tcp --dport 8500 -j ACCEPT
```

### 用户认证鉴权

本工具支持 JWT 用户权限管理, 可控制不同用户允许调用的 MCP 工具范围.

**生成密钥和签发 Token：**

```bash
# 生成密钥
python3 bin/generate_jwt.py --generate-key

# 签发永久有效的 token
python3 bin/generate_jwt.py --issue --sub admin --name "管理员" --role admin

# 签发 24 小时有效的 token
python3 bin/generate_jwt.py --issue --sub user --name "测试用户" --role user --expires 24h

# 列出已签发的 token
python3 bin/generate_jwt.py --list
```

签发后记录 token 字符串, 在 MCP 客户端请求头中配置：`Authorization=Bearer 用户的token`

**吊销 token：** 删除 `etc/jwt_issued_tokens.json` 中对应条目后重启服务.

**启用认证并配置权限：**

修改 `etc/tsc_ansible_mcp.toml`：

```toml
[auth]
enabled = true  # 改为 true 启用认证

[auth.tool_permissions]
# admin 用户允许使用所有工具
admin = ["*"]
# user 用户仅允许使用以下工具(无法使用 ansible_shell、ansible_copy、ansible_fetch)
# playbook_bootstrap_tsc_environment, get_result, get_host_detail, check_host_status 为必选基础工具, 所有 playbook 工具均依赖它们
user = ["playbook_bootstrap_tsc_environment", "get_result", "check_host_status", "playbook_*"]
```

修改后重启服务生效.

## 相关文档

- [架构设计](docs/ARCHITECTURE.md)
- [API 参考](docs/API-REFERENCE.md)
- [产品需求](docs/PRD.md)
- [技术规格](docs/SPEC.md)
- [版本历史](release-note.md)
