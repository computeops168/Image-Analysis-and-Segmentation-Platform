from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class ImageUploadResp(BaseModel):
    image_id: str
    image_url: str


class ImageSegmentsResp(BaseModel):
    image_id: str
    foreground_url: str | None = None
    background_url: str | None = None
    mask_url: str | None = None
    original_url: str | None = None
    available: bool


class ImageListItem(BaseModel):
    image_id: str
    filename: str
    image_url: str
    sensitivity_level: str
    created_at: datetime
    user_id: str
