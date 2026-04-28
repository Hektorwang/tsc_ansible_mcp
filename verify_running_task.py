"""
Verification script for task 4.1.4: Running task error handling
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, '.')

from lib.mcp_tools.task_results import register_task_results_tools
from lib.task_result_store import TaskResultStore


class MockServer:
    """Mock server for testing MCP tools."""
    
    def __init__(self, task_repo, execution_service):
        self.task_repo = task_repo
        self.execution_service = execution_service
        self.mcp = Mock()
        self.tools = {}
        
        # Mock the tool decorator
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


def test_running_task_handling():
    """Test that running tasks return proper error responses."""
    
    print("=" * 60)
    print("Testing Task 4.1.4: Running Task Error Handling")
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
        
        # Mock the permission decorator
        def mock_require_permission(permission_name):
            def decorator(func):
                return func
            return decorator
        
        # Patch the require_permission decorator
        import lib.mcp_tools.task_results as task_results_module
        original_require_permission = task_results_module.require_permission
        task_results_module.require_permission = mock_require_permission
        
        # Register tools
        register_task_results_tools(server)
        
        # Restore original decorator
        task_results_module.require_permission = original_require_permission
        
        # Add a running task
        task_id = "running-task-123"
        task_repo.add_task(task_id, {
            "task_id": task_id,
            "status": "running",
            "result": None
        })
        
        # Test 1: get_result with running task
        print("\n[Test 1] get_result with running task")
        print("-" * 60)
        get_result = server.tools["get_result"]
        result = get_result(task_id)
        
        print(f"Response: {result}")
        
        # Verify response format
        assert "task_id" in result, "Missing task_id in response"
        assert result["task_id"] == task_id, f"Wrong task_id: {result['task_id']}"
        assert "status" in result, "Missing status in response"
        assert result["status"] == "running", f"Wrong status: {result['status']}"
        assert "message" in result, "Missing message in response"
        
        # Verify polling guidance
        message = result["message"]
        assert "30-60 seconds" in message, "Missing polling interval guidance"
        assert "get_result" in message, "Missing get_result() mention"
        assert task_id in message, "Missing task_id in message"
        
        print("✓ Response has correct format")
        print(f"✓ Status is 'running'")
        print(f"✓ Message includes polling guidance: '{message}'")
        
        # Test 2: get_host_detail with running task
        print("\n[Test 2] get_host_detail with running task")
        print("-" * 60)
        get_host_detail = server.tools["get_host_detail"]
        result = get_host_detail(task_id, "192.168.1.1")
        
        print(f"Response: {result}")
        
        # Verify response format
        assert "task_id" in result, "Missing task_id in response"
        assert result["task_id"] == task_id, f"Wrong task_id: {result['task_id']}"
        assert "status" in result, "Missing status in response"
        assert result["status"] == "running", f"Wrong status: {result['status']}"
        assert "message" in result, "Missing message in response"
        
        # Verify wait guidance
        message = result["message"]
        assert "30-60 seconds" in message, "Missing wait interval guidance"
        assert "running" in message.lower() or "wait" in message.lower(), "Missing wait/running indication"
        
        print("✓ Response has correct format")
        print(f"✓ Status is 'running'")
        print(f"✓ Message includes wait guidance: '{message}'")
        
        # Test 3: Verify consistency across both tools
        print("\n[Test 3] Verify consistency")
        print("-" * 60)
        
        result1 = get_result(task_id)
        result2 = get_host_detail(task_id, "192.168.1.1")
        
        assert result1["status"] == result2["status"] == "running", "Inconsistent status"
        assert result1["task_id"] == result2["task_id"] == task_id, "Inconsistent task_id"
        
        print("✓ Both tools return consistent 'running' status")
        print("✓ Both tools include task_id in response")
        print("✓ Both tools provide polling/wait guidance")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! Task 4.1.4 is correctly implemented.")
        print("=" * 60)
        
        return True


if __name__ == "__main__":
    try:
        test_running_task_handling()
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
