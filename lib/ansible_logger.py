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

    def _log(self, level: str, message: str) -> None:
        """Internal log method."""
        if not self.enabled:
            return
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

        self._log("INFO", "=" * 50 + " ANSIBLE EXECUTION START " + "=" * 50)
        self._log("INFO", f"Task ID: {task_id}")
        if user:
            self._log("INFO", f"User: {user}")
        self._log("INFO", f"Timeout: {timeout}s")

        targets = list(inventory.get("all", {}).get("hosts", {}).keys())
        self._log("INFO", f"Targets: {targets}")

        if extravars:
            self._log("INFO", f"Extravars: {json.dumps(extravars, ensure_ascii=False)}")

        self._log("INFO", "Playbook:")
        playbook_yaml = yaml.dump(
            playbook, allow_unicode=True, default_flow_style=False
        )
        for line in playbook_yaml.split("\n"):
            if line.strip():
                self._log("INFO", f"  {line}")

        self._log("INFO", "Inventory:")
        inventory_json = json.dumps(inventory, ensure_ascii=False, indent=2)
        for line in inventory_json.split("\n"):
            if line.strip():
                self._log("INFO", f"  {line}")

        self._log("INFO", "=" * 100)

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
            log_level, f"[EVENT] Task: {task_name} | Host: {host} | Status: {status}"
        )

        if event_type in ["runner_on_failed", "runner_on_unreachable"]:
            error_msg = result.get("msg", result.get("stderr", "Unknown error"))
            self._log("ERROR", f"[EVENT DETAIL] error: {error_msg}")

        stdout = result.get("stdout", "")
        if stdout:
            for line in stdout.split("\n"):
                if line.strip():
                    self._log("DEBUG", f"[EVENT DETAIL] stdout: {line}")
        else:
            self._log("DEBUG", "[EVENT DETAIL] stdout: ")

        stderr = result.get("stderr", "")
        if stderr:
            for line in stderr.split("\n"):
                if line.strip():
                    self._log("DEBUG", f"[EVENT DETAIL] stderr: {line}")
        else:
            self._log("DEBUG", "[EVENT DETAIL] stderr: ")

        rc = result.get("rc", 0)
        self._log("DEBUG", f"[EVENT DETAIL] rc: {rc}")

        changed = result.get("changed", False)
        self._log("DEBUG", f"[EVENT DETAIL] changed: {changed}")

        if event_type == "runner_on_unreachable":
            self._log("DEBUG", "[EVENT DETAIL] unreachable: true")

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

        self._log("INFO", "=" * 50 + " ANSIBLE EXECUTION RESULT " + "=" * 50)
        self._log("INFO", f"Task ID: {task_id}")
        self._log("INFO", f"Status: {status}")
        self._log("INFO", "Summary:")
        self._log("INFO", f"  Total hosts: {summary.get('total', 0)}")
        self._log("INFO", f"  Success: {summary.get('success', 0)}")
        self._log("INFO", f"  Failed: {summary.get('failed', 0)}")
        if "unreachable" in summary:
            self._log("INFO", f"  Unreachable: {summary.get('unreachable', 0)}")
        self._log("INFO", f"Elapsed: {elapsed:.2f}s")
        self._log("INFO", "=" * 100)

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

        self._log("ERROR", "=" * 50 + " ANSIBLE EXECUTION ERROR " + "=" * 50)
        self._log("ERROR", f"Task ID: {task_id}")
        self._log("ERROR", f"Error: {error}")

        if details:
            self._log("ERROR", "Details:")
            for key, value in details.items():
                self._log("ERROR", f"  - {key}: {value}")

        self._log("ERROR", "=" * 100)


ansible_logger = AnsibleExecutionLogger()
