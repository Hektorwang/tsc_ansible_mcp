"""
Verification script for task 4.1.3: Host not found error handling
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
import sys
sys.path.insert(0, '.')

from lib.task_result_store import TaskResultStore
from lib.mcp_tools.task_results import register_task_results_tools


class MockServer:
    """Mock server for testing."""
    
    def __init__(self, task_repo, execution_service):
        self.task_repo = task_repo
        self.execution_service = execution_service
        self.mcp = Mock()
        self.tools = {}
        
        def tool_decorator(name, description):
            def decorator(func):
                self.tools[name] = func
                return func
            return decorator
        
        self.mcp.tool = tool_decorator


class MockTaskRepo:
    """Mock task repository."""
    
    def __init__(self):
        self.tasks = {}
    
    def get(self, task_id):
        return self.tasks.get(task_id)
    
    def add_task(self, task_id, task_data):
        self.tasks[task_id] = task_data


class MockExecutionService:
    """Mock execution service."""
    
    def __init__(self, result_store):
        self.result_store = result_store


def test_host_not_found_error():
    """Test that host not found returns proper error format."""
    
    print("=" * 60)
    print("Testing Task 4.1.3: Host Not Found Error")
    print("=" * 60)
    
    # Setup
    with tempfile.TemporaryDirectory() as tmpdir:
        # Reset singleton
        TaskResultStore._instance = None
        TaskResultStore._initialized = False
        
        result_store = TaskResultStore(Path(tmpdir))
        task_repo = MockTaskRepo()
        execution_service = MockExecutionService(result_store)
        server = MockServer(task_repo, execution_service)
        
        # Mock permission decorator
        def mock_require_permission(permission_name):
            def decorator(func):
                return func
            return decorator
        
        import lib.mcp_tools.task_results as task_results_module
        original_require_permission = task_results_module.require_permission
        task_results_module.require_permission = mock_require_permission
        
        # Register tools
        register_task_results_tools(server)
        
        # Restore
        task_results_module.require_permission = original_require_permission
        
        # Create a sample task with results
        task_id = "test-task-123"
        task_data = {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "task_id": task_id,
                "status": "partial_success",
                "success_hosts": ["192.168.1.1", "192.168.1.2"],
                "results": {
                    "192.168.1.1": {
                        "rc": 0,
                        "stdout": "Success output",
                        "stderr": ""
                    },
                    "192.168.1.2": {
                        "rc": 0,
                        "stdout": "Another success",
                        "stderr": ""
                    },
                    "192.168.1.10": {
                        "rc": 1,
                        "stdout": "",
                        "stderr": "Command not found"
                    }
                }
            }
        }
        
        task_repo.add_task(task_id, task_data)
        result_store.save_result(task_id, task_data["result"])
        
        # Test 1: Query non-existent host
        print("\nTest 1: Query non-existent host")
        print("-" * 60)
        get_host_detail = server.tools["get_host_detail"]
        result = get_host_detail(task_id, "192.168.1.99")
        
        print(f"Input: task_id={task_id}, host=192.168.1.99")
        print(f"Output: {json.dumps(result, indent=2)}")
        
        # Verify response format
        assert "task_id" in result, "Missing task_id in response"
        assert "host" in result, "Missing host in response"
        assert "status" in result, "Missing status in response"
        assert "message" in result, "Missing message in response"
        
        assert result["task_id"] == task_id, f"Wrong task_id: {result['task_id']}"
        assert result["host"] == "192.168.1.99", f"Wrong host: {result['host']}"
        assert result["status"] == "not_found", f"Wrong status: {result['status']}"
        assert "not found" in result["message"].lower(), "Message doesn't indicate not found"
        assert "192.168.1.99" in result["message"], "Message doesn't include host"
        assert task_id in result["message"], "Message doesn't include task_id"
        
        print("\n✓ Response format is correct")
        print(f"✓ task_id: {result['task_id']}")
        print(f"✓ host: {result['host']}")
        print(f"✓ status: {result['status']}")
        print(f"✓ message: {result['message']}")
        
        # Test 2: Query existing host (should succeed)
        print("\nTest 2: Query existing host (should succeed)")
        print("-" * 60)
        result2 = get_host_detail(task_id, "192.168.1.10")
        
        print(f"Input: task_id={task_id}, host=192.168.1.10")
        print(f"Output: {json.dumps(result2, indent=2)}")
        
        assert result2["task_id"] == task_id
        assert result2["host"] == "192.168.1.10"
        assert result2["status"] == "failed"  # This host failed
        assert result2["rc"] == 1
        assert "Command not found" in result2["stderr"]
        
        print("\n✓ Existing host query works correctly")
        
        # Test 3: Query non-existent task
        print("\nTest 3: Query non-existent task")
        print("-" * 60)
        result3 = get_host_detail("non-existent-task", "192.168.1.1")
        
        print(f"Input: task_id=non-existent-task, host=192.168.1.1")
        print(f"Output: {json.dumps(result3, indent=2)}")
        
        assert result3["task_id"] == "non-existent-task"
        assert result3["status"] == "not_found"
        assert "not found" in result3["message"].lower()
        
        print("\n✓ Non-existent task handled correctly")
        
        print("\n" + "=" * 60)
        print("All tests passed! Task 4.1.3 is correctly implemented.")
        print("=" * 60)


if __name__ == "__main__":
    try:
        test_host_not_found_error()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
