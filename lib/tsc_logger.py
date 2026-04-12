"""
日志管理模块

封装 loguru 日志库，提供统一的日志配置和使用接口
"""

from loguru import logger
from pathlib import Path
from typing import Optional, Dict, Any
import json


class TscLogger:
    """TSC 日志管理类"""

    def __init__(self, log_dir: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        self.log_dir = Path(log_dir) if log_dir else Path("./logs")
        self.log_dir.mkdir(exist_ok=True)
        self.config = config or {}
        self._logger_handlers = []
        self._setup_logger()

    def _setup_logger(self):
        """配置日志"""
        # 移除所有处理器
        logger.remove()
        self._logger_handlers = []
        
        # 从配置获取日志级别
        log_level = self.config.get("logging.level", "INFO")
        
        # 从配置获取日志文件配置
        app_log_file = self.log_dir / "tsc_ansible_mcp.log"
        ansible_log_file = self.log_dir / self.config.get("logging.ansible_execution_log", "ansible_execution.log")
        rotation = self.config.get("logging.ansible_execution_rotation", "50 MB")
        retention = self.config.get("logging.ansible_execution_retention", "30 days")
        
        # 标准化日志格式
        file_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}"
        console_format = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
        
        # 添加应用日志文件处理器
        app_handler = logger.add(
            app_log_file,
            rotation=rotation,
            retention=retention,
            compression="zip",
            level=log_level,
            format=file_format
        )
        self._logger_handlers.append(app_handler)
        
        # 添加 Ansible 执行日志文件处理器
        ansible_handler = logger.add(
            ansible_log_file,
            rotation=rotation,
            retention=retention,
            compression="zip",
            level=log_level,
            format=file_format
        )
        self._logger_handlers.append(ansible_handler)
        
        # 添加控制台处理器
        console_handler = logger.add(
            sink=print,
            level=log_level,
            format=console_format
        )
        self._logger_handlers.append(console_handler)

    def update_config(self, config: Dict[str, Any]):
        """更新日志配置"""
        self.config = config
        self._setup_logger()
        logger.info("日志配置已更新")

    def get_logger(self):
        """获取日志实例"""
        return logger

    def log_with_context(self, level: str, message: str, **context):
        """带上下文信息的日志记录"""
        context_str = json.dumps(context, ensure_ascii=False)
        logger.log(level, f"{message} | 上下文: {context_str}")

    def log_task_start(self, task_id: str, task_type: str, **context):
        """记录任务开始"""
        self.log_with_context("INFO", f"任务开始: {task_type}", task_id=task_id, **context)

    def log_task_end(self, task_id: str, status: str, **context):
        """记录任务结束"""
        self.log_with_context("INFO", f"任务结束: {status}", task_id=task_id, **context)

    def log_task_error(self, task_id: str, error: str, **context):
        """记录任务错误"""
        self.log_with_context("ERROR", f"任务错误: {error}", task_id=task_id, **context)

    def log_performance(self, operation: str, duration: float, **context):
        """记录性能信息"""
        self.log_with_context("INFO", f"性能指标: {operation} 耗时 {duration:.2f}s", **context)


# 全局日志实例
tsc_logger = TscLogger()
get_logger = tsc_logger.get_logger
log_with_context = tsc_logger.log_with_context
log_task_start = tsc_logger.log_task_start
log_task_end = tsc_logger.log_task_end
log_task_error = tsc_logger.log_task_error
log_performance = tsc_logger.log_performance
