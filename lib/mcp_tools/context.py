"""Context tools module.

Context-related MCP tools for session data persistence.
"""

from typing import Any, Dict

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_context_tools(server) -> None:
    """Register context-related tools.

    Args:
        server: Server instance to register tools with.
    """

    @server.mcp.tool(
        name="set_context",
        description="Set a context key-value pair. Used for persisting data across sessions, such as saving configurations or state information.",
    )
    @require_permission("set_context")
    def set_context(key: str, value: str) -> Dict[str, str]:
        """Set a context key-value pair.

        Args:
            key: Context key.
            value: Context value.

        Returns:
            Dict[str, str]: Operation result.
        """
        logger.info(f"MCP tool call: set_context, key={key}")
        server.context_repo.set(key, value)
        return {"status": "success", "key": key, "value": value}

    @server.mcp.tool(
        name="get_context",
        description="Get a context value by key. Retrieves previously stored context data.",
    )
    @require_permission("get_context")
    def get_context(key: str) -> Dict[str, Any]:
        """Get a context value by key.

        Args:
            key: Context key to retrieve.

        Returns:
            Dict[str, Any]: Context value or error message.
        """
        logger.info(f"MCP tool call: get_context, key={key}")
        value = server.context_repo.get(key)
        if value is not None:
            return {"status": "success", "key": key, "value": value}
        else:
            return {"status": "error", "message": f"Context key '{key}' not found"}

    @server.mcp.tool(
        name="delete_context",
        description="Delete a specific context key-value pair.",
    )
    @require_permission("delete_context")
    def delete_context(key: str) -> Dict[str, Any]:
        """Delete a context key-value pair.

        Args:
            key: Context key to delete.

        Returns:
            Dict[str, Any]: Operation result.
        """
        logger.info(f"MCP tool call: delete_context, key={key}")
        if server.context_repo.delete(key):
            return {"status": "success", "message": f"Deleted context key: {key}"}
        else:
            return {"status": "error", "message": f"Context key '{key}' not found"}

    @server.mcp.tool(
        name="list_contexts",
        description="List all context key-value pairs. Returns all currently stored context data.",
    )
    @require_permission("list_contexts")
    def list_contexts() -> Dict[str, Any]:
        """List all context key-value pairs.

        Returns:
            Dict[str, Any]: All context data.
        """
        logger.info("MCP tool call: list_contexts")
        contexts = server.context_repo.list()
        return {"status": "success", "contexts": contexts, "count": len(contexts)}

    @server.mcp.tool(
        name="clear_contexts",
        description="Clear all context data. Use with caution as this operation is irreversible.",
    )
    @require_permission("clear_contexts")
    def clear_contexts() -> Dict[str, Any]:
        """Clear all context data.

        Returns:
            Dict[str, Any]: Operation result with count of deleted items.
        """
        logger.info("MCP tool call: clear_contexts")
        count = server.context_repo.clear()
        return {"status": "success", "message": f"Cleared {count} context items"}
