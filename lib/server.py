"""
统一服务模块

MCP + REST API 统一服务入口
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from pydantic import BaseModel, Field

from lib.config import Config
from lib.database import Database, TaskRepository
from lib.executor import Executor
from lib.inventory_manager import InventoryManager
from lib.logger import get_logger

logger = get_logger()


class CredentialsModel(BaseModel):
    user: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    private_key: Optional[str] = None


class ShellRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    command: str = Field(..., description="命令内容")
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = None


class CopyRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    src: str = Field(..., description="本地源文件路径")
    dest: str = Field(..., description="远程目标路径")
    credentials: Optional[CredentialsModel] = None
    mode: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
    timeout: Optional[int] = None


class FetchRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    src: str = Field(..., description="远程源文件路径")
    dest: str = Field(..., description="本地目标目录")
    credentials: Optional[CredentialsModel] = None
    flat: bool = False
    timeout: Optional[int] = None


class PlaybookRequest(BaseModel):
    playbook: str = Field(..., description="playbook 文件名或路径")
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    credentials: Optional[CredentialsModel] = None
    extravars: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = None


class HostRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = None


class InstallPythonRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    credentials: Optional[CredentialsModel] = None
    version: Optional[str] = None
    date: Optional[str] = None
    timeout: Optional[int] = None


class InstallTscToolsRequest(BaseModel):
    targets: List[str] = Field(..., description="目标主机 IP 列表")
    credentials: Optional[CredentialsModel] = None
    version: Optional[str] = None
    date: Optional[str] = None
    timeout: Optional[int] = None


class AddInventoryRequest(BaseModel):
    host: str = Field(..., description="主机 IP 地址")
    credentials: Optional[CredentialsModel] = None


class TaskResponse(BaseModel):
    id: str
    type: str
    parameters: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str


class Server:
    """统一服务类，同时提供 MCP 和 REST API"""

    MCP_INSTRUCTIONS = """
TSC Ansible MCP 服务 - 远程主机自动化管理工具集

## 服务简介
本服务提供远程主机的自动化管理能力，包括主机状态检查、软件安装、命令执行、文件分发等功能。
基于 Ansible 实现，支持批量操作多台主机。

## 核心功能
1. **主机状态检查** - 检查架构、发行版、Python、tsc_tools 安装状态
2. **软件安装** - 安装 tsc_tools 工具集和 tsc_python 环境
3. **命令执行** - 在远程主机上执行 shell 命令
4. **文件操作** - 文件分发和获取
5. **Playbook 执行** - 运行 Ansible playbook

## 重要：安装顺序
安装软件时必须遵循以下顺序，不可颠倒：
1. **先安装 tsc_tools** - 调用 install_tsc_tools
2. **再安装 tsc_python** - 调用 install_python

## 推荐工作流程
1. 调用 check_host_status 检查主机状态
2. 如果 tsc_tools 未安装 -> 调用 install_tsc_tools
3. 如果 Python 未安装 -> 调用 install_python
4. 安装成功后 -> 执行其他操作

## 认证方式
支持密码和私钥两种 SSH 认证方式：
- 密码认证：传递 user、password 参数
- 私钥认证：传递 user、private_key 参数

## 使用示例
```
# 1. 检查主机状态
check_host_status(targets=["192.168.1.1"], user="root", password="xxx")

# 2. 安装 tsc_tools（必须先安装）
install_tsc_tools(targets=["192.168.1.1"], user="root", password="xxx")

# 3. 安装 Python
install_python(targets=["192.168.1.1"], user="root", password="xxx")

# 4. 执行命令
ansible_shell(targets=["192.168.1.1"], command="ls -la", user="root", password="xxx")

# 5. 列出 playbook
list_playbooks()

# 6. 执行 playbook
ansible_playbook(playbook="system_check.yml", targets=["192.168.1.1"], user="root", password="xxx")
```
"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        base_dir = self.config.path.parent.parent
        db_path = base_dir / "logs" / "tsc_ansible_mcp.db"
        self.database = Database(db_path)
        self.task_repo = TaskRepository(self.database)
        self.inventory_manager = InventoryManager()
        self.executor = Executor(self.config, self.inventory_manager)
        self.mcp = FastMCP(
            name="tsc_ansible_mcp",
            version="1.0.0",
            instructions=self.MCP_INSTRUCTIONS,
        )
        self._register_mcp_tools()
        self.app = self._create_fastapi_app()

    def _register_mcp_tools(self) -> None:
        @self.mcp.tool(
            name="ansible_shell",
            description="""在目标主机上执行 shell 命令。支持同时向多台主机批量执行命令，返回每台主机的执行结果。

重要提示：
- 执行前会自动检查主机状态，如果 Python 未安装会自动安装
- 建议先调用 check_host_status 确认主机环境

命令格式注意：
- 命令中包含双引号时，请使用单引号替代，例如: find /tmp -name '*.json'
- 或者在 JSON 中转义双引号，例如: find /tmp -name \"*.json\"
- 避免在命令中使用复杂的引号嵌套""",
        )
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
            self.task_repo.create(
                task_id, "ansible_shell", {"targets": targets, "command": command}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_shell(
                    targets=targets,
                    command=command,
                    credentials=credentials if credentials else None,
                    timeout=timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"ansible_shell 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {"task_id": task_id, "status": "failed", "error": str(e)}

        @self.mcp.tool(
            name="install_python",
            description="""在目标主机上安装 Python 环境。自动检测主机架构和发行版，下载对应的安装包进行安装。已安装的主机会跳过。

重要提示：安装 Python 前必须先安装 tsc_tools！如果 tsc_tools 未安装，请先调用 install_tsc_tools 工具。""",
        )
        def install_python(
            targets: List[str],
            user: Optional[str] = None,
            port: Optional[int] = None,
            password: Optional[str] = None,
            private_key: Optional[str] = None,
            version: Optional[str] = None,
            date: Optional[str] = None,
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
            self.task_repo.create(task_id, "install_python", {"targets": targets})
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.install_python(
                    targets=targets,
                    credentials=credentials if credentials else None,
                    version=version,
                    date=date,
                    timeout=timeout,
                )
                failed_hosts = []
                for host, r in result.get("results", {}).items():
                    if not r.get("installed") and not r.get("skipped"):
                        failed_hosts.append({"host": host, "message": r.get("message", "安装失败")})
                if failed_hosts:
                    result["error"] = "Python 安装失败，请停止后续操作并退出流程"
                    result["failed_hosts"] = failed_hosts
                    result["action_required"] = "请停止当前流程，向用户报告错误信息，不要继续执行后续操作"
                self.task_repo.update(task_id, "success" if not failed_hosts else "partial_success", result)
                return result
            except Exception as e:
                logger.exception(f"install_python 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                    "action_required": "请停止当前流程，向用户报告错误信息，不要继续执行后续操作",
                }

        @self.mcp.tool(
            name="check_host_status",
            description="""检查目标主机的状态，包括架构、发行版、Python 安装状态、tsc_tools 安装状态等。

重要提示（安装顺序）：
1. 如果 tsc_tools 未安装，请先调用 install_tsc_tools 工具进行安装
2. 如果 Python 未安装，请在 tsc_tools 安装成功后，调用 install_python 工具进行安装
3. 安装顺序：tsc_tools -> tsc_python，不可颠倒

注意：如果某个主机返回 error 字段（主机不可达），请勿对该主机执行后续操作！""",
        )
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
            self.task_repo.create(task_id, "check_host_status", {"targets": targets})
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.check_host_status(
                    targets=targets,
                    credentials=credentials if credentials else None,
                    timeout=timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, "success", result)
                return result
            except Exception as e:
                logger.exception(f"check_host_status 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {"task_id": task_id, "status": "failed", "error": str(e)}

        @self.mcp.tool(
            name="get_task_status",
            description="查询任务执行状态。通过 task_id 查询异步任务的执行结果和状态。",
        )
        def get_task_status(task_id: str) -> Dict[str, Any]:
            logger.info(f"MCP 工具调用: get_task_status, task_id={task_id}")
            task = self.task_repo.get(task_id)
            if task:
                return task
            return {"status": "error", "message": f"任务不存在: {task_id}"}

        @self.mcp.tool(
            name="install_tsc_tools",
            description="""在目标主机上安装 tsc_tools 工具集。自动从配置的 Nginx 服务器下载安装包并执行安装。已安装的主机会跳过。

安装顺序说明：tsc_tools 必须在 tsc_python 之前安装。安装完成后再调用 install_python 工具。""",
        )
        def install_tsc_tools(
            targets: List[str],
            user: Optional[str] = None,
            port: Optional[int] = None,
            password: Optional[str] = None,
            private_key: Optional[str] = None,
            version: Optional[str] = None,
            date: Optional[str] = None,
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
            self.task_repo.create(task_id, "install_tsc_tools", {"targets": targets})
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.install_tsc_tools(
                    targets=targets,
                    credentials=credentials if credentials else None,
                    version=version,
                    date=date,
                    timeout=timeout,
                )
                failed_hosts = []
                for host, r in result.get("results", {}).items():
                    if not r.get("installed") and not r.get("skipped"):
                        failed_hosts.append({"host": host, "message": r.get("message", "安装失败")})
                if failed_hosts:
                    result["error"] = "tsc_tools 安装失败，请停止后续操作并退出流程"
                    result["failed_hosts"] = failed_hosts
                    result["action_required"] = "请停止当前流程，向用户报告错误信息，不要继续执行后续操作"
                result["task_id"] = task_id
                self.task_repo.update(task_id, "success" if not failed_hosts else "partial_success", result)
                return result
            except Exception as e:
                logger.exception(f"install_tsc_tools 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                    "action_required": "请停止当前流程，向用户报告错误信息，不要继续执行后续操作",
                }

        @self.mcp.tool(
            name="ansible_copy",
            description="""分发本地文件到目标主机。将本地的文件通过 SSH 传输到目标主机的指定路径，支持同时分发到多台主机。

重要提示：
- 执行前会自动检查主机状态，如果 Python 未安装会自动安装
- 建议先调用 check_host_status 确认主机环境""",
        )
        def ansible_copy(
            targets: List[str],
            src: str,
            dest: str,
            user: Optional[str] = None,
            port: Optional[int] = None,
            password: Optional[str] = None,
            private_key: Optional[str] = None,
            mode: Optional[str] = None,
            owner: Optional[str] = None,
            group: Optional[str] = None,
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
            self.task_repo.create(
                task_id, "ansible_copy", {"targets": targets, "src": src, "dest": dest}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_copy(
                    targets=targets,
                    src=src,
                    dest=dest,
                    credentials=credentials if credentials else None,
                    timeout=timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"ansible_copy 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {"task_id": task_id, "status": "failed", "error": str(e)}

        @self.mcp.tool(
            name="ansible_fetch",
            description="""从远程主机获取文件到本地。通过 SSH 从目标主机下载文件到本地指定目录，支持同时从多台主机获取文件。

重要提示：
- 执行前会自动检查主机状态，如果 Python 未安装会自动安装
- 建议先调用 check_host_status 确认主机环境""",
        )
        def ansible_fetch(
            targets: List[str],
            src: str,
            dest: str,
            user: Optional[str] = None,
            port: Optional[int] = None,
            password: Optional[str] = None,
            private_key: Optional[str] = None,
            flat: bool = False,
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
            self.task_repo.create(
                task_id, "ansible_fetch", {"targets": targets, "src": src, "dest": dest}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_fetch(
                    targets=targets,
                    src=src,
                    dest=dest,
                    credentials=credentials if credentials else None,
                    flat=flat,
                    timeout=timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"ansible_fetch 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {"task_id": task_id, "status": "failed", "error": str(e)}

        @self.mcp.tool(
            name="list_playbooks",
            description="列出所有可用的 playbook 文件。返回 playbooks 目录下所有 playbook 文件及其元数据信息，包括描述、作者、版本等。",
        )
        def list_playbooks() -> Dict[str, Any]:
            logger.info("MCP 工具调用: list_playbooks")
            return self.executor.list_playbooks()

        @self.mcp.tool(
            name="ansible_playbook",
            description="""执行指定的 playbook 文件。在目标主机上运行 playbook，支持传入额外变量。

重要提示：
- 执行前会自动检查主机状态，如果 Python 未安装会自动安装
- 建议先调用 check_host_status 确认主机环境""",
        )
        def ansible_playbook(
            playbook: str,
            targets: List[str],
            user: Optional[str] = None,
            port: Optional[int] = None,
            password: Optional[str] = None,
            private_key: Optional[str] = None,
            extravars: Optional[Dict[str, Any]] = None,
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
            self.task_repo.create(
                task_id, "ansible_playbook", {"playbook": playbook, "targets": targets}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.run_playbook(
                    playbook=playbook,
                    targets=targets,
                    credentials=credentials if credentials else None,
                    extravars=extravars,
                    timeout=timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"ansible_playbook 执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                return {"task_id": task_id, "status": "failed", "error": str(e)}

    def _create_fastapi_app(self) -> FastAPI:
        app = FastAPI(
            title="TSC_ANSIBLE_MCP API",
            description="TSC Ansible MCP REST API 服务",
            version="1.1.0",
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
        async def ansible_shell(request: ShellRequest) -> Dict[str, Any]:
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
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_shell(
                    targets=request.targets,
                    command=request.command,
                    credentials=credentials if credentials else None,
                    timeout=request.timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"执行 Shell 命令失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/v1/executor/tasks/{task_id}", summary="查询任务状态")
        async def get_task(task_id: str) -> Dict[str, Any]:
            task = self.task_repo.get(task_id)
            if task:
                return task
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        @app.get("/api/v1/executor/tasks", summary="查询任务列表")
        async def list_tasks(
            status_filter: Optional[str] = None, limit: int = 100
        ) -> List[Dict[str, Any]]:
            return self.task_repo.list(status=status_filter, limit=limit)

        @app.delete("/api/v1/executor/tasks/{task_id}", summary="删除任务")
        async def delete_task(task_id: str) -> Dict[str, str]:
            if self.task_repo.delete(task_id):
                return {"status": "success", "message": f"任务 {task_id} 已删除"}
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

        @app.get("/api/v1/executor/stats", summary="任务统计")
        async def get_stats() -> Dict[str, int]:
            return self.task_repo.stats()

        @app.post("/api/v1/hosts/status", summary="检查主机状态")
        async def check_host_status(request: HostRequest) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "check_host_status", {"targets": request.targets}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.check_host_status(
                    targets=request.targets,
                    credentials=credentials if credentials else None,
                    timeout=request.timeout,
                )
                self.task_repo.update(task_id, "success", result)
                return result
            except Exception as e:
                logger.exception(f"检查主机状态失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v1/hosts/python/install", summary="安装 Python")
        async def install_python(request: InstallPythonRequest) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "install_python", {"targets": request.targets}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.install_python(
                    targets=request.targets,
                    credentials=credentials if credentials else None,
                    version=request.version,
                    date=request.date,
                    timeout=request.timeout,
                )
                task_status = (
                    "success"
                    if all(
                        r.get("installed") or r.get("skipped")
                        for r in result["results"].values()
                    )
                    else "partial_success"
                )
                self.task_repo.update(task_id, task_status, result)
                return result
            except Exception as e:
                logger.exception(f"安装 Python 失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v1/hosts/tsc_tools/install", summary="安装 tsc_tools")
        async def install_tsc_tools(request: InstallTscToolsRequest) -> Dict[str, Any]:
            credentials = (
                request.credentials.model_dump(exclude_none=True)
                if request.credentials
                else {}
            )
            task_id = str(uuid.uuid4())
            self.task_repo.create(
                task_id, "install_tsc_tools", {"targets": request.targets}
            )
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.install_tsc_tools(
                    targets=request.targets,
                    credentials=credentials if credentials else None,
                    version=request.version,
                    date=request.date,
                    timeout=request.timeout,
                )
                task_status = (
                    "success"
                    if all(
                        r.get("installed") or r.get("skipped")
                        for r in result["results"].values()
                    )
                    else "partial_success"
                )
                self.task_repo.update(task_id, task_status, result)
                return result
            except Exception as e:
                logger.exception(f"安装 tsc_tools 失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v1/copy", summary="Ansible Copy 模块")
        async def ansible_copy(request: CopyRequest) -> Dict[str, Any]:
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
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_copy(
                    targets=request.targets,
                    src=request.src,
                    dest=request.dest,
                    credentials=credentials if credentials else None,
                    timeout=request.timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"Copy 模块执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v1/fetch", summary="Ansible Fetch 模块")
        async def ansible_fetch(request: FetchRequest) -> Dict[str, Any]:
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
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.ansible_fetch(
                    targets=request.targets,
                    src=request.src,
                    dest=request.dest,
                    credentials=credentials if credentials else None,
                    flat=request.flat,
                    timeout=request.timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"Fetch 模块执行失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/api/v1/playbooks", summary="列出 Playbook")
        async def list_playbooks() -> Dict[str, Any]:
            return self.executor.list_playbooks()

        @app.post("/api/v1/playbooks/execute", summary="执行 Playbook")
        async def execute_playbook(request: PlaybookRequest) -> Dict[str, Any]:
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
            try:
                self.task_repo.update(task_id, "running")
                result = self.executor.run_playbook(
                    playbook=request.playbook,
                    targets=request.targets,
                    credentials=credentials if credentials else None,
                    extravars=request.extravars,
                    timeout=request.timeout,
                )
                result["task_id"] = task_id
                self.task_repo.update(task_id, result["status"], result)
                return result
            except Exception as e:
                logger.exception(f"执行 Playbook 失败: {e}")
                self.task_repo.update(task_id, "failed", {"error": str(e)})
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/api/v1/inventory", summary="添加主机到 Inventory")
        async def add_inventory(request: AddInventoryRequest) -> Dict[str, Any]:
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

        @app.get("/api/v1/inventory", summary="查询 Inventory")
        async def list_inventory() -> Dict[str, Any]:
            return self.inventory_manager.list_hosts()

        @app.delete("/api/v1/inventory/{host}", summary="从 Inventory 删除主机")
        async def remove_inventory(host: str) -> Dict[str, Any]:
            return self.inventory_manager.remove_host(host)

        @app.get("/health", summary="健康检查")
        async def health_check() -> Dict[str, str]:
            return {"status": "healthy"}

        return app

    def get_asgi_app(self):
        """获取 ASGI 应用，挂载 MCP 到 FastAPI"""
        mcp_app = self.mcp.http_app(path="/mcp", transport="streamable-http")
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def lifespan(app):
            async with mcp_app.lifespan(app):
                yield

        self.app.router.lifespan_context = lifespan
        self.app.mount("/", mcp_app)
        return self.app
