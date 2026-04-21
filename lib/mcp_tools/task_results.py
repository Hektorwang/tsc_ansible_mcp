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
        name="get_result",
        description="""Retrieve execution results for a task.

## Parameters
- task_id (required): Task ID to query results for.
- status (optional): Status filter. Set to 'failed' to get all failed host results. If omitted, returns all results.

## Return Value
Returns the execution result data. If status='failed', returns failed hosts with rc, stdout, and stderr. If omitted, returns all host results.

## Usage Examples
{"task_id": "xxx"}  // Get all host results
{"task_id": "xxx", "status": "failed"}  // Get all failed host results
""",
    )
    @require_permission("get_result")
    def get_result(
        task_id: str,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_result, task_id={task_id}, status={status}")
        
        task_data = server.task_repo.get(task_id)

        if task_data is None:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found in database",
            }

        result = task_data.get("result")
        if result is None:
            return {
                "task_id": task_id,
                "status": task_data.get("status", "unknown"),
                "message": f"Task {task_id} has no result data yet",
            }

        if status == "failed":
            host_results = result.get("results", {})
            success_hosts = set(result.get("success_hosts", []))
            failed_results = {
                h: r for h, r in host_results.items() if h not in success_hosts
            }
            return {
                "task_id": task_id,
                "status": result.get("status"),
                "failed_hosts": failed_results,
                "total_failed": len(failed_results),
            }

        return result

    @server.mcp.tool(
        name="get_failed_results",
        description="""Retrieve detailed execution results for all failed hosts in a task.

## Parameters
- task_id (required): Task ID to query failed results for.

## Return Value
Returns detailed results (rc, stdout, stderr) for all hosts that failed the task.

## Usage Example
{"task_id": "xxx"}
""",
    )
    @require_permission("get_failed_results")
    def get_failed_results(
        task_id: str,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_failed_results, task_id={task_id}")
        
        task_data = server.task_repo.get(task_id)
        
        if task_data is None:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found",
            }
        
        result = task_data.get("result")
        if result is None:
            return {
                "task_id": task_id,
                "status": "no_data",
                "failed_hosts": {},
                "total_failed": 0,
            }
        
        host_results = result.get("results", {})
        success_hosts = set(result.get("success_hosts", []))
        failed_results = {
            h: r for h, r in host_results.items() if h not in success_hosts
        }
        
        return {
            "task_id": task_id,
            "status": result.get("status"),
            "failed_hosts": failed_results,
            "total_failed": len(failed_results),
        }
