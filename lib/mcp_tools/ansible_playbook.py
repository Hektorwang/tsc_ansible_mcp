"""
ansible_playbook工具模块

执行playbook的MCP工具
"""

import uuid
from typing import Any, Dict, List, Optional, Union

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_playbook(server):
    """注册ansible_playbook工具"""

    @server.mcp.tool(
        name="ansible_playbook",
        description="""
# Task: Run Ansible Playbook

## Workflow

- Run specified playbook on target hosts

## Tool Calls

```json
{
  "name": "ansible_playbook",
  "arguments": {
    "playbook": "playbook_name.yml",
    "targets": ["host1.example.com"],
    "extravars": {"var1": "value1", "var2": "value2"}, //Optional
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```

## Important Notes
- The playbook name should be the filename (e.g., "system_check.yml") or the full path to the playbook file.
- Extra variables can be passed as a dictionary.
- If the playbook requires specific variables, make sure to include them in the extravars.

## Playbook Execution Flow
1. The system will check if Python is installed on the target hosts. If not, it will automatically install it.
2. The playbook will be executed with the provided parameters.
3. The result will be returned with detailed information for each host.

## Troubleshooting
- If the playbook execution fails, check the error message for details.
- Ensure that the playbook file exists in the playbooks directory.
- Verify that the target hosts are reachable and have the necessary permissions.
""",
    )
    @require_permission("ansible_playbook")
    def ansible_playbook(
        playbook: str,
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        extravars: Optional[Union[Dict[str, Any], str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP 工具调用: ansible_playbook, playbook={playbook}, targets={targets}"
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
            task_id, "ansible_playbook", {"playbook": playbook, "targets": targets}
        )
        result = server.execution_service.execute_playbook(
            playbook, targets, credentials, extravars, timeout, task_id
        )
        logger.info(
            f"MCP 工具响应: ansible_playbook, task_id={task_id}, result={result}"
        )
        return result
