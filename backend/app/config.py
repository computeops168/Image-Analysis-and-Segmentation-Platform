from __future__ import annotations

import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_FRONTEND_DIR = PROJECT_ROOT / "frontend"
DOTENV_PATH = PROJECT_ROOT / "backend" / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["https://localhost"]
    parsed = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return parsed or ["https://localhost"]


def _parse_int(raw: str | None, default: int, minimum: int = 1) -> int:
    try:
        value = int(raw) if raw is not None else default
    except ValueError:
        return default
    return max(minimum, value)


def _parse_csv(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default
    values = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return values or default


def _has_default_admin_password(raw_password: str, raw_hash: str | None) -> bool:
    if raw_hash:
        return False
    return raw_password in {"change-this-password", "admin", "password"}


def _is_weak_secret(value: str) -> bool:
    if len(value) < 32:
        return True
    lowered = value.lower()
    known_bad = {
        "change-this-secret",
        "secret",
        "changeme",
        "password",
        "default",
    }
    return lowered in known_bad


def _validate_security_defaults(
    env_name: str,
    admin_password: str,
    admin_password_hash: str | None,
    jwt_secret: str,
    cors_origins: list[str],
) -> None:
    if env_name in {"development", "dev", "local"}:
        return

    if _has_default_admin_password(admin_password, admin_password_hash):
        raise RuntimeError(
            "Refusing to start outside development with a default ADMIN_PASSWORD. "
            "Set a strong ADMIN_PASSWORD or ADMIN_PASSWORD_HASH."
        )
    if _is_weak_secret(jwt_secret):
        raise RuntimeError(
            "Refusing to start outside development with a weak JWT_SECRET. "
            "Use at least 32 random characters."
        )
    if "*" in cors_origins:
        raise RuntimeError(
            "Refusing to start outside development with wildcard CORS_ORIGINS='*'. "
            "Provide an explicit origin allowlist."
        )


_load_dotenv(DOTENV_PATH)

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
CORS_ORIGINS = _parse_origins(os.getenv("CORS_ORIGINS"))
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", str(DEFAULT_FRONTEND_DIR))).resolve()
APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-this-password")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

UPLOAD_MAX_BYTES = _parse_int(os.getenv("UPLOAD_MAX_BYTES"), default=10 * 1024 * 1024)
UPLOAD_ALLOWED_CONTENT_TYPES = _parse_csv(
    os.getenv("UPLOAD_ALLOWED_CONTENT_TYPES"),
    default=["image/jpeg", "image/png", "image/webp"],
)
UPLOAD_ALLOWED_EXTENSIONS = _parse_csv(
    os.getenv("UPLOAD_ALLOWED_EXTENSIONS"),
    default=[".jpg", ".jpeg", ".png", ".webp"],
)

RATE_LIMIT_LOGIN_PER_MINUTE = _parse_int(os.getenv("RATE_LIMIT_LOGIN_PER_MINUTE"), default=5)
RATE_LIMIT_IMAGES_PER_MINUTE = _parse_int(os.getenv("RATE_LIMIT_IMAGES_PER_MINUTE"), default=20)
RATE_LIMIT_JOBS_PER_MINUTE = _parse_int(os.getenv("RATE_LIMIT_JOBS_PER_MINUTE"), default=30)
IMAGE_CLASSIFIER_PROVIDER = os.getenv("IMAGE_CLASSIFIER_PROVIDER", "heuristic")

if ADMIN_PASSWORD_HASH and not re.match(r"^pbkdf2_sha256\$\d+\$[^$]+\$[^$]+$", ADMIN_PASSWORD_HASH):
    raise RuntimeError(
        "Invalid ADMIN_PASSWORD_HASH format. Expected: "
        "pbkdf2_sha256$<iterations>$<salt>$<hash_b64>"
    )

_validate_security_defaults(
    env_name=APP_ENV,
    admin_password=ADMIN_PASSWORD,
    admin_password_hash=ADMIN_PASSWORD_HASH,
    jwt_secret=JWT_SECRET,
    cors_origins=CORS_ORIGINS,
)
