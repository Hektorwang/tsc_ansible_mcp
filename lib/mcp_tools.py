"""
MCP工具模块

定义所有MCP工具函数
"""

import uuid
from typing import List, Optional, Dict, Any, Callable, Union

from lib.tsc_logger import get_logger
from lib.permission import require_permission

logger = get_logger()


def register_mcp_tools(server):
    """注册MCP工具"""
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
        timeout: Optional[int] = None
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
        return server.execution_service.execute_shell(targets, command, credentials, timeout, task_id)

    @server.mcp.tool(
        name="install_python",
        description="""
# Task: Install tsc_python Environment

## Workflow

- Check host status (verify if tsc_tools and tsc_python are installed)
- If tsc_tools is not installed, install tsc_tools first
- If tsc_python is not installed, install tsc_python

## Tool Calls

```json
{
  "name": "install_python",
  "arguments": {
    "targets": ["host1.example.com"],
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
## Decision Logic

- If tsc_python is already installed → Skip installation
- If tsc_python is not installed, → Execute install_python
""",
    )
    @require_permission("install_python")
    def install_python(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: install_python, targets={targets}")
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
        server.task_repo.create(task_id, "install_python", {"targets": targets})
        return server.execution_service.install_python(targets, credentials, timeout, task_id)

    @server.mcp.tool(
        name="install_tsc_tools",
        description="""
# Task: Install tsc_tools Environment

## Workflow

- Check host status (verify if tsc_tools is installed)
- If tsc_tools is not installed, install tsc_tools

## Tool Calls

```json
{
  "name": "install_tsc_tools",
  "arguments": {
    "targets": ["host1.example.com"],
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
## Decision Logic

- If tsc_tools is already installed → Skip installation
- If tsc_tools is not installed, → Execute install_tsc_tools
""",
    )
    @require_permission("install_tsc_tools")
    def install_tsc_tools(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: install_tsc_tools, targets={targets}")
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
        server.task_repo.create(task_id, "install_tsc_tools", {"targets": targets})
        return server.execution_service.install_tsc_tools(targets, credentials, timeout, task_id)

    @server.mcp.tool(
        name="check_host_status",
        description="""
# Task: Check Host Status

## Workflow

- Check host architecture
- Check host distribution
- Check tsc_tools installation status
- Check tsc_python installation status

## Tool Calls

```json
{
  "name": "check_host_status",
  "arguments": {
    "targets": ["host1.example.com"],
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
""",
    )
    @require_permission("check_host_status")
    def check_host_status(
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(f"MCP 工具调用: check_host_status, targets={targets}")
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
        server.task_repo.create(task_id, "check_host_status", {"targets": targets})
        return server.execution_service.check_host_status(targets, credentials, timeout, task_id)

    @server.mcp.tool(
        name="ansible_copy",
        description="""
# Task: Copy Files to Target Hosts

## Workflow

- Copy files from local to remote hosts

## Tool Calls

```json
{
  "name": "ansible_copy",
  "arguments": {
    "targets": ["host1.example.com"],
    "src": "/path/to/local/file",
    "dest": "/path/to/remote/file",
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
""",
    )
    @require_permission("ansible_copy")
    def ansible_copy(
        targets: List[str],
        src: str,
        dest: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP 工具调用: ansible_copy, targets={targets}, src={src}, dest={dest}"
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
            task_id, "ansible_copy", {"targets": targets, "src": src, "dest": dest}
        )
        return server.execution_service.ansible_copy(targets, src, dest, credentials, timeout, task_id)

    @server.mcp.tool(
        name="ansible_fetch",
        description="""
# Task: Fetch Files from Target Hosts

## Workflow

- Fetch files from remote hosts to local

## Tool Calls

```json
{
  "name": "ansible_fetch",
  "arguments": {
    "targets": ["host1.example.com"],
    "src": "/path/to/remote/file",
    "dest": "/path/to/local/directory",
    "flat": false, //Optional, default false
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```
""",
    )
    @require_permission("ansible_fetch")
    def ansible_fetch(
        targets: List[str],
        src: str,
        dest: str,
        flat: bool = False,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP 工具调用: ansible_fetch, targets={targets}, src={src}, dest={dest}"
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
            task_id, "ansible_fetch", {"targets": targets, "src": src, "dest": dest}
        )
        return server.execution_service.ansible_fetch(targets, src, dest, credentials, flat, timeout, task_id)

    @server.mcp.tool(
        name="list_playbooks",
        description="""
# Task: List Available Playbooks

## Workflow

- List all available playbooks in the playbooks directory

## Tool Calls

```json
{
  "name": "list_playbooks",
  "arguments": {}
}
```
""",
    )
    @require_permission("list_playbooks")
    def list_playbooks() -> Dict[str, Any]:

        logger.info("MCP 工具调用: list_playbooks")
        try:
            playbooks = server.playbook_scanner.scan_playbooks()
            return {
                "status": "success",
                "playbooks": playbooks,
                "count": len(playbooks),
                "message": f"共找到 {len(playbooks)} 个 playbook",
            }
        except Exception as e:
            logger.error(f"获取 playbook 列表失败: {str(e)}")
            return {
                "status": "error",
                "message": f"获取 playbook 列表失败: {str(e)}",
            }

    @server.mcp.tool(
        name="ansible_playbook",
        description="""
# Task: Run Ansible Playbook

## Workflow

- Run specified playbook on target hosts

## Tool Calls

```json
{
  "name": "ansible_playbook",
  "arguments": {
    "playbook": "playbook_name.yml",
    "targets": ["host1.example.com"],
    "extravars": {"var1": "value1", "var2": "value2"}, //Optional
    "password": "my_psw", //Optional
    "private_key": "path_to_key_file", //Optional
    "timeout": 600, //Optional
    "user": "admin", 
    "port": 22 //Optional
  }
}
```

## Important Notes
- The playbook name should be the filename (e.g., "system_check.yml") or the full path to the playbook file.
- Extra variables can be passed as a dictionary.
- If the playbook requires specific variables, make sure to include them in the extravars.

## Playbook Execution Flow
1. The system will check if Python is installed on the target hosts. If not, it will automatically install it.
2. The playbook will be executed with the provided parameters.
3. The result will be returned with detailed information for each host.

## Troubleshooting
- If the playbook execution fails, check the error message for details.
- Ensure that the playbook file exists in the playbooks directory.
- Verify that the target hosts are reachable and have the necessary permissions.
""",
    )
    @require_permission("ansible_playbook")
    def ansible_playbook(
        playbook: str,
        targets: List[str],
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        extravars: Optional[Union[Dict[str, Any], str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:

        logger.info(
            f"MCP 工具调用: ansible_playbook, playbook={playbook}, targets={targets}"
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
            task_id, "ansible_playbook", {"playbook": playbook, "targets": targets}
        )
        return server.execution_service.execute_playbook(playbook, targets, credentials, extravars, timeout, task_id)

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

    return locals()


def register_dynamic_playbook_tools(server):
    """注册动态playbook工具"""
    playbooks = server.playbook_scanner.scan_playbooks()
    for playbook in playbooks:
        playbook_name = playbook["name"]
        metadata = playbook.get("metadata", {})
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