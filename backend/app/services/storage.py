from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
USERS_DIR = DATA_DIR / "users"
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"
SEGMENTS_DIR = OUTPUTS_DIR / "segments"
UPLOAD_SECURITY_TIERS = ("low", "medium", "high", "quarantine")
UPLOAD_DIRS = {tier: UPLOADS_DIR / tier for tier in UPLOAD_SECURITY_TIERS}


def _validate_user_id(user_id: str) -> str:
    safe = Path(user_id).name
    if safe != user_id:
        raise ValueError("Invalid user id")
    return safe


def _user_root(user_id: str) -> Path:
    return USERS_DIR / _validate_user_id(user_id)


def _user_upload_dirs(user_id: str) -> dict[str, Path]:
    user_root = _user_root(user_id)
    uploads_root = user_root / "uploads"
    return {tier: uploads_root / tier for tier in UPLOAD_SECURITY_TIERS}


def _user_outputs_dir(user_id: str) -> Path:
    return _user_root(user_id) / "outputs"


def ensure_dirs(user_id: str | None = None) -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    for upload_dir in UPLOAD_DIRS.values():
        upload_dir.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    if user_id:
        user_upload_dirs = _user_upload_dirs(user_id)
        for upload_dir in user_upload_dirs.values():
            upload_dir.mkdir(parents=True, exist_ok=True)
        user_outputs = _user_outputs_dir(user_id)
        user_outputs.mkdir(parents=True, exist_ok=True)
        (user_outputs / "segments").mkdir(parents=True, exist_ok=True)


def get_segments_dir(user_id: str | None = None) -> Path:
    if user_id:
        return _user_outputs_dir(user_id) / "segments"
    return SEGMENTS_DIR


def build_file_url(request, filename: str) -> str:
    return f"{request.url.scheme}://{request.url.netloc}/api/files/{filename}"


def build_segment_url(request, filename: str) -> str:
    return f"{request.url.scheme}://{request.url.netloc}/api/segments/{filename}"


def get_upload_dir(tier: str, user_id: str | None = None) -> Path:
    try:
        if user_id:
            return _user_upload_dirs(user_id)[tier]
        return UPLOAD_DIRS[tier]
    except KeyError as exc:
        raise ValueError(f"Invalid upload tier '{tier}'.") from exc


def get_outputs_dir(user_id: str | None = None) -> Path:
    if user_id:
        return _user_outputs_dir(user_id)
    return OUTPUTS_DIR


def resolve_upload_path(filename: str, user_id: str | None = None) -> tuple[Path, str] | None:
    safe_name = Path(filename).name
    if safe_name != filename:
        return None

    if user_id:
        for tier, base in _user_upload_dirs(user_id).items():
            path = base / safe_name
            if path.exists():
                return path, tier
        if user_id == "admin":
            legacy_path = UPLOADS_DIR / safe_name
            if legacy_path.exists():
                return legacy_path, "low"
    else:
        for tier in UPLOAD_SECURITY_TIERS:
            path = UPLOAD_DIRS[tier] / safe_name
            if path.exists():
                return path, tier

    legacy_path = UPLOADS_DIR / safe_name
    if legacy_path.exists():
        return legacy_path, "low"

    return None


def resolve_storage_relpath(relpath: str) -> tuple[Path, str] | None:
    normalized = Path(relpath)
    if normalized.is_absolute():
        return None
    if ".." in normalized.parts:
        return None
    if len(normalized.parts) == 2:
        tier, filename = normalized.parts
        if tier not in UPLOAD_DIRS:
            return None
        safe_name = Path(filename).name
        if safe_name != filename:
            return None

        path = UPLOAD_DIRS[tier] / safe_name
        if path.exists():
            return path, tier
        return None
    if len(normalized.parts) == 3:
        user_id, tier, filename = normalized.parts
        if tier not in UPLOAD_DIRS:
            return None
        try:
            _validate_user_id(user_id)
        except ValueError:
            return None
        safe_name = Path(filename).name
        if safe_name != filename:
            return None
        path = _user_upload_dirs(user_id)[tier] / safe_name
        if path.exists():
            return path, tier
        return None
    return None


def resolve_output_path(filename: str, user_id: str | None = None) -> Path | None:
    safe_name = Path(filename).name
    if safe_name != filename:
        return None
    base = get_outputs_dir(user_id)
    candidate = base / safe_name
    if candidate.exists():
        return candidate
    if user_id is None or user_id == "admin":
        legacy_path = OUTPUTS_DIR / safe_name
        if legacy_path.exists():
            return legacy_path
    return None
