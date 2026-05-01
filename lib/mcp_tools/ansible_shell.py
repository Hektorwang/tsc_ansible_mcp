"""
ansible_shell MCP tool module.

Execute shell commands via MCP.
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tool_description_loader import load_tool_description
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_shell(server):
    """Register ansible_shell tool."""

    @server.mcp.tool(
        name="ansible_shell",
        description=load_tool_description("ansible_shell"),
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
