"""
check_host_status tool module

MCP tool to check host status
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tool_description_loader import load_tool_description
from lib.tsc_logger import get_logger

logger = get_logger()


def register_check_host_status(server):
    """Register check_host_status tool"""

    @server.mcp.tool(
        name="check_host_status",
        description=load_tool_description("check_host_status"),
    )
    @require_permission("check_host_status")
    def check_host_status(
        targets: List[str],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: check_host_status, targets={targets}")
        task_id = str(uuid.uuid4())
        server.task_repo.create(task_id, "check_host_status", {"targets": targets})
        result = server.execution_service.check_host_status(targets, timeout, task_id)
        logger.info(
            f"MCP tool response: check_host_status, task_id={task_id}, result={result}"
        )
        return result
