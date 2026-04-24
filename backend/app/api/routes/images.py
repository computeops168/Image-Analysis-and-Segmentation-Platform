from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session, select

from app.config import (
    UPLOAD_ALLOWED_CONTENT_TYPES,
    UPLOAD_ALLOWED_EXTENSIONS,
    UPLOAD_MAX_BYTES,
)
from app.db.session import get_session
from app.models.image import ImageAsset
from app.observability import record_upload_result
from app.schemas.images import ImageListItem, ImageSegmentsResp, ImageUploadResp
from app.security import AuthContext, require_user
from app.services.image_classification import ClassificationResult, classify_upload
from app.services.segmentation_outputs import write_segmentation_outputs
from app.services.storage import build_file_url, ensure_dirs, get_upload_dir, resolve_upload_path


router = APIRouter(prefix="/api", tags=["images"])
_CHUNK_SIZE = 1024 * 1024
_INGEST_UPLOAD_TIER = "quarantine"
_VALID_TIERS = {"low", "medium", "high", "quarantine"}
logger = logging.getLogger("app.api.images")


def _sniff_content_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"RIFF") and b"WEBP" in head[:16]:
        return "image/webp"
    return None


def _validate_upload(file: UploadFile, ext: str, head: bytes) -> None:
    if ext and ext.lower() not in UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension '{ext}'.",
        )
    if file.content_type not in UPLOAD_ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{file.content_type}'.",
        )
    sniffed = _sniff_content_type(head)
    if sniffed is None or sniffed not in UPLOAD_ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Uploaded file is not a supported image.")


@router.post("/images", response_model=ImageUploadResp)
def upload_image(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    try:
        ensure_dirs(auth.user_id)
        if not file:
            raise HTTPException(status_code=400, detail="No file uploaded")

        image_id = str(uuid4())
        ext = (Path(file.filename).suffix if file.filename else "").lower()
        filename = f"{image_id}{ext}"
        filepath = get_upload_dir(_INGEST_UPLOAD_TIER, user_id=auth.user_id) / filename

        head = file.file.read(32)
        _validate_upload(file, ext, head)

        written = len(head)
        if written > UPLOAD_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max allowed is {UPLOAD_MAX_BYTES} bytes.",
            )

        with filepath.open("wb") as output:
            output.write(head)
            while True:
                chunk = file.file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > UPLOAD_MAX_BYTES:
                    output.close()
                    filepath.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max allowed is {UPLOAD_MAX_BYTES} bytes.",
                    )
                output.write(chunk)

        classification = ClassificationResult(
            tier="quarantine",
            score=1.0,
            contains_sensitive_regions=True,
            model="classifier-error",
        )
        try:
            classified = classify_upload(filepath, file.filename)
            if classified.tier not in _VALID_TIERS:
                raise ValueError(f"Unsupported tier from classifier: {classified.tier}")
            classification = classified
            target_path = get_upload_dir("medium", user_id=auth.user_id) / filename
            if target_path != filepath:
                filepath = filepath.replace(target_path)

            if classification.mask is not None:
                write_segmentation_outputs(filepath, image_id, classification.mask, user_id=auth.user_id)
        except Exception:
            logger.exception(
                "image_classification_failed",
                extra={
                    "event_data": {
                        "event": "image_classification",
                        "filename": filename,
                    }
                },
            )

        image = ImageAsset(
            image_id=image_id,
            user_id=auth.user_id,
            filename=filename,
            storage_relpath=f"{auth.user_id}/medium/{filename}",
            sensitivity_level=classification.tier,
            sensitivity_score=classification.score,
            contains_sensitive_regions=classification.contains_sensitive_regions,
            segmentation_model=classification.model,
            created_at=datetime.utcnow(),
        )
        session.add(image)
        session.commit()
        record_upload_result("accepted")
        return ImageUploadResp(image_id=image_id, image_url=build_file_url(request, filename))
    except HTTPException:
        record_upload_result("rejected")
        raise
    except Exception:
        record_upload_result("error")
        raise


@router.post("/upload", response_model=ImageUploadResp)
def upload_image_compat(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    return upload_image(request=request, file=file, session=session, auth=auth)


@router.get("/images/{image_id}/segments", response_model=ImageSegmentsResp)
def get_image_segments(
    image_id: str,
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    safe_id = Path(image_id).name
    if safe_id != image_id:
        raise HTTPException(status_code=404, detail="Image not found")

    image: ImageAsset | None = session.exec(
        select(ImageAsset).where(ImageAsset.image_id == safe_id)
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not auth.is_admin and image.user_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Image not found")

    filenames = {
        "foreground": f"{safe_id}_foreground.png",
        "background": f"{safe_id}_background.png",
        "mask": f"{safe_id}_mask.png",
        "original": image.filename,
    }

    existing = {key: resolve_upload_path(name, user_id=image.user_id) for key, name in filenames.items()}
    available = any(entry is not None for entry in existing.values())

    if not available:
        return ImageSegmentsResp(image_id=safe_id, available=False)

    return ImageSegmentsResp(
        image_id=safe_id,
        foreground_url=build_file_url(request, filenames["foreground"])
        if existing["foreground"] is not None
        else None,
        background_url=build_file_url(request, filenames["background"])
        if existing["background"] is not None
        else None,
        mask_url=build_file_url(request, filenames["mask"]) if existing["mask"] is not None else None,
        original_url=build_file_url(request, filenames["original"])
        if existing["original"] is not None
        else None,
        available=True,
    )


@router.get("/images", response_model=list[ImageListItem])
def list_images(
    request: Request,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
    user_id: str | None = None,
):
    query = select(ImageAsset)
    if user_id:
        if not auth.is_admin and user_id != auth.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        query = query.where(ImageAsset.user_id == user_id)
    elif not auth.is_admin:
        query = query.where(ImageAsset.user_id == auth.user_id)

    images = session.exec(query).all()
    images_sorted = sorted(images, key=lambda img: img.created_at, reverse=True)
    return [
        ImageListItem(
            image_id=img.image_id,
            filename=img.filename,
            image_url=build_file_url(request, img.filename),
            sensitivity_level=img.sensitivity_level,
            created_at=img.created_at,
            user_id=img.user_id,
        )
        for img in images_sorted
    ]


@router.delete("/images/{image_id}")
def delete_image(
    image_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_user),
):
    safe_id = Path(image_id).name
    if safe_id != image_id:
        raise HTTPException(status_code=404, detail="Image not found")

    image: ImageAsset | None = session.exec(
        select(ImageAsset).where(ImageAsset.image_id == safe_id)
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if not auth.is_admin and image.user_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Image not found")

    owner_id = image.user_id if image.user_id else (None if auth.is_admin else auth.user_id)
    filenames = [
        image.filename,
        f"{safe_id}_foreground.png",
        f"{safe_id}_background.png",
        f"{safe_id}_mask.png",
    ]
    for name in filenames:
        resolved = resolve_upload_path(name, user_id=owner_id)
        if resolved:
            resolved[0].unlink(missing_ok=True)

    session.delete(image)
    session.commit()
    return {"ok": True}
