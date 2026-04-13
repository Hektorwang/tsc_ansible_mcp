"""
统一错误处理模块
"""

from functools import wraps
from typing import Any, Callable, Dict, TypeVar, cast

from lib.tsc_logger import get_logger

logger = get_logger()


# 定义错误响应格式
def create_error_response(code: str, message: str, **kwargs) -> Dict[str, Any]:
    """创建统一的错误响应格式"""
    return {
        "status": "error",
        "message": message,
        "code": code,
        "http_status": ErrorHandler.ERROR_CODES.get(code, 500),
        **kwargs,
    }


# 定义函数类型变量
F = TypeVar("F", bound=Callable[..., Any])


def error_handler(func: F) -> F:
    """统一错误处理装饰器"""
    import asyncio

    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"执行 {func.__name__} 时发生错误: {e}，参数: {args}, {kwargs}"
                )
                return ErrorHandler.handle_error_static(e, f"执行 {func.__name__}")

        return cast(F, async_wrapper)
    else:

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Dict[str, Any]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"执行 {func.__name__} 时发生错误: {e}，参数: {args}, {kwargs}"
                )
                return ErrorHandler.handle_error_static(e, f"执行 {func.__name__}")

        return cast(F, sync_wrapper)


class ErrorHandler:
    """错误处理类"""

    # 定义错误码
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
        """初始化错误处理器"""
        self.logger = logger

    def handle_error(self, exception: Exception, context: str = "") -> Dict[str, Any]:
        """处理异常并返回统一的错误响应"""
        if isinstance(exception, PermissionError):
            self.logger.exception(f"{context} 发生权限错误: {exception}")
            return self.permission_denied(f"{context} 权限不足: {str(exception)}")
        elif isinstance(exception, ValueError):
            self.logger.exception(f"{context} 发生参数错误: {exception}")
            return self.invalid_params(f"{context} 参数无效: {str(exception)}")
        elif isinstance(exception, FileNotFoundError):
            self.logger.exception(f"{context} 发生资源不存在错误: {exception}")
            return self.file_not_found(f"{context} 资源不存在: {str(exception)}")
        elif isinstance(exception, TimeoutError):
            self.logger.exception(f"{context} 发生超时错误: {exception}")
            return self.timeout(f"{context} 操作超时: {str(exception)}")
        elif isinstance(exception, ConnectionError):
            self.logger.exception(f"{context} 发生连接错误: {exception}")
            return self.connection_error(f"{context} 连接失败: {str(exception)}")
        else:
            self.logger.exception(f"{context} 发生错误: {exception}")
            return create_error_response(
                "INTERNAL_ERROR", f"{context} 执行失败: {str(exception)}"
            )

    @classmethod
    def permission_denied(cls, message: str = "权限不足") -> Dict[str, Any]:
        """返回权限错误响应"""
        return create_error_response("PERMISSION_DENIED", message)

    @classmethod
    def invalid_params(cls, message: str = "参数无效") -> Dict[str, Any]:
        """返回参数错误响应"""
        return create_error_response("INVALID_PARAMS", message)

    @classmethod
    def not_found(cls, message: str = "资源不存在") -> Dict[str, Any]:
        """返回资源不存在错误响应"""
        return create_error_response("NOT_FOUND", message)

    @classmethod
    def timeout(cls, message: str = "操作超时") -> Dict[str, Any]:
        """返回超时错误响应"""
        return create_error_response("TIMEOUT", message)

    @classmethod
    def connection_error(cls, message: str = "连接失败") -> Dict[str, Any]:
        """返回连接错误响应"""
        return create_error_response("CONNECTION_ERROR", message)

    @classmethod
    def host_unreachable(cls, message: str = "主机不可达") -> Dict[str, Any]:
        """返回主机不可达错误响应"""
        return create_error_response("HOST_UNREACHABLE", message)

    @classmethod
    def ssh_auth_failed(cls, message: str = "SSH 认证失败") -> Dict[str, Any]:
        """返回 SSH 认证失败错误响应"""
        return create_error_response("SSH_AUTH_FAILED", message)

    @classmethod
    def high_risk_command(cls, message: str = "高危命令被拦截") -> Dict[str, Any]:
        """返回高危命令错误响应"""
        return create_error_response("HIGH_RISK_COMMAND", message)

    @classmethod
    def file_not_found(cls, message: str = "文件不存在") -> Dict[str, Any]:
        """返回文件不存在错误响应"""
        return create_error_response("FILE_NOT_FOUND", message)

    @classmethod
    def python_install_failed(cls, message: str = "Python 安装失败") -> Dict[str, Any]:
        """返回 Python 安装失败错误响应"""
        return create_error_response("PYTHON_INSTALL_FAILED", message)

    @classmethod
    def tsc_tools_install_failed(
        cls, message: str = "tsc_tools 安装失败"
    ) -> Dict[str, Any]:
        """返回 tsc_tools 安装失败错误响应"""
        return create_error_response("TSC_TOOLS_INSTALL_FAILED", message)

    @staticmethod
    def handle_error_static(exception: Exception, context: str = "") -> Dict[str, Any]:
        """静态方法：处理异常并返回统一的错误响应"""
        handler = ErrorHandler()
        return handler.handle_error(exception, context)
