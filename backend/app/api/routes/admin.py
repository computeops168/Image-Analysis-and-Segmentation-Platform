from __future__ import annotations

from typing import List

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.image import ImageAsset
from app.models.job import Job
from app.models.user import User
from app.schemas.admin import AdminStats
from app.schemas.jobs import JobRead
from app.schemas.users import UserPasswordUpdate, UserRead
from app.security import require_admin
from app.security import hash_password
from app.services.storage import (
    OUTPUTS_DIR,
    UPLOADS_DIR,
    USERS_DIR,
    ensure_dirs,
    resolve_output_path,
    resolve_upload_path,
)


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStats)
def get_stats(session: Session = Depends(get_session)):
    jobs = session.exec(select(Job)).all()
    total = len(jobs)
    by_status = {}
    for j in jobs:
        by_status[j.status] = by_status.get(j.status, 0) + 1

    done_jobs = [j for j in jobs if j.status == "done"]
    avg_elapsed = int(
        sum((j.metrics or {}).get("elapsed_ms") or 0 for j in done_jobs) / len(done_jobs)
    ) if done_jobs else 0
    avg_blobs = int(
        sum((j.metrics or {}).get("blob_count") or 0 for j in done_jobs) / len(done_jobs)
    ) if done_jobs else 0
    success_rate = int(((by_status.get("done", 0) / total) * 100)) if total else 0

    recent_sorted = sorted(jobs, key=lambda j: j.created_at, reverse=True)[:10]
    recent: List[JobRead] = [
        JobRead(
            display_id=j.id,
            job_id=j.job_id,
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
        for j in recent_sorted
    ]

    return AdminStats(
        total=total,
        by_status=by_status,
        avg_elapsed_ms=avg_elapsed,
        avg_blob_count=avg_blobs,
        success_rate=success_rate,
        recent=recent,
    )


@router.get("/users", response_model=List[UserRead])
def list_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    images = session.exec(select(ImageAsset)).all()
    jobs = session.exec(select(Job)).all()

    image_counts = {}
    for img in images:
        image_counts[img.user_id] = image_counts.get(img.user_id, 0) + 1

    job_counts = {}
    for job in jobs:
        job_counts[job.user_id] = job_counts.get(job.user_id, 0) + 1

    users_sorted = sorted(users, key=lambda u: u.created_at, reverse=True)
    return [
        UserRead(
            user_id=u.user_id,
            username=u.username,
            is_admin=u.is_admin,
            created_at=u.created_at,
            image_count=image_counts.get(u.user_id, 0),
            job_count=job_counts.get(u.user_id, 0),
        )
        for u in users_sorted
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: str, session: Session = Depends(get_session)):
    safe_id = Path(user_id).name
    if safe_id != user_id:
        raise HTTPException(status_code=404, detail="User not found")

    user: User | None = session.exec(select(User).where(User.user_id == safe_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=409, detail="Cannot delete admin users")

    images = session.exec(select(ImageAsset).where(ImageAsset.user_id == safe_id)).all()
    jobs = session.exec(select(Job).where(Job.user_id == safe_id)).all()

    deleted_files = 0
    for img in images:
        filenames = [
            img.filename,
            f"{img.image_id}_foreground.png",
            f"{img.image_id}_background.png",
            f"{img.image_id}_mask.png",
        ]
        for name in filenames:
            resolved = resolve_upload_path(name, user_id=safe_id)
            if resolved:
                try:
                    resolved[0].unlink()
                    deleted_files += 1
                except OSError:
                    pass

    for job in jobs:
        if job.output_path:
            safe_name = Path(job.output_path).name
            resolved = resolve_output_path(safe_name, user_id=safe_id)
            if resolved:
                try:
                    resolved.unlink()
                    deleted_files += 1
                except OSError:
                    pass

    for job in jobs:
        session.delete(job)
    for img in images:
        session.delete(img)
    session.delete(user)
    session.commit()

    user_root = USERS_DIR / safe_id
    if user_root.exists():
        for path in user_root.rglob("*"):
            if path.is_file():
                try:
                    path.unlink()
                    deleted_files += 1
                except OSError:
                    pass
        for path in sorted(user_root.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            user_root.rmdir()
        except OSError:
            pass

    return {
        "ok": True,
        "deleted_jobs": len(jobs),
        "deleted_images": len(images),
        "deleted_files": deleted_files,
    }


@router.patch("/users/{user_id}/password")
def update_user_password(
    user_id: str,
    payload: UserPasswordUpdate,
    session: Session = Depends(get_session),
):
    safe_id = Path(user_id).name
    if safe_id != user_id:
        raise HTTPException(status_code=404, detail="User not found")

    user: User | None = session.exec(select(User).where(User.user_id == safe_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    return {"ok": True}


@router.delete("/clear-history")
def clear_history(session: Session = Depends(get_session)):
    ensure_dirs()

    jobs = session.exec(select(Job)).all()
    images = session.exec(select(ImageAsset)).all()

    for j in jobs:
        session.delete(j)
    for img in images:
        session.delete(img)
    session.commit()

    deleted_files = 0
    for root in (UPLOADS_DIR, OUTPUTS_DIR, USERS_DIR):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                path.unlink()
                deleted_files += 1
            except OSError:
                pass

    return {
        "ok": True,
        "deleted_jobs": len(jobs),
        "deleted_images": len(images),
        "deleted_files": deleted_files,
    }
