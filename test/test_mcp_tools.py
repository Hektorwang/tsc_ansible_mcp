import pytest
from unittest.mock import Mock, patch
from lib.mcp_tools.ansible_shell import register_ansible_shell
from lib.mcp_tools.task_results import register_task_results_tools


class TestMcpTools:
    """测试 MCP 工具模块"""

    def setup_method(self):
        """设置测试环境"""
        self.server = Mock()
        self.server.execution_service = Mock()
        self.server.task_repo = Mock()
        self.server.mcp = Mock()
        self.server.mcp.tool = Mock(return_value=lambda func: func)

    def test_register_ansible_shell(self):
        """测试注册 ansible_shell 工具"""
        # 模拟 execution_service.execute_shell 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"rc": 0, "stdout": "test output"}}
        }
        self.server.execution_service.execute_shell.return_value = expected_result
        
        # 注册工具
        register_ansible_shell(self.server)
        
        # 验证工具是否注册成功
        self.server.mcp.tool.assert_called_once()

    def test_register_task_results_tools(self):
        """测试注册任务结果相关工具"""
        # 模拟 task_result_store
        with patch('lib.mcp_tools.task_results.task_result_store') as mock_store:
            # 模拟 get_host_result 的返回值
            mock_store.get_host_result.return_value = {"rc": 0, "stdout": "test output"}
            # 模拟 get_failed_hosts 的返回值
            mock_store.get_failed_hosts.return_value = {"failed_hosts": []}
            # 模拟 get_all_results 的返回值
            mock_store.get_all_results.return_value = {"results": []}
            
            # 注册工具
            register_task_results_tools(self.server)
            
            # 验证工具是否注册成功
            assert self.server.mcp.tool.called
            assert self.server.mcp.tool.call_count == 3
