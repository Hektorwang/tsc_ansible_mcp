"""
任务结果存储模块

使用混合存储方案：
- 摘要存 SQLite 数据库
- 详情存 JSON 文件
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.logger import get_logger

logger = get_logger()


class TaskResultStore:
    """任务结果存储管理器

    使用混合存储方案：
    - 摘要存 SQLite（通过 TaskRepository）
    - 详情存 JSON 文件

    存储目录结构：
    logs/task_results/
    ├── task_xxx.json
    └── ...
    """

    _instance: Optional["TaskResultStore"] = None
    _initialized: bool = False

    def __new__(cls, result_dir: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, result_dir: Optional[Path] = None):
        if self._initialized:
            if result_dir:
                self.result_dir = result_dir
            return
        self._initialized = True

        if result_dir is None:
            base_dir = Path(__file__).parent.parent.resolve()
            result_dir = base_dir / "logs" / "task_results"

        self.result_dir = Path(result_dir)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"任务结果存储目录: {self.result_dir}")

    def _get_result_path(self, task_id: str) -> Path:
        """获取结果文件路径

        Args:
            task_id: 任务 ID

        Returns:
            结果文件路径
        """
        return self.result_dir / f"task_{task_id}.json"

    def save_result(self, task_id: str, results: Dict[str, Any]) -> None:
        """保存完整结果到文件

        Args:
            task_id: 任务 ID
            results: 完整结果数据
        """
        result_path = self._get_result_path(task_id)

        data = {
            "task_id": task_id,
            "saved_at": datetime.now().isoformat(),
            "results": results,
        }

        with result_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug(f"保存任务结果: {result_path}")

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取完整结果

        Args:
            task_id: 任务 ID

        Returns:
            完整结果数据，不存在返回 None
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            logger.warning(f"任务结果不存在: {task_id}")
            return None

        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("results")

    def get_host_result(self, task_id: str, host: str) -> Optional[Dict[str, Any]]:
        """获取特定主机结果

        Args:
            task_id: 任务 ID
            host: 主机 IP

        Returns:
            该主机的执行结果，不存在返回 None
        """
        results = self.get_result(task_id)
        if results is None:
            return None

        host_results = results.get("results", {})
        return host_results.get(host)

    def get_failed_hosts(
        self, task_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """获取失败主机结果

        Args:
            task_id: 任务 ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            失败主机的详细结果
        """
        results = self.get_result(task_id)
        if results is None:
            return {"task_id": task_id, "failed_hosts": {}, "total": 0}

        host_results = results.get("results", {})

        failed_hosts = {
            host: result
            for host, result in host_results.items()
            if result.get("rc", 0) != 0
        }

        total = len(failed_hosts)
        host_list = list(failed_hosts.items())[offset : offset + limit]

        return {
            "task_id": task_id,
            "failed_hosts": dict(host_list),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    def get_all_results(
        self, task_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """获取所有主机结果（分页）

        Args:
            task_id: 任务 ID
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            主机执行结果
        """
        results = self.get_result(task_id)
        if results is None:
            return {"task_id": task_id, "results": {}, "total": 0}

        host_results = results.get("results", {})

        total = len(host_results)
        host_list = list(host_results.items())[offset : offset + limit]

        return {
            "task_id": task_id,
            "results": dict(host_list),
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    def delete_result(self, task_id: str) -> bool:
        """删除结果文件

        Args:
            task_id: 任务 ID

        Returns:
            是否删除成功
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            return False

        result_path.unlink()
        logger.info(f"删除任务结果: {task_id}")
        return True

    def list_old_results(self, days: int = 7) -> List[str]:
        """列出指定天数前的结果文件

        Args:
            days: 天数

        Returns:
            任务 ID 列表
        """
        cutoff = datetime.now() - timedelta(days=days)
        old_tasks = []

        for result_file in self.result_dir.glob("task_*.json"):
            try:
                with result_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)

                saved_at = datetime.fromisoformat(data.get("saved_at", ""))
                if saved_at < cutoff:
                    task_id = data.get("task_id", "")
                    if task_id:
                        old_tasks.append(task_id)
            except Exception as e:
                logger.warning(f"读取结果文件失败: {result_file}, 错误: {e}")

        return old_tasks

    def cleanup_old_results(self, days: int = 7) -> int:
        """清理指定天数前的结果文件

        Args:
            days: 天数

        Returns:
            删除的文件数量
        """
        old_tasks = self.list_old_results(days)
        deleted = 0

        for task_id in old_tasks:
            if self.delete_result(task_id):
                deleted += 1

        logger.info(f"清理了 {deleted} 个旧任务结果")
        return deleted


task_result_store = TaskResultStore()
