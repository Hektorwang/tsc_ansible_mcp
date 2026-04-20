"""
list_playbooks tool module

MCP tool to list available playbooks
"""

from typing import Any, Dict

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_list_playbooks(server):
    """Register list_playbooks tool"""

    @server.mcp.tool(
        name="list_playbooks",
        description="""
# Task: List Available Playbooks

## Workflow

- List all available playbooks in the playbooks directory

## Tool Calls

```json
{
  "name": "list_playbooks",
  "arguments": {}
}
```
""",
    )
    @require_permission("list_playbooks")
    def list_playbooks() -> Dict[str, Any]:

        logger.info("MCP tool call: list_playbooks")
        try:
            playbooks = server.playbook_scanner.scan_playbooks()
            return {
                "status": "success",
                "playbooks": playbooks,
                "count": len(playbooks),
                "message": f"Found {len(playbooks)} playbooks",
            }
        except Exception as e:
            logger.error(f"Failed to get playbook list: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to get playbook list: {str(e)}",
            }
