"""
Log management module.

Encapsulates loguru logging library, provides unified log configuration and usage interface.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger


class TscLogger:
    """TSC log management class."""

    def __init__(
        self, log_dir: Optional[str] = None, config: Optional[Dict[str, Any]] = None
    ):
        self.log_dir = Path(log_dir) if log_dir else Path("./logs")
        self.log_dir.mkdir(exist_ok=True)
        self.config = config or {}
        self._logger_handlers = []
        self._setup_logger()

    def _setup_logger(self):
        """Configure logging."""
        # Remove all handlers
        logger.remove()
        self._logger_handlers = []

        # Get log level from config
        log_level = self.config.get("logging.level", "INFO")

        # Get log file configuration from config
        app_log_file = self.log_dir / "tsc_ansible_mcp.log"
        ansible_log_file = self.log_dir / self.config.get(
            "logging.ansible_execution_log", "ansible_execution.log"
        )
        rotation = self.config.get("logging.ansible_execution_rotation", "50 MB")
        retention = self.config.get("logging.ansible_execution_retention", "30 days")

        # Standardize log format
        file_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
        console_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"

        # Add application log file handler
        app_handler = logger.add(
            app_log_file,
            rotation=rotation,
            retention=retention,
            compression="zip",
            level=log_level,
            format=file_format,
        )
        self._logger_handlers.append(app_handler)

        # Add Ansible execution log file handler
        ansible_handler = logger.add(
            ansible_log_file,
            rotation=rotation,
            retention=retention,
            compression="zip",
            level=log_level,
            format=file_format,
        )
        self._logger_handlers.append(ansible_handler)

        # Add console handler
        console_handler = logger.add(sink=print, level=log_level, format=console_format)
        self._logger_handlers.append(console_handler)

    def update_config(self, config: Dict[str, Any]):
        """Update log configuration."""
        self.config = config
        self._setup_logger()
        logger.info("Log configuration updated")

    def get_logger(self):
        """Get logger instance."""
        return logger

    def log_with_context(self, level: str, message: str, **context):
        """Log with context information."""
        context_str = json.dumps(context, ensure_ascii=False)
        logger.log(level, f"{message} | Context: {context_str}")

    def log_task_start(self, task_id: str, task_type: str, **context):
        """Log task start."""
        self.log_with_context(
            "INFO", f"Task started: {task_type}", task_id=task_id, **context
        )

    def log_task_end(self, task_id: str, status: str, **context):
        """Log task end."""
        self.log_with_context("INFO", f"Task ended: {status}", task_id=task_id, **context)

    def log_task_error(self, task_id: str, error: str, **context):
        """Log task error."""
        self.log_with_context("ERROR", f"Task error: {error}", task_id=task_id, **context)

    def log_performance(self, operation: str, duration: float, **context):
        """Log performance information."""
        self.log_with_context(
            "INFO", f"Performance metric: {operation} took {duration:.2f}s", **context
        )


# Global logger instance
tsc_logger = TscLogger()
get_logger = tsc_logger.get_logger
log_with_context = tsc_logger.log_with_context
log_task_start = tsc_logger.log_task_start
log_task_end = tsc_logger.log_task_end
log_task_error = tsc_logger.log_task_error
log_performance = tsc_logger.log_performance
