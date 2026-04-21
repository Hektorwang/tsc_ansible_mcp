"""
Execution service module.

Encapsulates all execution logic, provides unified execution interface.
"""

from typing import Any, Dict, List, Optional

from lib.error_handler import error_handler
from lib.task_result_store import TaskResultStore


class ExecutionService:
    """Execution service class, encapsulates all execution logic."""

    def __init__(self, executor, task_repo, logger):
        self.executor = executor
        self.task_repo = task_repo
        self.logger = logger
        self.result_store = TaskResultStore()

    @error_handler
    def execute_shell(
        self,
        targets: List[str],
        command: str,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Execute shell command."""
        self.task_repo.update(task_id, "running")
        try:
            result = self.executor.ansible_shell(
                targets=targets,
                command=command,
                timeout=timeout,
                task_id=task_id,
            )
            self.task_repo.update(task_id, result["status"], result)
            return result
        finally:
            self.result_store.save_result(task_id, result)

    @error_handler
    def execute_playbook(
        self,
        playbook: str,
        targets: List[str],
        extravars: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Execute playbook."""
        self.task_repo.update(task_id, "running")
        try:
            result = self.executor.run_playbook(
                playbook=playbook,
                targets=targets,
                extravars=extravars,
                timeout=timeout,
                task_id=task_id,
            )
            self.task_repo.update(task_id, result["status"], result)
            return result
        finally:
            self.result_store.save_result(task_id, result)

    @error_handler
    def check_host_status(
        self,
        targets: List[str],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Check host status."""
        self.task_repo.update(task_id, "running")
        result = self.executor.check_host_status(
            targets=targets,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, "success", result)
        self.result_store.save_result(task_id, result)
        return result

    @error_handler
    def install_python(
        self,
        targets: List[str],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Install Python."""
        self.task_repo.update(task_id, "running")
        result = self.executor.install_python(
            targets=targets,
            timeout=timeout,
            task_id=task_id,
        )
        failed_hosts = []
        for host, r in result.get("results", {}).items():
            if not r.get("installed") and not r.get("skipped"):
                failed_hosts.append(
                    {"host": host, "message": r.get("message", "Installation failed")}
                )
        if failed_hosts:
            result["error"] = "Python installation failed, please stop subsequent operations and exit the process"
            result["failed_hosts"] = failed_hosts
            result["action_required"] = (
                "Please stop the current process, report the error information to the user, and do not continue with subsequent operations"
            )
        self.task_repo.update(
            task_id,
            "success" if not failed_hosts else "partial_success",
            result,
        )
        self.result_store.save_result(task_id, result)
        return result

    @error_handler
    def install_tsc_tools(
        self,
        targets: List[str],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Install tsc_tools."""
        self.task_repo.update(task_id, "running")
        result = self.executor.install_tsc_tools(
            targets=targets,
            timeout=timeout,
            task_id=task_id,
        )
        failed_hosts = []
        for host, r in result.get("results", {}).items():
            if not r.get("installed") and not r.get("skipped"):
                failed_hosts.append(
                    {"host": host, "message": r.get("message", "Installation failed")}
                )
        if failed_hosts:
            result["error"] = "tsc_tools installation failed, please stop subsequent operations and exit the process"
            result["failed_hosts"] = failed_hosts
            result["action_required"] = (
                "Please stop the current process, report the error information to the user, and do not continue with subsequent operations"
            )
        self.task_repo.update(
            task_id,
            "success" if not failed_hosts else "partial_success",
            result,
        )
        self.result_store.save_result(task_id, result)
        return result

    @error_handler
    def ansible_copy(
        self,
        targets: List[str],
        src: str,
        dest: str,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Distribute file."""
        self.task_repo.update(task_id, "running")
        result = self.executor.ansible_copy(
            targets=targets,
            src=src,
            dest=dest,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        self.result_store.save_result(task_id, result)
        return result

    @error_handler
    def ansible_fetch(
        self,
        targets: List[str],
        src: str,
        dest: str,
        flat: bool,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Fetch file."""
        self.task_repo.update(task_id, "running")
        result = self.executor.ansible_fetch(
            targets=targets,
            src=src,
            dest=dest,
            flat=flat,
            timeout=timeout,
            task_id=task_id,
        )
        self.task_repo.update(task_id, result["status"], result)
        self.result_store.save_result(task_id, result)
        return result
