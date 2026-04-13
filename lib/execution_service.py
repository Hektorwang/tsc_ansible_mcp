"""
执行服务模块

封装所有执行逻辑，提供统一的执行接口
"""

from typing import Dict, List, Optional, Any

from lib.error_handler import error_handler


class ExecutionService:
    """执行服务类，封装所有执行逻辑"""

    def __init__(self, executor, task_repo, logger):
        self.executor = executor
        self.task_repo = task_repo
        self.logger = logger

    @error_handler
    def execute_shell(
        self,
        targets: List[str],
        command: str,
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """执行 shell 命令"""
        self.task_repo.update(task_id, "running")
        result = self.executor.ansible_shell(
            targets=targets,
            command=command,
            credentials=credentials if credentials else None,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        return result

    @error_handler
    def execute_playbook(
        self,
        playbook: str,
        targets: List[str],
        credentials: Optional[Dict[str, Any]],
        extravars: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """执行 playbook"""
        self.task_repo.update(task_id, "running")
        result = self.executor.run_playbook(
            playbook=playbook,
            targets=targets,
            credentials=credentials if credentials else None,
            extravars=extravars,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        return result

    @error_handler
    def check_host_status(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """检查主机状态"""
        self.task_repo.update(task_id, "running")
        result = self.executor.check_host_status(
            targets=targets,
            credentials=credentials if credentials else None,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, "success", result)
        return result

    @error_handler
    def install_python(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """安装 Python"""
        self.task_repo.update(task_id, "running")
        result = self.executor.install_python(
            targets=targets,
            credentials=credentials if credentials else None,
            timeout=timeout,
            task_id=task_id,
        )
        failed_hosts = []
        for host, r in result.get("results", {}).items():
            if not r.get("installed") and not r.get("skipped"):
                failed_hosts.append(
                    {"host": host, "message": r.get("message", "安装失败")}
                )
        if failed_hosts:
            result["error"] = "Python 安装失败，请停止后续操作并退出流程"
            result["failed_hosts"] = failed_hosts
            result["action_required"] = (
                "请停止当前流程，向用户报告错误信息，不要继续执行后续操作"
            )
        self.task_repo.update(
            task_id,
            "success" if not failed_hosts else "partial_success",
            result,
        )
        return result

    @error_handler
    def install_tsc_tools(
        self,
        targets: List[str],
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """安装 tsc_tools"""
        self.task_repo.update(task_id, "running")
        result = self.executor.install_tsc_tools(
            targets=targets,
            credentials=credentials if credentials else None,
            timeout=timeout,
            task_id=task_id,
        )
        failed_hosts = []
        for host, r in result.get("results", {}).items():
            if not r.get("installed") and not r.get("skipped"):
                failed_hosts.append(
                    {"host": host, "message": r.get("message", "安装失败")}
                )
        if failed_hosts:
            result["error"] = "tsc_tools 安装失败，请停止后续操作并退出流程"
            result["failed_hosts"] = failed_hosts
            result["action_required"] = (
                "请停止当前流程，向用户报告错误信息，不要继续执行后续操作"
            )
        self.task_repo.update(
            task_id,
            "success" if not failed_hosts else "partial_success",
            result,
        )
        return result

    @error_handler
    def ansible_copy(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """分发文件"""
        self.task_repo.update(task_id, "running")
        result = self.executor.ansible_copy(
            targets=targets,
            src=src,
            dest=dest,
            credentials=credentials if credentials else None,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        return result

    @error_handler
    def ansible_fetch(
        self,
        targets: List[str],
        src: str,
        dest: str,
        credentials: Optional[Dict[str, Any]],
        flat: bool,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """获取文件"""
        self.task_repo.update(task_id, "running")
        result = self.executor.ansible_fetch(
            targets=targets,
            src=src,
            dest=dest,
            credentials=credentials if credentials else None,
            flat=flat,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        return result
