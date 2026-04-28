"""
Verification script for Task 4.1.5: Result file missing error handling.

Tests that when a task exists in the database but the result file is missing,
the system returns a proper error response with status="error".
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

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


def mock_require_permission(permission_name):
    """Mock permission decorator."""
    def decorator(func):
        return func
    return decorator


def test_result_file_missing():
    """Test that missing result file returns proper error."""
    print("=" * 70)
    print("Task 4.1.5 Verification: Result File Missing Error")
    print("=" * 70)
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Reset singleton
        TaskResultStore._instance = None
        TaskResultStore._initialized = False
        
        # Create components
        result_store = TaskResultStore(Path(tmpdir))
        task_repo = MockTaskRepo()
        execution_service = MockExecutionService(result_store)
        server = MockServer(task_repo, execution_service)
        
        # Patch the permission decorator
        import lib.mcp_tools.task_results as task_results_module
        original_require_permission = task_results_module.require_permission
        task_results_module.require_permission = mock_require_permission
        
        # Register tools
        register_task_results_tools(server)
        
        # Restore original decorator
        task_results_module.require_permission = original_require_permission
        
        # Get tools
        get_result = server.tools["get_result"]
        get_host_detail = server.tools["get_host_detail"]
        
        # Test 1: get_result with status="failed" and missing file
        print("\nTest 1: get_result with status='failed' and missing file")
        print("-" * 70)
        
        task_id = "task-missing-file-1"
        task_repo.add_task(task_id, {
            "task_id": task_id,
            "status": "completed",
            "result": {
                "status": "completed",
                "success_hosts": ["192.168.1.1"],
                "results": {
                    "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""},
                    "192.168.1.10": {"rc": 1, "stdout": "", "stderr": "error"}
                }
            }
        })
        
        # Do NOT save result to file - file will be missing
        result = get_result(task_id, status="failed")
        
        print(f"Task ID: {task_id}")
        print(f"Result: {result}")
        
        assert result["task_id"] == task_id, f"Expected task_id={task_id}, got {result.get('task_id')}"
        assert result["status"] == "error", f"Expected status='error', got {result.get('status')}"
        assert "message" in result, "Missing 'message' field"
        assert "missing" in result["message"].lower() or "not available" in result["message"].lower(), \
            f"Message should mention missing file: {result['message']}"
        
        print("✓ Test 1 PASSED: Correct error response for missing file with status='failed'")
        
        # Test 2: get_result with status="success" and missing file
        print("\nTest 2: get_result with status='success' and missing file")
        print("-" * 70)
        
        task_id2 = "task-missing-file-2"
        task_repo.add_task(task_id2, {
            "task_id": task_id2,
            "status": "completed",
            "result": {
                "status": "completed",
                "success_hosts": ["192.168.1.1"],
                "results": {
                    "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""}
                }
            }
        })
        
        result2 = get_result(task_id2, status="success")
        
        print(f"Task ID: {task_id2}")
        print(f"Result: {result2}")
        
        assert result2["task_id"] == task_id2, f"Expected task_id={task_id2}, got {result2.get('task_id')}"
        assert result2["status"] == "error", f"Expected status='error', got {result2.get('status')}"
        assert "message" in result2, "Missing 'message' field"
        
        print("✓ Test 2 PASSED: Correct error response for missing file with status='success'")
        
        # Test 3: get_host_detail with missing file
        print("\nTest 3: get_host_detail with missing file")
        print("-" * 70)
        
        task_id3 = "task-missing-file-3"
        task_repo.add_task(task_id3, {
            "task_id": task_id3,
            "status": "completed",
            "result": {
                "status": "completed",
                "success_hosts": ["192.168.1.1"],
                "results": {
                    "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""}
                }
            }
        })
        
        result3 = get_host_detail(task_id3, "192.168.1.1")
        
        print(f"Task ID: {task_id3}")
        print(f"Host: 192.168.1.1")
        print(f"Result: {result3}")
        
        assert result3["task_id"] == task_id3, f"Expected task_id={task_id3}, got {result3.get('task_id')}"
        assert result3["status"] == "error", f"Expected status='error', got {result3.get('status')}"
        assert "message" in result3, "Missing 'message' field"
        
        print("✓ Test 3 PASSED: Correct error response for get_host_detail with missing file")
        
        # Test 4: Summary mode should still work (reads from database)
        print("\nTest 4: Summary mode (status=None) should work with missing file")
        print("-" * 70)
        
        task_id4 = "task-missing-file-4"
        task_repo.add_task(task_id4, {
            "task_id": task_id4,
            "status": "completed",
            "result": {
                "status": "completed",
                "success_hosts": ["192.168.1.1", "192.168.1.2"],
                "results": {
                    "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""},
                    "192.168.1.2": {"rc": 0, "stdout": "ok", "stderr": ""},
                    "192.168.1.10": {"rc": 1, "stdout": "", "stderr": "error"}
                }
            }
        })
        
        result4 = get_result(task_id4)  # No status parameter = summary mode
        
        print(f"Task ID: {task_id4}")
        print(f"Result: {result4}")
        
        assert result4["task_id"] == task_id4, f"Expected task_id={task_id4}, got {result4.get('task_id')}"
        assert result4["status"] == "completed", f"Expected status='completed', got {result4.get('status')}"
        assert result4["total_hosts"] == 3, f"Expected total_hosts=3, got {result4.get('total_hosts')}"
        assert result4["success_count"] == 2, f"Expected success_count=2, got {result4.get('success_count')}"
        assert result4["failed_count"] == 1, f"Expected failed_count=1, got {result4.get('failed_count')}"
        
        print("✓ Test 4 PASSED: Summary mode works correctly (reads from database, not file)")
        
        # Test 5: Verify error response format consistency
        print("\nTest 5: Error response format consistency")
        print("-" * 70)
        
        # All error responses should have task_id, status, and message
        errors = [result, result2, result3]
        
        for i, error in enumerate(errors, 1):
            assert "task_id" in error, f"Error {i} missing task_id"
            assert "status" in error, f"Error {i} missing status"
            assert error["status"] == "error", f"Error {i} status should be 'error'"
            assert "message" in error, f"Error {i} missing message"
            assert len(error["message"]) > 20, f"Error {i} message too short"
        
        print("✓ Test 5 PASSED: All error responses follow consistent format")
        
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print("\nTask 4.1.5 Implementation Summary:")
        print("- get_result with status filter detects missing result files")
        print("- get_host_detail detects missing result files")
        print("- Error responses include task_id, status='error', and descriptive message")
        print("- Summary mode (status=None) still works (reads from database)")
        print("- All error responses follow consistent format")


if __name__ == "__main__":
    try:
        test_result_file_missing()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
