from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    image_id: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class JobMetrics(BaseModel):
    blob_count: Optional[int] = None
    elapsed_ms: Optional[int] = None


class JobRead(BaseModel):
    display_id: Optional[int] = None
    job_id: str
    user_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    input_path: Optional[str] = None
    input_url: Optional[str] = None
    output_path: Optional[str] = None
    output_url: Optional[str] = None
    pipeline: Dict[str, Any]
    metrics: JobMetrics
    error_msg: Optional[str] = None


class JobCreateResp(BaseModel):
    job_id: str
