#!/usr/bin/env python3
"""
Verification script for Task 5.1: 更新异步工具的轮询指导消息

This script verifies that all async tools have proper polling guidance messages.
"""

import re
from pathlib import Path

def verify_polling_guidance():
    """Verify that all async tools have proper polling guidance messages."""
    
    print("=== Task 5.1 Verification: 更新异步工具的轮询指导消息 ===\n")
    
    # Check execution service for proper polling message
    execution_service_path = Path("lib/execution_service.py")
    if execution_service_path.exists():
        content = execution_service_path.read_text()
        
        # Check for the polling guidance message
        if "Poll every 30-60 seconds using get_result" in content:
            print("✅ 5.1.5 & 5.1.6: Execution service has proper polling guidance with get_result() syntax and 30-60 second interval")
        else:
            print("❌ 5.1.5 & 5.1.6: Execution service missing proper polling guidance")
    
    # Check each async tool
    async_tools = [
        ("ansible_shell", "5.1.1"),
        ("ansible_copy", "5.1.2"), 
        ("ansible_fetch", "5.1.3"),
        ("check_host_status", "5.1.4")
    ]
    
    for tool_name, task_num in async_tools:
        tool_path = Path(f"lib/mcp_tools/{tool_name}.py")
        if tool_path.exists():
            content = tool_path.read_text()
            
            # Check if tool description mentions get_result
            if "use get_result(task_id)" in content:
                print(f"✅ {task_num}: {tool_name} tool description updated to use get_result()")
            else:
                print(f"❌ {task_num}: {tool_name} tool description not updated")
        else:
            print(f"❌ {task_num}: {tool_name}.py not found")
    
    print("\n=== Summary ===")
    print("Task 5.1 verification complete. All async tools should now have:")
    print("- Updated tool descriptions referencing get_result() instead of get_task_status()")
    print("- Execution service returns proper polling guidance with 30-60 second intervals")
    print("- Exact get_result(task_id) call syntax in messages")

if __name__ == "__main__":
    verify_polling_guidance()