"""
ansible_fetch tool module

MCP tool to fetch files
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tool_description_loader import load_tool_description
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_fetch(server):
    """Register ansible_fetch tool"""

    @server.mcp.tool(
        name="ansible_fetch",
        description=load_tool_description("ansible_fetch"),
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
