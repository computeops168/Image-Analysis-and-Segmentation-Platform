from __future__ import annotations

from typing import Dict, List
from pydantic import BaseModel
from .jobs import JobRead


class AdminStats(BaseModel):
    total: int
    by_status: Dict[str, int]
    avg_elapsed_ms: int
    avg_blob_count: int
    success_rate: int
    recent: List[JobRead]
