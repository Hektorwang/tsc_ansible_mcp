"""MCP 授权中间件

拦截 MCP 协议请求，根据用户角色过滤工具列表和检查工具执行权限
"""

import json
import time
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lib.context_vars import set_current_user, clear_current_user
from lib.logger import get_logger

logger = get_logger()


class MCPAuthorizationMiddleware(BaseHTTPMiddleware):
    """MCP 授权中间件

    功能：
    1. 提取 JWT token 并验证
    2. 设置用户上下文
    3. 过滤工具列表（根据角色）
    4. 检查工具执行权限
    """

    def __init__(self, app, auth_instance: Any):
        """初始化授权中间件

        Args:
            app: ASGI 应用
            auth_instance: 认证实例
        """
        super().__init__(app)
        self.auth = auth_instance

    async def dispatch(self, request: Request, call_next):
        """处理请求

        Args:
            request: 请求对象
            call_next: 下一个中间件或应用

        Returns:
            响应对象
        """
        start_time = time.time()
        request_id = id(request)

        logger.debug(f"[{request_id}] 中间件开始处理请求: path={request.url.path}")

        # 只处理 MCP 端点
        if not request.url.path.startswith("/mcp"):
            logger.debug(
                f"[{request_id}] 非MCP端点，跳过中间件: path={request.url.path}"
            )
            return await call_next(request)

        logger.info(
            f"[{request_id}] MCP端点请求: path={request.url.path}, method={request.method}"
        )

        # 如果认证未启用，直接放行
        if not self.auth.enabled:
            logger.warning(
                f"[{request_id}] 认证未启用，直接放行MCP请求: path={request.url.path}"
            )
            return await call_next(request)

        logger.info(f"[{request_id}] 认证已启用，开始验证JWT Token")

        # 提取 JWT token
        authorization = request.headers.get("authorization", "")
        logger.debug(
            f"[{request_id}] Authorization header: {authorization[:30] if authorization else 'None'}..."
        )

        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(
                f"[{request_id}] MCP 端点认证失败: 缺少Bearer Token, path={request.url.path}"
            )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 401,
                        "message": "JWT Token required for MCP endpoints",
                    },
                },
                status_code=401,
            )

        token = authorization.split(" ", 1)[1]
        logger.debug(
            f"[{request_id}] 提取到JWT Token: {token[:30]}..., 长度={len(token)}"
        )

        logger.debug(f"[{request_id}] 开始验证JWT Token")
        payload = self.auth.jwt_utils.verify_jwt(token)
        logger.debug(f"[{request_id}] JWT验证结果: {payload is not None}")

        if not payload:
            logger.warning(
                f"[{request_id}] MCP 端点无效 JWT Token: token={token[:30]}..."
            )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": 401, "message": "Invalid or expired JWT Token"},
                },
                status_code=401,
            )

        # 设置用户上下文
        user_info = {
            "sub": payload.get("sub"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
        }
        set_current_user(user_info)
        logger.debug(f"[{request_id}] 已设置用户上下文: {user_info}")

        elapsed_time = time.time() - start_time
        logger.info(
            f"[{request_id}] MCP 端点认证成功: path={request.url.path}, "
            f"User={user_info['name']}({user_info['sub']}), Role={user_info['role']}, "
            f"耗时={elapsed_time:.3f}s"
        )

        try:
            # 处理 POST 请求
            if request.method == "POST":
                # 读取请求体
                body = await request.body()
                logger.debug(f"[{request_id}] 读取到请求体: length={len(body)}")

                try:
                    request_data = json.loads(body)
                    method = request_data.get("method")
                    request_id_str = request_data.get("id")

                    logger.info(
                        f"[{request_id}] MCP请求: method={method}, id={request_id_str}"
                    )

                    # 处理不同类型的MCP请求
                    if method == "tools/list":
                        # 工具列表请求需要过滤
                        logger.info(f"[{request_id}] 检测到tools/list请求，开始处理")
                        response = await call_next(request)
                        return await self._filter_tools_list_response(
                            request_id, response, user_info
                        )

                    elif method == "tools/call":
                        # 工具调用请求需要权限检查
                        tool_name = request_data.get("params", {}).get("name")
                        logger.info(
                            f"[{request_id}] 工具调用请求: tool={tool_name}, user={user_info.get('name')}, role={user_info.get('role')}"
                        )

                        if tool_name:
                            logger.debug(
                                f"[{request_id}] 开始检查权限: role={user_info['role']}, tool={tool_name}"
                            )
                            has_permission = self.auth.jwt_utils.check_permission(
                                user_info["role"], tool_name
                            )
                            logger.debug(
                                f"[{request_id}] 权限检查结果: {has_permission}"
                            )

                            if not has_permission:
                                logger.warning(
                                    f"[{request_id}] 工具调用权限不足: User={user_info['name']}, "
                                    f"Role={user_info['role']}, Tool={tool_name}"
                                )
                                return JSONResponse(
                                    {
                                        "jsonrpc": "2.0",
                                        "id": request_id_str,
                                        "error": {
                                            "code": 403,
                                            "message": f"Permission denied for tool: {tool_name}",
                                        },
                                    },
                                    status_code=403,
                                )
                            else:
                                logger.info(
                                    f"[{request_id}] 工具调用权限检查通过: tool={tool_name}, role={user_info['role']}"
                                )

                    else:
                        logger.info(
                            f"[{request_id}] 继续处理其他MCP请求: method={method}, 直接放行"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"[{request_id}] JSON解析失败: {e}")

            # 继续处理请求
            response = await call_next(request)

            total_time = time.time() - start_time
            logger.info(f"[{request_id}] 请求处理完成，总耗时={total_time:.3f}s")

            return response

        finally:
            clear_current_user()
            logger.debug(f"[{request_id}] 清除用户上下文")

    async def _filter_tools_list_response(
        self, request_id: int, response, user_info: Dict[str, Any]
    ):
        """过滤工具列表响应

        Args:
            request_id: 请求ID
            response: 原始响应
            user_info: 用户信息

        Returns:
            过滤后的响应
        """
        role = user_info["role"]
        logger.info(f"[{request_id}] 开始过滤工具列表: role={role}")

        # 读取响应体
        response_body = b""
        try:
            async for chunk in response.body_iterator:
                response_body += chunk
        except Exception as e:
            logger.error(f"[{request_id}] 读取响应体失败: {e}", exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 500,
                        "message": f"Failed to read response: {str(e)}",
                    },
                },
                status_code=500,
            )

        logger.debug(f"[{request_id}] 响应体长度: {len(response_body)}")

        if not response_body:
            logger.warning(f"[{request_id}] 响应体为空")
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": 500, "message": "Empty response"}},
                status_code=500,
            )

        logger.debug(f"[{request_id}] 开始解析JSON响应")
        response_json = None
        is_sse = False

        try:
            response_text = response_body.decode("utf-8")
            logger.debug(f"[{request_id}] 响应文本前200字符: {response_text[:200]}")

            # 处理 SSE (Server-Sent Events) 格式
            # SSE 格式: "event: message\ndata: {JSON}\n\n"
            is_sse = response_text.startswith("event:")

            if is_sse:
                logger.debug(f"[{request_id}] 检测到SSE格式响应")
                lines = response_text.strip().split("\n")
                json_line = None
                for line in lines:
                    if line.startswith("data:"):
                        json_line = line[5:].strip()  # 去掉 "data:" 前缀
                        break

                if not json_line:
                    logger.error(f"[{request_id}] SSE格式响应中未找到data行")
                    return JSONResponse(
                        {
                            "jsonrpc": "2.0",
                            "error": {
                                "code": 500,
                                "message": "Invalid SSE response: no data line",
                            },
                        },
                        status_code=500,
                    )

                logger.debug(f"[{request_id}] 提取SSE data行: {json_line[:200]}")
                response_json = json.loads(json_line)
            else:
                # 纯JSON格式
                logger.debug(f"[{request_id}] 检测到纯JSON格式响应")
                response_json = json.loads(response_text)

            logger.debug(f"[{request_id}] JSON解析成功")
        except UnicodeDecodeError as e:
            logger.error(f"[{request_id}] UTF-8解码失败: {e}", exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 500,
                        "message": f"Invalid UTF-8 response: {str(e)}",
                    },
                },
                status_code=500,
            )
        except json.JSONDecodeError as e:
            body_preview = response_body[:200].decode("utf-8", errors="replace")
            logger.error(
                f"[{request_id}] JSON解析失败: {e}, 响应体: {body_preview}",
                exc_info=True,
            )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 500,
                        "message": f"Invalid JSON response: {str(e)}",
                    },
                },
                status_code=500,
            )
        except Exception as e:
            logger.error(f"[{request_id}] 处理响应失败: {e}", exc_info=True)
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": 500,
                        "message": f"Failed to process response: {str(e)}",
                    },
                },
                status_code=500,
            )

        # 过滤工具列表
        logger.debug(
            f"[{request_id}] 响应JSON: {json.dumps(response_json, ensure_ascii=False)[:500]}"
        )

        if "result" in response_json and "tools" in response_json["result"]:
            all_tools = response_json["result"]["tools"]
            logger.debug(f"[{request_id}] 开始过滤工具列表: 总数={len(all_tools)}")

            filtered_tools = []
            for tool in all_tools:
                tool_name = tool.get("name", "")
                has_permission = self.auth.jwt_utils.check_permission(role, tool_name)
                logger.debug(
                    f"[{request_id}] 工具过滤: {tool_name} -> {has_permission}"
                )
                if has_permission:
                    filtered_tools.append(tool)

            response_json["result"]["tools"] = filtered_tools

            logger.info(
                f"[{request_id}] 工具列表过滤完成: Role={role}, "
                f"Total={len(all_tools)}, Filtered={len(filtered_tools)}"
            )

        # 返回过滤后的响应，保持原始格式
        if is_sse:
            # SSE 格式
            filtered_body = f"event: message\ndata: {json.dumps(response_json)}\n\n"
            # 获取原始headers，但修改content-type
            headers = dict(response.headers)
            headers["content-type"] = "text/event-stream"
            headers["content-length"] = str(len(filtered_body.encode("utf-8")))
            return Response(
                content=filtered_body,
                status_code=response.status_code,
                headers=headers,
                media_type="text/event-stream",
            )
        else:
            # 纯 JSON 格式
            return JSONResponse(
                response_json,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
