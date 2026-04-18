"""
统一服务模块

MCP + REST API 统一服务入口
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
    DeleteContextRequest,
    ErrorResponse,
    FetchRequest,
    GetContextRequest,
    HostRequest,
    InstallPythonRequest,
    InstallTscToolsRequest,
    PlaybookRequest,
    SetContextRequest,
    ShellRequest,
    TaskResponse,
)


class Server:
    """统一服务类，同时提供 MCP 和 REST API"""

    MCP_INSTRUCTIONS = """
TSC Ansible MCP Service - Remote Host Automation Management Toolkit

## Service Overview
This service provides automated remote host management capabilities, including host status checking, target host runtime environment bootstraping, command execution, file distribution, and more.
Built on Ansible, supporting batch operations on multiple hosts.

## Core Features
1. **Host Status Check** - Check architecture, distribution, tsc_tools, and tsc_python(a pre-compiled python3 environment) installation status
2. **Software Installation** - Install tsc_tools toolkit and tsc_python environment
3. **Command Execution** - Execute shell commands on remote hosts
4. **File Operations** - File distribution and retrieval
5. **Playbook Execution** - Run Ansible playbooks

## Important: Installation Order
When bootstraping runtime envionment, you must follow this order, do not reverse:
1. **Install tsc_tools first** - Call install_tsc_tools
2. **Then install tsc_python** - Call install_python

## Recommended Workflow
1. Call check_host_status to check host status
2. If tsc_tools or tsc_python is not installed -> Call bootstrap_tsc_environment, it will install tsc_tools and tsc_python
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

# 2. Install tsc_tools and tsc_python (recommended)
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
        # 设置全局 auth 实例，供权限检查装饰器使用
        Server._auth_instance = self.auth
        # 更新日志配置
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
        """执行服务"""
        return ExecutionService(self.executor, self.task_repo, logger)

    def _register_mcp_tools(self) -> None:
        """注册MCP工具"""
        register_mcp_tools(self)

    def _register_dynamic_playbook_tools(self) -> None:
        """动态注册 playbook 工具"""
        self.playbook_scanner.scan_playbooks()

        for playbook_name, metadata in self.playbook_scanner.playbooks.items():
            tool_description = self.playbook_scanner.generate_tool_definition(metadata)
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

                    logger.info(
                        f"MCP 工具调用: playbook_{playbook_name}, targets={targets}"
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
                    self.task_repo.create(task_id, playbook_name, {"targets": targets})
                    return self.execution_service.execute_playbook(
                        playbook_name,
                        targets,
                        credentials,
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

            logger.info(f"已注册 playbook 工具: {tool_name}")

    def _create_fastapi_app(self) -> FastAPI:
        app = FastAPI(
            title="TSC_ANSIBLE_MCP API",
            description="TSC Ansible MCP REST API 服务",
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

        @app.post("/api/v1/shell", summary="执行 Shell 命令")
        @error_handler
        async def ansible_shell(
            request: ShellRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_shell",
                {"targets": request.targets, "command": request.command},
            )
            result = self.execution_service.execute_shell(
                targets=request.targets,
                command=request.command,
                credentials=credentials if credentials else None,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.get("/api/v1/executor/tasks/{task_id}", summary="查询任务状态")
        async def get_task(
            task_id: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            task = self.task_repo.get(task_id)
            if task:
                return task
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        @app.get("/api/v1/executor/tasks", summary="查询任务列表")
        async def list_tasks(
            status_filter: Optional[str] = None,
            limit: int = 100,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> List[Dict[str, Any]]:
            return self.task_repo.list(status=status_filter, limit=limit)

        @app.delete("/api/v1/executor/tasks/{task_id}", summary="删除任务")
        async def delete_task(
            task_id: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, str]:
            if self.task_repo.delete(task_id):
                return {"status": "success", "message": f"任务 {task_id} 已删除"}
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        @app.get("/api/v1/executor/stats", summary="任务统计")
        async def get_stats(
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, int]:
            return self.task_repo.stats()

        @app.post("/api/v1/hosts/status", summary="检查主机状态")
        @error_handler
        async def check_host_status(
            request: HostRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "check_host_status", {"targets": request.targets}
            )
            result = self.execution_service.check_host_status(
                targets=request.targets,
                credentials=credentials if credentials else None,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post("/api/v1/hosts/python/install", summary="安装 Python")
        @error_handler
        async def install_python(
            request: InstallPythonRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "install_python", {"targets": request.targets}
            )
            result = self.execution_service.install_python(
                targets=request.targets,
                credentials=credentials if credentials else None,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post("/api/v1/hosts/tsc_tools/install", summary="安装 tsc_tools")
        @error_handler
        async def install_tsc_tools(
            request: InstallTscToolsRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "install_tsc_tools", {"targets": request.targets}
            )
            result = self.execution_service.install_tsc_tools(
                targets=request.targets,
                credentials=credentials if credentials else None,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post("/api/v1/copy", summary="Ansible Copy 模块")
        @error_handler
        async def ansible_copy(
            request: CopyRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
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
                credentials=credentials if credentials else None,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post(
            "/api/v1/fetch",
            summary="Ansible Fetch 模块",
        )
        @error_handler
        async def ansible_fetch(
            request: FetchRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
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
                credentials=credentials if credentials else None,
                flat=request.flat,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.get(
            "/api/v1/playbooks",
            summary="列出 Playbook",
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

        @app.post("/api/v1/playbooks/execute", summary="执行 Playbook")
        @error_handler
        async def execute_playbook(
            request: PlaybookRequest,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id,
                "ansible_playbook",
                {"playbook": request.playbook, "targets": request.targets},
            )
            result = self.execution_service.execute_playbook(
                playbook=request.playbook,
                targets=request.targets,
                credentials=credentials if credentials else None,
                extravars=request.extravars,
                timeout=request.timeout,
                task_id=task_id,
            )
            return result

        @app.post(
            "/api/v1/inventory",
            summary="添加主机到 Inventory",
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
            summary="查询 Inventory",
        )
        async def list_inventory(
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            return self.inventory_manager.list_hosts()

        @app.delete(
            "/api/v1/inventory/{host}",
            summary="从 Inventory 删除主机",
        )
        async def remove_inventory(
            host: str,
            user_info: Dict[str, Any] = Depends(self.auth.verify_request),
        ) -> Dict[str, Any]:
            return self.inventory_manager.remove_host(host)

        @app.get("/health", summary="健康检查")
        async def health_check() -> Dict[str, str]:
            return {"status": "healthy"}

        # 集成包管理路由
        from lib.api.routes import packages

        app.include_router(packages.router)

        return app

    def get_asgi_app(self):
        """获取 ASGI 应用，挂载 MCP 到 FastAPI"""
        # 创建 MCP 应用（Streamable HTTP transport）
        # http_app(path="/") 设置 MCP 端点为根路径
        # 然后我们会将它挂载到 FastAPI 的 /mcp 路径
        mcp_app = self.mcp.http_app(path="/", transport="streamable-http")

        from lib.middleware import MCPAuthorizationMiddleware

        self.app.router.lifespan_context = mcp_app.router.lifespan_context

        # 使用授权中间件包装 MCP 应用
        authorized_mcp_app = MCPAuthorizationMiddleware(mcp_app, self.auth)

        # 将 MCP 应用挂载到 FastAPI 应用的 /mcp 路径
        # 这样 MCP 端点在 http://host:port/mcp
        # REST API 端点在 http://host:port/api/v1/...
        self.app.mount("/mcp", authorized_mcp_app)

        return self.app
