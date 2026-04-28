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
        description="""Retrieve execution results for a task with three query modes.

## Query Modes

### Mode 1: Task Summary (status omitted)
Returns high-level statistics without host details.
Example: {"task_id": "xxx"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "total_hosts": 10,
  "success_count": 8,
  "failed_count": 2,
  "message": "Use get_result(task_id, status='failed') to see failed hosts"
}

### Mode 2: Failed Hosts List (status="failed")
Returns all failed hosts with details.
Example: {"task_id": "xxx", "status": "failed"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "failed_hosts": {"host_ip": {"rc": 1, "stdout": "", "stderr": "error"}},
  "total_failed": 2,
  "message": "Use get_host_detail(task_id, host_ip) for specific host investigation"
}

### Mode 3: Success Hosts List (status="success")
Returns all successful hosts with details.
Example: {"task_id": "xxx", "status": "success"}
Response: {
  "task_id": "xxx",
  "status": "completed",
  "success_hosts": {"host_ip": {"rc": 0, "stdout": "output", "stderr": ""}},
  "total_success": 8
}

## Parameters
- task_id (required): Task ID to query results for.
- status (optional): Status filter. Valid values: 'failed' or 'success'. If omitted, returns task summary.

## Polling Guidance
If task status is "running", poll again in 30-60 seconds.
""",
    )
    @require_permission("get_result")
    def get_result(
        task_id: str,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_result, task_id={task_id}, status={status}")

        # Validate status parameter
        if status is not None and status not in ["failed", "success"]:
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Invalid status parameter '{status}'. Valid values: 'failed' or 'success'"
            }

        task_data = server.task_repo.get(task_id)

        if task_data is None:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found in database",
            }

        result = task_data.get("result")
        if result is None:
            task_status = task_data.get("status", "unknown")
            if task_status == "running":
                return {
                    "task_id": task_id,
                    "status": "running",
                    "message": f"Task is still running. Poll again in 30-60 seconds using get_result('{task_id}')"
                }
            return {
                "task_id": task_id,
                "status": task_status,
                "message": f"Task {task_id} has no result data yet",
            }

        # Mode 1: Task Summary (status=None)
        if status is None:
            success_hosts = result.get("success_hosts", [])
            all_hosts = result.get("results", {})
            total_hosts = len(all_hosts)
            success_count = len(success_hosts)
            failed_count = total_hosts - success_count

            summary = {
                "task_id": task_id,
                "status": result.get("status"),
                "total_hosts": total_hosts,
                "success_count": success_count,
                "failed_count": failed_count,
            }

            # Add guidance message
            if failed_count > 0:
                summary["message"] = f"Task completed with {failed_count} failed host(s). Use get_result('{task_id}', status='failed') to see failed hosts"
            else:
                summary["message"] = "Task completed successfully on all hosts"

            return summary

        # Mode 2 & 3: Read from ResultStore (JSON files) for filtered host lists
        # This is required per design: Layer 2 queries should use ResultStore, not database
        store_result = server.execution_service.result_store.get_result(task_id, status)
        
        if store_result is None:
            # Result file is missing but task exists in database
            return {
                "task_id": task_id,
                "status": "error",
                "message": f"Result file for task {task_id} is missing. The task exists in database but detailed results are not available."
            }
        
        # Mode 2: Failed Hosts List (status="failed")
        if status == "failed":
            failed_results = store_result.get("failed_hosts", {})
            return {
                "task_id": task_id,
                "status": result.get("status"),
                "failed_hosts": failed_results,
                "total_failed": store_result.get("total_failed", len(failed_results)),
                "message": "Use get_host_detail(task_id, host_ip) to investigate specific host" if failed_results else "No failed hosts"
            }

        # Mode 3: Success Hosts List (status="success")
        if status == "success":
            success_results = store_result.get("success_hosts", {})
            return {
                "task_id": task_id,
                "status": result.get("status"),
                "success_hosts": success_results,
                "total_success": store_result.get("total_success", len(success_results)),
            }

    @server.mcp.tool(
        name="get_host_detail",
        description="""Query execution details for a specific host.

## Purpose
Retrieve detailed execution results (rc, stdout, stderr, status) for a single host without loading all host results.

## Parameters
- task_id (required): Task ID to query.
- host (required): Host IP address to query.

## Return Value
Returns host execution details:
{
  "task_id": "xxx",
  "host": "192.168.1.10",
  "rc": 1,
  "stdout": "",
  "stderr": "command not found",
  "status": "failed"
}

## Error Responses
- Task not found: {"task_id": "xxx", "status": "not_found", "message": "Task xxx not found"}
- Host not found: {"task_id": "xxx", "host": "1.1.1.1", "status": "not_found", "message": "Host not found in task results"}
- Task running: {"task_id": "xxx", "status": "running", "message": "Task is still running. Wait and try again"}

## Usage Example
{"task_id": "abc-123", "host": "192.168.1.10"}
""",
    )
    @require_permission("get_host_detail")
    def get_host_detail(
        task_id: str,
        host: str,
    ) -> Dict[str, Any]:

        logger.info(f"MCP tool call: get_host_detail, task_id={task_id}, host={host}")

        # Check if task exists
        task_data = server.task_repo.get(task_id)

        if task_data is None:
            return {
                "task_id": task_id,
                "status": "not_found",
                "message": f"Task {task_id} not found in database",
            }

        # Check if task has results
        result = task_data.get("result")
        if result is None:
            task_status = task_data.get("status", "unknown")
            if task_status == "running":
                return {
                    "task_id": task_id,
                    "status": "running",
                    "message": "Task is still running. Wait and try again in 30-60 seconds"
                }
            return {
                "task_id": task_id,
                "status": task_status,
                "message": f"Task {task_id} has no result data yet",
            }

        # Get host result from ResultStore
        host_result = server.execution_service.result_store.get_host_result(task_id, host)

        if host_result is None:
            # Check if result file exists to distinguish between missing file and missing host
            result_path = server.execution_service.result_store._get_result_path(task_id)
            if not result_path.exists():
                # Result file is missing but task exists in database
                return {
                    "task_id": task_id,
                    "status": "error",
                    "message": f"Result file for task {task_id} is missing. The task exists in database but detailed results are not available."
                }
            # File exists but host not found
            return {
                "task_id": task_id,
                "host": host,
                "status": "not_found",
                "message": f"Host {host} not found in task {task_id} results"
            }

        return host_result
