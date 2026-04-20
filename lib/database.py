"""
Database management module.

Provides database initialization, Session management, and TaskRepository class using SQLAlchemy ORM.
"""

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lib.models import Base, Context, Task
from lib.tsc_logger import get_logger

logger = get_logger()


class Database:
    """Database management class."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{self.db_path}"
        # Optimize SQLite concurrent configuration
        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,  # Allow multi-threaded access
                "timeout": 30,  # Increase timeout (seconds)
            },
            pool_pre_ping=True,  # Check if connection is valid
            pool_recycle=3600,  # Recycle connections every hour
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._init_db()
        logger.info(f"Database initialized: {self.db_path}")

    def _init_db(self) -> None:
        Base.metadata.create_all(self.engine)
        logger.debug("Database table creation/validation completed")

    @contextmanager
    def get_session(self):
        session = self.SessionLocal()
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

    def create(self, task_id: str, task_type: str, parameters: Dict[str, Any]) -> None:
        now = datetime.now()
        with self.db.get_session() as session:
            task = Task(
                id=task_id,
                type=task_type,
                parameters=json.dumps(parameters),
                status="pending",
                result=None,
                created_at=now,
                updated_at=now,
            )
            session.add(task)
        logger.info(f"Created task: {task_id}, type: {task_type}")

    def update(
        self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ) -> None:
        now = datetime.now()
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = status
                task.updated_at = now
                if result is not None:
                    task.result = json.dumps(result)
        logger.info(f"Updated task: {task_id}, status: {status}")

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.debug(f"Task not found: {task_id}")
                return None
            return {
                "id": task.id,
                "type": task.type,
                "parameters": json.loads(task.parameters) if task.parameters else {},
                "status": task.status,
                "result": json.loads(task.result) if task.result else None,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }

    def list(
        self, status: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        with self.db.get_session() as session:
            query = session.query(Task).order_by(Task.created_at.desc())
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
                        "result": json.loads(task.result) if task.result else None,
                        "created_at": task.created_at.isoformat(),
                        "updated_at": task.updated_at.isoformat(),
                    }
                )
            logger.debug(f"Queried task list: status={status}, count={len(result)}")
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
                session.query(Task).filter(Task.created_at < cutoff_datetime).delete()
            )
        logger.info(f"Cleaned up expired tasks: deleted {count} records")
        return count

    def stats(self) -> Dict[str, int]:
        from sqlalchemy import func

        with self.db.get_session() as session:
            total = (
                session.query(func.count(Task.id)).scalar() or 0
            )  # pylint: disable=not-callable
            pending = (
                session.query(func.count(Task.id))  # pylint: disable=not-callable
                .filter(Task.status == "pending")
                .scalar()
                or 0
            )
            running = (
                session.query(func.count(Task.id))  # pylint: disable=not-callable
                .filter(Task.status == "running")
                .scalar()
                or 0
            )
            success = (
                session.query(func.count(Task.id))  # pylint: disable=not-callable
                .filter(Task.status == "success")
                .scalar()
                or 0
            )
            failed = (
                session.query(func.count(Task.id))  # pylint: disable=not-callable
                .filter(Task.status == "failed")
                .scalar()
                or 0
            )
            partial_success = (
                session.query(func.count(Task.id))  # pylint: disable=not-callable
                .filter(Task.status == "partial_success")
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
        now = datetime.now()
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                context.value = value
                context.updated_at = now
            else:
                context = Context(
                    key=key,
                    value=value,
                    created_at=now,
                    updated_at=now,
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
