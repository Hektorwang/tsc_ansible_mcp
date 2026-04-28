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

    def get_result(
        self, task_id: str, status: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get task result.

        Args:
            task_id: Task ID.
            status: Optional status filter ('failed' or 'success'). If specified, filters hosts by execution status.

        Returns:
            Result data, None if not found.
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            logger.warning(f"Task result not found: {task_id}")
            return None

        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        results = data.get("results")
        if results is None:
            return None

        if status == "failed":
            host_results = results.get("results", {})
            success_hosts = set(results.get("success_hosts", []))
            failed_results = {
                h: r for h, r in host_results.items() if h not in success_hosts
            }
            return {
                "task_id": task_id,
                "status": results.get("status"),
                "failed_hosts": failed_results,
                "total_failed": len(failed_results),
            }

        if status == "success":
            host_results = results.get("results", {})
            success_hosts = results.get("success_hosts", [])
            success_results = {
                h: host_results[h] for h in success_hosts if h in host_results
            }
            return {
                "task_id": task_id,
                "status": results.get("status"),
                "success_hosts": success_results,
                "total_success": len(success_results),
            }

        return results

    def get_host_result(self, task_id: str, host: str) -> Optional[Dict[str, Any]]:
        """Get execution result for a specific host.

        Args:
            task_id: Task ID.
            host: Host IP address.

        Returns:
            Host result data including rc, stdout, stderr, and status.
            None if task or host not found.
        """
        result_path = self._get_result_path(task_id)

        if not result_path.exists():
            logger.warning(f"Task result not found: {task_id}")
            return None

        with result_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        results = data.get("results")
        if results is None:
            return None

        host_results = results.get("results", {})
        if host not in host_results:
            logger.warning(f"Host {host} not found in task {task_id}")
            return None

        # Get host result and add status field
        host_result = host_results[host].copy()
        success_hosts = set(results.get("success_hosts", []))
        host_result["status"] = "success" if host in success_hosts else "failed"
        host_result["host"] = host
        host_result["task_id"] = task_id

        return host_result

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
