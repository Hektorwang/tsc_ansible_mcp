"""
dynamic_playbooks工具模块

注册动态playbook工具
"""

import uuid
from typing import List, Optional, Dict, Any, Callable, Union

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_dynamic_playbook_tools(server):
    """注册动态playbook工具"""
    playbooks = server.playbook_scanner.scan_playbooks()
    for playbook_name, metadata in playbooks.items():
        tool_name = f"playbook_{playbook_name}"

        def make_playbook_tool(playbook_name: str) -> Callable[..., Dict[str, Any]]:
            @require_permission(f"playbook_{playbook_name}")
            def playbook_tool(
                targets: List[str],
                user: Optional[str] = None,
                port: Optional[int] = None,
                password: Optional[str] = None,
                private_key: Optional[str] = None,
                extravars: Optional[Union[Dict[str, Any], str]] = None,
                timeout: Optional[int] = None,
            ) -> Dict[str, Any]:

                tool_name = f"playbook_{playbook_name}"
                logger.info(
                    f"MCP 工具调用: {tool_name}, targets={targets}"
                )
                credentials: Dict[str, Any] = {}
                if user:
                    credentials["user"] = user
                if port:
                    credentials["port"] = port
                if password:
                    credentials["password"] = password
                if private_key:
                    credentials["private_key"] = private_key
                task_id = str(uuid.uuid4())
                server.task_repo.create(
                    task_id, tool_name, {"targets": targets, "playbook": playbook_name}
                )
                return server.execution_service.execute_playbook(
                    playbook_name,
                    targets,
                    credentials,
                    extravars,
                    timeout,
                    task_id,
                )
            return playbook_tool

        playbook_tool = make_playbook_tool(playbook_name)
        tool_description = server.playbook_scanner.generate_tool_definition(metadata)
        server.mcp.tool(name=tool_name, description=tool_description)(playbook_tool)