"""
Database management module.

Provides database initialization, Session management, and repository classes
using SQLAlchemy ORM.
"""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from lib.models import Base, Context, Host, Task
from lib.tsc_logger import get_logger

logger = get_logger()


class Database:
    """Database management class."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": 30,
            },
            pool_pre_ping=True,
            pool_recycle=3600,
        )
        self.session_local = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self._init_db()
        logger.info(f"Database initialized: {self.db_path}")

    def _init_db(self) -> None:
        Base.metadata.create_all(self.engine)
        self._migrate_schema()
        logger.debug("Database table creation/validation completed")

    def _migrate_schema(self) -> None:
        """Add missing columns to existing tables."""
        from sqlalchemy import text

        with self.engine.connect() as conn:
            result = conn.execute(text("PRAGMA table_info(hosts)"))
            column_names = {row[1] for row in result.fetchall()}
            if "ansible_old_password" not in column_names:
                conn.execute(
                    text("ALTER TABLE hosts ADD COLUMN ansible_old_password VARCHAR"),
                )
                conn.commit()
                logger.info("Migration: added ansible_old_password to hosts")

    @contextmanager
    def get_session(self):
        session = self.session_local()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


class TaskRepository:
    """Task repository class using SQLAlchemy ORM for database operations"""

    def __init__(self, db: Database):
        self.db = db

    def create(
        self,
        task_id: str,
        task_type: str,
        parameters: Dict[str, Any],
    ) -> None:
        now = datetime.now()
        with self.db.get_session() as session:
            task = Task(
                id=task_id,
                type=task_type,
                parameters=json.dumps(parameters),
                status="pending",
                result=None,
            )
            session.add(task)
        logger.info(f"Created task: {task_id}, type: {task_type}")

    def update(
        self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ) -> None:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = status
                task.update_time = datetime.now()
                if result is not None:
                    task.result = json.dumps(result)
        logger.info(f"Updated task: {task_id}, status: {status}")

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.debug(f"Task not found: {task_id}")
                return None
            base_dir = Path(__file__).parent.parent.resolve()
            task_log_path = base_dir / "logs" / "tasks" / f"{task_id}.log"
            return {
                "id": task.id,
                "type": task.type,
                "parameters": (json.loads(task.parameters) if task.parameters else {}),
                "status": task.status,
                "result": (json.loads(task.result) if task.result else None),
                "create_time": task.create_time.isoformat(),
                "update_time": task.update_time.isoformat(),
                "log_file": str(task_log_path) if task_log_path.exists() else None,
            }

    def list(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            query = session.query(Task).order_by(Task.create_time.desc())
            if status:
                query = query.filter(Task.status == status)
            query = query.limit(limit)
            tasks = query.all()
            result = []
            for task in tasks:
                result.append(
                    {
                        "id": task.id,
                        "type": task.type,
                        "parameters": (
                            json.loads(task.parameters) if task.parameters else {}
                        ),
                        "status": task.status,
                        "result": (json.loads(task.result) if task.result else None),
                        "create_time": task.create_time.isoformat(),
                        "update_time": task.update_time.isoformat(),
                    }
                )
            msg = "Queried task list: status={}, count={}"
            logger.debug(msg, status, len(result))
            return result

    def delete(self, task_id: str) -> bool:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                session.delete(task)
                logger.info(f"Deleted task: {task_id}")
                return True
            return False

    def cleanup_expired(self, expiry_hours: int = 24) -> int:
        expiry_seconds = expiry_hours * 3600
        cutoff_time = datetime.now().timestamp() - expiry_seconds
        cutoff_datetime = datetime.fromtimestamp(cutoff_time)
        with self.db.get_session() as session:
            count = (
                session.query(Task)
                .filter(
                    Task.create_time < cutoff_datetime,
                )
                .delete()
            )
        logger.info("Cleaned up expired tasks: deleted %d records", count)
        return count

    def stats(self) -> Dict[str, int]:
        # pylint: disable=not-callable
        with self.db.get_session() as session:
            total = session.query(func.count(Task.id)).scalar() or 0
            pending = (
                session.query(func.count(Task.id))
                .filter(
                    Task.status == "pending",
                )
                .scalar()
                or 0
            )
            running = (
                session.query(func.count(Task.id))
                .filter(
                    Task.status == "running",
                )
                .scalar()
                or 0
            )
            success = (
                session.query(func.count(Task.id))
                .filter(
                    Task.status == "success",
                )
                .scalar()
                or 0
            )
            failed = (
                session.query(func.count(Task.id))
                .filter(
                    Task.status == "failed",
                )
                .scalar()
                or 0
            )
            partial_success = (
                session.query(func.count(Task.id))
                .filter(
                    Task.status == "partial_success",
                )
                .scalar()
                or 0
            )
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "success": success,
            "failed": failed,
            "partial_success": partial_success,
        }


class ContextRepository:
    """Persistent context repository class"""

    def __init__(self, db: Database):
        self.db = db

    def set(self, key: str, value: str) -> None:
        """Set context"""
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                context.value = value
                context.update_time = datetime.now()
            else:
                context = Context(
                    key=key,
                    value=value,
                )
                session.add(context)
        logger.info(f"Set context: {key} = {value}")

    def get(self, key: str) -> Optional[str]:
        """Get context"""
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                logger.debug(f"Got context: {key} = {context.value}")
                return context.value
            logger.debug(f"Context not found: {key}")
            return None

    def delete(self, key: str) -> bool:
        """Delete context"""
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                session.delete(context)
                logger.info(f"Deleted context: {key}")
                return True
            return False

    def list(self) -> Dict[str, str]:
        """List all contexts"""
        with self.db.get_session() as session:
            contexts = session.query(Context).all()
            result = {ctx.key: ctx.value for ctx in contexts}
            logger.debug(f"Listed contexts: {len(result)} entries")
            return result

    def clear(self) -> int:
        """Clear all contexts"""
        with self.db.get_session() as session:
            count = session.query(Context).delete()
            logger.info(f"Cleared contexts: deleted {count} entries")
            return count


class Inventory:
    """Inventory management with atomic ORM + YAML operations."""

    def __init__(self, db: Database, inventory_path: Optional[Path] = None):
        """Initialize host repository.

        Args:
            db: Database instance.
            inventory_path: Path to inventory.yml file.
        """
        self.db = db
        if inventory_path is None:
            base_dir = Path(__file__).parent.parent.resolve()
            inventory_path = base_dir / "etc" / "inventory.yml"
        self.inventory_path = Path(inventory_path)

    def import_from_yaml(self) -> Dict[str, Any]:
        """Import hosts from inventory.yml to ORM database.

        Returns:
            Dict with status and imported count.
        """
        if not self.inventory_path.exists():
            logger.warning(f"Inventory file not found: {self.inventory_path}")
            return {"status": "error", "message": "Inventory file not found"}

        try:
            with self.inventory_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            hosts_data = data.get("all", {}).get("hosts", {})
            if not hosts_data:
                logger.info("No hosts found in inventory.yml")
                return {"status": "success", "imported": 0}

            with self.db.get_session() as session:
                session.query(Host).delete()

                now = datetime.now()
                for host_ip, host_data in hosts_data.items():
                    port = (
                        host_data.get("ansible_port")
                        or host_data.get("ansible_ssh_port")
                        or 22
                    )
                    user = (
                        host_data.get("ansible_user")
                        or host_data.get("ansible_ssh_user")
                        or "root"
                    )
                    password = (
                        host_data.get("ansible_password")
                        or host_data.get("ansible_ssh_pass")
                        or host_data.get("ansible_ssh_password")
                    )
                    old_password = host_data.get(
                        "ansible_old_password"
                    ) or host_data.get("ansible_ssh_old_password")
                    private_key = host_data.get(
                        "ansible_private_key_file"
                    ) or host_data.get("ansible_ssh_private_key_file")
                    python_interp = host_data.get(
                        "ansible_python_interpreter"
                    ) or host_data.get("ansible_ssh_python_interpreter")
                    host = Host(
                        host=host_ip,
                        ansible_host=host_data.get("ansible_host", host_ip),
                        ansible_port=port,
                        ansible_user=user,
                        ansible_password=password,
                        ansible_old_password=old_password,
                        ansible_private_key=private_key,
                        ansible_python_interpreter=python_interp,
                    )
                    session.add(host)

                count = len(hosts_data)
                logger.info(f"Imported {count} hosts from inventory.yml")
                return {"status": "success", "imported": count}

        except (yaml.YAMLError, OSError) as e:
            logger.error("Failed to import inventory.yml: %s", e)
            return {"status": "error", "message": str(e)}

    def export_to_yaml(self, session: Session) -> None:
        """Export hosts from ORM to inventory.yml file.

        Note: This method must be called within an active database session
        to ensure atomicity with ORM updates.

        Args:
            session: Active database session.
        """
        all_hosts = session.query(Host).all()

        yaml_data: Dict[str, Any] = {"all": {"hosts": {}, "vars": {}}}

        common_vars: Dict[str, Any] = {}
        for host in all_hosts:
            host_data: Dict[str, Any] = {"ansible_host": host.ansible_host}

            if host.ansible_port != 22:
                host_data["ansible_port"] = int(host.ansible_port)

            if host.ansible_user and host.ansible_user != "root":
                host_data["ansible_user"] = host.ansible_user
            elif host.ansible_user == "root":
                common_vars.setdefault("ansible_user", "root")

            if host.ansible_private_key:
                host_data["ansible_ssh_private_key_file"] = host.ansible_private_key

            if host.ansible_python_interpreter:
                host_data["ansible_python_interpreter"] = (
                    host.ansible_python_interpreter
                )

            yaml_data["all"]["hosts"][host.host] = host_data

        if common_vars:
            yaml_data["all"]["vars"].update(common_vars)

        self.inventory_path.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=self.inventory_path.parent, suffix=".tmp", prefix="inventory_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                )
            os.replace(tmp_path, str(self.inventory_path))
            logger.info(f"Exported {len(all_hosts)} hosts to inventory.yml")
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _to_dict(self, host: Host) -> Dict[str, Any]:
        """Convert Host model to dictionary.

        Args:
            host: Host model instance.

        Returns:
            Dictionary representation of the host.
        """
        result = {
            "ansible_host": host.ansible_host,
            "ansible_port": host.ansible_port,
        }
        if host.ansible_user:
            result["ansible_user"] = host.ansible_user
        if host.ansible_password:
            result["ansible_password"] = host.ansible_password
        if host.ansible_old_password:
            result["ansible_old_password"] = host.ansible_old_password
        if host.ansible_private_key:
            result["ansible_ssh_private_key_file"] = host.ansible_private_key
        if host.ansible_python_interpreter:
            result["ansible_python_interpreter"] = host.ansible_python_interpreter
        return result

    def get_host(self, host: str) -> Optional[Dict[str, Any]]:
        """Get host information.

        Args:
            host: Host IP or hostname.

        Returns:
            Host data dictionary or None.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                logger.debug(f"Host not found: {host}")
                return None
            return self._to_dict(host_record)

    def list_hosts(self) -> Dict[str, Any]:
        """List all hosts.

        Returns:
            Dict with total count and host list.
        """
        with self.db.get_session() as session:
            hosts = session.query(Host).all()
            return {"total": len(hosts), "hosts": [h.host for h in hosts]}

    def get_all_hosts(self) -> Dict[str, Dict[str, Any]]:
        """Get all hosts with their data.

        Returns:
            Dict mapping host IP to host data.
        """
        with self.db.get_session() as session:
            hosts = session.query(Host).all()
            return {h.host: self._to_dict(h) for h in hosts}

    def add_host(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add or update host with atomic ORM + YAML sync.

        Args:
            host: Host IP or hostname.
            user: SSH username.
            port: SSH port.
            password: SSH password.
            private_key: SSH private key path.

        Returns:
            Dict with status and message.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                host_record = Host(
                    host=host,
                    ansible_host=host,
                    ansible_port=port or 22,
                    ansible_user=user or "root",
                    ansible_password=password,
                    ansible_private_key=private_key,
                )
                session.add(host_record)
            else:
                if port:
                    host_record.ansible_port = port
                if user:
                    host_record.ansible_user = user
                if password:
                    host_record.ansible_password = password
                if private_key:
                    host_record.ansible_private_key = private_key
                host_record.update_time = datetime.now()

            self.export_to_yaml(session)

            logger.info("Added/updated host in inventory: %s", host)
            return {
                "status": "success",
                "message": "Host added/updated",
                "host": host,
            }

    def update_host_port(self, host: str, new_port: int) -> Dict[str, Any]:
        """Update host SSH port with atomic ORM + YAML sync.

        Args:
            host: Host IP or hostname.
            new_port: New SSH port number.

        Returns:
            Dict with status and message.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                logger.warning(
                    "Host not found in inventory: %s, adding it",
                    host,
                )
                host_record = Host(
                    host=host,
                    ansible_host=host,
                    ansible_port=new_port,
                    ansible_user="root",
                )
                session.add(host_record)
            else:
                # Save old port to ansible_old_port
                host_record.ansible_old_port = host_record.ansible_port
                host_record.ansible_port = new_port
                host_record.update_time = datetime.now()

            self.export_to_yaml(session)

            logger.info(f"Updated host SSH port: {host} -> {new_port}")
            return {
                "status": "success",
                "message": f"Host port updated: {new_port}",
                "host": host,
            }

    def update_host_credentials(
        self,
        host: str,
        user: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        old_password: Optional[str] = None,
        private_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update host credentials with atomic ORM + YAML sync.

        When password is updated, the old password is automatically archived
        to ansible_old_password for retry fallback.

        Args:
            host: Host IP or hostname.
            user: SSH username.
            port: SSH port.
            password: SSH password (new).
            old_password: Previous SSH password (for retry fallback).
            private_key: SSH private key path.

        Returns:
            Dict with status and message.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                return {"status": "error", "message": f"Host not found: {host}"}

            if user:
                host_record.ansible_user = user
            if port:
                host_record.ansible_port = port
            if password:
                if host_record.ansible_password:
                    host_record.ansible_old_password = host_record.ansible_password
                host_record.ansible_password = password
            if old_password:
                host_record.ansible_old_password = old_password
            if private_key:
                host_record.ansible_private_key = private_key
            host_record.update_time = datetime.now()

            self.export_to_yaml(session)

            logger.info(f"Updated host credentials: {host}")
            return {
                "status": "success",
                "message": "Host credentials updated",
                "host": host,
            }

    def update_python_interpreter(
        self,
        host: str,
        python_path: str,
    ) -> Dict[str, Any]:
        """Update host Python interpreter with atomic ORM + YAML sync.

        Args:
            host: Host IP or hostname.
            python_path: Python interpreter path.

        Returns:
            Dict with status and message.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                logger.warning(
                    "Host not found in inventory: %s, adding it",
                    host,
                )
                host_record = Host(
                    host=host,
                    ansible_host=host,
                    ansible_python_interpreter=python_path,
                    ansible_user="root",
                )
                session.add(host_record)
            else:
                host_record.ansible_python_interpreter = python_path
                host_record.update_time = datetime.now()

            self.export_to_yaml(session)

            logger.info(
                "Updated host Python interpreter: %s -> %s",
                host,
                python_path,
            )
            return {
                "status": "success",
                "message": f"Python interpreter updated: {python_path}",
                "host": host,
            }

    def remove_host(self, host: str) -> Dict[str, Any]:
        """Remove host with atomic ORM + YAML sync.

        Args:
            host: Host IP or hostname.

        Returns:
            Dict with status and message.
        """
        with self.db.get_session() as session:
            host_record = session.query(Host).filter(Host.host == host).first()
            if not host_record:
                logger.warning(f"Host not found in inventory: {host}")
                return {
                    "status": "not_found",
                    "message": "Host not found",
                    "host": host,
                }

            session.delete(host_record)
            self.export_to_yaml(session)

            logger.info("Removed host from inventory: %s", host)
            return {
                "status": "success",
                "message": "Host removed",
                "host": host,
            }
