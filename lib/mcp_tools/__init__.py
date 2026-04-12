"""
MCP工具包

包含所有MCP工具模块
"""

from .ansible_shell import register_ansible_shell
from .install_python import register_install_python
from .install_tsc_tools import register_install_tsc_tools
from .check_host_status import register_check_host_status
from .ansible_copy import register_ansible_copy
from .ansible_fetch import register_ansible_fetch
from .list_playbooks import register_list_playbooks
from .ansible_playbook import register_ansible_playbook
from .context import register_context_tools
from .dynamic_playbooks import register_dynamic_playbook_tools
from .task_results import register_task_results_tools


def register_mcp_tools(server):
    """注册所有MCP工具"""
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
    register_dynamic_playbook_tools(server)