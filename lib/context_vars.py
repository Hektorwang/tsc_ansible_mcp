"""Request context variables.

Use contextvars to pass user information during request processing.
"""

from contextvars import ContextVar
from typing import Any, Dict, Optional

current_user: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "current_user", default=None
)


def set_current_user(user_info: Dict[str, Any]) -> None:
    """Set current user information.

    Args:
        user_info: User information dictionary, containing sub, name, role fields.
    """
    current_user.set(user_info)


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current user information.

    Returns:
        User information dictionary, None if not set.
    """
    return current_user.get()


def get_current_role() -> str:
    """Get current user role.

    Returns:
        User role, "user" if not set.
    """
    user = get_current_user()
    if user:
        return user.get("role", "user")
    return "user"


def get_current_user_name() -> str:
    """Get current user name.

    Returns:
        User name, "unknown" if not set.
    """
    user = get_current_user()
    if user:
        return user.get("name", "unknown")
    return "unknown"


def get_current_user_id() -> str:
    """Get current user ID.

    Returns:
        User ID, "unknown" if not set.
    """
    user = get_current_user()
    if user:
        return user.get("sub", "unknown")
    return "unknown"


def clear_current_user() -> None:
    """Clear current user information."""
    current_user.set(None)
