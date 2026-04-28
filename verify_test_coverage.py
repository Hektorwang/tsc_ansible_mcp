#!/usr/bin/env python3
"""
Verify test coverage for task 4.1.6 - Error scenario unit tests
"""

import ast
import sys
from pathlib import Path

def extract_test_classes(file_path):
    """Extract all test class names and their test methods"""
    with open(file_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    test_classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
            methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef) and m.name.startswith('test_')]
            test_classes[node.name] = methods
    
    return test_classes

def main():
    """Main verification function"""
    print("=" * 70)
    print("Task 4.1.6: Error Scenario Test Coverage Analysis")
    print("=" * 70)
    print()
    
    test_file = Path("tests/test_mcp_task_results.py")
    
    if not test_file.exists():
        print(f"ERROR: Test file not found: {test_file}")
        return 1
    
    test_classes = extract_test_classes(test_file)
    
    print(f"Found {len(test_classes)} test classes with {sum(len(methods) for methods in test_classes.values())} test methods:\n")
    
    # Required error scenarios from task 4.1
    required_scenarios = {
        "4.1.1 Task not found error": ["TestGetResultNotFound", "TestGetHostDetailNotFound"],
        "4.1.2 Invalid status parameter": ["TestGetResultInvalidStatus"],
        "4.1.3 Host not found error": ["TestGetHostDetailNotFound"],
        "4.1.4 Task running error": ["TestGetResultRunningTask", "TestGetHostDetailRunningTask"],
        "4.1.5 Result file missing error": ["TestResultFileMissingError"],
        "Additional: No result data": ["TestGetResultNoResultData", "TestGetHostDetailNoResultData"],
        "Additional: Error consistency": ["TestErrorResponseConsistency"],
    }
    
    print("Required Error Scenarios Coverage:")
    print("-" * 70)
    
    all_covered = True
    for scenario, expected_classes in required_scenarios.items():
        print(f"\n{scenario}:")
        for class_name in expected_classes:
            if class_name in test_classes:
                methods = test_classes[class_name]
                print(f"  ✓ {class_name} ({len(methods)} tests)")
                for method in methods:
                    print(f"    - {method}")
            else:
                print(f"  ✗ {class_name} - MISSING")
                all_covered = False
    
    print("\n" + "=" * 70)
    print("Summary:")
    print("=" * 70)
    print(f"Total test classes: {len(test_classes)}")
    print(f"Total test methods: {sum(len(methods) for methods in test_classes.values())}")
    
    if all_covered:
        print("\n✓ All required error scenarios have test coverage!")
        return 0
    else:
        print("\n✗ Some required error scenarios are missing test coverage")
        return 1

if __name__ == "__main__":
    sys.exit(main())
