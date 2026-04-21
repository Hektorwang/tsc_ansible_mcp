"""
ansible_playbook tool module

MCP tool to execute playbooks
"""

import uuid
from typing import Any, Dict, List, Optional, Union

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_playbook(server):
    """Register ansible_playbook tool"""

    @server.mcp.tool(
        name="ansible_playbook",
        description="""Execute a specified Ansible playbook on target hosts.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- The tool auto-installs Python3 if missing on target hosts.

## Parameters
- playbook (required): Playbook filename (e.g., 'system_check.yml') or full path.
- targets (required): List of target hostnames or IPs.
- extravars (optional): Extra variables as a dictionary.
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns execution summary including task_id, status, success_hosts list, and failed_hosts list. To view failed host details, use get_result(task_id, status='failed').

## Usage Example
{
  "playbook": "system_check.yml",
  "targets": ["web-server-01", "db-server-02"],
  "extravars": {"check_type": "full"}
}
""",
    )
    @require_permission("ansible_playbook")
    def ansible_playbook(
        playbook: str,
        targets: List[str],
        extravars: Optional[Union[Dict[str, Any], str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_playbook, playbook={playbook}, targets={targets}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "ansible_playbook", {"playbook": playbook, "targets": targets}
        )
        result = server.execution_service.execute_playbook(
            playbook, targets, extravars, timeout, task_id
        )
        logger.info(
            f"MCP tool response: ansible_playbook, task_id={task_id}, result={result}"
        )
        return result
