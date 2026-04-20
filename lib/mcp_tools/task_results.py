"""
Task results tool module

MCP tool to query task execution results
"""

from typing import Any, Dict, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_task_results_tools(server):
    """Register task results related tools"""

    @server.mcp.tool(
        name="get_task_detail",
        description="Query execution details for a specific host in a specified task. Use this tool to get detailed execution results for a specific host when the execution result returns summary information.",
    )
    @require_permission("get_task_detail")
    def get_task_detail(
        task_id: str,
        host: str,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_task_detail, task_id={task_id}, host={host}")
        from lib.task_result_store import task_result_store

        result = task_result_store.get_host_result(task_id, host)
        if result is None:
            return {
                "task_id": task_id,
                "host": host,
                "status": "not_found",
                "message": f"Task {task_id} not found or no results for host {host}",
            }

        return {
            "task_id": task_id,
            "host": host,
            "status": "success",
            "result": result,
        }

    @server.mcp.tool(
        name="get_failed_hosts",
        description="Query details of all failed hosts in a specified task. Use this tool to get detailed error information for failed hosts when the execution result contains failed hosts.",
    )
    @require_permission("get_failed_hosts")
    def get_failed_hosts(
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_failed_hosts, task_id={task_id}")
        from lib.task_result_store import task_result_store

        return task_result_store.get_failed_hosts(task_id, limit, offset)

    @server.mcp.tool(
        name="get_all_results",
        description="Paginate and query execution results for all hosts in a specified task. Use this tool for paginated queries when you need to view execution results for all hosts.",
    )
    @require_permission("get_all_results")
    def get_all_results(
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_all_results, task_id={task_id}")
        from lib.task_result_store import task_result_store

        return task_result_store.get_all_results(task_id, limit, offset)
