import pytest
from lib.config import Config
from lib.task_result_store import TaskResultStore


class TestIntegration:
    """集成测试"""

    def test_config_and_task_result_store_integration(self):
        """测试配置和任务结果存储的集成"""
        # 测试配置加载
        config = Config()
        assert config.get("mcp.host") == "0.0.0.0"
        assert config.get("mcp.port") == 8500

        # 测试任务结果存储
        result_store = TaskResultStore()
        task_id = "test_integration_task"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""},
                "host2": {"rc": 1, "stdout": "", "stderr": "test error"}
            },
            "elapsed": 1.23
        }

        # 保存结果
        result_store.save_result(task_id, results)
        # 获取结果
        retrieved_results = result_store.get_result(task_id)
        assert retrieved_results == results
        # 删除结果
        deleted = result_store.delete_result(task_id)
        assert deleted
        # 确认结果已删除
        assert result_store.get_result(task_id) is None

