from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class ImageAsset(SQLModel, table=True):
    __tablename__ = "images"

    id: Optional[int] = Field(default=None, primary_key=True)
    image_id: str = Field(index=True, unique=True)
    user_id: Optional[str] = Field(default=None, index=True)
    filename: str
    storage_relpath: str = Field(default="")
    sensitivity_level: str = Field(default="quarantine", index=True)
    sensitivity_score: float = Field(default=0.0)
    contains_sensitive_regions: bool = Field(default=False)
    segmentation_model: Optional[str] = Field(default=None)
    created_at: datetime
