#!/usr/bin/env python3
"""
TSC_ANSIBLE_MCP 统一服务入口

同时启动 MCP 和 REST API 服务
"""

import sys
import os
from pathlib import Path
import uvicorn

project_root = str(Path(__file__).parent.parent.absolute())
if sys.path and sys.path[0] != project_root:
    if project_root in sys.path:
        sys.path.remove(project_root)
    sys.path.insert(0, project_root)


from lib.config import Config
from lib.server import Server
from lib.tsc_logger import get_logger

logger = get_logger()
os.environ["ANSIBLE_CONFIG"] = (
    (Path(project_root) / "ansible.cfg").absolute().as_posix()
)


def main():
    config = Config()
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
