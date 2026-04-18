"""释放主机锁工具"""

from typing import List, Optional

from fastmcp import FastMCP

from lib.tsc_logger import get_logger

logger = get_logger()


def register_release_host_locks(server):
    """注册释放主机锁工具"""
    mcp: FastMCP = server.mcp
    executor = server.executor

    @mcp.tool(name="release_host_locks", description="释放主机锁")
    def release_host_locks(
        targets: Optional[List[str]] = None,
    ):
        """释放主机锁

        Args:
            targets: 目标主机列表（为空时释放所有主机锁）

        Returns:
            释放锁的结果
        """
        try:
            if targets:
                logger.info(f"释放指定主机锁: {targets}")
                for host in targets:
                    executor._release_hosts([host])
            else:
                # 释放所有主机锁
                logger.info("释放所有主机锁")
                # 这里需要访问executor的_active_hosts属性
                # 由于_active_hosts是私有的，我们需要使用反射或修改executor类
                # 为了简单起见，我们可以创建一个临时列表来存储所有活跃主机
                import inspect

                # 获取_active_hosts属性
                active_hosts = getattr(executor, "_active_hosts", set())
                if active_hosts:
                    executor._release_hosts(list(active_hosts))

            logger.info("主机锁释放成功")
            return {"status": "success", "message": "主机锁释放成功"}
        except Exception as e:
            logger.error(f"释放主机锁失败: {str(e)}")
            return {"status": "failed", "message": f"释放主机锁失败: {str(e)}"}
