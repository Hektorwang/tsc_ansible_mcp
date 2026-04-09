#!/usr/bin/env python3
"""
TSC_ANSIBLE_MCP 统一服务入口

同时启动 MCP 和 REST API 服务
"""

import sys
from pathlib import Path
import uvicorn

project_root = str(Path(__file__).parent.parent)
if sys.path and sys.path[0] != project_root:
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)


from lib.config import Config
from lib.logger import get_logger, setup_logger
from lib.server import Server

logger = get_logger()


def main():
    config = Config()
    log_level = config.get("logging.level", "INFO")
    setup_logger(log_level=log_level)
    logger.info("启动 TSC_ANSIBLE_MCP 服务")
    logger.info(f"MCP 端点: http://{config.mcp_host}:{config.mcp_port}/mcp")
    logger.info(f"REST API 文档: http://{config.mcp_host}:{config.mcp_port}/docs")

    server = Server(config)
    app = server.get_asgi_app()

    uvicorn.run(
        app,
        host=config.mcp_host,
        port=config.mcp_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
