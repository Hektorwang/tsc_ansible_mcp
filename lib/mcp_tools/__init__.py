"""MCP tools package.

Contains all MCP tool modules. Dynamic playbook tools are registered
by server.py's _register_dynamic_playbook_tools() method.
"""

from .ansible_copy import register_ansible_copy
from .ansible_fetch import register_ansible_fetch
from .ansible_playbook import register_ansible_playbook
from .ansible_shell import register_ansible_shell
from .check_host_status import register_check_host_status
from .context import register_context_tools
from .install_python import register_install_python
from .install_tsc_tools import register_install_tsc_tools
from .list_playbooks import register_list_playbooks
from .task_results import register_task_results_tools


def register_mcp_tools(server) -> None:
    """Register all static MCP tools.

    Dynamic playbook tools are registered separately by
    Server._register_dynamic_playbook_tools().

    Args:
        server: Server instance to register tools with.
    """
    register_ansible_shell(server)
    register_install_python(server)
    register_install_tsc_tools(server)
    register_check_host_status(server)
    register_ansible_copy(server)
    register_ansible_fetch(server)
    register_list_playbooks(server)
    register_ansible_playbook(server)
    register_context_tools(server)
    register_task_results_tools(server)
