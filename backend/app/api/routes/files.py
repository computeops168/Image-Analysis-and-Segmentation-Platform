from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.image import ImageAsset
from app.models.job import Job
from app.security import AuthContext, require_user
from app.services.storage import (
    resolve_output_path,
    resolve_storage_relpath,
    resolve_upload_path,
)


router = APIRouter(prefix="/api", tags=["files"])
_SEGMENT_SUFFIXES = ("_foreground.png", "_background.png", "_mask.png")


def _extract_image_id_from_segment(filename: str) -> str | None:
    for suffix in _SEGMENT_SUFFIXES:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return None


def _extract_job_id_from_output(filename: str) -> str | None:
    marker = "_output"
    if marker not in filename:
        return None
    prefix = filename.split(marker, 1)[0]
    return prefix or None


def _resolve_file_path(
    file_id: str,
    auth: AuthContext,
    session: Session,
) -> Path | None:
    safe_name = Path(file_id).name
    if safe_name != file_id:
        return None

    image: ImageAsset | None = session.exec(
        select(ImageAsset).where(ImageAsset.filename == safe_name)
    ).first()
    if image is None:
        image_id = _extract_image_id_from_segment(safe_name)
        if image_id:
            image = session.exec(
                select(ImageAsset).where(ImageAsset.image_id == image_id)
            ).first()

    if image is not None:
        if not auth.is_admin and image.user_id != auth.user_id:
            return None
        if image.filename == safe_name:
            resolved = resolve_storage_relpath(image.storage_relpath)
            if resolved:
                return resolved[0]
            resolved = resolve_upload_path(image.filename, user_id=image.user_id)
            return resolved[0] if resolved else None

        resolved = resolve_upload_path(safe_name, user_id=image.user_id)
        return resolved[0] if resolved else None

    job_id = _extract_job_id_from_output(safe_name)
    if job_id:
        job: Job | None = session.exec(select(Job).where(Job.job_id == job_id)).first()
        if job and (auth.is_admin or job.user_id == auth.user_id):
            return resolve_output_path(safe_name, user_id=job.user_id)

    if auth.is_admin:
        resolved = resolve_upload_path(safe_name)
        if resolved:
            return resolved[0]
        legacy_output = resolve_output_path(safe_name)
        if legacy_output:
            return legacy_output

    return None


@router.get("/files/{file_id}")
def get_file(
    file_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    safe_name = Path(file_id).name
    if safe_name != file_id:
        raise HTTPException(status_code=404, detail="File not found")

    resolved = _resolve_file_path(file_id, auth, session)
    if resolved:
        return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="File not found")


@router.get("/segments/{file_id}")
def get_segment_file(
    file_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    safe_name = Path(file_id).name
    if safe_name != file_id:
        raise HTTPException(status_code=404, detail="File not found")

    resolved = _resolve_file_path(file_id, auth, session)
    if resolved:
        return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="File not found")
