from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    image_id: str = Field(index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    status: str
    created_at: datetime
    updated_at: datetime

    input_path: Optional[str] = None
    input_url: Optional[str] = None
    output_path: Optional[str] = None
    output_url: Optional[str] = None

    pipeline: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    metrics: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    error_msg: Optional[str] = None
