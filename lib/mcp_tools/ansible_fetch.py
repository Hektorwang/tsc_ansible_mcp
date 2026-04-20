"""
ansible_fetch tool module

MCP tool to fetch files
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_fetch(server):
    """Register ansible_fetch tool"""

    @server.mcp.tool(
        name="ansible_fetch",
        description="""
# Task: Fetch Files from Target Hosts

## Workflow

- Fetch files from remote hosts to local

## Tool Calls

```json
{
  "name": "ansible_fetch",
  "arguments": {
    "targets": ["host1.example.com"],
    "src": "/path/to/remote/file",
    "dest": "/path/to/local/directory",
    "flat": false, //Optional, default false
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
    @require_permission("ansible_fetch")
    def ansible_fetch(
        targets: List[str],
        src: str,
        dest: str,
        flat: bool = False,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_fetch, targets={targets}, src={src}, dest={dest}"
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
            task_id, "ansible_fetch", {"targets": targets, "src": src, "dest": dest}
        )
        result = server.execution_service.ansible_fetch(
            targets, src, dest, credentials, flat, timeout, task_id
        )
        logger.info(f"MCP tool response: ansible_fetch, task_id={task_id}, result={result}")
        return result
