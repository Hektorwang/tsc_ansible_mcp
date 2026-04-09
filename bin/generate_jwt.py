#!/usr/bin/env python3
"""
JWT 生成和管理工具

提供 JWT 密钥生成、JWT 签发、JWT 验证等功能
"""

import argparse
import re
import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
if sys.path and sys.path[0] != project_root:
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)

from lib.config import Config
from lib.jwt_utils import JWTUtils


def parse_expires(expires_str: str) -> int:
    """解析过期时间字符串

    Args:
        expires_str: 过期时间字符串，如 24h, 7d, 30d

    Returns:
        过期时间（秒）

    Raises:
        ValueError: 格式错误
    """
    match = re.match(r"^(\d+)([hd])$", expires_str.lower())
    if not match:
        raise ValueError(f"无效的过期时间格式: {expires_str}，支持格式: 24h, 7d, 30d")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        return value * 3600
    else:
        return value * 86400


def main():
    parser = argparse.ArgumentParser(
        description="JWT 生成和管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 生成新密钥
  python bin/generate_jwt.py --generate-key

  # 签发 JWT（永久有效）
  python bin/generate_jwt.py --issue --sub user_001 --name "张三" --role admin

  # 签发 JWT（24小时有效期）
  python bin/generate_jwt.py --issue --sub user_001 --name "张三" --role admin --expires 24h

  # 列出已签发的 JWT
  python bin/generate_jwt.py --list

  # 验证 JWT
  python bin/generate_jwt.py --verify <token>

  # 撤销 JWT
  python bin/generate_jwt.py --revoke <jwt_id>
        """,
    )

    parser.add_argument(
        "--generate-key",
        action="store_true",
        help="生成新的 JWT 密钥（会使所有已签发的 JWT 失效）",
    )

    parser.add_argument(
        "--issue",
        action="store_true",
        help="签发 JWT",
    )

    parser.add_argument(
        "--sub",
        type=str,
        help="用户唯一标识",
    )

    parser.add_argument(
        "--name",
        type=str,
        help="用户名称",
    )

    parser.add_argument(
        "--role",
        type=str,
        help="用户角色（admin, user 或自定义角色）",
    )

    parser.add_argument(
        "--expires",
        type=str,
        help="过期时间（如 24h, 7d, 30d），不指定则永久有效",
    )

    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="JWT 描述",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="列出已签发的 JWT",
    )

    parser.add_argument(
        "--verify",
        type=str,
        help="验证 JWT",
    )

    parser.add_argument(
        "--revoke",
        type=str,
        help="撤销 JWT（通过 jwt_id）",
    )

    args = parser.parse_args()

    config = Config()
    secret_key_file = Path(
        config.get("auth.jwt_secret_key_file", "etc/jwt_secret_key.txt")
    )
    if not secret_key_file.is_absolute():
        secret_key_file = Path(project_root) / secret_key_file

    issued_tokens_file = Path(
        config.get("auth.jwt_issued_tokens_file", "etc/jwt_issued_tokens.json")
    )
    if not issued_tokens_file.is_absolute():
        issued_tokens_file = Path(project_root) / issued_tokens_file

    tool_permissions = config.get("auth.tool_permissions", {})
    if not tool_permissions:
        tool_permissions = {
            "admin": ["*"],
            "user": [
                "list_playbooks",
                "ansible_playbook",
                "get_task_status",
                "playbook_*",
            ],
        }

    jwt_utils = JWTUtils(
        secret_key_file=secret_key_file,
        issued_tokens_file=issued_tokens_file,
        tool_permissions=tool_permissions,
    )

    if args.generate_key:
        print("=" * 60)
        print("生成新的 JWT 密钥")
        print("=" * 60)
        print()

        new_key = jwt_utils.regenerate_secret_key()
        print(f"新密钥: {new_key}")
        print()
        print("警告: 所有已签发的 JWT 将失效，需要重新签发")
        print()

    elif args.issue:
        if not args.sub or not args.name or not args.role:
            print("错误: 签发 JWT 需要指定 --sub, --name 和 --role")
            sys.exit(1)

        print("=" * 60)
        print("签发 JWT")
        print("=" * 60)
        print()

        expires_in = None
        if args.expires:
            try:
                expires_in = parse_expires(args.expires)
            except ValueError as e:
                print(f"错误: {e}")
                sys.exit(1)

        token = jwt_utils.generate_jwt(
            sub=args.sub,
            name=args.name,
            role=args.role,
            expires_in=expires_in,
            description=args.description,
        )

        print(f"JWT Token: {token}")
        print()
        print(f"用户标识: {args.sub}")
        print(f"用户名称: {args.name}")
        print(f"用户角色: {args.role}")
        if expires_in:
            print(f"有效期: {args.expires} ({expires_in} 秒)")
        else:
            print("有效期: 永久有效")
        print()
        print("使用方式:")
        print(
            f'  curl -H "Authorization: Bearer {token}" http://localhost:8500/api/v1/executor/stats'
        )
        print()

    elif args.list:
        print("=" * 60)
        print("已签发的 JWT 列表")
        print("=" * 60)
        print()

        tokens = jwt_utils.list_issued_tokens()
        if not tokens:
            print("暂无已签发的 JWT")
        else:
            for i, record in enumerate(tokens, 1):
                print(f"{i}. JWT ID: {record.get('jwt_id')}")
                print(f"   用户标识: {record.get('sub')}")
                print(f"   用户名称: {record.get('name')}")
                print(f"   用户角色: {record.get('role')}")
                print(f"   签发时间: {record.get('issued_at')}")
                print(f"   过期时间: {record.get('expires_at') or '永久有效'}")
                print(f"   描述: {record.get('description') or '无'}")
                print()

    elif args.verify:
        print("=" * 60)
        print("验证 JWT")
        print("=" * 60)
        print()

        payload = jwt_utils.verify_jwt(args.verify)
        if payload:
            print("JWT 验证成功")
            print()
            print(f"用户标识: {payload.get('sub')}")
            print(f"用户名称: {payload.get('name')}")
            print(f"用户角色: {payload.get('role')}")
            print(f"签发时间: {payload.get('iat')}")
            if payload.get("exp"):
                print(f"过期时间: {payload.get('exp')}")
            else:
                print("过期时间: 永久有效")
            print()
            print(
                f"角色权限: {jwt_utils.get_user_permissions(payload.get('role', 'user'))}"
            )
            print()
        else:
            print("JWT 验证失败: Token 无效或已过期")
            sys.exit(1)

    elif args.revoke:
        print("=" * 60)
        print("撤销 JWT")
        print("=" * 60)
        print()

        success = jwt_utils.revoke_jwt(args.revoke)
        if success:
            print(f"JWT {args.revoke} 已撤销")
            print()
            print("注意: 需要重启服务才能生效")
            print()
        else:
            print(f"未找到 JWT: {args.revoke}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
