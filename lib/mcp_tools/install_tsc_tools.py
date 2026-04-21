"""
install_tsc_tools tool module

MCP tool to install tsc_tools
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_install_tsc_tools(server):
    """Register install_tsc_tools tool"""

    @server.mcp.tool(
        name="install_tsc_tools",
        description="""Install tsc_tools environment on target hosts.

## Prerequisites
- Target hosts must be configured in inventory.yml first.

## Parameters
- targets (required): List of target hostnames or IPs.
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns installation results for each host including installed status and any errors.

## Decision Logic
- If tsc_tools is already installed → Skip installation
- If tsc_tools is not installed → Execute installation

## Usage Example
{
  "targets": ["web-server-01", "db-server-02"]
}
""",
    )
    @require_permission("install_tsc_tools")
    def install_tsc_tools(
        targets: List[str],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: install_tsc_tools, targets={targets}")
        task_id = str(uuid.uuid4())
        server.task_repo.create(task_id, "install_tsc_tools", {"targets": targets})
        result = server.execution_service.install_tsc_tools(
            targets, timeout, task_id
        )
        logger.info(
            f"MCP tool response: install_tsc_tools, task_id={task_id}, result={result}"
        )
        return result
