"""
ansible_copy tool module

MCP tool to copy files
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_copy(server):
    """Register ansible_copy tool"""

    @server.mcp.tool(
        name="ansible_copy",
        description="""
# Task: Copy Files to Target Hosts

## Workflow

- Copy files from local to remote hosts

## Tool Calls

```json
{
  "name": "ansible_copy",
  "arguments": {
    "targets": ["host1.example.com"],
    "src": "/path/to/local/file",
    "dest": "/path/to/remote/file",
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
""",
    )
    @require_permission("ansible_copy")
    def ansible_copy(
        targets: List[str],
        src: str,
        dest: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_copy, targets={targets}, src={src}, dest={dest}"
        )
        credentials: Dict[str, Any] = {}
        if user:
            credentials["user"] = user
        if port:
            credentials["port"] = port
        if password:
            credentials["password"] = password
        if private_key:
            credentials["private_key"] = private_key
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "ansible_copy", {"targets": targets, "src": src, "dest": dest}
        )
        result = server.execution_service.ansible_copy(
            targets, src, dest, credentials, timeout, task_id
        )
        logger.info(f"MCP tool response: ansible_copy, task_id={task_id}, result={result}")
        return result
