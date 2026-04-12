"""
list_playbooks工具模块

列出可用playbook的MCP工具
"""

from typing import Dict, Any

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_list_playbooks(server):
    """注册list_playbooks工具"""
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

        logger.info("MCP 工具调用: list_playbooks")
        try:
            playbooks = server.playbook_scanner.scan_playbooks()
            return {
                "status": "success",
                "playbooks": playbooks,
                "count": len(playbooks),
                "message": f"共找到 {len(playbooks)} 个 playbook",
            }
        except Exception as e:
            logger.error(f"获取 playbook 列表失败: {str(e)}")
            return {
                "status": "error",
                "message": f"获取 playbook 列表失败: {str(e)}",
            }