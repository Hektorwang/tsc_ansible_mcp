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
        description="""Copy files from local machine to target hosts. Returns complete results (rc, stdout, stderr) for each host.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH.
  2. Python is installed (required for the copy module).
  If Python is not installed, run playbook_bootstrap_tsc_environment first.

## Parameters
- targets (required): List of target hostnames or IPs.
- src (required): Local file path to copy from.
- dest (required): Remote file path to copy to.
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns execution results including rc, stdout, and stderr for each host.
If the task takes longer than expected, status will be "running" - use get_task_status(task_id) to poll for the final result.

## Usage Example
{
  "targets": ["web-server-01"],
  "src": "/path/to/local/config.yml",
  "dest": "/etc/myapp/config.yml"
}
""",
    )
    @require_permission("ansible_copy")
    def ansible_copy(
        targets: List[str],
        src: str,
        dest: str,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_copy, targets={targets}, src={src}, dest={dest}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "ansible_copy", {"targets": targets, "src": src, "dest": dest}
        )
        result = server.execution_service.ansible_copy(
            targets, src, dest, timeout, task_id
        )
        logger.info(
            f"MCP tool response: ansible_copy, task_id={task_id}, result={result}"
        )
        return result
