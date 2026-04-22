"""
Unified error handling module.
"""

from functools import wraps
from typing import Any, Callable, Dict, TypeVar, cast

from lib.tsc_logger import get_logger

logger = get_logger()


# Define error response format
def create_error_response(code: str, message: str, **kwargs) -> Dict[str, Any]:
    """Create unified error response format."""
    return {
        "status": "error",
        "message": message,
        "code": code,
        "http_status": ErrorHandler.ERROR_CODES.get(code, 500),
        **kwargs,
    }


# Define function type variable
F = TypeVar("F", bound=Callable[..., Any])


def error_handler(func: F) -> F:
    """Unified error handling decorator."""
    import asyncio

    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Error occurred in {func.__name__}: {e}, args: {args}, kwargs: {kwargs}"
                )
                return ErrorHandler.handle_error_static(e, f"Execution {func.__name__}")

        return cast(F, async_wrapper)
    else:

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"Error occurred in {func.__name__}: {e}, args: {args}, kwargs: {kwargs}"
                )
                return ErrorHandler.handle_error_static(e, f"Execution {func.__name__}")

        return cast(F, sync_wrapper)


class ErrorHandler:
    """Error handling class."""

    # Define error codes
    ERROR_CODES = {
        "PERMISSION_DENIED": 403,
        "INVALID_PARAMS": 400,
        "NOT_FOUND": 404,
        "INTERNAL_ERROR": 500,
        "TIMEOUT": 408,
        "CONNECTION_ERROR": 503,
        "HOST_UNREACHABLE": 503,
        "SSH_AUTH_FAILED": 401,
        "HIGH_RISK_COMMAND": 403,
        "FILE_NOT_FOUND": 404,
        "PYTHON_INSTALL_FAILED": 500,
        "TSC_TOOLS_INSTALL_FAILED": 500,
    }

    def __init__(self):
        """Initialize error handler."""
        self.logger = logger

    def handle_error(self, exception: Exception, context: str = "") -> Dict[str, Any]:
        """Handle exception and return unified error response."""
        if isinstance(exception, PermissionError):
            self.logger.exception(f"{context} Permission error: {exception}")
            return self.permission_denied(
                f"{context} Insufficient permission: {str(exception)}"
            )
        elif isinstance(exception, ValueError):
            self.logger.exception(f"{context} Parameter error: {exception}")
            return self.invalid_params(f"{context} Invalid parameter: {str(exception)}")
        elif isinstance(exception, FileNotFoundError):
            self.logger.exception(f"{context} Resource not found error: {exception}")
            return self.file_not_found(
                f"{context} Resource not found: {str(exception)}"
            )
        elif isinstance(exception, TimeoutError):
            self.logger.exception(f"{context} Timeout error: {exception}")
            return self.timeout(f"{context} Operation timed out: {str(exception)}")
        elif isinstance(exception, ConnectionError):
            self.logger.exception(f"{context} Connection error: {exception}")
            return self.connection_error(
                f"{context} Connection failed: {str(exception)}"
            )
        else:
            self.logger.exception(f"{context} Error occurred: {exception}")
            return create_error_response(
                "INTERNAL_ERROR", f"{context} Execution failed: {str(exception)}"
            )

    @classmethod
    def permission_denied(
        cls, message: str = "Insufficient permission"
    ) -> Dict[str, Any]:
        """Return permission error response."""
        return create_error_response("PERMISSION_DENIED", message)

    @classmethod
    def invalid_params(cls, message: str = "Invalid parameter") -> Dict[str, Any]:
        """Return parameter error response."""
        return create_error_response("INVALID_PARAMS", message)

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> Dict[str, Any]:
        """Return resource not found error response."""
        return create_error_response("NOT_FOUND", message)

    @classmethod
    def timeout(cls, message: str = "Operation timed out") -> Dict[str, Any]:
        """Return timeout error response."""
        return create_error_response("TIMEOUT", message)

    @classmethod
    def connection_error(cls, message: str = "Connection failed") -> Dict[str, Any]:
        """Return connection error response."""
        return create_error_response("CONNECTION_ERROR", message)

    @classmethod
    def host_unreachable(cls, message: str = "Host unreachable") -> Dict[str, Any]:
        """Return host unreachable error response."""
        return create_error_response("HOST_UNREACHABLE", message)

    @classmethod
    def ssh_auth_failed(
        cls, message: str = "SSH authentication failed"
    ) -> Dict[str, Any]:
        """Return SSH authentication failed error response."""
        return create_error_response("SSH_AUTH_FAILED", message)

    @classmethod
    def high_risk_command(
        cls, message: str = "High-risk command blocked"
    ) -> Dict[str, Any]:
        """Return high-risk command error response."""
        return create_error_response("HIGH_RISK_COMMAND", message)

    @classmethod
    def file_not_found(cls, message: str = "File not found") -> Dict[str, Any]:
        """Return file not found error response."""
        return create_error_response("FILE_NOT_FOUND", message)

    @classmethod
    def python_install_failed(
        cls, message: str = "Python installation failed"
    ) -> Dict[str, Any]:
        """Return Python installation failed error response."""
        return create_error_response("PYTHON_INSTALL_FAILED", message)

    @classmethod
    def tsc_tools_install_failed(
        cls, message: str = "tsc_tools installation failed"
    ) -> Dict[str, Any]:
        """Return tsc_tools installation failed error response."""
        return create_error_response("TSC_TOOLS_INSTALL_FAILED", message)

    @staticmethod
    def handle_error_static(exception: Exception, context: str = "") -> Dict[str, Any]:
        """Static method: Handle exception and return unified error response."""
        handler = ErrorHandler()
        return handler.handle_error(exception, context)
