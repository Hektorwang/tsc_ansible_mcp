"""
JWT 认证中间件模块

提供 JWT 认证和权限控制功能
"""

import ipaddress
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lib.config import Config
from lib.jwt_utils import JWTUtils
from lib.tsc_logger import get_logger

logger = get_logger()


class AuthMiddleware:
    """JWT 认证中间件类"""

    def __init__(self, config: Config):
        """初始化认证中间件

        Args:
            config: 配置对象
        """
        self.config = config
        self.enabled = config.get("auth.enabled", False)

        secret_key_file = self._get_file_path(
            config.get("auth.jwt_secret_key_file", "etc/jwt_secret_key.txt")
        )
        issued_tokens_file = self._get_file_path(
            config.get("auth.jwt_issued_tokens_file", "etc/jwt_issued_tokens.json")
        )

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

        self.jwt_utils = JWTUtils(
            secret_key_file=secret_key_file,
            issued_tokens_file=issued_tokens_file,
            tool_permissions=tool_permissions,
        )

        self.whitelist_ips = self._parse_whitelist(config.get("auth.whitelist_ips", []))
        self.security = HTTPBearer(auto_error=False)

        logger.info(
            f"JWT 认证中间件初始化: enabled={self.enabled}, "
            f"secret_key_file={secret_key_file}, "
            f"roles={list(tool_permissions.keys())}"
        )

    def _get_file_path(self, file_path: str) -> Path:
        """获取文件绝对路径

        Args:
            file_path: 文件路径（相对或绝对）

        Returns:
            绝对路径
        """
        path = Path(file_path)
        if path.is_absolute():
            return path
        else:
            base_dir = self.config.path.parent.parent
            return base_dir / file_path

    def _parse_whitelist(
        self, ip_list: List[str]
    ) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
        """解析 IP 白名单配置

        Args:
            ip_list: IP 地址列表

        Returns:
            IP 网络列表
        """
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
        """检查客户端 IP 是否在白名单中

        Args:
            client_ip: 客户端 IP 地址

        Returns:
            是否允许
        """
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

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP

        Args:
            request: 请求对象

        Returns:
            客户端 IP 地址
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        if request.client:
            return request.client.host

        return "unknown"

    def _create_jwt_error_response(
        self, code: str, message: str, details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """创建 JWT 认证失败的错误响应

        Args:
            code: 错误码
            message: 错误消息
            details: 错误详情

        Returns:
            错误响应字典
        """
        error: Dict[str, Any] = {
            "code": code,
            "message": message,
        }
        if details:
            error["details"] = details
        return {
            "status": "error",
            "error": error,
        }

    async def verify_request(self, request: Request) -> Dict[str, Any]:
        """验证请求（IP 白名单 + JWT 认证）

        Args:
            request: 请求对象

        Returns:
            用户信息字典

        Raises:
            HTTPException: 认证失败
        """
        if not self.enabled:
            return {"sub": "auth_disabled", "name": "auth_disabled", "role": "admin"}

        client_ip = self._get_client_ip(request)

        if not self.is_ip_allowed(client_ip):
            logger.warning(f"IP 白名单验证失败: {client_ip}")
            raise HTTPException(
                status_code=403,
                detail=self._create_jwt_error_response(
                    "IP_NOT_ALLOWED", f"Access denied for IP: {client_ip}"
                ),
            )

        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(f"JWT Token 缺失, IP: {client_ip}")
            raise HTTPException(
                status_code=401,
                detail=self._create_jwt_error_response(
                    "TOKEN_MISSING",
                    "JWT Token required. Please provide Authorization: Bearer <token> header.",
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.split(" ", 1)[1]
        payload = self.jwt_utils.verify_jwt(token)

        if not payload:
            logger.warning(f"无效的 JWT Token, IP: {client_ip}")
            raise HTTPException(
                status_code=401,
                detail=self._create_jwt_error_response(
                    "TOKEN_INVALID", "JWT Token 无效或已过期"
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_info = {
            "sub": payload.get("sub", "unknown"),
            "name": payload.get("name", "unknown"),
            "role": payload.get("role", "user"),
        }

        logger.info(
            f"JWT 认证成功: IP={client_ip}, User={user_info['name']}({user_info['sub']}), Role={user_info['role']}"
        )

        return user_info

    def check_tool_permission(self, user_info: Dict[str, Any], tool_name: str) -> bool:
        """检查用户是否有权限调用工具

        Args:
            user_info: 用户信息
            tool_name: 工具名称

        Returns:
            是否有权限
        """
        role = user_info.get("role", "user")
        has_permission = self.jwt_utils.check_permission(role, tool_name)

        if not has_permission:
            logger.warning(
                f"权限不足: User={user_info.get('name')}({user_info.get('sub')}), "
                f"Role={role}, Tool={tool_name}"
            )

        return has_permission

    def log_audit(
        self,
        user_info: Dict[str, Any],
        request: Request,
        tool_name: str,
        request_params: Dict[str, Any],
        response_status: str,
        response_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """记录审计日志

        Args:
            user_info: 用户信息
            request: 请求对象
            tool_name: 工具名称
            request_params: 请求参数
            response_status: 响应状态
            response_data: 响应数据
        """
        client_ip = self._get_client_ip(request)

        log_data = {
            "user": f"{user_info.get('name')}({user_info.get('sub')})",
            "role": user_info.get("role"),
            "ip": client_ip,
            "tool": tool_name,
            "request": request_params,
            "response_status": response_status,
        }

        if response_data:
            if isinstance(response_data, dict):
                log_data["response_summary"] = {
                    "status": response_data.get("status"),
                    "task_id": response_data.get("task_id"),
                }
            else:
                log_data["response_summary"] = str(response_data)[:200]

        logger.info(f"审计日志: {json.dumps(log_data, ensure_ascii=False)}")

    def get_user_permissions(self, role: str) -> List[str]:
        """获取角色的权限列表

        Args:
            role: 用户角色

        Returns:
            权限列表
        """
        return self.jwt_utils.get_user_permissions(role)
