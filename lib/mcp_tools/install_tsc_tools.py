"""
install_tsc_tools tool module

MCP tool to install tsc_tools
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_install_tsc_tools(server):
    """Register install_tsc_tools tool"""

    @server.mcp.tool(
        name="install_tsc_tools",
        description="""
# Task: Install tsc_tools Environment

## Workflow

- Check host status (verify if tsc_tools is installed)
- If tsc_tools is not installed, install tsc_tools

## Tool Calls

```json
{
  "name": "install_tsc_tools",
  "arguments": {
    "targets": ["host1.example.com"],
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
## Decision Logic

- If tsc_tools is already installed → Skip installation
- If tsc_tools is not installed, → Execute install_tsc_tools
""",
    )
    @require_permission("install_tsc_tools")
    def install_tsc_tools(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: install_tsc_tools, targets={targets}")
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
        server.task_repo.create(task_id, "install_tsc_tools", {"targets": targets})
        result = server.execution_service.install_tsc_tools(
            targets, credentials, timeout, task_id
        )
        logger.info(
            f"MCP tool response: install_tsc_tools, task_id={task_id}, result={result}"
        )
        return result
