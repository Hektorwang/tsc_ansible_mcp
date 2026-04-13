"""
context工具模块

上下文相关的MCP工具
"""

from typing import Dict, Any

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_context_tools(server):
    """注册上下文相关工具"""

    @server.mcp.tool(
        name="set_context",
        description="设置上下文键值对。用于在会话间持久化存储数据，例如保存配置、状态信息等。",
    )
    @require_permission("set_context")
    def set_context(key: str, value: str) -> Dict[str, str]:

        logger.info(f"MCP 工具调用: set_context, key={key}")
        server.context_repo.set(key, value)
        return {"status": "success", "key": key, "value": value}

    @server.mcp.tool(
        name="get_context",
        description="获取上下文值。通过键名获取之前存储的上下文数据。",
    )
    @require_permission("get_context")
    def get_context(key: str) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: get_context, key={key}")
        value = server.context_repo.get(key)
        if value is not None:
            return {"status": "success", "key": key, "value": value}
        else:
            return {"status": "error", "message": f"上下文键 '{key}' 不存在"}

    @server.mcp.tool(
        name="delete_context",
        description="删除指定的上下文键值对。",
    )
    @require_permission("delete_context")
    def delete_context(key: str) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: delete_context, key={key}")
        if server.context_repo.delete(key):
            return {"status": "success", "message": f"已删除上下文键: {key}"}
        else:
            return {"status": "error", "message": f"上下文键 '{key}' 不存在"}

    @server.mcp.tool(
        name="list_contexts",
        description="列出所有上下文键值对。返回当前存储的所有上下文数据。",
    )
    @require_permission("list_contexts")
    def list_contexts() -> Dict[str, Any]:

        logger.info("MCP 工具调用: list_contexts")
        contexts = server.context_repo.list()
        return {"status": "success", "contexts": contexts, "count": len(contexts)}

    @server.mcp.tool(
        name="clear_contexts",
        description="清空所有上下文数据。谨慎使用，此操作不可恢复。",
    )
    @require_permission("clear_contexts")
    def clear_contexts() -> Dict[str, Any]:

        logger.info("MCP 工具调用: clear_contexts")
        count = server.context_repo.clear()
        return {"status": "success", "message": f"已清空 {count} 条上下文数据"}
