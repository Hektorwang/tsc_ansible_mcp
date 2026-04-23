#!/usr/bin/env python3
"""Test changing SSH port using the same code as MCP server."""

import sys
import os
import uuid
import json
from pathlib import Path

project_root = str(Path(__file__).parent.absolute())
if sys.path and sys.path[0] != project_root:
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)

os.environ["ANSIBLE_CONFIG"] = (Path(project_root) / "ansible.cfg").absolute().as_posix()

from lib.config import Config
from lib.server import Server
from lib.tsc_logger import get_logger
from lib.database import Database

logger = get_logger()


def main() -> int:
    print("=== Testing SSH Port Change for 192.168.19.38 ===")
    
    # Initialize server components
    config = Config()
    db_path = Path(project_root) / "logs" / "tsc_ansible_mcp.db"
    database = Database(db_path)
    
    server = Server(config)
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    print(f"Task ID: {task_id}")
    
    # Create task record
    database.create(task_id, "admin_change_ssh_config", {"targets": ["192.168.19.38"]})
    
    # Execute playbook
    try:
        result = server.execution_service.execute_playbook(
            playbook="admin_change_ssh_config",
            targets=["192.168.19.38"],
            extravars={"new_port": 3203},
            timeout=None,
            task_id=task_id,
        )
        
        print(f"\n=== Execution Result ===")
        print(f"Status: {result['status']}")
        print(f"Summary: {json.dumps(result['summary'], indent=2)}")
        
        if result.get('results'):
            print(f"\n=== Detailed Results ===")
            for host, host_result in result['results'].items():
                print(f"\nHost {host}:")
                print(f"  rc={host_result.get('rc', -1)}")
                print(f"  stdout: {host_result.get('stdout', '')[:2000]}")
                if host_result.get('stderr'):
                    print(f"  stderr: {host_result.get('stderr', '')[:2000]}")
        
        return 0 if result['status'] == 'success' else 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
