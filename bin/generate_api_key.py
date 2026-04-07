#!/usr/bin/env python3
"""
API Key 生成工具

生成安全的 API Key 用于认证
"""

import secrets
import string
import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
if sys.path and sys.path[0] != project_root:
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)


def generate_api_key(length: int = 32) -> str:
    """
    生成安全的 API Key

    Args:
        length: Key 的长度（默认 32）

    Returns:
        生成的 API Key，格式为 sk-{random_string}
    """
    alphabet = string.ascii_letters + string.digits
    key = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"sk-{key}"


def main():
    print("=" * 60)
    print("TSC Ansible MCP API Key 生成工具")
    print("=" * 60)
    print()

    key = generate_api_key()
    print(f"生成的 API Key: {key}")
    print()
    print("使用说明:")
    print("1. 将此 Key 添加到配置文件 etc/tsc_ansible_mcp.toml")
    print("2. 在 [auth] 部分的 api_keys 列表中添加此 Key")
    print("3. 示例:")
    print()
    print("   [auth]")
    print("   enabled = true")
    print(f'   api_keys = ["{key}"]')
    print("   header_name = \"X-API-Key\"")
    print()
    print("4. 使用 API 时，在请求头中携带此 Key:")
    print(f'   curl -H "X-API-Key: {key}" http://localhost:8500/api/v1/executor/stats')
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
