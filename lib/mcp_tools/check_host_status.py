"""
check_host_status工具模块

检查主机状态的MCP工具
"""

import uuid
from typing import List, Optional, Dict, Any

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_check_host_status(server):
    """注册check_host_status工具"""
    @server.mcp.tool(
        name="check_host_status",
        description="""
# Task: Check Host Status

## Workflow

- Check host architecture
- Check host distribution
- Check tsc_tools installation status
- Check tsc_python installation status

## Tool Calls

```json
{
  "name": "check_host_status",
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
""",
    )
    @require_permission("check_host_status")
    def check_host_status(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: check_host_status, targets={targets}")
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
        server.task_repo.create(task_id, "check_host_status", {"targets": targets})
        return server.execution_service.check_host_status(targets, credentials, timeout, task_id)