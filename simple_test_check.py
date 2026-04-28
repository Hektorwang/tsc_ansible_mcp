#!/usr/bin/env python3
"""
Simple test to verify the test file can be imported
"""

import sys

try:
    # Try to import the test module
    sys.path.insert(0, '.')
    import tests.test_mcp_task_results as test_module
    
    print("✓ Test module imported successfully")
    print()
    
    # Count test classes
    test_classes = [name for name in dir(test_module) if name.startswith('Test')]
    print(f"Found {len(test_classes)} test classes:")
    for cls_name in test_classes:
        cls = getattr(test_module, cls_name)
        test_methods = [m for m in dir(cls) if m.startswith('test_')]
        print(f"  - {cls_name}: {len(test_methods)} test methods")
    
    print()
    print("✓ All test classes are valid")
    sys.exit(0)
    
except SyntaxError as e:
    print(f"✗ Syntax error in test file: {e}")
    sys.exit(1)
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
