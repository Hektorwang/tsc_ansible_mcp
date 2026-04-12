import pytest
import asyncio
from lib.error_handler import ErrorHandler, create_error_response, error_handler


class TestErrorHandler:
    """测试错误处理模块"""

    def test_create_error_response(self):
        """测试创建错误响应"""
        error = create_error_response("PERMISSION_DENIED", "权限不足")
        assert error["status"] == "error"
        assert error["code"] == "PERMISSION_DENIED"
        assert error["message"] == "权限不足"

        # 测试带额外参数的错误响应
        error = create_error_response("INVALID_PARAMS", "参数无效", field="username")
        assert error["status"] == "error"
        assert error["code"] == "INVALID_PARAMS"
        assert error["message"] == "参数无效"
        assert error["field"] == "username"

    def test_error_handler(self):
        """测试错误处理装饰器"""
        @error_handler
        def test_func():
            raise ValueError("测试错误")

        result = test_func()
        assert result["status"] == "error"
        assert result["code"] == "INVALID_PARAMS"
        assert "测试错误" in result["message"]

    def test_error_handler_success(self):
        """测试错误处理装饰器（成功情况）"""
        @error_handler
        def test_func():
            return {"status": "success", "message": "操作成功"}

        result = test_func()
        assert result["status"] == "success"
        assert result["message"] == "操作成功"

    def test_error_handler_handle_error(self):
        """测试 ErrorHandler.handle_error 方法"""
        try:
            raise ValueError("测试异常")
        except Exception as e:
            result = ErrorHandler.handle_error_static(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "INVALID_PARAMS"
            assert "测试操作" in result["message"]
            assert "测试异常" in result["message"]

    def test_error_handler_permission_denied(self):
        """测试 ErrorHandler.permission_denied 方法"""
        result = ErrorHandler.permission_denied()
        assert result["status"] == "error"
        assert result["code"] == "PERMISSION_DENIED"
        assert result["message"] == "权限不足"

        # 测试自定义消息
        result = ErrorHandler.permission_denied("无权访问此资源")
        assert result["status"] == "error"
        assert result["code"] == "PERMISSION_DENIED"
        assert result["message"] == "无权访问此资源"

    def test_error_handler_invalid_params(self):
        """测试 ErrorHandler.invalid_params 方法"""
        result = ErrorHandler.invalid_params()
        assert result["status"] == "error"
        assert result["code"] == "INVALID_PARAMS"
        assert result["message"] == "参数无效"

        # 测试自定义消息
        result = ErrorHandler.invalid_params("用户名不能为空")
        assert result["status"] == "error"
        assert result["code"] == "INVALID_PARAMS"
        assert result["message"] == "用户名不能为空"

    def test_error_handler_not_found(self):
        """测试 ErrorHandler.not_found 方法"""
        result = ErrorHandler.not_found()
        assert result["status"] == "error"
        assert result["code"] == "NOT_FOUND"
        assert result["message"] == "资源不存在"

        # 测试自定义消息
        result = ErrorHandler.not_found("用户不存在")
        assert result["status"] == "error"
        assert result["code"] == "NOT_FOUND"
        assert result["message"] == "用户不存在"

    def test_error_handler_timeout(self):
        """测试 ErrorHandler.timeout 方法"""
        result = ErrorHandler.timeout()
        assert result["status"] == "error"
        assert result["code"] == "TIMEOUT"
        assert result["message"] == "操作超时"

        # 测试自定义消息
        result = ErrorHandler.timeout("请求超时，请重试")
        assert result["status"] == "error"
        assert result["code"] == "TIMEOUT"
        assert result["message"] == "请求超时，请重试"



    def test_error_handler_async_wrapper(self):
        """测试异步函数错误处理（通过同步包装）"""
        async def run_async_test():
            @error_handler
            async def test_async_func():
                raise ValueError("测试异步错误")

            result = await test_async_func()
            assert result["status"] == "error"
            assert result["code"] == "INVALID_PARAMS"
            assert "测试异步错误" in result["message"]

        asyncio.run(run_async_test())

    def test_error_handler_with_extra_params(self):
        """测试带额外参数的错误响应"""
        error = create_error_response("INVALID_PARAMS", "参数无效", field="username", value="test")
        assert error["status"] == "error"
        assert error["code"] == "INVALID_PARAMS"
        assert error["message"] == "参数无效"
        assert error["field"] == "username"
        assert error["value"] == "test"
        assert error["http_status"] == 400

    def test_error_handler_different_exceptions(self):
        """测试不同类型的异常处理"""
        # 测试PermissionError
        try:
            raise PermissionError("权限被拒绝")
        except Exception as e:
            result = ErrorHandler.handle_error_static(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "PERMISSION_DENIED"
            assert "权限被拒绝" in result["message"]
            assert result["http_status"] == 403

        # 测试FileNotFoundError
        try:
            raise FileNotFoundError("文件不存在")
        except Exception as e:
            result = ErrorHandler.handle_error_static(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "NOT_FOUND"
            assert "文件不存在" in result["message"]
            assert result["http_status"] == 404

        # 测试TimeoutError
        try:
            raise TimeoutError("操作超时")
        except Exception as e:
            result = ErrorHandler.handle_error_static(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "TIMEOUT"
            assert "操作超时" in result["message"]
            assert result["http_status"] == 408

        # 测试通用Exception
        try:
            raise Exception("未知错误")
        except Exception as e:
            result = ErrorHandler.handle_error_static(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "INTERNAL_ERROR"
            assert "未知错误" in result["message"]
            assert result["http_status"] == 500

    def test_error_handler_instance_method(self):
        """测试ErrorHandler实例方法的使用"""
        handler = ErrorHandler()
        try:
            raise ValueError("测试异常")
        except Exception as e:
            result = handler.handle_error(e, "测试操作")
            assert result["status"] == "error"
            assert result["code"] == "INVALID_PARAMS"
            assert "测试操作" in result["message"]
            assert "测试异常" in result["message"]
            assert result["http_status"] == 400