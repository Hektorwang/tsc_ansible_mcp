"""Permission check decorator.

Provides permission check decorator for MCP tool functions, implementing defense in depth.
"""

from functools import wraps
from typing import Any, Callable, Dict, Optional

from lib.context_vars import get_current_role
from lib.tsc_logger import get_logger

logger = get_logger()


def require_permission(tool_name: str):
    """Permission check decorator.

    Args:
        tool_name: Tool name.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable) -> Callable:
        from lib.server import Server

        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            # Get auth instance
            try:
                if not hasattr(Server, "_auth_instance"):
                    logger.warning("Auth instance not initialized")
                    return {
                        "status": "error",
                        "message": "Internal error: auth not initialized",
                    }

                auth = Server._auth_instance  # pylint: disable=no-member

                # Allow all tools when authentication is disabled
                if not auth.enabled:
                    logger.debug(f"Authentication disabled, allowing tool call: Tool={tool_name}")
                    return func(*args, **kwargs)

                role = get_current_role()

                # Authentication enabled but user context not set, deny access
                if not role:
                    logger.warning(f"Tool call failed: User context not set, Tool={tool_name}")
                    return {
                        "status": "error",
                        "message": "Authentication required: user context not set",
                    }

                # Check permission
                if not auth.jwt_utils.check_permission(role, tool_name):
                    logger.warning(f"Insufficient tool permissions: Role={role}, Tool={tool_name}")
                    return {
                        "status": "error",
                        "message": f"Permission denied: role '{role}' cannot access tool '{tool_name}'",
                    }

                # Permission check passed, execute original function
                return func(*args, **kwargs)

            except Exception as e:
                logger.exception(f"Permission check failed: {e}")
                return {
                    "status": "error",
                    "message": f"Permission check failed: {str(e)}",
                }

        return wrapper

    return decorator


def check_tool_permission(
    auth_instance: Any, tool_name: str
) -> Optional[Dict[str, Any]]:
    """Check tool call permission (non-decorator version).

    Args:
        auth_instance: Auth instance.
        tool_name: Tool name.

    Returns:
        None if permission granted, error dictionary otherwise.
    """
    role = get_current_role()

    if not role:
        logger.warning(f"Tool call failed: User context not set, Tool={tool_name}")
        return {
            "status": "error",
            "message": "Authentication required: user context not set",
        }

    if not auth_instance.jwt_utils.check_permission(role, tool_name):
        logger.warning(f"Insufficient tool permissions: Role={role}, Tool={tool_name}")
        return {
            "status": "error",
            "message": f"Permission denied: role '{role}' cannot access tool '{tool_name}'",
        }

    return None
