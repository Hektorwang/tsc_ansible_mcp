#!/usr/bin/env python3
"""
Task 4.2.1 & 4.2.2 Verification Script

This script verifies that all error responses in get_result and get_host_detail:
1. Follow the unified error response format
2. Include task_id field in all error messages
3. Have descriptive and consistent error messages

Tests all error scenarios:
- Task not found
- Invalid status parameter
- Host not found
- Task still running
- Result file missing
"""

import sys
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.task_result_store import TaskResultStore
from lib.database import TaskRepository


class MockServer:
    """Mock server for testing"""
    def __init__(self):
        self.task_repo = TaskRepository()
        self.execution_service = type('obj', (object,), {
            'result_store': TaskResultStore()
        })()


def verify_error_response_format(response: dict, scenario: str) -> list:
    """Verify error response has correct format"""
    errors = []
    
    # Check required fields
    if "task_id" not in response:
        errors.append(f"{scenario}: Missing 'task_id' field")
    
    if "status" not in response:
        errors.append(f"{scenario}: Missing 'status' field")
    
    if "message" not in response:
        errors.append(f"{scenario}: Missing 'message' field")
    
    # Check status value
    if "status" in response:
        valid_statuses = ["error", "not_found", "running"]
        if response["status"] not in valid_statuses:
            errors.append(f"{scenario}: Invalid status '{response['status']}', expected one of {valid_statuses}")
    
    # Check message is descriptive
    if "message" in response:
        if len(response["message"]) < 10:
            errors.append(f"{scenario}: Message too short (< 10 chars): '{response['message']}'")
    
    return errors


def test_get_result_errors():
    """Test all error scenarios in get_result"""
    print("\n=== Testing get_result Error Responses ===\n")
    
    from lib.mcp_tools.task_results import register_task_results_tools
    
    mock_server = MockServer()
    
    # Create a mock MCP server with tool registration
    class MCPServer:
        def __init__(self):
            self.tools = {}
        
        def tool(self, name, description):
            def decorator(func):
                self.tools[name] = func
                return func
            return decorator
    
    mock_server.mcp = MCPServer()
    register_task_results_tools(mock_server)
    
    get_result = mock_server.mcp.tools["get_result"]
    get_host_detail = mock_server.mcp.tools["get_host_detail"]
    
    all_errors = []
    test_results = []
    
    # Test 1: Task not found
    print("Test 1: Task not found")
    result1 = get_result("non-existent-task-123")
    print(f"  Response: {json.dumps(result1, indent=2)}")
    errors1 = verify_error_response_format(result1, "Task not found")
    if errors1:
        all_errors.extend(errors1)
        test_results.append(("Task not found", "FAIL", errors1))
    else:
        test_results.append(("Task not found", "PASS", []))
    
    # Test 2: Invalid status parameter
    print("\nTest 2: Invalid status parameter")
    # First create a task
    task_id = "test-task-invalid-status"
    mock_server.task_repo.create(
        task_id=task_id,
        tool_name="test_tool",
        params={"test": "data"}
    )
    mock_server.task_repo.update_status(task_id, "completed")
    mock_server.task_repo.save_result(task_id, {
        "status": "completed",
        "results": {},
        "success_hosts": []
    })
    
    result2 = get_result(task_id, status="invalid_status")
    print(f"  Response: {json.dumps(result2, indent=2)}")
    errors2 = verify_error_response_format(result2, "Invalid status parameter")
    if errors2:
        all_errors.extend(errors2)
        test_results.append(("Invalid status parameter", "FAIL", errors2))
    else:
        test_results.append(("Invalid status parameter", "PASS", []))
    
    # Test 3: Task not found with status filter
    print("\nTest 3: Task not found with status filter")
    result3 = get_result("non-existent-task-456", status="failed")
    print(f"  Response: {json.dumps(result3, indent=2)}")
    errors3 = verify_error_response_format(result3, "Task not found (with status)")
    if errors3:
        all_errors.extend(errors3)
        test_results.append(("Task not found (with status)", "FAIL", errors3))
    else:
        test_results.append(("Task not found (with status)", "PASS", []))
    
    # Test 4: Result file missing
    print("\nTest 4: Result file missing")
    task_id_missing = "test-task-missing-file"
    mock_server.task_repo.create(
        task_id=task_id_missing,
        tool_name="test_tool",
        params={"test": "data"}
    )
    mock_server.task_repo.update_status(task_id_missing, "completed")
    mock_server.task_repo.save_result(task_id_missing, {
        "status": "completed",
        "results": {},
        "success_hosts": []
    })
    # Don't create result file - it's missing
    
    result4 = get_result(task_id_missing, status="failed")
    print(f"  Response: {json.dumps(result4, indent=2)}")
    errors4 = verify_error_response_format(result4, "Result file missing")
    if errors4:
        all_errors.extend(errors4)
        test_results.append(("Result file missing", "FAIL", errors4))
    else:
        test_results.append(("Result file missing", "PASS", []))
    
    return test_results, all_errors


def test_get_host_detail_errors():
    """Test all error scenarios in get_host_detail"""
    print("\n=== Testing get_host_detail Error Responses ===\n")
    
    from lib.mcp_tools.task_results import register_task_results_tools
    
    mock_server = MockServer()
    
    # Create a mock MCP server with tool registration
    class MCPServer:
        def __init__(self):
            self.tools = {}
        
        def tool(self, name, description):
            def decorator(func):
                self.tools[name] = func
                return func
            return decorator
    
    mock_server.mcp = MCPServer()
    register_task_results_tools(mock_server)
    
    get_host_detail = mock_server.mcp.tools["get_host_detail"]
    
    all_errors = []
    test_results = []
    
    # Test 1: Task not found
    print("Test 1: Task not found")
    result1 = get_host_detail("non-existent-task-789", "192.168.1.1")
    print(f"  Response: {json.dumps(result1, indent=2)}")
    errors1 = verify_error_response_format(result1, "get_host_detail: Task not found")
    if errors1:
        all_errors.extend(errors1)
        test_results.append(("Task not found", "FAIL", errors1))
    else:
        test_results.append(("Task not found", "PASS", []))
    
    # Test 2: Host not found
    print("\nTest 2: Host not found")
    task_id = "test-task-host-not-found"
    mock_server.task_repo.create(
        task_id=task_id,
        tool_name="test_tool",
        params={"test": "data"}
    )
    mock_server.task_repo.update_status(task_id, "completed")
    mock_server.task_repo.save_result(task_id, {
        "status": "completed",
        "results": {
            "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""}
        },
        "success_hosts": ["192.168.1.1"]
    })
    
    # Save result file
    mock_server.execution_service.result_store.save_result(task_id, {
        "status": "completed",
        "results": {
            "192.168.1.1": {"rc": 0, "stdout": "ok", "stderr": ""}
        },
        "success_hosts": ["192.168.1.1"]
    })
    
    result2 = get_host_detail(task_id, "192.168.1.99")
    print(f"  Response: {json.dumps(result2, indent=2)}")
    errors2 = verify_error_response_format(result2, "get_host_detail: Host not found")
    if errors2:
        all_errors.extend(errors2)
        test_results.append(("Host not found", "FAIL", errors2))
    else:
        test_results.append(("Host not found", "PASS", []))
    
    # Test 3: Result file missing
    print("\nTest 3: Result file missing")
    task_id_missing = "test-task-missing-file-2"
    mock_server.task_repo.create(
        task_id=task_id_missing,
        tool_name="test_tool",
        params={"test": "data"}
    )
    mock_server.task_repo.update_status(task_id_missing, "completed")
    mock_server.task_repo.save_result(task_id_missing, {
        "status": "completed",
        "results": {},
        "success_hosts": []
    })
    # Don't create result file
    
    result3 = get_host_detail(task_id_missing, "192.168.1.1")
    print(f"  Response: {json.dumps(result3, indent=2)}")
    errors3 = verify_error_response_format(result3, "get_host_detail: Result file missing")
    if errors3:
        all_errors.extend(errors3)
        test_results.append(("Result file missing", "FAIL", errors3))
    else:
        test_results.append(("Result file missing", "PASS", []))
    
    # Test 4: Task still running
    print("\nTest 4: Task still running")
    task_id_running = "test-task-running"
    mock_server.task_repo.create(
        task_id=task_id_running,
        tool_name="test_tool",
        params={"test": "data"}
    )
    mock_server.task_repo.update_status(task_id_running, "running")
    
    result4 = get_host_detail(task_id_running, "192.168.1.1")
    print(f"  Response: {json.dumps(result4, indent=2)}")
    errors4 = verify_error_response_format(result4, "get_host_detail: Task running")
    if errors4:
        all_errors.extend(errors4)
        test_results.append(("Task running", "FAIL", errors4))
    else:
        test_results.append(("Task running", "PASS", []))
    
    return test_results, all_errors


def print_summary(get_result_results, get_host_detail_results, all_errors):
    """Print test summary"""
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    print("\nget_result Error Response Tests:")
    for test_name, status, errors in get_result_results:
        print(f"  [{status}] {test_name}")
        if errors:
            for error in errors:
                print(f"        - {error}")
    
    print("\nget_host_detail Error Response Tests:")
    for test_name, status, errors in get_host_detail_results:
        print(f"  [{status}] {test_name}")
        if errors:
            for error in errors:
                print(f"        - {error}")
    
    total_tests = len(get_result_results) + len(get_host_detail_results)
    passed_tests = sum(1 for _, status, _ in get_result_results + get_host_detail_results if status == "PASS")
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    
    if all_errors:
        print("\n" + "="*70)
        print("ISSUES FOUND:")
        print("="*70)
        for error in all_errors:
            print(f"  - {error}")
        return False
    else:
        print("\n" + "="*70)
        print("✓ ALL TESTS PASSED")
        print("="*70)
        print("\nVerification Results:")
        print("  ✓ All error responses include task_id field")
        print("  ✓ All error responses have proper status field")
        print("  ✓ All error responses have descriptive messages")
        print("  ✓ Error response format is consistent")
        return True


def main():
    """Main verification function"""
    print("="*70)
    print("Task 4.2.1 & 4.2.2 Verification")
    print("Verifying all error responses include task_id and follow unified format")
    print("="*70)
    
    try:
        # Test get_result errors
        get_result_results, get_result_errors = test_get_result_errors()
        
        # Test get_host_detail errors
        get_host_detail_results, get_host_detail_errors = test_get_host_detail_errors()
        
        # Combine all errors
        all_errors = get_result_errors + get_host_detail_errors
        
        # Print summary
        success = print_summary(get_result_results, get_host_detail_results, all_errors)
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
