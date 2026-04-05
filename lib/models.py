"""
TSC_ANSIBLE_MCP 数据库模型定义
"""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class Task(Base):
    """任务模型"""

    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True)
    type = Column(String(50), nullable=False)
    parameters = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    result = Column(Text, nullable=True)
    created_at = Column(String(30), nullable=False)
    updated_at = Column(String(30), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "parameters": self.parameters,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
