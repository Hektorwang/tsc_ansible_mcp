"""
Data model module

Defines data models for all requests and responses, as well as database models
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Host(Base):
    """Host inventory model."""

    __tablename__ = "hosts"

    host = Column(String, primary_key=True, index=True)
    ansible_host = Column(String, nullable=False)
    ansible_port = Column(Integer, default=22)
    ansible_old_port = Column(Integer, nullable=True)
    ansible_user = Column(String, default="root")
    ansible_password = Column(String, nullable=True)
    ansible_old_password = Column(String, nullable=True)
    ansible_private_key = Column(String, nullable=True)
    ansible_python_interpreter = Column(String, nullable=True)
    create_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    update_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )


class Task(Base):
    """Task model"""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    result = Column(JSON, nullable=True)
    create_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    update_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )


class Context(Base):
    """Context model"""

    __tablename__ = "contexts"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    create_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    update_time = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )


class CredentialsModel(BaseModel):
    user: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    private_key: Optional[str] = None


class ShellRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="List of target host IPs", min_length=1, max_length=100
    )
    command: str = Field(
        ..., description="Command content", min_length=1, max_length=1000
    )
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = Field(
        None, description="Timeout in seconds", ge=1, le=3600
    )


class CopyRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="List of target host IPs", min_length=1, max_length=100
    )
    src: str = Field(
        ..., description="Local source file path", min_length=1, max_length=500
    )
    dest: str = Field(
        ..., description="Remote destination path", min_length=1, max_length=500
    )
    credentials: Optional[CredentialsModel] = None
    mode: Optional[str] = Field(None, description="File permissions")
    owner: Optional[str] = Field(None, description="File owner")
    group: Optional[str] = Field(None, description="File group")
    timeout: Optional[int] = Field(
        None, description="Timeout in seconds", ge=1, le=3600
    )


class FetchRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="List of target host IPs", min_length=1, max_length=100
    )
    src: str = Field(
        ..., description="Remote source file path", min_length=1, max_length=500
    )
    dest: str = Field(
        ..., description="Local destination directory", min_length=1, max_length=500
    )
    credentials: Optional[CredentialsModel] = None
    flat: bool = False
    timeout: Optional[int] = Field(
        None, description="Timeout in seconds", ge=1, le=3600
    )


class PlaybookRequest(BaseModel):
    playbook: str = Field(
        ..., description="Playbook filename or path", min_length=1, max_length=500
    )
    targets: List[str] = Field(
        ..., description="List of target host IPs", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    extravars: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = Field(
        None, description="Timeout in seconds", ge=1, le=3600
    )


class HostRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="List of target host IPs", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = Field(
        None, description="Timeout in seconds", ge=1, le=3600
    )


class AddInventoryRequest(BaseModel):
    host: str = Field(..., description="Host IP address", min_length=1, max_length=100)
    credentials: Optional[CredentialsModel] = None


class TaskResponse(BaseModel):
    id: str
    type: str
    parameters: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str


class SetContextRequest(BaseModel):
    key: str = Field(..., description="Context key")
    value: str = Field(..., description="Context value")


class GetContextRequest(BaseModel):
    key: str = Field(..., description="Context key")


class DeleteContextRequest(BaseModel):
    key: str = Field(..., description="Context key")


class GetTaskDetailRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    host: str = Field(..., description="Hostname")


class GetFailedHostsRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    limit: int = 20
    offset: int = 0


class GetAllResultsRequest(BaseModel):
    task_id: str = Field(..., description="Task ID")
    limit: int = 20
    offset: int = 0
