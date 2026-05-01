"""
ansible_copy tool module

MCP tool to copy files
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tool_description_loader import load_tool_description
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_copy(server):
    """Register ansible_copy tool"""

    @server.mcp.tool(
        name="ansible_copy",
        description=load_tool_description("ansible_copy"),
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
