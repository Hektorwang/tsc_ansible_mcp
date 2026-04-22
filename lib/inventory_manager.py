"""
Inventory management module.

Provides a compatibility layer for InventoryManager using Inventory (ORM) as backend.
Manages host inventory data with atomic ORM + YAML synchronization.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from lib.database import Database, Inventory
from lib.tsc_logger import get_logger

logger = get_logger()


class InventoryManager:
    """Inventory management class (delegates to Inventory ORM)."""

    def __init__(self, inventory_path: Optional[Path] = None):
        base_dir = Path(__file__).parent.parent.resolve()
        db_path = base_dir / "logs" / "tsc_ansible_mcp.db"
        self._db = Database(db_path)
        if inventory_path is None:
            inventory_path = base_dir / "etc" / "inventory.yml"
        self.inventory = Inventory(self._db, inventory_path=inventory_path)
        self._ensure_synced()

    def _ensure_synced(self) -> None:
        """Auto-import from YAML if ORM is empty and YAML has data."""
        hosts = self.inventory.list_hosts()
        if hosts["total"] == 0:
            result = self.inventory.import_from_yaml()
            if result["status"] == "success" and result["imported"] > 0:
                logger.info(
                    f"Auto-imported {result['imported']} hosts from inventory.yml"
                )

    def add_host(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.inventory.add_host(host, user, port, password, private_key)

    def update_host_credentials(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.inventory.update_host_credentials(
            host, user, port, password, private_key
        )

    def update_python_interpreter(
        self,
        host: str,
        python_path: str,
    ) -> Dict[str, Any]:
        return self.inventory.update_python_interpreter(host, python_path)

    def update_host_port(
        self,
        host: str,
        new_port: int,
    ) -> Dict[str, Any]:
        return self.inventory.update_host_port(host, new_port)

    def get_host(self, host: str) -> Optional[Dict[str, Any]]:
        return self.inventory.get_host(host)

    def remove_host(self, host: str) -> Dict[str, Any]:
        return self.inventory.remove_host(host)

    def list_hosts(self) -> Dict[str, Any]:
        return self.inventory.list_hosts()

    def get_all_hosts(self) -> Dict[str, Dict[str, Any]]:
        return self.inventory.get_all_hosts()

    def to_ansible_inventory(self) -> Dict[str, Any]:
        hosts = self.get_all_hosts()
        return {"all": {"hosts": hosts, "vars": {}}}
