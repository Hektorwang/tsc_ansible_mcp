"""请求上下文变量

使用 contextvars 在请求处理过程中传递用户信息
"""

from contextvars import ContextVar
from typing import Any, Dict, Optional

current_user: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "current_user", default=None
)


def set_current_user(user_info: Dict[str, Any]) -> None:
    """设置当前用户信息

    Args:
        user_info: 用户信息字典，包含 sub, name, role 等字段
    """
    current_user.set(user_info)


def get_current_user() -> Optional[Dict[str, Any]]:
    """获取当前用户信息

    Returns:
        用户信息字典，未设置时返回 None
    """
    return current_user.get()


def get_current_role() -> str:
    """获取当前用户角色

    Returns:
        用户角色，未设置时返回 "user"
    """
    user = get_current_user()
    if user:
        return user.get("role", "user")
    return "user"


def get_current_user_name() -> str:
    """获取当前用户名称

    Returns:
        用户名称，未设置时返回 "unknown"
    """
    user = get_current_user()
    if user:
        return user.get("name", "unknown")
    return "unknown"


def get_current_user_id() -> str:
    """获取当前用户 ID

    Returns:
        用户 ID，未设置时返回 "unknown"
    """
    user = get_current_user()
    if user:
        return user.get("sub", "unknown")
    return "unknown"


def clear_current_user() -> None:
    """清除当前用户信息"""
    current_user.set(None)
