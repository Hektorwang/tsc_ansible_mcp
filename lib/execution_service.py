"""
Execution service module.

Encapsulates all execution logic, provides unified execution interface.
"""

import threading
from typing import Any, Dict, List, Optional

from lib.error_handler import error_handler
from lib.task_result_store import TaskResultStore


class ExecutionService:
    """Execution service class, encapsulates all execution logic."""

    # Wait timeout in seconds before returning running status to caller.
    # Set slightly below typical MCP client timeout (60s) to allow response overhead.
    TOOL_WAIT_TIMEOUT = 55

    def __init__(self, executor, task_repo, logger):
        self.executor = executor
        self.task_repo = task_repo
        self.logger = logger
        self.result_store = TaskResultStore()

    def _run_in_background(
        self,
        task_id: str,
        target_fn,
        *args,
        **kwargs,
    ) -> Dict[str, Any]:
        """Run a callable in a background thread and wait up to TOOL_WAIT_TIMEOUT seconds.

        If the callable completes within the wait window, returns the final result
        fetched from the task repository. Otherwise returns a running status response
        so the caller can poll via get_task_status.

        Args:
            task_id: Task ID already created in the repository.
            target_fn: Callable that performs the actual work. Must update task_repo
                and result_store on completion.
            *args: Positional arguments forwarded to target_fn.
            **kwargs: Keyword arguments forwarded to target_fn.

        Returns:
            Final result dict if completed within timeout, otherwise running status dict.
        """
        thread = threading.Thread(target=target_fn, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        thread.join(timeout=self.TOOL_WAIT_TIMEOUT)

        if thread.is_alive():
            self.logger.warning(
                f"Task {task_id} still running after {self.TOOL_WAIT_TIMEOUT}s wait, "
                "returning running status. Use get_task_status(task_id) to poll result."
            )
            return {
                "task_id": task_id,
                "status": "running",
                "message": (
                    f"Task is running in background. "
                    f"Use get_task_status('{task_id}') to poll for the result."
                ),
            }

        task = self.task_repo.get(task_id)
        if task and task.get("result"):
            return task["result"]
        return {"task_id": task_id, "status": task["status"] if task else "unknown"}

    @error_handler
    def execute_shell(
        self,
        targets: List[str],
        command: str,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Execute shell command on target hosts.

        Args:
            targets: List of target host IPs.
            command: Shell command to execute.
            timeout: Execution timeout in seconds.
            task_id: Pre-created task ID.

        Returns:
            Execution result dict, or running status if background thread is still active.
        """
        self.task_repo.update(task_id, "running")

        def _run() -> None:
            try:
                result = self.executor.ansible_shell(
                    targets=targets,
                    command=command,
                    timeout=timeout,
                    task_id=task_id,
                )
                self.task_repo.update(task_id, result["status"], result)
                self.result_store.save_result(task_id, result)
            except Exception as exc:
                self.logger.error(f"execute_shell background error: {exc}", exc_info=True)
                error_result = {"task_id": task_id, "status": "failed", "error": str(exc)}
                self.task_repo.update(task_id, "failed", error_result)

        return self._run_in_background(task_id, _run)

    @error_handler
    def execute_playbook(
        self,
        playbook: str,
        targets: List[str],
        extravars: Optional[Dict[str, Any]],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Execute an Ansible playbook on target hosts.

        Args:
            playbook: Playbook filename or path.
            targets: List of target host IPs.
            extravars: Extra variables passed to the playbook.
            timeout: Execution timeout in seconds.
            task_id: Pre-created task ID.

        Returns:
            Execution result dict, or running status if background thread is still active.
        """
        self.task_repo.update(task_id, "running")

        def _run() -> None:
            try:
                result = self.executor.run_playbook(
                    playbook=playbook,
                    targets=targets,
                    extravars=extravars,
                    timeout=timeout,
                    task_id=task_id,
                )
                self.task_repo.update(task_id, result["status"], result)
                self.result_store.save_result(task_id, result)
            except Exception as exc:
                self.logger.error(f"execute_playbook background error: {exc}", exc_info=True)
                error_result = {"task_id": task_id, "status": "failed", "error": str(exc)}
                self.task_repo.update(task_id, "failed", error_result)

        return self._run_in_background(task_id, _run)

    @error_handler
    def check_host_status(
        self,
        targets: List[str],
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Check host status (architecture, distro, Python, tsc_tools).

        Args:
            targets: List of target host IPs.
            timeout: Execution timeout in seconds.
            task_id: Pre-created task ID.

        Returns:
            Execution result dict, or running status if background thread is still active.
        """
        self.task_repo.update(task_id, "running")

        def _run() -> None:
            try:
                result = self.executor.check_host_status(
                    targets=targets,
                    timeout=timeout,
                    task_id=task_id,
                )
                self.task_repo.update(task_id, result.get("status", "success"), result)
                self.result_store.save_result(task_id, result)
            except Exception as exc:
                self.logger.error(f"check_host_status background error: {exc}", exc_info=True)
                error_result = {"task_id": task_id, "status": "failed", "error": str(exc)}
                self.task_repo.update(task_id, "failed", error_result)

        return self._run_in_background(task_id, _run)

    @error_handler
    def ansible_copy(
        self,
        targets: List[str],
        src: str,
        dest: str,
        timeout: Optional[int],
        task_id: str,
    ) -> Dict[str, Any]:
        """Distribute a local file to remote hosts.

        Args:
            targets: List of target host IPs.
            src: Local source file path.
            dest: Remote destination path.
            timeout: Execution timeout in seconds.
            task_id: Pre-created task ID.

        Returns:
            Execution result dict, or running status if background thread is still active.
        """
        self.task_repo.update(task_id, "running")

        def _run() -> None:
            try:
                result = self.executor.ansible_copy(
                    targets=targets,
                    src=src,
                    dest=dest,
                    timeout=timeout,
                    task_id=task_id,
                )
                self.task_repo.update(task_id, result["status"], result)
                self.result_store.save_result(task_id, result)
            except Exception as exc:
                self.logger.error(f"ansible_copy background error: {exc}", exc_info=True)
                error_result = {"task_id": task_id, "status": "failed", "error": str(exc)}
                self.task_repo.update(task_id, "failed", error_result)

        return self._run_in_background(task_id, _run)

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
        """Fetch a file from remote hosts to local.

        Args:
            targets: List of target host IPs.
            src: Remote source file path.
            dest: Local destination directory.
            flat: Whether to flatten the directory structure.
            timeout: Execution timeout in seconds.
            task_id: Pre-created task ID.

        Returns:
            Execution result dict, or running status if background thread is still active.
        """
        self.task_repo.update(task_id, "running")

        def _run() -> None:
            try:
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
            except Exception as exc:
                self.logger.error(f"ansible_fetch background error: {exc}", exc_info=True)
                error_result = {"task_id": task_id, "status": "failed", "error": str(exc)}
                self.task_repo.update(task_id, "failed", error_result)

        return self._run_in_background(task_id, _run)
