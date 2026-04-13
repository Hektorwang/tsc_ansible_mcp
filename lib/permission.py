"""权限检查装饰器

为 MCP 工具函数提供权限检查装饰器，实现深度防御
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

from lib.context_vars import get_current_role
from lib.tsc_logger import get_logger

logger = get_logger()


def require_permission(tool_name: str):
    """权限检查装饰器

    Args:
        tool_name: 工具名称

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        from lib.server import Server

        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            # 获取 auth 实例
            try:
                if not hasattr(Server, "_auth_instance"):
                    logger.warning("Auth instance not initialized")
                    return {
                        "status": "error",
                        "message": "Internal error: auth not initialized",
                    }

                auth = Server._auth_instance  # pylint: disable=no-member

                # 认证未启用时放行所有工具
                if not auth.enabled:
                    logger.debug(f"认证未启用，放行工具调用: Tool={tool_name}")
                    return func(*args, **kwargs)

                role = get_current_role()

                # 认证已启用但未设置用户上下文，拒绝访问
                if not role:
                    logger.warning(f"工具调用失败: 未设置用户上下文, Tool={tool_name}")
                    return {
                        "status": "error",
                        "message": "Authentication required: user context not set",
                    }

                # 检查权限
                if not auth.jwt_utils.check_permission(role, tool_name):
                    logger.warning(f"工具调用权限不足: Role={role}, Tool={tool_name}")
                    return {
                        "status": "error",
                        "message": f"Permission denied: role '{role}' cannot access tool '{tool_name}'",
                    }

                # 权限检查通过，执行原函数
                return func(*args, **kwargs)

            except Exception as e:
                logger.exception(f"权限检查失败: {e}")
                return {
                    "status": "error",
                    "message": f"Permission check failed: {str(e)}",
                }

        return wrapper

    return decorator


def check_tool_permission(
    auth_instance: Any, tool_name: str
) -> Optional[Dict[str, Any]]:
    """检查工具调用权限（非装饰器版本）

    Args:
        auth_instance: 认证实例
        tool_name: 工具名称

    Returns:
        如果有权限返回 None，否则返回错误字典
    """
    role = get_current_role()

    if not role:
        logger.warning(f"工具调用失败: 未设置用户上下文, Tool={tool_name}")
        return {
            "status": "error",
            "message": "Authentication required: user context not set",
        }

    if not auth_instance.jwt_utils.check_permission(role, tool_name):
        logger.warning(f"工具调用权限不足: Role={role}, Tool={tool_name}")
        return {
            "status": "error",
            "message": f"Permission denied: role '{role}' cannot access tool '{tool_name}'",
        }

    return None
