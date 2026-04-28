"""
ansible_shell MCP tool module.

Execute shell commands via MCP.
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_shell(server):
    """Register ansible_shell tool."""

    @server.mcp.tool(
        name="ansible_shell",
        description="""Execute shell commands on target hosts using Ansible. Returns complete results (rc, stdout, stderr) for each host.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- REQUIRED: Call check_host_status before this tool to verify:
  1. Host is reachable via SSH.
  2. Python is installed (required for the shell module).
  If Python is not installed, run playbook_bootstrap_tsc_environment first.

## Command Formatting Rules
1. Wrap arguments in single quotes to avoid escaping issues. Example: `find /tmp -name '*.json'`
2. If double quotes are required, escape them using backslashes. Example: `find /tmp -name \"*.json\"`
3. Do not use complex nested quotes. Simplify the command logic instead.
4. If you see 'Blacklisted high-risk command' warning, stop immediately and report to user.

## Return Value
Returns execution results including rc, stdout, and stderr for each host.
If the task takes longer than expected, status will be "running" - use get_result(task_id) to poll for the final result.

## Usage Example
{
  "targets": ["web-server-01", "db-server-02"],
  "command": "ls -la /var/log"
}
""",
    )
    @require_permission("ansible_shell")
    def ansible_shell(
        targets: List[str],
        command: str,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP tool call: ansible_shell, targets={targets}, command={command}"
        )
        task_id = str(uuid.uuid4())
        server.task_repo.create(
            task_id, "ansible_shell", {"targets": targets, "command": command}
        )
        result = server.execution_service.execute_shell(
            targets, command, timeout, task_id
        )
        logger.info(
            f"MCP tool response: ansible_shell, task_id={task_id}, result={result}"
        )
        return result
