from __future__ import annotations

from datetime import datetime
from typing import List
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.image import ImageAsset
from app.models.job import Job
from app.observability import record_job_status
from app.schemas.jobs import JobCreate, JobCreateResp, JobRead
from app.security import ADMIN_USER_ID, AuthContext, require_user
from app.services.job_runner import run_job
from app.services.storage import (
    build_file_url,
    ensure_dirs,
    resolve_output_path,
    resolve_storage_relpath,
    resolve_upload_path,
)


router = APIRouter(prefix="/api", tags=["jobs"])


def _utcnow() -> datetime:
    return datetime.utcnow()


@router.post("/jobs", response_model=JobCreateResp)
def create_job(
    request: Request,
    payload: JobCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    image: ImageAsset | None = session.exec(
        select(ImageAsset).where(ImageAsset.image_id == payload.image_id)
    ).first()
    if not image:
        raise HTTPException(status_code=400, detail="image_id not found")
    if not auth.is_admin and image.user_id != auth.user_id:
        raise HTTPException(status_code=404, detail="image_id not found")
    ensure_dirs(image.user_id or ADMIN_USER_ID)

    resolved_upload = None
    if image.storage_relpath:
        resolved_upload = resolve_storage_relpath(image.storage_relpath)
    if not resolved_upload:
        resolved_upload = resolve_upload_path(image.filename, user_id=image.user_id)
    if not resolved_upload:
        raise HTTPException(status_code=400, detail="Uploaded image file not found")
    input_file, tier = resolved_upload
    if tier == "quarantine":
        raise HTTPException(status_code=409, detail="Image is quarantined and cannot be processed yet")

    job_id = str(uuid4())
    input_path = str(input_file.resolve())
    input_url = build_file_url(request, image.filename)

    owner_id = image.user_id or ADMIN_USER_ID
    job = Job(
        job_id=job_id,
        image_id=payload.image_id,
        user_id=owner_id,
        status="queued",
        created_at=_utcnow(),
        updated_at=_utcnow(),
        input_path=input_path,
        input_url=input_url,
        output_path=None,
        output_url=None,
        pipeline={"steps": payload.steps},
        metrics={"blob_count": None, "elapsed_ms": None},
        error_msg=None,
    )
    session.add(job)
    session.commit()
    record_job_status("created")

    background.add_task(_run_job_task, job_id)
    return JobCreateResp(job_id=job_id)


def _run_job_task(job_id: str) -> None:
    from app.db.session import engine
    from sqlmodel import Session

    with Session(engine) as session:
        run_job(session, job_id)


@router.get("/jobs", response_model=List[JobRead])
def list_jobs(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    query = select(Job)
    if not auth.is_admin:
        query = query.where(Job.user_id == auth.user_id)
    jobs = session.exec(query).all()
    jobs_sorted = sorted(jobs, key=lambda j: j.created_at, reverse=True)
    return [
        JobRead(
            display_id=j.id,
            job_id=j.job_id,
            user_id=j.user_id,
            status=j.status,
            created_at=j.created_at,
            updated_at=j.updated_at,
            input_path=j.input_path,
            input_url=j.input_url,
            output_path=j.output_path,
            output_url=j.output_url,
            pipeline=j.pipeline or {},
            metrics=j.metrics or {},
            error_msg=j.error_msg,
        )
        for j in jobs_sorted
    ]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not auth.is_admin and job.user_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobRead(
        display_id=job.id,
        job_id=job.job_id,
        user_id=job.user_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        input_path=job.input_path,
        input_url=job.input_url,
        output_path=job.output_path,
        output_url=job.output_url,
        pipeline=job.pipeline or {},
        metrics=job.metrics or {},
        error_msg=job.error_msg,
    )


@router.delete("/jobs/{job_id}")
def delete_job(
    job_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    job = session.exec(select(Job).where(Job.job_id == job_id)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not auth.is_admin and job.user_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.output_path:
        safe_name = Path(job.output_path).name
        resolved = resolve_output_path(safe_name, user_id=job.user_id)
        if resolved:
            resolved.unlink(missing_ok=True)

    session.delete(job)
    session.commit()
    return {"ok": True}
