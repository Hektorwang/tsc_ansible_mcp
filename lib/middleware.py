"""MCP 授权中间件

拦截 MCP 协议请求，根据用户角色过滤工具列表和检查工具执行权限
"""

import json
from typing import Any, Callable, Dict, Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send, Message

from lib.context_vars import set_current_user, clear_current_user
from lib.logger import get_logger

logger = get_logger()


class MCPAuthorizationMiddleware:
    """MCP 授权中间件

    功能：
    1. 提取 JWT token 并验证
    2. 设置用户上下文
    3. 过滤工具列表（根据角色）
    4. 检查工具执行权限
    """

    def __init__(self, app: ASGIApp, auth_instance: Any):
        """初始化授权中间件

        Args:
            app: ASGI 应用
            auth_instance: 认证实例
        """
        self.app = app
        self.auth = auth_instance

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """处理请求

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 只处理 MCP 端点
        if not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        # 如果认证未启用，直接放行
        if not self.auth.enabled:
            await self.app(scope, receive, send)
            return

        # 提取 JWT token
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode()

        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(f"MCP 端点认证失败: {scope['path']}")
            await self._send_json_error(
                send, 401, "JWT Token required for MCP endpoints"
            )
            return

        token = authorization.split(" ", 1)[1]
        payload = self.auth.jwt_utils.verify_jwt(token)

        if not payload:
            logger.warning("MCP 端点无效 JWT Token")
            await self._send_json_error(send, 401, "Invalid or expired JWT Token")
            return

        # 设置用户上下文
        user_info = {
            "sub": payload.get("sub"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
        }
        set_current_user(user_info)

        logger.info(
            f"MCP 端点认证成功: {scope['path']}, "
            f"User={user_info['name']}({user_info['sub']}), Role={user_info['role']}"
        )

        # 拦截 MCP 协议请求
        if scope["method"] == "POST":
            await self._handle_mcp_request(scope, receive, send, user_info)
        else:
            await self.app(scope, receive, send)

    async def _handle_mcp_request(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        user_info: Dict[str, Any],
    ) -> None:
        """处理 MCP 协议请求

        Args:
            scope: ASGI scope
            receive: ASGI receive
            send: ASGI send
            user_info: 用户信息
        """
        # 读取请求体
        body = await self._read_body(receive)

        try:
            request_data = json.loads(body)
            method = request_data.get("method")

            # 拦截 tools/list 请求
            if method == "tools/list":
                await self._handle_tools_list(scope, send, user_info, request_data)
                return

            # 拦截 tools/call 请求
            if method == "tools/call":
                tool_name = request_data.get("params", {}).get("name")
                if tool_name:
                    if not self.auth.jwt_utils.check_permission(
                        user_info["role"], tool_name
                    ):
                        logger.warning(
                            f"工具调用权限不足: User={user_info['name']}, "
                            f"Role={user_info['role']}, Tool={tool_name}"
                        )
                        await self._send_json_error(
                            send,
                            403,
                            f"Permission denied for tool: {tool_name}",
                            request_data.get("id"),
                        )
                        return

            # 其他请求继续处理
            # 需要重新构造 receive，因为已经读取了 body
            async def new_receive() -> Message:
                return {"type": "http.request", "body": body.encode()}

            await self.app(scope, new_receive, send)

        except json.JSONDecodeError:
            # 非 JSON 请求，直接放行
            async def new_receive() -> Message:
                return {"type": "http.request", "body": body.encode()}

            await self.app(scope, new_receive, send)
        except Exception as e:
            logger.exception(f"处理 MCP 请求失败: {e}")
            await self._send_json_error(send, 500, f"Internal server error: {str(e)}")
        finally:
            clear_current_user()

    async def _handle_tools_list(
        self,
        scope: Scope,
        send: Send,
        user_info: Dict[str, Any],
        request_data: Dict[str, Any],
    ) -> None:
        """处理工具列表请求

        Args:
            scope: ASGI scope
            send: ASGI send
            user_info: 用户信息
            request_data: 请求数据
        """
        role = user_info["role"]

        # 创建一个响应拦截器
        response_data = []
        original_send = send

        async def intercept_send(message: Message) -> None:
            """拦截响应消息"""
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body)
                        response_data.append(data)
                    except:
                        pass
            await original_send(message)

        # 调用原始应用获取工具列表
        body_str = json.dumps(request_data)

        async def new_receive() -> Message:
            return {"type": "http.request", "body": body_str.encode()}

        try:
            await self.app(scope, new_receive, intercept_send)
        except Exception as e:
            logger.exception(f"获取工具列表失败: {e}")

        # 过滤工具列表
        if response_data:
            original_response = response_data[0]
            if "result" in original_response and "tools" in original_response["result"]:
                all_tools = original_response["result"]["tools"]
                filtered_tools = [
                    tool
                    for tool in all_tools
                    if self.auth.jwt_utils.check_permission(role, tool.get("name", ""))
                ]

                # 构造过滤后的响应
                filtered_response = {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": {"tools": filtered_tools},
                }

                logger.info(
                    f"工具列表过滤: Role={role}, "
                    f"Total={len(all_tools)}, Filtered={len(filtered_tools)}"
                )

                # 发送过滤后的响应
                await self._send_json_response(
                    send, 200, filtered_response, request_data.get("id")
                )
            else:
                # 如果响应格式不符合预期，直接发送原始响应
                await self._send_json_response(
                    send, 200, original_response, request_data.get("id")
                )

    async def _read_body(self, receive: Receive) -> str:
        """读取请求体

        Args:
            receive: ASGI receive

        Returns:
            请求体字符串
        """
        body_parts = []
        while True:
            message = await receive()
            if message["type"] == "http.request":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break

        return b"".join(body_parts).decode("utf-8")

    async def _send_json_error(
        self,
        send: Send,
        status_code: int,
        message: str,
        request_id: Optional[Any] = None,
    ) -> None:
        """发送 JSON 错误响应

        Args:
            send: ASGI send
            status_code: HTTP 状态码
            message: 错误消息
            request_id: 请求 ID
        """
        error_response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": status_code, "message": message},
        }

        await self._send_json_response(send, status_code, error_response, request_id)

    async def _send_json_response(
        self,
        send: Send,
        status_code: int,
        data: Dict[str, Any],
        request_id: Optional[Any] = None,
    ) -> None:
        """发送 JSON 响应

        Args:
            send: ASGI send
            status_code: HTTP 状态码
            data: 响应数据
            request_id: 请求 ID
        """
        body = json.dumps(data).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(body)).encode()],
                ],
            }
        )

        await send({"type": "http.response.body", "body": body})
