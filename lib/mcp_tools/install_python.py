"""
install_python tool module

MCP tool to install Python
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_install_python(server):
    """Register install_python tool"""

    @server.mcp.tool(
        name="install_python",
        description="""Install tsc_python environment on target hosts.

## Prerequisites
- Target hosts must be configured in inventory.yml first.
- If tsc_tools is not installed, it will be installed first automatically.

## Parameters
- targets (required): List of target hostnames or IPs.
- timeout (optional): Execution timeout in seconds.

## Return Value
Returns installation results for each host including installed status and any errors.

## Decision Logic
- If tsc_python is already installed → Skip installation
- If tsc_python is not installed → Execute installation

## Usage Example
{
  "targets": ["web-server-01", "db-server-02"]
}
""",
    )
    @require_permission("install_python")
    def install_python(
        targets: List[str],
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: install_python, targets={targets}")
        task_id = str(uuid.uuid4())
        server.task_repo.create(task_id, "install_python", {"targets": targets})
        result = server.execution_service.install_python(
            targets, timeout, task_id
        )
        logger.info(f"MCP tool response: install_python, task_id={task_id}, result={result}")
        return result
