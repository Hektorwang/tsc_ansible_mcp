"""
日志管理模块

使用 loguru 进行日志管理，支持文件落盘
"""

import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def setup_logger(log_dir: Optional[Path] = None, log_level: str = "INFO") -> None:
    if log_dir is None:
        base_dir = Path(__file__).parent.parent.resolve()
        log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tsc_ansible_mcp.log"
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        str(log_file),
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )


def get_logger():
    return logger


setup_logger()
