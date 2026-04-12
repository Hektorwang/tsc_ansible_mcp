import pytest
from unittest.mock import Mock, patch
from lib.execution_service import ExecutionService


class TestExecutionService:
    """测试 ExecutionService 类"""

    def setup_method(self):
        """设置测试环境"""
        self.executor = Mock()
        self.task_repo = Mock()
        self.logger = Mock()
        self.execution_service = ExecutionService(self.executor, self.task_repo, self.logger)

    def test_execute_shell(self):
        """测试执行 shell 命令"""
        # 模拟 executor.ansible_shell 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"rc": 0, "stdout": "test output"}}
        }
        self.executor.ansible_shell.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.execute_shell(
            targets=["192.168.1.1"],
            command="echo test",
            credentials={"user": "root"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.ansible_shell.assert_called_once()
        self.task_repo.update.assert_called()

    def test_check_host_status(self):
        """测试检查主机状态"""
        # 模拟 executor.check_host_status 的返回值
        expected_result = {
            "task_id": "test_task",
            "results": {"192.168.1.1": {"python_installed": True}}
        }
        self.executor.check_host_status.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.check_host_status(
            targets=["192.168.1.1"],
            credentials={"user": "root"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.check_host_status.assert_called_once()
        self.task_repo.update.assert_called()

    def test_install_python(self):
        """测试安装 Python"""
        # 模拟 executor.install_python 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"installed": True}}
        }
        self.executor.install_python.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.install_python(
            targets=["192.168.1.1"],
            credentials={"user": "root"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.install_python.assert_called_once()
        self.task_repo.update.assert_called()

    def test_install_tsc_tools(self):
        """测试安装 tsc_tools"""
        # 模拟 executor.install_tsc_tools 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"installed": True}}
        }
        self.executor.install_tsc_tools.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.install_tsc_tools(
            targets=["192.168.1.1"],
            credentials={"user": "root"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.install_tsc_tools.assert_called_once()
        self.task_repo.update.assert_called()

    def test_ansible_copy(self):
        """测试 ansible copy 模块"""
        # 模拟 executor.ansible_copy 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"changed": True}}
        }
        self.executor.ansible_copy.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.ansible_copy(
            targets=["192.168.1.1"],
            src="/local/file",
            dest="/remote/file",
            credentials={"user": "root"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.ansible_copy.assert_called_once()
        self.task_repo.update.assert_called()

    def test_ansible_fetch(self):
        """测试 ansible fetch 模块"""
        # 模拟 executor.ansible_fetch 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"changed": True}}
        }
        self.executor.ansible_fetch.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.ansible_fetch(
            targets=["192.168.1.1"],
            src="/remote/file",
            dest="/local/file",
            credentials={"user": "root"},
            flat=False,
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.ansible_fetch.assert_called_once()
        self.task_repo.update.assert_called()

    def test_execute_playbook(self):
        """测试执行 playbook"""
        # 模拟 executor.run_playbook 的返回值
        expected_result = {
            "task_id": "test_task",
            "status": "success",
            "results": {"192.168.1.1": {"rc": 0}}
        }
        self.executor.run_playbook.return_value = expected_result
        
        # 执行测试
        result = self.execution_service.execute_playbook(
            playbook="test.yml",
            targets=["192.168.1.1"],
            credentials={"user": "root"},
            extravars={"var": "value"},
            timeout=60,
            task_id="test_task"
        )
        
        # 验证结果
        assert result == expected_result
        self.executor.run_playbook.assert_called_once()
        self.task_repo.update.assert_called()
