from __future__ import annotations

import logging
from pathlib import Path

from app.services.storage import get_upload_dir

logger = logging.getLogger("app.segmentation_outputs")


def write_segmentation_outputs(
    image_path: Path,
    image_id: str,
    mask,
    user_id: str | None = None,
) -> dict[str, str] | None:
    if mask is None:
        return None

    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning(
            "segmentation_outputs_missing_deps",
            extra={
                "event_data": {
                    "event": "segmentation_outputs",
                    "path": str(image_path),
                    "image_id": image_id,
                    "error": str(exc),
                }
            },
        )
        return None

    try:
        high_dir = get_upload_dir("high", user_id=user_id)
        medium_dir = get_upload_dir("medium", user_id=user_id)
        low_dir = get_upload_dir("low", user_id=user_id)

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            rgb = np.asarray(image)

        mask_arr = np.asarray(mask).astype(bool)
        mask_img = Image.fromarray((mask_arr.astype(np.uint8) * 255), mode="L")
        if mask_img.size != image.size:
            mask_img = mask_img.resize(image.size, resample=Image.NEAREST)
        mask_arr = np.asarray(mask_img).astype(bool)

        fg = rgb.copy()
        fg[~mask_arr] = 0
        bg = rgb.copy()
        bg[mask_arr] = 0

        foreground_path = high_dir / f"{image_id}_foreground.png"
        background_path = low_dir / f"{image_id}_background.png"
        mask_path = medium_dir / f"{image_id}_mask.png"

        Image.fromarray(fg).save(foreground_path)
        Image.fromarray(bg).save(background_path)
        mask_img.save(mask_path)

        return {
            "foreground": str(foreground_path),
            "background": str(background_path),
            "mask": str(mask_path),
            "original": str(image_path),
        }
    except Exception as exc:
        logger.warning(
            "segmentation_outputs_failed",
            extra={
                "event_data": {
                    "event": "segmentation_outputs",
                    "path": str(image_path),
                    "image_id": image_id,
                    "error": str(exc),
                }
            },
        )
        return None
