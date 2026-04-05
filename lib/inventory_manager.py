"""
Inventory 管理模块

管理本地 Inventory 缓存文件 etc/inventory.yml
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from lib.logger import get_logger

logger = get_logger()


class InventoryManager:
    """Inventory 管理类"""

    def __init__(self, inventory_path: Optional[Path] = None):
        if inventory_path is None:
            base_dir = Path(__file__).parent.parent.resolve()
            inventory_path = base_dir / "etc" / "inventory.yml"
        self.path = Path(inventory_path)
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                logger.debug(f"加载 Inventory: {self.path}")
                return data
        return {"all": {"hosts": {}}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
        logger.debug(f"保存 Inventory: {self.path}")

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
        logger.info(f"添加/更新主机到 Inventory: {host}")
        return {"status": "success", "message": "主机已添加/更新到 Inventory", "host": host}

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
        logger.info(f"更新主机 Python 解释器: {host} -> {python_path}")
        return {"status": "success", "message": f"Python 解释器已更新: {python_path}", "host": host}

    def get_host(self, host: str) -> Optional[Dict[str, Any]]:
        hosts = self._data.get("all", {}).get("hosts", {})
        return hosts.get(host)

    def remove_host(self, host: str) -> Dict[str, Any]:
        hosts = self._data.get("all", {}).get("hosts", {})
        if host in hosts:
            del hosts[host]
            self._save()
            logger.info(f"从 Inventory 删除主机: {host}")
            return {"status": "success", "message": "主机已从 Inventory 删除", "host": host}
        logger.warning(f"主机不存在于 Inventory: {host}")
        return {"status": "not_found", "message": "主机不存在于 Inventory", "host": host}

    def list_hosts(self) -> Dict[str, Any]:
        hosts = self._data.get("all", {}).get("hosts", {})
        return {"total": len(hosts), "hosts": list(hosts.keys())}

    def get_all_hosts(self) -> Dict[str, Dict[str, Any]]:
        return self._data.get("all", {}).get("hosts", {})

    def to_ansible_inventory(self) -> Dict[str, Any]:
        return self._data
