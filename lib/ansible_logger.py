"""
Ansible execution detailed logging module.

Uses loguru to record complete detailed information of ansible execution.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


class AnsibleExecutionLogger:
    """Ansible execution detailed logging.

    Uses loguru to record complete detailed information of ansible execution, including:
    - Playbook, inventory, parameters at execution start
    - Each event during execution
    - Execution result summary
    - Execution error details
    """

    _instance: Optional["AnsibleExecutionLogger"] = None
    _initialized: bool = False

    def __new__(cls, config: Optional[Any] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Any] = None):
        if self._initialized:
            return
        self._initialized = True
        self.enabled = True
        self.log_file: Optional[Path] = None
        self.retention = "30 days"
        self.rotation = "50 MB"
        self._task_handlers: Dict[str, int] = {}  # task_id -> loguru handler id
        self._task_log_dir: Path = Path(__file__).parent.parent / "logs" / "tasks"
        self._task_log_retention: str = "7 days"
        if config:
            self._setup_from_config(config)

    def _setup_from_config(self, config: Any) -> None:
        """Set log parameters from config object."""
        self.enabled = config.get("logging.ansible_execution_enabled", True)
        if not self.enabled:
            return

        log_dir = Path(config.get("logging.dir", "logs"))
        if not log_dir.is_absolute():
            base_dir = Path(__file__).parent.parent.resolve()
            log_dir = base_dir / log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        log_filename = config.get(
            "logging.ansible_execution_log", "ansible_execution.log"
        )
        self.log_file = log_dir / log_filename
        self.retention = config.get("logging.ansible_execution_retention", "30 days")
        self.rotation = config.get("logging.ansible_execution_rotation", "50 MB")

        # Per-task log settings
        self._task_log_dir = getattr(
            config,
            "task_log_dir",
            Path(__file__).parent.parent / "logs" / "tasks",
        )
        self._task_log_retention = getattr(config, "task_log_retention", "7 days")

        self._setup_logger()

    def _setup_logger(self) -> None:
        """Set up loguru logger."""
        if not self.log_file:
            return

        logger.add(
            str(self.log_file),
            rotation=self.rotation,
            retention=self.retention,
            compression="zip",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            encoding="utf-8",
            filter=lambda record: record["extra"].get("ansible_execution", False),
        )

    def _get_task_log_path(self, task_id: str) -> Path:
        """Get per-task log file path.

        Args:
            task_id: Task ID.

        Returns:
            Path to the task-specific log file.
        """
        task_log_dir = self._task_log_dir
        task_log_dir.mkdir(parents=True, exist_ok=True)
        return task_log_dir / f"{task_id}.log"

    def _log(self, level: str, message: str, task_id: Optional[str] = None) -> None:
        """Internal log method.

        Args:
            level: Log level string.
            message: Log message.
            task_id: Optional task ID used to bind per-task context.
        """
        if not self.enabled:
            return
        if task_id:
            logger.bind(ansible_execution=True, task_id=task_id).log(level, message)
        else:
            logger.bind(ansible_execution=True).log(level, message)

    def log_execution_start(
        self,
        task_id: str,
        playbook: List[Dict[str, Any]],
        inventory: Dict[str, Any],
        timeout: int,
        extravars: Optional[Dict[str, Any]] = None,
        user: Optional[str] = None,
    ) -> None:
        """Log execution start.

        Args:
            task_id: Task ID.
            playbook: Playbook content.
            inventory: Inventory content.
            timeout: Timeout.
            extravars: Extra variables.
            user: Username.
        """
        if not self.enabled:
            return

        self._log("INFO", "=" * 50 + " ANSIBLE EXECUTION START " + "=" * 50, task_id=task_id)
        self._log("INFO", f"Task ID: {task_id}", task_id=task_id)
        if user:
            self._log("INFO", f"User: {user}", task_id=task_id)
        self._log("INFO", f"Timeout: {timeout}s", task_id=task_id)

        targets = list(inventory.get("all", {}).get("hosts", {}).keys())
        self._log("INFO", f"Targets: {targets}", task_id=task_id)

        if extravars:
            self._log("INFO", f"Extravars: {json.dumps(extravars, ensure_ascii=False)}", task_id=task_id)

        self._log("INFO", "Playbook:", task_id=task_id)
        playbook_yaml = yaml.dump(
            playbook, allow_unicode=True, default_flow_style=False
        )
        for line in playbook_yaml.split("\n"):
            if line.strip():
                self._log("INFO", f"  {line}", task_id=task_id)

        self._log("INFO", "Inventory:", task_id=task_id)
        inventory_json = json.dumps(inventory, ensure_ascii=False, indent=2)
        for line in inventory_json.split("\n"):
            if line.strip():
                self._log("INFO", f"  {line}", task_id=task_id)

        self._log("INFO", "=" * 100, task_id=task_id)

        # Add per-task log sink
        log_path = self._get_task_log_path(task_id)
        handler_id = logger.add(
            str(log_path),
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            encoding="utf-8",
            retention=self._task_log_retention,
            filter=lambda record, tid=task_id: record["extra"].get("task_id") == tid,
        )
        self._task_handlers[task_id] = handler_id

    def log_execution_event(
        self,
        task_id: str,
        event_type: str,
        host: str,
        task_name: str,
        result: Dict[str, Any],
    ) -> None:
        """Log execution event.

        Args:
            task_id: Task ID.
            event_type: Event type.
            host: Host name.
            task_name: Task name.
            result: Execution result.
        """
        if not self.enabled:
            return

        status = "OK"
        log_level = "INFO"
        if event_type == "runner_on_failed":
            status = "FAILED"
            log_level = "WARNING"
        elif event_type == "runner_on_unreachable":
            status = "UNREACHABLE"
            log_level = "WARNING"

        self._log(
            log_level, f"[EVENT] Task: {task_name} | Host: {host} | Status: {status}", task_id=task_id
        )

        if event_type in ["runner_on_failed", "runner_on_unreachable"]:
            error_msg = result.get("msg", result.get("stderr", "Unknown error"))
            self._log("ERROR", f"[EVENT DETAIL] error: {error_msg}", task_id=task_id)

        stdout = result.get("stdout", "")
        if stdout:
            for line in stdout.split("\n"):
                if line.strip():
                    self._log("DEBUG", f"[EVENT DETAIL] stdout: {line}", task_id=task_id)
        else:
            self._log("DEBUG", "[EVENT DETAIL] stdout: ", task_id=task_id)

        stderr = result.get("stderr", "")
        if stderr:
            for line in stderr.split("\n"):
                if line.strip():
                    self._log("DEBUG", f"[EVENT DETAIL] stderr: {line}", task_id=task_id)
        else:
            self._log("DEBUG", "[EVENT DETAIL] stderr: ", task_id=task_id)

        rc = result.get("rc", 0)
        self._log("DEBUG", f"[EVENT DETAIL] rc: {rc}", task_id=task_id)

        changed = result.get("changed", False)
        self._log("DEBUG", f"[EVENT DETAIL] changed: {changed}", task_id=task_id)

        if event_type == "runner_on_unreachable":
            self._log("DEBUG", "[EVENT DETAIL] unreachable: true", task_id=task_id)

    def log_execution_result(
        self,
        task_id: str,
        status: str,
        summary: Dict[str, Any],
        elapsed: float,
    ) -> None:
        """Log execution result summary.

        Args:
            task_id: Task ID.
            status: Execution status.
            summary: Result summary.
            elapsed: Elapsed time.
        """
        if not self.enabled:
            return

        self._log("INFO", "=" * 50 + " ANSIBLE EXECUTION RESULT " + "=" * 50, task_id=task_id)
        self._log("INFO", f"Task ID: {task_id}", task_id=task_id)
        self._log("INFO", f"Status: {status}", task_id=task_id)
        self._log("INFO", "Summary:", task_id=task_id)
        self._log("INFO", f"  Total hosts: {summary.get('total', 0)}", task_id=task_id)
        self._log("INFO", f"  Success: {summary.get('success', 0)}", task_id=task_id)
        self._log("INFO", f"  Failed: {summary.get('failed', 0)}", task_id=task_id)
        if "unreachable" in summary:
            self._log("INFO", f"  Unreachable: {summary.get('unreachable', 0)}", task_id=task_id)
        self._log("INFO", f"Elapsed: {elapsed:.2f}s", task_id=task_id)
        self._log("INFO", "=" * 100, task_id=task_id)

        # Remove per-task log sink after execution completes
        handler_id = self._task_handlers.pop(task_id, None)
        if handler_id is not None:
            try:
                logger.remove(handler_id)
            except Exception:
                pass  # Handler may have already been removed

    def log_execution_error(
        self,
        task_id: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log execution error details.

        Args:
            task_id: Task ID.
            error: Error message.
            details: Error details.
        """
        if not self.enabled:
            return

        self._log("ERROR", "=" * 50 + " ANSIBLE EXECUTION ERROR " + "=" * 50, task_id=task_id)
        self._log("ERROR", f"Task ID: {task_id}", task_id=task_id)
        self._log("ERROR", f"Error: {error}", task_id=task_id)

        if details:
            self._log("ERROR", "Details:", task_id=task_id)
            for key, value in details.items():
                self._log("ERROR", f"  - {key}: {value}", task_id=task_id)

        self._log("ERROR", "=" * 100, task_id=task_id)


ansible_logger = AnsibleExecutionLogger()
