import os
import tempfile
import shutil
from pathlib import Path
import pytest
from lib.task_result_store import TaskResultStore


class TestTaskResultStore:
    """测试 TaskResultStore 类"""

    def setup_method(self):
        """设置测试环境"""
        self.temp_dir = tempfile.mkdtemp()
        self.result_store = TaskResultStore(Path(self.temp_dir))

    def teardown_method(self):
        """清理测试环境"""
        shutil.rmtree(self.temp_dir)

    def test_save_result(self):
        """测试保存结果"""
        task_id = "test_task_1"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""},
                "host2": {"rc": 1, "stdout": "", "stderr": "test error"}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        result_path = self.result_store._get_result_path(task_id)
        assert result_path.exists()

    def test_get_result(self):
        """测试获取结果"""
        task_id = "test_task_2"
        expected_results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, expected_results)
        actual_results = self.result_store.get_result(task_id)
        assert actual_results == expected_results

    def test_get_host_result(self):
        """测试获取特定主机结果"""
        task_id = "test_task_3"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""},
                "host2": {"rc": 1, "stdout": "", "stderr": "test error"}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        host_result = self.result_store.get_host_result(task_id, "host1")
        assert host_result == results["results"]["host1"]

    def test_get_failed_hosts(self):
        """测试获取失败主机结果"""
        task_id = "test_task_4"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""},
                "host2": {"rc": 1, "stdout": "", "stderr": "test error"},
                "host3": {"rc": 2, "stdout": "", "stderr": "another error"}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        failed_hosts = self.result_store.get_failed_hosts(task_id)
        assert len(failed_hosts["failed_hosts"]) == 2
        assert "host2" in failed_hosts["failed_hosts"]
        assert "host3" in failed_hosts["failed_hosts"]

    def test_get_all_results(self):
        """测试获取所有主机结果"""
        task_id = "test_task_5"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""},
                "host2": {"rc": 1, "stdout": "", "stderr": "test error"}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        all_results = self.result_store.get_all_results(task_id)
        assert len(all_results["results"]) == 2
        assert "host1" in all_results["results"]
        assert "host2" in all_results["results"]

    def test_delete_result(self):
        """测试删除结果"""
        task_id = "test_task_6"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        result_path = self.result_store._get_result_path(task_id)
        assert result_path.exists()

        deleted = self.result_store.delete_result(task_id)
        assert deleted
        assert not result_path.exists()

    def test_list_old_results(self):
        """测试列出旧结果"""
        task_id = "test_task_7"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        old_tasks = self.result_store.list_old_results(days=0)
        assert task_id in old_tasks

    def test_cleanup_old_results(self):
        """测试清理旧结果"""
        task_id = "test_task_8"
        results = {
            "results": {
                "host1": {"rc": 0, "stdout": "test output", "stderr": ""}
            },
            "elapsed": 1.23
        }

        self.result_store.save_result(task_id, results)
        deleted = self.result_store.cleanup_old_results(days=0)
        assert deleted == 1
        result_path = self.result_store._get_result_path(task_id)
        assert not result_path.exists()
