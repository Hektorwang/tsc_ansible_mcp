"""
install_python工具模块

安装Python的MCP工具
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_install_python(server):
    """注册install_python工具"""

    @server.mcp.tool(
        name="install_python",
        description="""
# Task: Install tsc_python Environment

## Workflow

- Check host status (verify if tsc_tools and tsc_python are installed)
- If tsc_tools is not installed, install tsc_tools first
- If tsc_python is not installed, install tsc_python

## Tool Calls

```json
{
  "name": "install_python",
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

- If tsc_python is already installed → Skip installation
- If tsc_python is not installed, → Execute install_python
""",
    )
    @require_permission("install_python")
    def install_python(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: install_python, targets={targets}")
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
        server.task_repo.create(task_id, "install_python", {"targets": targets})
        result = server.execution_service.install_python(
            targets, credentials, timeout, task_id
        )
        logger.info(f"MCP 工具响应: install_python, task_id={task_id}, result={result}")
        return result
