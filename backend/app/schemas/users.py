from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    is_admin: bool = False


class UserRead(BaseModel):
    user_id: str
    username: str
    is_admin: bool
    created_at: datetime
    image_count: int = 0
    job_count: int = 0


class UserPasswordUpdate(BaseModel):
    password: str = Field(min_length=1)
