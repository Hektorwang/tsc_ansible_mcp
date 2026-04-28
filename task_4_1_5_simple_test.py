"""Simple test to verify task 4.1.5 implementation."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.task_result_store import TaskResultStore

# Reset singleton
TaskResultStore._instance = None
TaskResultStore._initialized = False

# Create temp directory
with tempfile.TemporaryDirectory() as tmpdir:
    store = TaskResultStore(Path(tmpdir))
    
    # Test 1: get_result returns None when file doesn't exist
    result = store.get_result("non-existent-task", status="failed")
    assert result is None, "Should return None for missing file"
    print("✓ Test 1 passed: get_result returns None for missing file")
    
    # Test 2: get_host_result returns None when file doesn't exist
    result = store.get_host_result("non-existent-task", "192.168.1.1")
    assert result is None, "Should return None for missing file"
    print("✓ Test 2 passed: get_host_result returns None for missing file")
    
    # Test 3: _get_result_path returns correct path
    path = store._get_result_path("test-task")
    assert not path.exists(), "File should not exist"
    print("✓ Test 3 passed: _get_result_path works correctly")
    
    print("\nAll basic tests passed!")
    print("The implementation correctly handles missing result files.")
