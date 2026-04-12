"""
数据库管理模块

使用 SQLAlchemy ORM 提供数据库初始化、Session 管理和 TaskRepository 类
"""

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from lib.logger import get_logger
from lib.models import Base, Task, Context

logger = get_logger()


class Database:
    """数据库管理类"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{self.db_path}"
        # 优化 SQLite 并发配置
        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={
                "check_same_thread": False,  # 允许多线程访问
                "timeout": 30,  # 增加超时时间（秒）
            },
            pool_pre_ping=True,  # 检查连接是否有效
            pool_recycle=3600,  # 每小时回收连接
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._init_db()
        logger.info(f"数据库初始化完成: {self.db_path}")

    def _init_db(self) -> None:
        Base.metadata.create_all(self.engine)
        logger.debug("数据库表创建/验证完成")

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
    """任务仓库类，使用 SQLAlchemy ORM 操作数据库"""

    def __init__(self, db: Database):
        self.db = db

    def create(self, task_id: str, task_type: str, parameters: Dict[str, Any]) -> None:
        now = datetime.now().isoformat()
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
        logger.info(f"创建任务: {task_id}, 类型: {task_type}")

    def update(
        self, task_id: str, status: str, result: Optional[Dict[str, Any]] = None
    ) -> None:
        now = datetime.now().isoformat()
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = status
                task.updated_at = now
                if result is not None:
                    task.result = json.dumps(result)
        logger.info(f"更新任务: {task_id}, 状态: {status}")

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.debug(f"任务不存在: {task_id}")
                return None
            return {
                "id": task.id,
                "type": task.type,
                "parameters": json.loads(task.parameters) if task.parameters else {},
                "status": task.status,
                "result": json.loads(task.result) if task.result else None,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
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
                        "created_at": task.created_at,
                        "updated_at": task.updated_at,
                    }
                )
            logger.debug(f"查询任务列表: 状态={status}, 数量={len(result)}")
            return result

    def delete(self, task_id: str) -> bool:
        with self.db.get_session() as session:
            task = session.query(Task).filter(Task.id == task_id).first()
            if task:
                session.delete(task)
                logger.info(f"删除任务: {task_id}")
                return True
            return False

    def cleanup_expired(self, expiry_hours: int = 24) -> int:
        expiry_seconds = expiry_hours * 3600
        cutoff_time = datetime.now().timestamp() - expiry_seconds
        cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()
        with self.db.get_session() as session:
            count = session.query(Task).filter(Task.created_at < cutoff_iso).delete()
        logger.info(f"清理过期任务: 删除 {count} 条记录")
        return count

    def stats(self) -> Dict[str, int]:
        from sqlalchemy import func

        with self.db.get_session() as session:
            total = session.query(func.count(Task.id)).scalar() or 0  # pylint: disable=not-callable
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
    """持久化上下文仓库类"""

    def __init__(self, db: Database):
        self.db = db

    def set(self, key: str, value: str) -> None:
        """设置上下文"""
        now = datetime.now().isoformat()
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
        logger.info(f"设置上下文: {key} = {value}")

    def get(self, key: str) -> Optional[str]:
        """获取上下文"""
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                logger.debug(f"获取上下文: {key} = {context.value}")
                return context.value
            logger.debug(f"上下文不存在: {key}")
            return None

    def delete(self, key: str) -> bool:
        """删除上下文"""
        with self.db.get_session() as session:
            context = session.query(Context).filter(Context.key == key).first()
            if context:
                session.delete(context)
                logger.info(f"删除上下文: {key}")
                return True
            return False

    def list(self) -> Dict[str, str]:
        """列出所有上下文"""
        with self.db.get_session() as session:
            contexts = session.query(Context).all()
            result = {ctx.key: ctx.value for ctx in contexts}
            logger.debug(f"列出上下文: {len(result)} 条")
            return result

    def clear(self) -> int:
        """清空所有上下文"""
        with self.db.get_session() as session:
            count = session.query(Context).delete()
            logger.info(f"清空上下文: 删除 {count} 条")
            return count
