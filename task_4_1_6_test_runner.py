#!/usr/bin/env python3
"""
Simple test runner for task 4.1.6 - verify error scenario test coverage
"""

import sys
import subprocess

def main():
    """Run tests and report results"""
    print("=" * 60)
    print("Task 4.1.6: Running Error Scenario Unit Tests")
    print("=" * 60)
    print()
    
    # Run pytest with verbose output
    cmd = [sys.executable, "-m", "pytest", "tests/test_mcp_task_results.py", "-v", "--tb=short"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print()
        print("=" * 60)
        print(f"Exit Code: {result.returncode}")
        print("=" * 60)
        return result.returncode
    except subprocess.TimeoutExpired:
        print("ERROR: Test execution timed out after 60 seconds")
        return 1
    except Exception as e:
        print(f"ERROR: Failed to run tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
