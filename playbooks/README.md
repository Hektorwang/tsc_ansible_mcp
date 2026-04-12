# Playbook 元数据规范

## 🎯 推荐格式：JSON 注释（LLM 最友好）

使用注释掉的 JSON 格式，让 LLM 更容易理解和使用。

## 📚 当前可用的 Playbook

### collect_iaas_info.yml - IaaS 基础设施信息采集

采集 IaaS 层基础设施信息，包括处理器、内存、存储（RAID）、操作系统、包管理器等详细信息。

**功能特性：**

- ✅ 处理器信息（型号、核心数、架构）
- ✅ 内存信息（容量、类型、使用率）
- ✅ 存储信息（磁盘、RAID 配置）
- ✅ 操作系统信息（发行版、内核版本）
- ✅ 包管理器信息
- ✅ 可选的实时资源使用状态采集

**使用示例：**

```python
# 基础信息采集
ansible_playbook(
    playbook="collect_iaas_info.yml",
    targets=["192.168.1.10"],
    user="root",
    password="your_password"
)

# 包含实时资源使用状态
ansible_playbook(
    playbook="collect_iaas_info.yml",
    targets=["192.168.1.10", "192.168.1.11"],
    extravars={"runtime": true},
    user="root",
    password="your_password"
)
```

**参数说明：**

- `runtime` (bool): 是否采集当前硬件资源使用状态，默认 false

**注意事项：**

- 需要目标主机已安装 tsc_tools
- 命令执行路径：`source /home/tsc/tsc_profile; tsc --tsc_iaas_info [--runtime]`

---

## 📋 JSON 元数据字段说明

### 必需字段

| 字段          | 类型   | 说明              |
| ------------- | ------ | ----------------- |
| `description` | string | Playbook 功能描述 |
| `author`      | string | 作者              |
| `version`     | string | 版本号            |
| `tags`        | array  | 标签列表          |

### 推荐字段

| 字段         | 类型   | 说明     |
| ------------ | ------ | -------- |
| `parameters` | array  | 参数列表 |
| `use_cases`  | array  | 使用场景 |
| `example`    | object | 调用示例 |
| `notes`      | array  | 注意事项 |

### 参数对象字段

```json
{
  "name": "runtime", // 参数名（必需）
  "type": "bool", // 类型：int, str, bool, list, dict
  "default": false, // 默认值
  "description": "Collect runtime resource usage" // 描述（必需）
}
```

### 示例对象字段

```json
{
  "playbook": "collect_iaas_info.yml", // playbook 文件名
  "targets": ["192.168.1.10"], // 目标主机列表
  "extravars": {
    // 额外变量（可选）
    "runtime": true
  },
  "user": "root", // SSH 用户
  "password": "your_password" // SSH 密码
}
```

## 🎓 为什么选择 JSON 注释格式？

### 1. LLM 原生支持

- JSON 是 LLM 最熟悉的数据格式
- 不需要学习自定义格式
- 解析准确率高

### 2. 完整的调用示例

```json
"example": {
  "playbook": "collect_iaas_info.yml",
  "targets": ["192.168.1.10"],
  "extravars": {"runtime": true}
}
```

LLM 可以直接复制使用！

### 3. 丰富的类型信息

- `type`: 明确参数类型
- `default`: 显示默认值
- `description`: 详细说明

### 4. 保持单文件

- ✅ 元数据和代码在一起
- ✅ 不需要额外的 .meta.json 文件
- ✅ 通过 ansible-lint 验证

## 📝 最佳实践

### 1. 提供完整的调用示例

❌ 不好：

```json
"example": {
  "playbook": "collect_iaas_info.yml"
}
```

✅ 好：

```json
"example": {
  "playbook": "collect_iaas_info.yml",
  "targets": ["192.168.1.10"],
  "extravars": {"runtime": true},
  "user": "root",
  "password": "your_password"
}
```

### 2. 明确参数类型

❌ 不好：

```json
{
  "name": "runtime",
  "description": "Collect runtime info"
}
```

✅ 好：

```json
{
  "name": "runtime",
  "type": "bool",
  "default": false,
  "description": "Collect current hardware resource usage status"
}
```

### 3. 列出使用场景

```json
"use_cases": [
  "Collect infrastructure hardware information",
  "Check CPU, memory, and storage details",
  "Get RAID configuration information",
  "View OS and package manager details",
  "Monitor current resource usage (with --runtime)"
]
```

这能帮助 LLM 判断何时使用这个 Playbook。

### 4. 添加注意事项

```json
"notes": [
  "Requires tsc_tools to be installed on target hosts",
  "Source profile: /home/tsc/tsc_profile",
  "Command: tsc --tsc_iaas_info [--runtime]"
]
```

## 🛠️ 工具支持

### ansible-lint 验证

```bash
ansible-lint playbooks/collect_iaas_info.yml
```

### REST API 查询

```bash
curl http://localhost:8500/api/v1/playbooks | jq
```

### MCP 工具调用

```python
list_playbooks()  # 查看所有 playbook 及其元数据
```

## 🎯 总结

**推荐使用 JSON 注释格式**，因为：

1. ✅ LLM 最友好
2. ✅ 可以提供完整调用示例
3. ✅ 类型信息丰富
4. ✅ 保持单文件
5. ✅ 通过 ansible-lint 验证
6. ✅ 易于解析和维护

这种格式让你的 Playbook 更容易被 LLM 理解和使用！
