"""
JWT authentication middleware module.

Provides JWT authentication and permission control functionality.
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
    """JWT authentication middleware class."""

    def __init__(self, config: Config):
        """Initialize authentication middleware.

        Args:
            config: Configuration object.
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
            f"JWT authentication middleware initialized: enabled={self.enabled}, "
            f"secret_key_file={secret_key_file}, "
            f"roles={list(tool_permissions.keys())}"
        )

    def _get_file_path(self, file_path: str) -> Path:
        """Get absolute file path.

        Args:
            file_path: File path (relative or absolute).

        Returns:
            Absolute path.
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
        """Parse IP whitelist configuration.

        Args:
            ip_list: List of IP addresses.

        Returns:
            List of IP networks.
        """
        networks = []
        for ip in ip_list:
            try:
                if "/" in ip:
                    networks.append(ipaddress.ip_network(ip, strict=False))
                else:
                    networks.append(ipaddress.ip_network(f"{ip}/32"))
                logger.debug(f"IP whitelist added: {ip}")
            except ValueError as e:
                logger.warning(f"Invalid IP whitelist configuration: {ip}, error: {e}")
        return networks

    def is_ip_allowed(self, client_ip: str) -> bool:
        """Check if client IP is in whitelist.

        Args:
            client_ip: Client IP address.

        Returns:
            Whether allowed.
        """
        if not self.whitelist_ips:
            return True

        try:
            ip_addr = ipaddress.ip_address(client_ip)
            allowed = any(ip_addr in network for network in self.whitelist_ips)
            if not allowed:
                logger.warning(f"IP {client_ip} not in whitelist")
            return allowed
        except ValueError as e:
            logger.warning(f"Invalid client IP: {client_ip}, error: {e}")
            return False

    def _get_client_ip(self, request: Request) -> str:
        """Get client real IP.

        Args:
            request: Request object.

        Returns:
            Client IP address.
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
        """Create JWT authentication failure error response.

        Args:
            code: Error code.
            message: Error message.
            details: Error details.

        Returns:
            Error response dictionary.
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
        """Verify request (IP whitelist + JWT authentication).

        Args:
            request: Request object.

        Returns:
            User information dictionary.

        Raises:
            HTTPException: Authentication failed.
        """
        if not self.enabled:
            return {"sub": "auth_disabled", "name": "auth_disabled", "role": "admin"}

        client_ip = self._get_client_ip(request)

        if not self.is_ip_allowed(client_ip):
            logger.warning(f"IP whitelist verification failed: {client_ip}")
            raise HTTPException(
                status_code=403,
                detail=self._create_jwt_error_response(
                    "IP_NOT_ALLOWED", f"Access denied for IP: {client_ip}"
                ),
            )

        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(f"JWT Token missing, IP: {client_ip}")
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
            logger.warning(f"Invalid JWT Token, IP: {client_ip}")
            raise HTTPException(
                status_code=401,
                detail=self._create_jwt_error_response(
                    "TOKEN_INVALID", "JWT Token invalid or expired"
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_info = {
            "sub": payload.get("sub", "unknown"),
            "name": payload.get("name", "unknown"),
            "role": payload.get("role", "user"),
        }

        logger.info(
            f"JWT authentication successful: IP={client_ip}, User={user_info['name']}({user_info['sub']}), Role={user_info['role']}"
        )

        return user_info

    def check_tool_permission(self, user_info: Dict[str, Any], tool_name: str) -> bool:
        """Check if user has permission to call tool.

        Args:
            user_info: User information.
            tool_name: Tool name.

        Returns:
            Whether has permission.
        """
        role = user_info.get("role", "user")
        has_permission = self.jwt_utils.check_permission(role, tool_name)

        if not has_permission:
            logger.warning(
                f"Insufficient permission: User={user_info.get('name')}({user_info.get('sub')}), "
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
        """Log audit log.

        Args:
            user_info: User information.
            request: Request object.
            tool_name: Tool name.
            request_params: Request parameters.
            response_status: Response status.
            response_data: Response data.
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

        logger.info(f"Audit log: {json.dumps(log_data, ensure_ascii=False)}")

    def get_user_permissions(self, role: str) -> List[str]:
        """Get permissions list for role.

        Args:
            role: User role.

        Returns:
            List of permissions.
        """
        return self.jwt_utils.get_user_permissions(role)
