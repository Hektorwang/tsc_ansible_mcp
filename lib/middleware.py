"""MCP authorization middleware.

Intercepts MCP protocol requests, filters tool lists based on user roles, and checks tool execution permissions.
"""

import json
import time
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lib.context_vars import clear_current_user, set_current_user
from lib.tsc_logger import get_logger

logger = get_logger()


class MCPAuthorizationMiddleware(BaseHTTPMiddleware):
    """MCP authorization middleware.

    Features:
    1. Extract and verify JWT token
    2. Set user context
    3. Filter tool lists (based on role)
    4. Check tool execution permissions
    """

    def __init__(self, app, auth_instance: Any):
        """Initialize authorization middleware.

        Args:
            app: ASGI application.
            auth_instance: Auth instance.
        """
        super().__init__(app)
        self.auth = auth_instance

    async def dispatch(self, request: Request, call_next):
        """Process request.

        Args:
            request: Request object.
            call_next: Next middleware or application.

        Returns:
            Response object.
        """
        start_time = time.time()
        request_id = id(request)

        logger.debug(
            f"[{request_id}] Middleware started processing request: path={request.url.path}"
        )

        # Only process MCP endpoints
        if not request.url.path.startswith("/mcp"):
            logger.debug(
                f"[{request_id}] Non-MCP endpoint, skipping middleware: path={request.url.path}"
            )
            return await call_next(request)

        logger.info(
            f"[{request_id}] MCP endpoint request: path={request.url.path}, method={request.method}"
        )

        # If authentication is disabled, allow all requests
        if not self.auth.enabled:
            logger.info(
                f"[{request_id}] Authentication disabled, allowing MCP request: path={request.url.path}, method={request.method}"
            )
            if request.method == "POST":
                body = await request.body()
                try:
                    request_data = json.loads(body)
                    method_name = request_data.get("method")
                    request_id_str = request_data.get("id")
                    logger.info(
                        f"[{request_id}] MCP request (auth disabled): method={method_name}, id={request_id_str}"
                    )
                    logger.info(
                        f"[{request_id}] MCP request body: {json.dumps(request_data, ensure_ascii=False, indent=2)}"
                    )
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.info(
                        f"[{request_id}] MCP request body (raw, not JSON): {body[:500]}"
                    )
            response = await call_next(request)

            if request.method == "POST":
                logger.info(
                    f"[{request_id}] Response status: {response.status_code}, headers={dict(response.headers)}"
                )
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk
                if response_body:
                    try:
                        resp_data = json.loads(response_body.decode("utf-8"))
                        logger.info(
                            f"[{request_id}] MCP response body: {json.dumps(resp_data, ensure_ascii=False, indent=2)}"
                        )
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.info(
                            f"[{request_id}] MCP response body (raw): {response_body[:2000].decode('utf-8', errors='replace')}"
                        )
                return Response(
                    content=response_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )

            return response

        logger.info(
            f"[{request_id}] Authentication enabled, starting JWT token verification"
        )

        # Extract JWT token
        authorization = request.headers.get("authorization", "")
        logger.debug(
            f"[{request_id}] Authorization header: {authorization[:30] if authorization else 'None'}..."
        )

        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(
                f"[{request_id}] MCP endpoint authentication failed: Missing Bearer Token, path={request.url.path}"
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
            f"[{request_id}] Extracted JWT Token: {token[:30]}..., length={len(token)}"
        )

        logger.debug(f"[{request_id}] Starting JWT token verification")
        payload = self.auth.jwt_utils.verify_jwt(token)
        logger.debug(f"[{request_id}] JWT verification result: {payload is not None}")

        if not payload:
            logger.warning(
                f"[{request_id}] MCP endpoint invalid JWT Token: token={token[:30]}..."
            )
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": 401, "message": "Invalid or expired JWT Token"},
                },
                status_code=401,
            )

        # Set user context
        user_info = {
            "sub": payload.get("sub"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
        }
        set_current_user(user_info)
        logger.debug(f"[{request_id}] User context set: {user_info}")

        elapsed_time = time.time() - start_time
        logger.info(
            f"[{request_id}] MCP endpoint authentication successful: path={request.url.path}, "
            f"User={user_info['name']}({user_info['sub']}), Role={user_info['role']}, "
            f"elapsed={elapsed_time:.3f}s"
        )

        try:
            # Process POST request
            if request.method == "POST":
                # Read request body
                body = await request.body()
                logger.info(
                    f"[{request_id}] POST request body: size={len(body)}, content={body[:300]}"
                )

                try:
                    request_data = json.loads(body)
                    method = request_data.get("method")
                    request_id_str = request_data.get("id")

                    logger.info(
                        f"[{request_id}] MCP request: method={method}, id={request_id_str}"
                    )

                    # Process different types of MCP requests
                    if method == "tools/list":
                        # Tool list request needs filtering
                        logger.info(
                            f"[{request_id}] tools/list request detected, processing"
                        )
                        logger.debug(
                            f"[{request_id}] tools/list request full body: {json.dumps(request_data, ensure_ascii=False)}"
                        )
                        response = await call_next(request)
                        return await self._filter_tools_list_response(
                            request_id, response, user_info
                        )

                    elif method == "tools/call":
                        # Tool call request needs permission check
                        tool_name = request_data.get("params", {}).get("name")
                        logger.info(
                            f"[{request_id}] Tool call request: tool={tool_name}, user={user_info.get('name')}, role={user_info.get('role')}"
                        )

                        if tool_name:
                            logger.debug(
                                f"[{request_id}] Starting permission check: role={user_info['role']}, tool={tool_name}"
                            )
                            has_permission = self.auth.jwt_utils.check_permission(
                                user_info["role"], tool_name
                            )
                            logger.debug(
                                f"[{request_id}] Permission check result: {has_permission}"
                            )

                            if not has_permission:
                                logger.warning(
                                    f"[{request_id}] Insufficient tool permissions: User={user_info['name']}, "
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
                                    f"[{request_id}] Tool call permission check passed: tool={tool_name}, role={user_info['role']}"
                                )

                    else:
                        logger.info(
                            f"[{request_id}] Continuing to process other MCP requests: method={method}, allowing"
                        )

                except json.JSONDecodeError as e:
                    logger.error(f"[{request_id}] JSON parsing failed: {e}")
                    logger.debug(
                        f"[{request_id}] Raw request body that failed to parse: {body}"
                    )

            # Continue processing request
            response = await call_next(request)

            total_time = time.time() - start_time
            logger.info(
                f"[{request_id}] Request processing completed, total time={total_time:.3f}s"
            )

            return response

        finally:
            clear_current_user()
            logger.debug(f"[{request_id}] User context cleared")

    async def _filter_tools_list_response(
        self, request_id: int, response, user_info: Dict[str, Any]
    ):
        """Filter tool list response.

        Args:
            request_id: Request ID.
            response: Original response.
            user_info: User information.

        Returns:
            Filtered response.
        """
        role = user_info["role"]
        logger.info(f"[{request_id}] Starting to filter tool list: role={role}")

        # Read response body
        response_body = b""
        try:
            async for chunk in response.body_iterator:
                response_body += chunk
                logger.debug(f"[{request_id}] Read chunk: size={len(chunk)}")
        except Exception as e:
            logger.error(
                f"[{request_id}] Failed to read response body: {e}", exc_info=True
            )
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

        logger.info(
            f"[{request_id}] Response body total size: {len(response_body)} bytes"
        )
        logger.debug(
            f"[{request_id}] Response body first 500 bytes: {response_body[:500]}"
        )

        if not response_body:
            logger.error(f"[{request_id}] Response body is empty")
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": 500, "message": "Empty response"}},
                status_code=500,
            )

        logger.debug(f"[{request_id}] Starting to parse JSON response")
        response_json = None
        is_sse = False

        try:
            response_text = response_body.decode("utf-8")
            logger.debug(
                f"[{request_id}] Response text first 200 chars: {response_text[:200]}"
            )

            # Handle SSE (Server-Sent Events) format
            # SSE format: "event: message\ndata: {JSON}\n\n"
            is_sse = response_text.startswith("event:")

            if is_sse:
                logger.debug(f"[{request_id}] SSE format response detected")
                lines = response_text.strip().split("\n")
                json_line = None
                for line in lines:
                    if line.startswith("data:"):
                        json_line = line[5:].strip()  # Remove "data:" prefix
                        break

                if not json_line:
                    logger.error(
                        f"[{request_id}] No data line found in SSE format response"
                    )
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

                logger.debug(
                    f"[{request_id}] Extracted SSE data line: {json_line[:200]}"
                )
                response_json = json.loads(json_line)
            else:
                # Pure JSON format
                logger.debug(f"[{request_id}] Pure JSON format response detected")
                response_json = json.loads(response_text)

            logger.debug(f"[{request_id}] JSON parsing successful")
        except UnicodeDecodeError as e:
            logger.error(f"[{request_id}] UTF-8 decoding failed: {e}", exc_info=True)
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
                f"[{request_id}] JSON parsing failed: {e}, response body: {body_preview}",
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
            logger.error(
                f"[{request_id}] Failed to process response: {e}", exc_info=True
            )
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

        # Filter tool list
        logger.info(
            f"[{request_id}] Response JSON keys: {list(response_json.keys()) if isinstance(response_json, dict) else 'not a dict'}"
        )

        if "result" in response_json and "tools" in response_json["result"]:
            all_tools = response_json["result"]["tools"]
            logger.info(
                f"[{request_id}] Starting to filter tool list: total={len(all_tools)}"
            )
            logger.debug(
                f"[{request_id}] All tool names: {[t.get('name', 'unknown') for t in all_tools]}"
            )

            filtered_tools = []
            for tool in all_tools:
                tool_name = tool.get("name", "")
                has_permission = self.auth.jwt_utils.check_permission(role, tool_name)
                logger.debug(
                    f"[{request_id}] Tool filtering: {tool_name} -> {has_permission}"
                )
                if has_permission:
                    filtered_tools.append(tool)

            response_json["result"]["tools"] = filtered_tools

            logger.info(
                f"[{request_id}] Tool list filtering completed: Role={role}, "
                f"Total={len(all_tools)}, Filtered={len(filtered_tools)}"
            )
            logger.info(
                f"[{request_id}] Filtered tool names: {[t.get('name', 'unknown') for t in filtered_tools]}"
            )
            logger.debug(
                f"[{request_id}] Final filtered response JSON (first 1000 chars): {json.dumps(response_json, ensure_ascii=False)[:1000]}"
            )
        else:
            logger.warning(
                f"[{request_id}] No tools found in response JSON. Keys: {list(response_json.keys())}"
            )

        # Return filtered response, maintaining original format
        if is_sse:
            # SSE format
            filtered_body = f"event: message\ndata: {json.dumps(response_json)}\n\n"
            # Get original headers, but modify content-type
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
            # Pure JSON format
            return JSONResponse(
                response_json,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
