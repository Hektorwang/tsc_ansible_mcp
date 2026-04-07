# Python 检测逻辑修复总结

## 问题描述

用户在 192.168.19.104 上安装 tsc_python 时，该机器已有系统自带的 Python 3.9.9，LLM 不同意安装 tsc_python。

## 根本原因

1. **字段混淆**: `python_installed` 字段表示"是否有任何 Python"（包括系统 Python 和 tsc_python）
2. **逻辑错误**: `install_python` 检查 `python_installed` 来决定是否跳过安装
3. **语义不清**: 工具描述没有明确说明 `install_python` 安装的是 tsc_python，而不是系统 Python

## 修复内容

### 1. 添加 `tsc_python_installed` 字段

**文件**: `lib/executor.py`

```python
# check_host_status 返回结果中添加
results[host] = {
    "arch": "",
    "arch_raw": "",
    "distro": "",
    "distro_raw": "",
    "python_installed": False,        # 是否有任何 Python
    "python_version": "",
    "python_path": "",
    "tsc_python_installed": False,    # 是否已安装 tsc_python
    "tsc_tools_installed": False,
}
```

**检测逻辑**:
```python
# 区分系统 Python 和 tsc_python
tsc_python_path = f"{install_path}/micromamba/envs/tsc_python/bin/python3"
results[host]["tsc_python_installed"] = (python_path == tsc_python_path)
```

### 2. 修改 `install_python` 跳过逻辑

**文件**: `lib/executor.py`

```python
# 之前: 检查 python_installed
elif env_info.get("python_installed"):
    results[host] = {
        "installed": False,
        "skipped": True,
        "message": "Python 已安装",
    }

# 现在: 检查 tsc_python_installed
elif env_info.get("tsc_python_installed"):
    results[host] = {
        "installed": False,
        "skipped": True,
        "message": "tsc_python 已安装",
        "python_version": env_info.get("python_version", ""),
        "python_path": env_info.get("python_path", ""),
    }
```

### 3. 更新工具描述

**文件**: `lib/server.py`

#### check_host_status 描述

```python
description="""检查目标主机的状态，包括架构、发行版、Python 安装状态、tsc_python 安装状态、tsc_tools 安装状态等。

返回字段说明：
- python_installed: 是否有任何 Python（系统 Python 或 tsc_python）
- tsc_python_installed: 是否已安装 tsc_python（独立环境）
- python_path: Python 路径（可能是系统 Python 或 tsc_python）
- python_version: Python 版本
- tsc_tools_installed: 是否已安装 tsc_tools
"""
```

#### install_python 描述

```python
description="""在目标主机上安装 tsc_python 环境（独立的 Python 环境）。

重要说明：
- 此工具安装的是 tsc_python，不是系统 Python
- 即使目标主机已有系统 Python，也可以安装 tsc_python
- tsc_python 是独立的 Python 环境，不会影响系统 Python
- 安装前必须先安装 tsc_tools！

安装条件：
- 如果 tsc_python 已安装 → 跳过安装
- 如果 tsc_python 未安装 → 执行安装（无论是否有系统 Python）
"""
```

## 修复效果

### 场景 1: 主机有系统 Python，但没有 tsc_python

**check_host_status 返回**:
- `python_installed`: True
- `tsc_python_installed`: False
- `python_path`: /usr/bin/python3

**install_python 行为**:
- ✅ 会安装 tsc_python（因为 `tsc_python_installed=False`）

### 场景 2: 主机已安装 tsc_python

**check_host_status 返回**:
- `python_installed`: True
- `tsc_python_installed`: True
- `python_path`: /home/tsc/tsc_tools/micromamba/envs/tsc_python/bin/python3

**install_python 行为**:
- ⏭️ 跳过安装（因为 `tsc_python_installed=True`）

### 场景 3: 主机没有任何 Python

**check_host_status 返回**:
- `python_installed`: False
- `tsc_python_installed`: False
- `python_path`: ''

**install_python 行为**:
- ✅ 会安装 tsc_python（因为 `tsc_python_installed=False`）

## LLM 使用建议

### 用户需求: "我需要一个 Python 环境"
- 检查 `python_installed`
- 如果 False，安装 tsc_python

### 用户需求: "我要安装 tsc_python"
- 检查 `tsc_python_installed`
- 如果 False，安装 tsc_python

### 用户需求: "这台机器有 Python 3.9.9，但我想安装 tsc_python"
- 检查 `tsc_python_installed`
- 如果 False，安装 tsc_python（不受系统 Python 影响）

## 测试验证

运行测试脚本:
```bash
python test_fix_verification.py
```

## 相关文件

- `lib/executor.py`: 核心逻辑修改
- `lib/server.py`: 工具描述更新
- `test_fix_verification.py`: 修复验证脚本
