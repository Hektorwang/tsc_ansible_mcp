# Inventory 管理逻辑说明

## 📋 概述

本系统实现了智能的 inventory 管理机制，确保主机凭据的可靠性和 fallback 能力。

## 🔄 工作流程

### 1. LLM 提供凭据时的验证流程

```
LLM 提供凭据
    ↓
使用新凭据测试连接
    ↓
    ├─ 连接成功 → 更新主 inventory → 使用新凭据
    │
    └─ 连接失败 → 尝试使用缓存凭据
                     ↓
                     ├─ 缓存凭据成功 → 使用缓存凭据（不更新 inventory）
                     │
                     └─ 缓存凭据失败 → 连接失败
```

### 2. 无 LLM 凭据时的流程

```
无新凭据
    ↓
使用缓存 inventory 信息
    ↓
    ├─ 有缓存 → 使用缓存凭据
    │
    └─ 无缓存 → 连接失败
```

## 🎯 核心方法

### `_test_connectivity(targets, inventory, timeout)`

测试主机连接性。

**参数：**
- `targets`: 目标主机列表
- `inventory`: Ansible inventory
- `timeout`: 超时时间

**返回：**
- 字典 `{host: bool}`，表示每台主机的连接状态

**示例：**
```python
connectivity = self._test_connectivity(
    targets=["192.168.1.10", "192.168.1.11"],
    inventory=inventory,
    timeout=30
)
# 返回: {"192.168.1.10": True, "192.168.1.11": False}
```

### `_build_inventory(targets, credentials, use_cached)`

构建 Ansible inventory。

**参数：**
- `targets`: 目标主机列表
- `credentials`: LLM 提供的凭据信息
- `use_cached`: 是否强制使用缓存的 inventory（用于 fallback）

**返回：**
- Ansible inventory 字典

**使用场景：**
```python
# 使用 LLM 提供的新凭据
inventory = self._build_inventory(targets, credentials, use_cached=False)

# 使用缓存的凭据（fallback）
inventory = self._build_inventory(targets, None, use_cached=True)
```

### `update_host_credentials(host, user, port, password, private_key)`

更新主机凭据信息（仅在验证成功后调用）。

**参数：**
- `host`: 主机地址
- `user`: SSH 用户名
- `port`: SSH 端口
- `password`: SSH 密码
- `private_key`: SSH 私钥路径

**注意：**
- 此方法仅在连接验证成功后调用
- 会持久化保存到 `etc/inventory.yml`

## 📊 使用示例

### 场景 1：LLM 提供正确凭据

```python
# LLM 调用
check_host_status(
    targets=["192.168.1.10"],
    user="root",
    password="correct_password"
)

# 执行流程：
# 1. 使用新凭据测试连接 → 成功
# 2. 更新 inventory
# 3. 使用新凭据执行后续操作
```

### 场景 2：LLM 提供错误凭据，但缓存凭据可用

```python
# 第一次调用（成功）
check_host_status(
    targets=["192.168.1.10"],
    user="root",
    password="correct_password"
)
# inventory 已保存: {"192.168.1.10": {"user": "root", "password": "correct_password"}}

# 第二次调用（错误凭据）
check_host_status(
    targets=["192.168.1.10"],
    user="root",
    password="wrong_password"
)

# 执行流程：
# 1. 使用新凭据测试连接 → 失败
# 2. 尝试使用缓存凭据 → 成功
# 3. 使用缓存凭据执行后续操作（不更新 inventory）
```

### 场景 3：无缓存且凭据错误

```python
# 首次调用（错误凭据）
check_host_status(
    targets=["192.168.1.10"],
    user="root",
    password="wrong_password"
)

# 执行流程：
# 1. 使用新凭据测试连接 → 失败
# 2. 尝试使用缓存凭据 → 无缓存
# 3. 连接失败，返回错误信息
```

## 🔒 安全性考虑

### 1. 凭据验证

- ✅ 所有凭据在更新 inventory 前都会验证
- ✅ 验证失败不会覆盖已有凭据
- ✅ 支持密码和私钥两种认证方式

### 2. Fallback 机制

- ✅ 自动 fallback 到缓存凭据
- ✅ 避免因凭据错误导致服务中断
- ✅ 提供详细的日志记录

### 3. 持久化存储

- ✅ 凭据保存在 `etc/inventory.yml`
- ✅ 支持版本控制和审计
- ✅ 支持团队共享

## 📝 日志说明

### 连接测试日志

```
INFO  使用 LLM 提供的凭据测试连接...
INFO  测试主机连接性: ['192.168.1.10', '192.168.1.11']
INFO  主机 192.168.1.10 连接测试成功
WARNING  主机 192.168.1.11 连接测试失败
WARNING  LLM 凭据连接失败的主机: ['192.168.1.11']
INFO  主机 192.168.1.11 使用缓存凭据连接成功，将使用缓存信息
INFO  主机 192.168.1.10 验证成功，已更新 inventory
```

### Inventory 构建日志

```
DEBUG  使用 LLM 提供的凭据: 192.168.1.10
DEBUG  使用缓存的 inventory 信息: 192.168.1.11
DEBUG  最终使用的 inventory: {...}
```

## 🛠️ 故障排查

### 问题 1：连接总是失败

**可能原因：**
1. 网络不通
2. SSH 服务未启动
3. 防火墙阻止

**解决方法：**
```bash
# 检查网络连通性
ping 192.168.1.10

# 检查 SSH 服务
ssh root@192.168.1.10

# 检查防火墙
telnet 192.168.1.10 22
```

### 问题 2：凭据验证成功但操作失败

**可能原因：**
1. 权限不足
2. Python 未安装
3. 目标路径不存在

**解决方法：**
```bash
# 检查权限
ssh root@192.168.1.10 "whoami"

# 检查 Python
ssh root@192.168.1.10 "python3 --version"

# 检查路径
ssh root@192.168.1.10 "ls -la /opt/tsc/"
```

### 问题 3：缓存凭据失效

**可能原因：**
1. 密码已更改
2. 私钥已删除
3. 用户权限变更

**解决方法：**
```bash
# 删除缓存凭据
rm etc/inventory.yml

# 重新提供正确凭据
check_host_status(targets=["192.168.1.10"], user="root", password="new_password")
```

## 📚 相关文件

- `lib/executor.py` - 核心执行逻辑
- `lib/inventory_manager.py` - Inventory 管理类
- `etc/inventory.yml` - Inventory 持久化文件

## 🎯 最佳实践

1. **首次使用时提供正确凭据**
   ```python
   check_host_status(
       targets=["192.168.1.10"],
       user="root",
       password="correct_password"
   )
   ```

2. **定期更新凭据**
   ```python
   # 当密码变更时，重新验证
   check_host_status(
       targets=["192.168.1.10"],
       user="root",
       password="new_password"
   )
   ```

3. **监控连接状态**
   ```python
   result = check_host_status(targets=["192.168.1.10"])
   if result["status"] == "failed":
       # 处理连接失败
       pass
   ```

4. **使用日志排查问题**
   ```bash
   # 查看详细日志
   tail -f logs/tsc_ansible_mcp.log | grep -E "(连接|凭据|inventory)"
   ```

## 🔄 版本历史

- **v1.0.0** - 初始版本，支持基本的 inventory 管理
- **v1.1.0** - 添加智能验证和 fallback 机制
- **v1.2.0** - 优化日志输出和错误处理

## 📞 支持

如有问题，请查看日志文件或联系开发团队。
