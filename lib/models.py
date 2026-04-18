"""
数据模型模块

定义所有请求和响应的数据模型以及数据库模型
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Task(Base):
    """任务模型"""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True)
    type = Column(String, nullable=False)
    parameters = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class Context(Base):
    """上下文模型"""

    __tablename__ = "contexts"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class CredentialsModel(BaseModel):
    user: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None
    private_key: Optional[str] = None


class ShellRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    command: str = Field(..., description="命令内容", min_length=1, max_length=1000)
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class CopyRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    src: str = Field(..., description="本地源文件路径", min_length=1, max_length=500)
    dest: str = Field(..., description="远程目标路径", min_length=1, max_length=500)
    credentials: Optional[CredentialsModel] = None
    mode: Optional[str] = Field(None, description="文件权限")
    owner: Optional[str] = Field(None, description="文件所有者")
    group: Optional[str] = Field(None, description="文件所属组")
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class FetchRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    src: str = Field(..., description="远程源文件路径", min_length=1, max_length=500)
    dest: str = Field(..., description="本地目标目录", min_length=1, max_length=500)
    credentials: Optional[CredentialsModel] = None
    flat: bool = False
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class PlaybookRequest(BaseModel):
    playbook: str = Field(
        ..., description="playbook 文件名或路径", min_length=1, max_length=500
    )
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    extravars: Optional[Dict[str, Any]] = None
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class HostRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class InstallPythonRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    version: Optional[str] = Field(None, description="版本号")
    date: Optional[str] = Field(None, description="日期标识")
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class InstallTscToolsRequest(BaseModel):
    targets: List[str] = Field(
        ..., description="目标主机 IP 列表", min_length=1, max_length=100
    )
    credentials: Optional[CredentialsModel] = None
    version: Optional[str] = Field(None, description="版本号")
    date: Optional[str] = Field(None, description="日期标识")
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=1, le=3600)


class AddInventoryRequest(BaseModel):
    host: str = Field(..., description="主机 IP 地址", min_length=1, max_length=100)
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
    key: str = Field(..., description="上下文键")
    value: str = Field(..., description="上下文值")


class GetContextRequest(BaseModel):
    key: str = Field(..., description="上下文键")


class DeleteContextRequest(BaseModel):
    key: str = Field(..., description="上下文键")


class GetTaskDetailRequest(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    host: str = Field(..., description="主机名")


class GetFailedHostsRequest(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    limit: int = 20
    offset: int = 0


class GetAllResultsRequest(BaseModel):
    task_id: str = Field(..., description="任务 ID")
    limit: int = 20
    offset: int = 0
