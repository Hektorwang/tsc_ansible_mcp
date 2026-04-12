"""
任务结果工具模块

查询任务执行结果的MCP工具
"""

from typing import Dict, Any, Optional

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_task_results_tools(server):
    """注册任务结果相关工具"""
    @server.mcp.tool(
        name="get_task_detail",
        description="查询特定主机在指定任务中的执行详情。当执行结果返回摘要信息时，使用此工具获取特定主机的详细执行结果。",
    )
    @require_permission("get_task_detail")
    def get_task_detail(
        task_id: str,
        host: str,
    ) -> Dict[str, Any]:
        
        logger.info(
            f"MCP 工具调用: get_task_detail, task_id={task_id}, host={host}"
        )
        from lib.task_result_store import task_result_store

        result = task_result_store.get_host_result(task_id, host)
        if result is None:
            return {
                "task_id": task_id,
                "host": host,
                "status": "not_found",
                "message": f"任务 {task_id} 不存在或主机 {host} 无结果",
            }

        return {
            "task_id": task_id,
            "host": host,
            "status": "success",
            "result": result,
        }

    @server.mcp.tool(
        name="get_failed_hosts",
        description="查询指定任务中所有失败主机的详情。当执行结果包含失败主机时，使用此工具获取失败主机的详细错误信息。",
    )
    @require_permission("get_failed_hosts")
    def get_failed_hosts(
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        
        logger.info(f"MCP 工具调用: get_failed_hosts, task_id={task_id}")
        from lib.task_result_store import task_result_store

        return task_result_store.get_failed_hosts(task_id, limit, offset)

    @server.mcp.tool(
        name="get_all_results",
        description="分页查询指定任务的所有主机执行结果。当需要查看所有主机的执行结果时，使用此工具进行分页查询。",
    )
    @require_permission("get_all_results")
    def get_all_results(
        task_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        
        logger.info(f"MCP 工具调用: get_all_results, task_id={task_id}")
        from lib.task_result_store import task_result_store

        return task_result_store.get_all_results(task_id, limit, offset)
