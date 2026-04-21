"""
Unified service module

Unified service entry for MCP + REST API
"""

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from lib.auth import AuthMiddleware
from lib.config import Config
from lib.database import ContextRepository, Database, TaskRepository
from lib.error_handler import error_handler
from lib.execution_service import ExecutionService
from lib.executor import Executor
from lib.inventory_manager import InventoryManager
from lib.mcp_tools import register_mcp_tools
from lib.permission import require_permission
from lib.playbook_scanner import PlaybookScanner
from lib.tsc_logger import get_logger

logger = get_logger()


from lib.models import (
    AddInventoryRequest,
    CopyRequest,
    CredentialsModel,
    FetchRequest,
    HostRequest,
    PlaybookRequest,
    ShellRequest,
)


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

# 4. List playbooks
list_playbooks()

# 5. Execute playbook
ansible_playbook(playbook="system_check.yml", targets=["192.168.1.1"], user="root", password="xxx")
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
        # Set global auth instance for permission check decorator
        Server._auth_instance = self.auth
        # Update log configuration
        from lib.tsc_logger import tsc_logger

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
        register_mcp_tools(self)

    def _register_dynamic_playbook_tools(self) -> None:
        """Dynamically register playbook tools."""
        tool_definitions = self.playbook_scanner.scan_playbooks()

        for tool_def in tool_definitions:
            tool_name = tool_def["name"]
            tool_description = tool_def["description"]
            playbook_name = tool_name.replace("playbook_", "")

            def make_playbook_tool(playbook_name: str) -> Callable[..., Dict[str, Any]]:
                @require_permission(f"playbook_{playbook_name}")
                def playbook_tool(
                    targets: List[str],
                    extravars: Optional[Union[Dict[str, Any], str]] = None,
                    timeout: Optional[int] = None,
                ) -> Dict[str, Any]:

                    logger.info(
                        f"MCP tool call: playbook_{playbook_name}, targets={targets}"
                    )
                    parsed_extravars: Optional[Dict[str, Any]] = None
                    if extravars is not None:
                        if isinstance(extravars, str):
                            try:
                                parsed_extravars = json.loads(extravars)
                            except json.JSONDecodeError:
                                parsed_extravars = None
                        else:
                            parsed_extravars = extravars
                    task_id = str(uuid.uuid4())
                    self.task_repo.create(task_id, playbook_name, {"targets": targets})
                    return self.execution_service.execute_playbook(
                        playbook_name,
                        targets,
                        parsed_extravars,
                        timeout,
                        task_id,
                    )

                return playbook_tool

            tool_func: Callable[..., Dict[str, Any]] = make_playbook_tool(playbook_name)
            tool_func.__name__ = tool_name
            tool_func.__doc__ = tool_description

            decorated_tool = self.mcp.tool(
                name=tool_name,
                description=tool_description,
            )(tool_func)

            logger.info(f"Registered playbook tool: {tool_name}")

    def _create_fastapi_app(self) -> FastAPI:
        app = FastAPI(
            title="TSC_ANSIBLE_MCP API",
            description="TSC Ansible MCP REST API service",
            version="1.10.0",
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

        @app.get("/api/v1/executor/tasks/{task_id}", summary="Query task status")
        async def get_task(
            task_id: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task = self.task_repo.get(task_id)
            if task:
                return task
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

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
                return {"status": "success", "message": f"Task {task_id} deleted"}
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

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
                {"targets": request.targets, "src": request.src, "dest": request.dest},
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
                {"targets": request.targets, "src": request.src, "dest": request.dest},
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

        # Integrate package management routes
        from lib.api.routes import packages

        app.include_router(packages.router)

        return app

    def get_asgi_app(self):
        """Get ASGI application, mount MCP to FastAPI"""
        # Create MCP application (Streamable HTTP transport)
        # http_app(path="/") sets MCP endpoint to root path
        # Then we mount it to FastAPI at /mcp path
        mcp_app = self.mcp.http_app(path="/", transport="streamable-http")

        from lib.middleware import MCPAuthorizationMiddleware

        self.app.router.lifespan_context = mcp_app.router.lifespan_context

        # Wrap MCP application with authorization middleware
        authorized_mcp_app = MCPAuthorizationMiddleware(mcp_app, self.auth)

        # Mount MCP application to FastAPI application at /mcp path
        # This makes MCP endpoints at http://host:port/mcp
        # REST API endpoints at http://host:port/api/v1/...
        self.app.mount("/mcp", authorized_mcp_app)

        return self.app
