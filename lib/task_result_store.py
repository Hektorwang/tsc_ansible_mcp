"""
Task result storage module.

Uses hybrid storage:
- Summary stored in SQLite database
- Details stored in JSON files
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.tsc_logger import get_logger

logger = get_logger()


class TaskResultStore:
    """Task result storage manager.

    Uses hybrid storage:
    - Summary stored in SQLite (via TaskRepository)
    - Details stored in JSON files

    Storage directory structure:
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
        logger.info(f"Task result storage directory: {self.result_dir}")

    def _get_result_path(self, task_id: str) -> Path:
        """Get result file path.

        Args:
            task_id: Task ID.

        Returns:
            Result file path.
        """
        return self.result_dir / f"task_{task_id}.json"

    def save_result(self, task_id: str, results: Dict[str, Any]) -> None:
        """Save full result to file.

        Args:
            task_id: Task ID.
            results: Full result data.
        """
        result_path = self._get_result_path(task_id)

        data = {
            "task_id": task_id,
            "saved_at": datetime.now().isoformat(),
            "results": results,
        }

        with result_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.debug(f"Saved task result: {result_path}")

    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get full result.

        Args:
            task_id: Task ID.

        Returns:
            Full result data, None if not found.
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            logger.warning(f"Task result not found: {task_id}")
            return None

        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("results")

    def get_host_result(self, task_id: str, host: str) -> Optional[Dict[str, Any]]:
        """Get result for specific host.

        Args:
            task_id: Task ID.
            host: Host IP.

        Returns:
            Execution result for the host, None if not found.
        """
        results = self.get_result(task_id)
        if results is None:
            return None

        host_results = results.get("results", {})
        return host_results.get(host)

    def get_failed_hosts(
        self, task_id: str, limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """Get failed host results.

        Args:
            task_id: Task ID.
            limit: Return count limit.
            offset: Offset.

        Returns:
            Detailed results of failed hosts.
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
        """Get all host results (paginated).

        Args:
            task_id: Task ID.
            limit: Return count limit.
            offset: Offset.

        Returns:
            Host execution results.
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
        """Delete result file.

        Args:
            task_id: Task ID.

        Returns:
            Whether deletion was successful.
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            return False

        result_path.unlink()
        logger.info(f"Deleted task result: {task_id}")
        return True

    def list_old_results(self, days: int = 7) -> List[str]:
        """List result files older than specified days.

        Args:
            days: Number of days.

        Returns:
            List of task IDs.
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
                logger.warning(f"Failed to read result file: {result_file}, error: {e}")

        return old_tasks

    def cleanup_old_results(self, days: int = 7) -> int:
        """Clean up result files older than specified days.

        Args:
            days: Number of days.

        Returns:
            Number of deleted files.
        """
        old_tasks = self.list_old_results(days)
        deleted = 0

        for task_id in old_tasks:
            if self.delete_result(task_id):
                deleted += 1

        logger.info(f"Cleaned up {deleted} old task results")
        return deleted


task_result_store = TaskResultStore()
