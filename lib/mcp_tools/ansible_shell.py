"""
ansible_shell工具模块

执行shell命令的MCP工具
"""

import uuid
from typing import Any, Dict, List, Optional

from lib.permission import require_permission
from lib.tsc_logger import get_logger

logger = get_logger()


def register_ansible_shell(server):
    """注册ansible_shell工具"""

    @server.mcp.tool(
        name="ansible_shell",
        description="""Execute shell commands on target hosts using Ansible. Supports batch execution across multiple targets and returns the result for each host individually.

## Prerequisites & Safety
- **Auto-Installation**: The tool automatically checks for Python3 on target hosts. If missing, it will install `tsc_python` before execution.
- **Pre-check**: It is highly recommended to call `check_host_status` first to ensure the environment is ready.

## Authentication & Connection
The following parameters allow customizing the connection:
- `targets`: List of target hostnames or IPs.
- `user`: SSH username (optional, defaults to current user).
- `port`: SSH port (optional, defaults to 22).
- `password`: SSH password (optional, use only if key-based auth is not configured).
- `private_key`: Path or content of the private key file (optional).
- `timeout`: Command execution timeout in seconds (optional).

## Command Formatting Rules (Critical)
To ensure reliable execution, strictly follow these quoting rules:
1. **Preferred**: Wrap arguments in **single quotes** to avoid escaping issues. 
   - Good: `find /tmp -name '*.json'`
2. **Alternative**: If double quotes are required, escape them using backslashes in the JSON string.
   - Good: `find /tmp -name \"*.json\"`
3. **Forbidden**: Do not use complex nested quotes. Simplify the command logic instead.
4. **Forbidden**: If you detect the hint 'Blacklisted high-risk command', you must:
   - Tell user that's a security violation immediately.
   - STRICTLY stop generating any further commands, explanations, or code blocks.
   - Do NOT attempt to justify, bypass, or suggest alternatives after this warning.
   - The response must end exactly at the warning message.
   - OUTPUT FORMAT: "高危黑名单命令: {command} 被拦截, 日志已被记录, 请联系管理员."

## Usage Examples
{
  "arguments": {
    "targets": ["web-server-01", "db-server-02"],
    "command": "ls -la /var/log",
  }
}
// Example with authentication and special characters:
{
  "arguments": {
    "targets": ["app-node-01"],
    "command": "grep 'error' /var/log/app.log",
    "user": "deploy",
    "port": 2222,
    "private_key": "/path/to/key.pem"
  }
}
""",
    )
    @require_permission("ansible_shell")
    def ansible_shell(
        targets: List[str],
        command: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP 工具调用: ansible_shell, targets={targets}, command={command}"
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
            task_id, "ansible_shell", {"targets": targets, "command": command}
        )
        result = server.execution_service.execute_shell(
            targets, command, credentials, timeout, task_id
        )
        logger.info(f"MCP 工具响应: ansible_shell, task_id={task_id}, result={result}")
        return result
