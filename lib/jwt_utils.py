"""
JWT 工具模块

提供 JWT 生成、验证、密钥管理、记录管理和权限匹配功能
"""

import json
import secrets
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import jwt

from lib.logger import get_logger

logger = get_logger()

JWT_ALGORITHM = "HS256"
MIN_SECRET_KEY_LENGTH = 32


class JWTUtils:
    """JWT 工具类"""

    def __init__(
        self,
        secret_key_file: Path,
        issued_tokens_file: Path,
        tool_permissions: Dict[str, List[str]],
    ):
        """初始化 JWT 工具

        Args:
            secret_key_file: 密钥文件路径
            issued_tokens_file: 已签发 JWT 记录文件路径
            tool_permissions: 角色权限配置
        """
        self.secret_key_file = secret_key_file
        self.issued_tokens_file = issued_tokens_file
        self.tool_permissions = tool_permissions
        self.secret_key: str = ""
        self.issued_tokens: List[Dict[str, Any]] = []

        self._load_or_generate_secret_key()
        self._load_issued_tokens()

    def _load_or_generate_secret_key(self) -> None:
        """加载或生成密钥"""
        if self.secret_key_file.exists():
            key = self.secret_key_file.read_text().strip()
            if len(key) >= MIN_SECRET_KEY_LENGTH:
                self.secret_key = key
                logger.info(f"从文件加载 JWT 密钥: {self.secret_key_file}")
                return
            else:
                logger.warning(
                    f"密钥长度不足 ({len(key)} < {MIN_SECRET_KEY_LENGTH})，将自动生成新密钥"
                )

        self.secret_key = self._generate_secret_key()
        self.secret_key_file.parent.mkdir(parents=True, exist_ok=True)
        self.secret_key_file.write_text(self.secret_key)
        logger.info(f"自动生成 JWT 密钥并保存到: {self.secret_key_file}")

    def _generate_secret_key(self) -> str:
        """生成符合长度要求的密钥

        Returns:
            生成的密钥
        """
        alphabet = string.ascii_letters + string.digits + "-_"
        key = "".join(secrets.choice(alphabet) for _ in range(48))
        return f"sk-jwt-{key}"

    def _load_issued_tokens(self) -> None:
        """加载已签发的 JWT 记录"""
        if self.issued_tokens_file.exists():
            try:
                content = self.issued_tokens_file.read_text()
                data = json.loads(content)
                self.issued_tokens = data.get("tokens", [])
                logger.info(f"加载了 {len(self.issued_tokens)} 个已签发的 JWT 记录")
            except Exception as e:
                logger.error(f"加载 JWT 记录失败: {e}")
                self.issued_tokens = []
        else:
            self.issued_tokens = []
            self._save_issued_tokens()
            logger.info(f"创建 JWT 记录文件: {self.issued_tokens_file}")

    def _save_issued_tokens(self) -> None:
        """保存已签发的 JWT 记录"""
        self.issued_tokens_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"tokens": self.issued_tokens}
        self.issued_tokens_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )

    def generate_jwt(
        self,
        sub: str,
        name: str,
        role: str,
        expires_in: Optional[int] = None,
        description: Optional[str] = None,
    ) -> str:
        """生成 JWT

        Args:
            sub: 用户唯一标识
            name: 用户名称
            role: 用户角色
            expires_in: 过期时间（秒），None 表示永久有效
            description: JWT 描述

        Returns:
            生成的 JWT 字符串
        """
        now = int(time.time())
        payload: Dict[str, Any] = {
            "sub": sub,
            "name": name,
            "role": role,
            "iat": now,
        }

        if expires_in:
            payload["exp"] = now + expires_in

        token = jwt.encode(payload, self.secret_key, algorithm=JWT_ALGORITHM)

        jwt_id = f"jwt_{sub}_{now}"
        expires_at = None
        if expires_in:
            expires_at = datetime.fromtimestamp(
                now + expires_in, tz=timezone.utc
            ).isoformat()

        record = {
            "jwt_id": jwt_id,
            "sub": sub,
            "name": name,
            "role": role,
            "issued_at": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "expires_at": expires_at,
            "description": description or "",
            "token": token,
        }

        self.issued_tokens.append(record)
        self._save_issued_tokens()

        logger.info(
            f"生成 JWT: sub={sub}, name={name}, role={role}, expires_in={expires_in}, token已保存"
        )
        return token

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT

        Args:
            token: JWT 字符串

        Returns:
            验证成功返回 payload，失败返回 None
        """
        logger.debug(f"开始验证JWT: token长度={len(token)}, token前缀={token[:30]}...")
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[JWT_ALGORITHM])
            logger.debug(
                f"JWT验证成功: sub={payload.get('sub')}, name={payload.get('name')}, role={payload.get('role')}"
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning(f"JWT已过期: token={token[:30]}...")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT验证失败: {e}, token={token[:30]}...")
            return None

    def list_issued_tokens(self) -> List[Dict[str, Any]]:
        """列出所有已签发的 JWT

        Returns:
            JWT 记录列表
        """
        return self.issued_tokens.copy()

    def revoke_jwt(self, jwt_id: str) -> bool:
        """撤销 JWT

        Args:
            jwt_id: JWT ID

        Returns:
            撤销成功返回 True，未找到返回 False
        """
        for i, record in enumerate(self.issued_tokens):
            if record.get("jwt_id") == jwt_id:
                self.issued_tokens.pop(i)
                self._save_issued_tokens()
                logger.info(f"撤销 JWT: {jwt_id}")
                return True
        logger.warning(f"未找到 JWT: {jwt_id}")
        return False

    def check_permission(self, role: str, tool_name: str) -> bool:
        """检查角色是否有权限调用工具

        Args:
            role: 用户角色
            tool_name: 工具名称

        Returns:
            有权限返回 True，无权限返回 False
        """
        logger.debug(f"检查权限: role={role}, tool={tool_name}")

        if role not in self.tool_permissions:
            logger.warning(
                f"未知角色: {role}, 可用角色: {list(self.tool_permissions.keys())}"
            )
            return False

        permissions = self.tool_permissions[role]
        logger.debug(f"角色权限列表: role={role}, permissions={permissions}")

        for pattern in permissions:
            if self._match_permission(pattern, tool_name):
                logger.debug(
                    f"权限匹配成功: role={role}, tool={tool_name}, pattern={pattern}"
                )
                return True

        logger.debug(f"权限匹配失败: role={role}, tool={tool_name}, 无匹配的pattern")
        return False

    def _match_permission(self, pattern: str, tool_name: str) -> bool:
        """匹配权限模式

        Args:
            pattern: 权限模式（支持 * 和前缀匹配）
            tool_name: 工具名称

        Returns:
            匹配成功返回 True
        """
        logger.debug(f"匹配权限模式: pattern={pattern}, tool={tool_name}")

        if pattern == "*":
            logger.debug(f"通配符匹配: pattern={pattern}")
            return True

        if pattern.endswith("*"):
            prefix = pattern[:-1]
            matched = tool_name.startswith(prefix)
            logger.debug(
                f"前缀匹配: pattern={pattern}, prefix={prefix}, matched={matched}"
            )
            return matched

        matched = pattern == tool_name
        logger.debug(
            f"精确匹配: pattern={pattern}, tool={tool_name}, matched={matched}"
        )
        return matched

    def get_user_permissions(self, role: str) -> List[str]:
        """获取角色的权限列表

        Args:
            role: 用户角色

        Returns:
            权限列表
        """
        return self.tool_permissions.get(role, [])

    def regenerate_secret_key(self) -> str:
        """重新生成密钥

        Returns:
            新的密钥
        """
        self.secret_key = self._generate_secret_key()
        self.secret_key_file.write_text(self.secret_key)
        logger.warning("重新生成 JWT 密钥，所有已签发的 JWT 将失效")
        return self.secret_key
