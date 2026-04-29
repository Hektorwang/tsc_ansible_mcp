"""
Unified service module

Unified service entry for MCP + REST API
"""

# pylint: disable=unused-argument,wrong-import-position,import-outside-toplevel

import json
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from lib.api.routes import packages
from lib.auth import AuthMiddleware
from lib.config import Config
from lib.database import ContextRepository, Database, TaskRepository
from lib.error_handler import error_handler
from lib.execution_service import ExecutionService
from lib.executor import Executor
from lib.inventory_manager import InventoryManager
from lib.mcp_tools import register_mcp_tools
from lib.middleware import MCPAuthorizationMiddleware
from lib.models import (
    AddInventoryRequest,
    CopyRequest,
    FetchRequest,
    HostRequest,
    PlaybookRequest,
    ShellRequest,
)
from lib.permission import require_permission
from lib.playbook_scanner import PlaybookScanner
from lib.tsc_logger import get_logger, tsc_logger

logger = get_logger()


class Server:
    """Unified service class providing both MCP and REST API"""

    MCP_INSTRUCTIONS = """
TSC Ansible MCP Service - Remote Host Automation Management Toolkit

## Service Overview
This service provides automated remote host management capabilities, including host status checking, target host runtime environment bootstraping, command execution, file distribution, and more.
Built on Ansible, supporting batch operations on multiple hosts.

## Core Features
1. **Host Status Check** - Check architecture, distribution, tsc_tools, and tsc_python(a pre-compiled python3 environment) installation status
2. **Software Installation** - Install tsc_tools and tsc_python(python3) via playbook_bootstrap_tsc_environment
3. **Command Execution** - Execute shell commands on remote hosts
4. **File Operations** - File distribution and retrieval
5. **Playbook Execution** - Run Ansible playbooks

## Recommended Workflow
1. Call check_host_status to check host status
2. If tsc_tools or tsc_python is not installed -> Call playbook_bootstrap_tsc_environment to install both
3. After successful installation -> Perform other operations

## Important Note
If check_host_status reports that tsc_tools or tsc_python are not installed, use the bootstrap_tsc_environment playbook tool to install them.

## Authentication Methods
Supports both password and private key SSH authentication:
- Password authentication: Provide user, password parameters
- Private key authentication: Provide user, private_key parameters

## Usage Examples
```
# 1. Check host status
check_host_status(targets=["192.168.1.1"], user="root", password="xxx")

# 2. Bootstrap environment (install tsc_tools and tsc_python)
playbook_bootstrap_tsc_environment(targets=["192.168.1.1"], user="root", password="xxx")

# 3. Execute command
ansible_shell(targets=["192.168.1.1"], command="ls -la", user="root", password="xxx")

# 4. Execute playbook
playbook_system_check(targets=["192.168.1.1"], user="root", password="xxx")
```
"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        base_dir = self.config.path.parent.parent
        db_path = base_dir / "logs" / "tsc_ansible_mcp.db"
        self.database = Database(db_path)
        self.task_repo = TaskRepository(self.database)
        self.context_repo = ContextRepository(self.database)
        self.inventory_manager = InventoryManager()
        self.executor = Executor(self.config, self.inventory_manager)
        self.auth = AuthMiddleware(self.config)
        Server._auth_instance = self.auth
        tsc_logger.update_config(self.config._data)
        self.playbook_scanner = PlaybookScanner(self.config)
        self.mcp = FastMCP(
            name="tsc_ansible_mcp",
            version=self.config.mcp_version,
            instructions=self.MCP_INSTRUCTIONS,
        )
        self._register_mcp_tools()
        self._register_dynamic_playbook_tools()
        self.app = self._create_fastapi_app()

    @property
    def execution_service(self) -> ExecutionService:
        """Execution service."""
        return ExecutionService(self.executor, self.task_repo, logger)

    def _register_mcp_tools(self) -> None:
        """Register MCP tools."""
        logger.info("Starting static MCP tool registration...")
        register_mcp_tools(self)
        logger.info("Static MCP tools registered successfully")

    def _register_dynamic_playbook_tools(self) -> None:
        """Dynamically register playbook tools."""
        logger.info("Starting dynamic playbook tool registration...")
        tool_definitions = self.playbook_scanner.scan_playbooks()
        logger.info(f"Found {len(tool_definitions)} playbook definitions to register")

        for tool_def in tool_definitions:
            tool_name = tool_def["name"]
            # Prepend a mandatory prerequisites notice so LLM always calls
            # check_host_status before invoking any playbook tool.
            prerequisites_notice = (
                "## Prerequisites\n"
                "- Target hosts must be configured in inventory.yml first.\n"
                "- REQUIRED: Call check_host_status before this tool to verify:\n"
                "  1. Host is reachable via SSH.\n"
                "  2. Python is installed (required for playbook execution).\n"
                "  If Python is not installed, run playbook_bootstrap_tsc_environment first.\n"
                "- If the task takes longer than expected, status will be \"running\" - "
                "use get_task_status(task_id) to poll for the final result.\n\n"
            )
            tool_description = prerequisites_notice + tool_def["description"]
            playbook_name = tool_name.replace("playbook_", "")

            param_props = tool_def.get("parameters", {}).get("properties", {})
            playbook_params = []  # 不包含 'targets', 'extravars', 'timeout'

            for param_name, param_info in param_props.items():
                if param_name not in ("targets", "extravars", "timeout"):
                    playbook_params.append((param_name, param_info))

            # 动态构造函数签名
            from typing import Optional, Union, Dict, Any, List

            # 构造函数签名字符串
            sig_parts = [
                "self",  # 不，等等，我们需要创建一个闭包！
                "targets: List[str]",
                "extravars: Optional[Union[Dict[str, Any], str]] = None",
                "timeout: Optional[int] = None",
            ]

            # 添加 playbook 特定参数
            param_defaults = {}
            for param_name, param_info in playbook_params:
                param_type = param_info.get("type")
                if param_type == "string":
                    sig_part = f"{param_name}: Optional[str] = None"
                elif param_type == "integer":
                    sig_part = f"{param_name}: Optional[int] = None"
                elif param_type == "object":
                    sig_part = f"{param_name}: Optional[Dict[str, Any]] = None"
                elif param_type == "array":
                    sig_part = f"{param_name}: Optional[List[Dict[str, Any]]] = None"
                else:
                    sig_part = f"{param_name}: Optional[Any] = None"
                sig_parts.append(sig_part)
                param_defaults[param_name] = None  # 默认值都是 None

            # 构造函数体
            func_body_lines = [
                "logger.info(",
                '    "MCP tool call: playbook_%s, targets=%s, extravars=%s",',
                "    playbook_name,",
                "    targets,",
                "    extravars,",
                ")",
                "parsed_extravars: Optional[Dict[str, Any]] = None",
                "",
                "if extravars is not None:",
                "    if isinstance(extravars, str):",
                "        try:",
                "            parsed_extravars = json.loads(extravars)",
                "        except json.JSONDecodeError:",
                "            parsed_extravars = None",
                "    else:",
                "        parsed_extravars = extravars",
                "",
                "playbook_vars = {}",
            ]

            # 收集 playbook 特定参数
            for param_name, _ in playbook_params:
                func_body_lines.extend(
                    [
                        f"if {param_name} is not None:",
                        f'    playbook_vars["{param_name}"] = {param_name}',
                    ]
                )

            func_body_lines.extend(
                [
                    "",
                    "if parsed_extravars and playbook_vars:",
                    "    merged = {**parsed_extravars, **playbook_vars}",
                    "    parsed_extravars = merged",
                    "elif playbook_vars:",
                    "    parsed_extravars = playbook_vars",
                    "",
                    "task_id = str(uuid.uuid4())",
                    'params = {"targets": targets}',
                    "self.task_repo.create(task_id, playbook_name, params)",
                    "result = self.execution_service.execute_playbook(",
                    "    playbook_name,",
                    "    targets,",
                    "    parsed_extravars,",
                    "    timeout,",
                    "    task_id,",
                    ")",
                    "logger.info(",
                    '    "MCP tool response: playbook_%s, task_id=%s, result=%s",',
                    "    playbook_name,",
                    "    task_id,",
                    "    result,",
                    ")",
                    "return result",
                ]
            )

            # 使用 exec() 动态创建函数
            # 创建一个 locals 字典来存储函数
            func_locals = {
                "json": json,
                "uuid": uuid,
                "logger": logger,
                "self": self,
                "playbook_name": playbook_name,
                "List": List,
                "Optional": Optional,
                "Union": Union,
                "Dict": Dict,
                "Any": Any,
            }

            # 构建完整的函数源码
            full_func_src = f"""def {tool_name}({', '.join(sig_parts[1:])}) -> Dict[str, Any]:
    """ + "\n    ".join(
                func_body_lines
            )

            # 执行源码来创建函数
            exec(full_func_src, func_locals)
            playbook_tool = func_locals[tool_name]

            # 装饰工具并注册
            playbook_tool = require_permission(f"playbook_{playbook_name}")(
                playbook_tool
            )
            self.mcp.tool(name=tool_name, description=tool_description)(playbook_tool)

            logger.info(f"Registered playbook tool: {tool_name}")

        logger.info(f"Total dynamic playbook tools registered: {len(tool_definitions)}")

    def _create_fastapi_app(self) -> FastAPI:
        app = FastAPI(
            title="TSC_ANSIBLE_MCP API",
            description="TSC Ansible MCP REST API service",
            version=self.config.mcp_version,
            docs_url="/docs",
            redoc_url="/redoc",
        )

        @app.exception_handler(HTTPException)
        async def http_exception_handler(request, exc):
            return JSONResponse(
                status_code=exc.status_code,
                content={"status": "error", "message": exc.detail},
            )

        @app.post("/api/v1/shell", summary="Execute Shell command")
        @error_handler
        async def ansible_shell(
            request: ShellRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_shell",
                {"targets": request.targets, "command": request.command},
            )
            result = self.execution_service.execute_shell(
                targets=request.targets,
                command=request.command,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.get(
            "/api/v1/executor/tasks/{task_id}",
            summary="Query task status",
        )
        async def get_task(
            task_id: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task = self.task_repo.get(task_id)
            if task:
                return task
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}",
            )

        @app.get("/api/v1/executor/tasks", summary="Query task list")
        async def list_tasks(
            status_filter: Optional[str] = None,
            limit: int = 100,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> List[Dict[str, Any]]:
            return self.task_repo.list(status=status_filter, limit=limit)

        @app.delete("/api/v1/executor/tasks/{task_id}", summary="Delete task")
        async def delete_task(
            task_id: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, str]:
            if self.task_repo.delete(task_id):
                return {
                    "status": "success",
                    "message": f"Task {task_id} deleted",
                }
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}",
            )

        @app.get("/api/v1/executor/stats", summary="Task statistics")
        async def get_stats(
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, int]:
            return self.task_repo.stats()

        @app.post("/api/v1/hosts/status", summary="Check host status")
        @error_handler
        async def check_host_status(
            request: HostRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "check_host_status", {"targets": request.targets}
            )
            result = self.execution_service.check_host_status(
                targets=request.targets,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post("/api/v1/copy", summary="Ansible Copy module")
        @error_handler
        async def ansible_copy(
            request: CopyRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_copy",
                {
                    "targets": request.targets,
                    "src": request.src,
                    "dest": request.dest,
                },
            )
            result = self.execution_service.ansible_copy(
                targets=request.targets,
                src=request.src,
                dest=request.dest,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post(
            "/api/v1/fetch",
            summary="Ansible Fetch module",
        )
        @error_handler
        async def ansible_fetch(
            request: FetchRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_fetch",
                {
                    "targets": request.targets,
                    "src": request.src,
                    "dest": request.dest,
                },
            )
            result = self.execution_service.ansible_fetch(
                targets=request.targets,
                src=request.src,
                dest=request.dest,
                flat=request.flat,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.get(
            "/api/v1/playbooks",
            summary="List playbooks",
        )
        async def list_playbooks(
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            playbooks = self.playbook_scanner.scan_playbooks()
            return {
                "status": "success",
                "playbooks": list(playbooks.values()),
                "count": len(playbooks),
            }

        @app.post("/api/v1/playbooks/execute", summary="Execute Playbook")
        @error_handler
        async def execute_playbook(
            request: PlaybookRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_playbook",
                {"playbook": request.playbook, "targets": request.targets},
            )
            result = self.execution_service.execute_playbook(
                playbook=request.playbook,
                targets=request.targets,
                extravars=request.extravars,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post(
            "/api/v1/inventory",
            summary="Add host to inventory",
        )
        async def add_inventory(
            request: AddInventoryRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            return self.inventory_manager.add_host(
                host=request.host,
                user=credentials.get("user"),
                port=credentials.get("port"),
                password=credentials.get("password"),
                private_key=credentials.get("private_key"),
            )

        @app.get(
            "/api/v1/inventory",
            summary="Query inventory",
        )
        async def list_inventory(
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            return self.inventory_manager.list_hosts()

        @app.delete(
            "/api/v1/inventory/{host}",
            summary="Remove host from inventory",
        )
        async def remove_inventory(
            host: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            return self.inventory_manager.remove_host(host)

        @app.get("/health", summary="Health check")
        async def health_check() -> Dict[str, str]:
            return {"status": "healthy"}

        app.include_router(packages.router)

        return app

    def get_asgi_app(self):
        """Get ASGI application, mount MCP to FastAPI."""
        mcp_app = self.mcp.http_app(path="/", transport="streamable-http")
        self.app.router.lifespan_context = mcp_app.router.lifespan_context

        authorized_mcp_app = MCPAuthorizationMiddleware(mcp_app, self.auth)

        self.app.mount("/mcp", authorized_mcp_app)

        return self.app
