"""
Inventory management module.

Manages local Inventory cache file etc/inventory.yml.
Supports concurrent-safe file operations.
"""

import fcntl
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from lib.tsc_logger import get_logger

logger = get_logger()


class InventoryManager:
    """Inventory management class (thread-safe)."""

    def __init__(self, inventory_path: Optional[Path] = None):
        if inventory_path is None:
            base_dir = Path(__file__).parent.parent.resolve()
            inventory_path = base_dir / "etc" / "inventory.yml"
        self.path = Path(inventory_path)
        self._data = self._load()
        self._lock_timeout = 10  # File lock timeout (seconds)

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded Inventory: {self.path}")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load Inventory: {e}")
                return {"all": {"hosts": {}}}
        return {"all": {"hosts": {}}}

    def _save(self) -> None:
        """Save Inventory (thread-safe, using file lock)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.path.open("w", encoding="utf-8") as f:
                    # Acquire file lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        yaml.dump(
                            self._data, f, default_flow_style=False, allow_unicode=True
                        )
                        logger.debug(f"Saved Inventory: {self.path}")
                    finally:
                        # Release file lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                break
            except (IOError, BlockingIOError) as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Inventory file is locked, waiting for retry ({attempt + 1}/{max_retries})"
                    )
                    time.sleep(0.1 * (attempt + 1))
                else:
                    logger.error(f"Failed to save Inventory (file lock timeout): {e}")
                    raise
            except Exception as e:
                logger.error(f"Failed to save Inventory: {e}")
                raise

    def add_host(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if "all" not in self._data:
            self._data["all"] = {"hosts": {}}
        if "hosts" not in self._data["all"]:
            self._data["all"]["hosts"] = {}
        if host not in self._data["all"]["hosts"]:
            self._data["all"]["hosts"][host] = {"ansible_host": host}
        host_data = self._data["all"]["hosts"][host]
        if "ansible_host" not in host_data:
            host_data["ansible_host"] = host
        if user:
            host_data["ansible_user"] = user
        if port:
            host_data["ansible_port"] = port
        if password:
            host_data["ansible_password"] = password
        if private_key:
            host_data["ansible_ssh_private_key_file"] = private_key
        self._save()
        logger.info(f"Added/updated host to Inventory: {host}")
        return {
            "status": "success",
            "message": "Host added/updated to Inventory",
            "host": host,
        }

    def update_host_credentials(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update host credentials (only called after validation succeeds)."""
        if "all" not in self._data:
            self._data["all"] = {"hosts": {}}
        if "hosts" not in self._data["all"]:
            self._data["all"]["hosts"] = {}
        if host not in self._data["all"]["hosts"]:
            self._data["all"]["hosts"][host] = {"ansible_host": host}

        host_data = self._data["all"]["hosts"][host]
        if "ansible_host" not in host_data:
            host_data["ansible_host"] = host

        if user:
            host_data["ansible_user"] = user
        if port:
            host_data["ansible_port"] = port
        if password:
            host_data["ansible_password"] = password
        if private_key:
            host_data["ansible_ssh_private_key_file"] = private_key

        self._save()
        logger.info(f"Updated host credentials to Inventory: {host}")
        return {"status": "success", "message": "Host credentials updated", "host": host}

    def update_python_interpreter(
        self,
        host: str,
        python_path: str,
    ) -> Dict[str, Any]:
        if "all" not in self._data:
            self._data["all"] = {"hosts": {}}
        if "hosts" not in self._data["all"]:
            self._data["all"]["hosts"] = {}
        if host not in self._data["all"]["hosts"]:
            self._data["all"]["hosts"][host] = {"ansible_host": host}
        self._data["all"]["hosts"][host]["ansible_python_interpreter"] = python_path
        self._save()
        logger.info(f"Updated host Python interpreter: {host} -> {python_path}")
        return {
            "status": "success",
            "message": f"Python interpreter updated: {python_path}",
            "host": host,
        }

    def get_host(self, host: str) -> Optional[Dict[str, Any]]:
        hosts = self._data.get("all", {}).get("hosts", {})
        return hosts.get(host)

    def remove_host(self, host: str) -> Dict[str, Any]:
        hosts = self._data.get("all", {}).get("hosts", {})
        if host in hosts:
            del hosts[host]
            self._save()
            logger.info(f"Removed host from Inventory: {host}")
            return {
                "status": "success",
                "message": "Host removed from Inventory",
                "host": host,
            }
        logger.warning(f"Host not found in Inventory: {host}")
        return {
            "status": "not_found",
            "message": "Host not found in Inventory",
            "host": host,
        }

    def list_hosts(self) -> Dict[str, Any]:
        hosts = self._data.get("all", {}).get("hosts", {})
        return {"total": len(hosts), "hosts": list(hosts.keys())}

    def get_all_hosts(self) -> Dict[str, Dict[str, Any]]:
        return self._data.get("all", {}).get("hosts", {})

    def to_ansible_inventory(self) -> Dict[str, Any]:
        return self._data
