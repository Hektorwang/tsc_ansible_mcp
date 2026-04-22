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
        description="""Fetch files from remote hosts to local machine. Returns complete results (rc, stdout, stderr) for each host.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- The tool auto-installs Python3 if missing on target hosts.

## Parameters
- targets (required): List of target hostnames or IPs.
- src (required): Remote file path to fetch from.
- dest (required): Local directory path to save to.
- flat (optional): If true, save files without host directory structure (default: false).
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns complete execution results including rc, stdout, and stderr for each host.

## Usage Example
{
  "targets": ["web-server-01"],
  "src": "/var/log/nginx/access.log",
  "dest": "/tmp/logs/",
  "flat": true
}
""",
    )
    @require_permission("ansible_fetch")
    def ansible_fetch(
        targets: List[str],
        src: str,
        dest: str,
        flat: bool = False,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_fetch, targets={targets}, src={src}, dest={dest}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "ansible_fetch", {"targets": targets, "src": src, "dest": dest}
        )
        result = server.execution_service.ansible_fetch(
            targets, src, dest, flat, timeout, task_id
        )
        logger.info(
            f"MCP tool response: ansible_fetch, task_id={task_id}, result={result}"
        )
        return result
