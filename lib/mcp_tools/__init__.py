"""MCP tools package.

Contains all MCP tool modules. Dynamic playbook tools are registered
by server.py's _register_dynamic_playbook_tools() method.
"""

from .ansible_copy import register_ansible_copy
from .ansible_fetch import register_ansible_fetch
from .ansible_shell import register_ansible_shell
from .check_host_status import register_check_host_status
from .change_ssh_port import register_change_ssh_port
from .change_ssh_password import register_change_ssh_password
from .task_results import register_task_results_tools


def register_mcp_tools(server) -> None:
    """Register all static MCP tools.

    Dynamic playbook tools are registered separately by
    Server._register_dynamic_playbook_tools().

    Args:
        server: Server instance to register tools with.
    """
    register_ansible_shell(server)
    register_check_host_status(server)
    register_ansible_copy(server)
    register_ansible_fetch(server)
    register_change_ssh_port(server)
    register_change_ssh_password(server)
    register_task_results_tools(server)
