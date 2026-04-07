"""
认证中间件模块

提供 Bearer Token 认证和 IP 白名单功能
"""

import ipaddress
from pathlib import Path
from typing import List, Optional, Union

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.config import Config
from lib.logger import get_logger

logger = get_logger()


class AuthMiddleware:
    """认证中间件类，支持 Bearer Token 认证"""

    def __init__(self, config: Config):
        self.config = config
        self.enabled = config.get("auth.enabled", False)
        self.tokens_file = self._get_tokens_file_path(config)
        self.api_keys = self._load_tokens()
        self.whitelist_ips = self._parse_whitelist(config.get("auth.whitelist_ips", []))
        self.security = HTTPBearer(auto_error=False)
        logger.info(
            f"认证中间件初始化: enabled={self.enabled}, tokens_file={self.tokens_file}, api_keys_count={len(self.api_keys)}"
        )

    def _get_tokens_file_path(self, config: Config) -> Path:
        """获取 tokens 文件路径"""
        tokens_file = config.get("auth.tokens_file", "etc/tokens.txt")
        if Path(tokens_file).is_absolute():
            return Path(tokens_file)
        else:
            base_dir = config.path.parent.parent
            return base_dir / tokens_file

    def _load_tokens(self) -> List[str]:
        """从文件加载 tokens"""
        if not self.tokens_file.exists():
            logger.warning(f"Tokens 文件不存在: {self.tokens_file}")
            return []

        tokens = []
        try:
            with open(self.tokens_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        tokens.append(line)
            logger.info(f"从 {self.tokens_file} 加载了 {len(tokens)} 个 token")
        except Exception as e:
            logger.error(f"加载 tokens 文件失败: {e}")
            return []

        return tokens

    def _parse_whitelist(
        self, ip_list: List[str]
    ) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """解析 IP 白名单配置"""
        networks = []
        for ip in ip_list:
            try:
                if "/" in ip:
                    networks.append(ipaddress.ip_network(ip, strict=False))
                else:
                    networks.append(ipaddress.ip_network(f"{ip}/32"))
                logger.debug(f"IP 白名单添加: {ip}")
            except ValueError as e:
                logger.warning(f"无效的 IP 白名单配置: {ip}, 错误: {e}")
        return networks

    def is_ip_allowed(self, client_ip: str) -> bool:
        """检查客户端 IP 是否在白名单中"""
        if not self.whitelist_ips:
            return True

        try:
            ip_addr = ipaddress.ip_address(client_ip)
            allowed = any(ip_addr in network for network in self.whitelist_ips)
            if not allowed:
                logger.warning(f"IP {client_ip} 不在白名单中")
            return allowed
        except ValueError as e:
            logger.warning(f"无效的客户端 IP: {client_ip}, 错误: {e}")
            return False

    async def verify_api_key(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> str:
        """验证 Bearer Token（使用 FastAPI HTTPBearer）"""
        if not self.enabled:
            logger.debug("认证未启用，跳过验证")
            return "auth_disabled"

        token = credentials.credentials

        if token not in self.api_keys:
            logger.warning(f"无效的 Bearer Token: {token[:8]}...")
            raise HTTPException(
                status_code=401,
                detail="Invalid Bearer Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"Bearer Token 验证成功: {token[:8]}...")
        return token

    async def verify_request(self, request: Request) -> str:
        """验证请求（IP 白名单 + Bearer Token）"""
        if not self.enabled:
            return "auth_disabled"

        client_ip = self._get_client_ip(request)

        if not self.is_ip_allowed(client_ip):
            logger.warning(f"IP 白名单验证失败: {client_ip}")
            raise HTTPException(
                status_code=403, detail=f"Access denied for IP: {client_ip}"
            )

        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(f"Bearer Token 缺失, IP: {client_ip}")
            raise HTTPException(
                status_code=401,
                detail="Bearer Token required. Please provide Authorization: Bearer <token> header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split(" ", 1)[1]

        if token not in self.api_keys:
            logger.warning(f"无效的 Bearer Token: {token[:8]}..., IP: {client_ip}")
            raise HTTPException(
                status_code=401,
                detail="Invalid Bearer Token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        logger.info(f"认证成功: IP={client_ip}, Token={token[:8]}...")
        return token

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"
