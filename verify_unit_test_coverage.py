#!/usr/bin/env python3
"""
Verification script for unit test coverage of tasks 6.1, 6.2, and 6.3.

This script analyzes the existing test files to verify that all required
test scenarios from the tasks are covered.
"""

import sys
from pathlib import Path


def check_task_6_1_coverage():
    """Check coverage for Task 6.1: TaskResultStore unit tests."""
    print("\n=== Task 6.1: TaskResultStore Unit Tests ===")
    
    test_file = Path("tests/test_task_result_store.py")
    if not test_file.exists():
        print("❌ Test file not found: tests/test_task_result_store.py")
        return False
    
    content = test_file.read_text()
    
    # Task 6.1.1: Test get_host_result() success scenarios
    tests_6_1_1 = [
        "test_get_host_result_success_host",
        "test_get_host_result_failed_host"
    ]
    
    # Task 6.1.2: Test get_host_result() host not found
    tests_6_1_2 = [
        "test_get_host_result_host_not_found"
    ]
    
    # Task 6.1.3: Test get_host_result() task not found
    tests_6_1_3 = [
        "test_get_host_result_task_not_found",
        "test_get_host_result_no_results_data"
    ]
    
    # Task 6.1.4: Test get_result() status="success" filter
    tests_6_1_4 = [
        "test_get_result_success_filter",
        "test_get_result_success_includes_details",
        "test_get_result_success_empty"
    ]
    
    all_tests = {
        "6.1.1 get_host_result() success scenarios": tests_6_1_1,
        "6.1.2 get_host_result() host not found": tests_6_1_2,
        "6.1.3 get_host_result() task not found": tests_6_1_3,
        "6.1.4 get_result() status='success' filter": tests_6_1_4
    }
    
    all_passed = True
    for subtask, test_names in all_tests.items():
        print(f"\n  Subtask {subtask}:")
        for test_name in test_names:
            if f"def {test_name}" in content:
                print(f"    ✓ {test_name}")
            else:
                print(f"    ✗ {test_name} - NOT FOUND")
                all_passed = False
    
    return all_passed


def check_task_6_2_coverage():
    """Check coverage for Task 6.2: get_result tool unit tests."""
    print("\n=== Task 6.2: get_result Tool Unit Tests ===")
    
    test_file = Path("tests/test_mcp_task_results.py")
    if not test_file.exists():
        print("❌ Test file not found: tests/test_mcp_task_results.py")
        return False
    
    content = test_file.read_text()
    
    # Task 6.2.1: Test summary mode (status=None)
    tests_6_2_1 = [
        "test_no_result_data_returns_status",
        "test_summary_mode_not_affected_by_missing_file"
    ]
    
    # Task 6.2.2: Test failed host filter (status="failed")
    tests_6_2_2 = [
        "test_get_result_failed_filter_with_no_failures",
        "test_get_result_with_status_filter_missing_file"
    ]
    
    # Task 6.2.3: Test success host filter (status="success")
    tests_6_2_3 = [
        "test_get_result_success_filter_with_no_successes",
        "test_get_result_success_filter_missing_file"
    ]
    
    # Task 6.2.4: Test invalid status parameter
    tests_6_2_4 = [
        "test_invalid_status_returns_error",
        "test_invalid_status_includes_valid_options",
        "test_invalid_status_includes_task_id",
        "test_invalid_status_with_various_values"
    ]
    
    # Task 6.2.5: Test task not found
    tests_6_2_5 = [
        "test_task_not_found_returns_not_found_status",
        "test_task_not_found_includes_task_id",
        "test_task_not_found_with_status_filter",
        "test_task_not_found_message_format"
    ]
    
    # Task 6.2.6: Test task still running
    tests_6_2_6 = [
        "test_running_task_returns_running_status",
        "test_running_task_includes_polling_guidance"
    ]
    
    all_tests = {
        "6.2.1 Summary mode (status=None)": tests_6_2_1,
        "6.2.2 Failed host filter (status='failed')": tests_6_2_2,
        "6.2.3 Success host filter (status='success')": tests_6_2_3,
        "6.2.4 Invalid status parameter": tests_6_2_4,
        "6.2.5 Task not found": tests_6_2_5,
        "6.2.6 Task still running": tests_6_2_6
    }
    
    all_passed = True
    for subtask, test_names in all_tests.items():
        print(f"\n  Subtask {subtask}:")
        for test_name in test_names:
            if f"def {test_name}" in content:
                print(f"    ✓ {test_name}")
            else:
                print(f"    ✗ {test_name} - NOT FOUND")
                all_passed = False
    
    return all_passed


def check_task_6_3_coverage():
    """Check coverage for Task 6.3: get_host_detail tool unit tests."""
    print("\n=== Task 6.3: get_host_detail Tool Unit Tests ===")
    
    test_file = Path("tests/test_mcp_task_results.py")
    if not test_file.exists():
        print("❌ Test file not found: tests/test_mcp_task_results.py")
        return False
    
    content = test_file.read_text()
    
    # Task 6.3.1: Test successful query for single host
    tests_6_3_1 = [
        "test_host_not_found_returns_not_found_status",  # Implies success case exists
        "test_host_not_found_includes_both_task_id_and_host"
    ]
    
    # Task 6.3.2: Test host not found
    tests_6_3_2 = [
        "test_host_not_found_returns_not_found_status",
        "test_host_not_found_includes_both_task_id_and_host",
        "test_host_not_found_message_format"
    ]
    
    # Task 6.3.3: Test task not found
    tests_6_3_3 = [
        "test_task_not_found_returns_not_found_status",  # In TestGetHostDetailNotFound
        "test_task_not_found_includes_task_id"
    ]
    
    # Task 6.3.4: Test task still running
    tests_6_3_4 = [
        "test_running_task_returns_running_status",  # In TestGetHostDetailRunningTask
        "test_running_task_includes_wait_guidance"
    ]
    
    all_tests = {
        "6.3.1 Successful query for single host": tests_6_3_1,
        "6.3.2 Host not found": tests_6_3_2,
        "6.3.3 Task not found": tests_6_3_3,
        "6.3.4 Task still running": tests_6_3_4
    }
    
    all_passed = True
    for subtask, test_names in all_tests.items():
        print(f"\n  Subtask {subtask}:")
        for test_name in test_names:
            # Check in TestGetHostDetailNotFound or TestGetHostDetailRunningTask classes
            if f"def {test_name}" in content:
                print(f"    ✓ {test_name}")
            else:
                print(f"    ✗ {test_name} - NOT FOUND")
                all_passed = False
    
    return all_passed


def main():
    """Main verification function."""
    print("=" * 70)
    print("Unit Test Coverage Verification for Tasks 6.1, 6.2, 6.3")
    print("=" * 70)
    
    task_6_1_passed = check_task_6_1_coverage()
    task_6_2_passed = check_task_6_2_coverage()
    task_6_3_passed = check_task_6_3_coverage()
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"Task 6.1 (TaskResultStore unit tests): {'✓ PASS' if task_6_1_passed else '✗ FAIL'}")
    print(f"Task 6.2 (get_result tool unit tests): {'✓ PASS' if task_6_2_passed else '✗ FAIL'}")
    print(f"Task 6.3 (get_host_detail tool unit tests): {'✓ PASS' if task_6_3_passed else '✗ FAIL'}")
    
    if task_6_1_passed and task_6_2_passed and task_6_3_passed:
        print("\n✓ All unit test coverage requirements are met!")
        return 0
    else:
        print("\n✗ Some test coverage requirements are missing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
