from __future__ import annotations

import time
import random
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
from shutil import copyfile
from typing import Optional

from sqlmodel import Session, select

from app.models.job import Job
from app.observability import record_job_status
from app.services.storage import get_outputs_dir, get_upload_dir


def _utcnow() -> datetime:
    return datetime.utcnow()


def run_job(session: Session, job_id: str) -> None:
    started = time.perf_counter()
    job: Optional[Job] = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if not job:
        return

    job.status = "running"
    job.updated_at = _utcnow()
    session.add(job)
    session.commit()

    time.sleep(0.2)

    try:
        input_path = Path(job.input_path) if job.input_path else None
        user_id = job.user_id or "admin"
        foreground_filename = f"{job.image_id}_foreground.png"
        foreground_path = get_upload_dir("high", user_id=user_id) / foreground_filename
        output_path: Path | None = None

        if foreground_path.exists():
            output_path = foreground_path
        else:
            output_filename = f"{job.job_id}_output{input_path.suffix if input_path else ''}"
            output_path = get_outputs_dir(user_id) / output_filename

            if input_path and input_path.exists():
                copyfile(input_path, output_path)
            else:
                raise FileNotFoundError("Input file not found")

        time.sleep(0.6)

        parsed = urlparse(job.input_url or "")
        base = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        if foreground_path.exists():
            output_url = f"{base}/api/files/{foreground_filename}" if base else None
        else:
            output_url = f"{base}/api/files/{output_filename}" if base else None

        job.status = "done"
        job.updated_at = _utcnow()
        job.output_path = str(output_path) if output_path else None
        job.output_url = output_url
        job.metrics = {
            "blob_count": random.randint(1, 20),
            "elapsed_ms": random.randint(200, 900),
        }
        job.error_msg = None
        record_job_status("done", time.perf_counter() - started)
    except Exception as exc:
        job.status = "failed"
        job.updated_at = _utcnow()
        job.error_msg = str(exc)
        record_job_status("failed", time.perf_counter() - started)
    finally:
        session.add(job)
        session.commit()
