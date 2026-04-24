from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.config import (
    ADMIN_PASSWORD,
    ADMIN_PASSWORD_HASH,
    ADMIN_USERNAME,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
)
from app.db.session import get_session
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)
_PASSWORD_HASH_ITERATIONS = 200_000
ADMIN_USER_ID = "admin"


@dataclass
class AuthContext:
    username: str
    user_id: str
    is_admin: bool


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + pad).encode("utf-8"))


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_admin_credentials(username: str, password: str) -> bool:
    if not secrets.compare_digest(username, ADMIN_USERNAME):
        return False
    if ADMIN_PASSWORD_HASH:
        return _verify_password_against_hash(password, ADMIN_PASSWORD_HASH)
    return secrets.compare_digest(password, ADMIN_PASSWORD)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = _PASSWORD_HASH_ITERATIONS
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    digest_b64 = base64.b64encode(derived).decode("utf-8")
    return f"pbkdf2_sha256${iterations}${salt}${digest_b64}"


def verify_password(password: str, encoded_hash: str) -> bool:
    return _verify_password_against_hash(password, encoded_hash)


def _verify_password_against_hash(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        expected = base64.b64decode(digest_b64.encode("utf-8"))
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False


def create_access_token(
    username: str,
    user_id: str | None = None,
    is_admin: bool = False,
) -> tuple[str, int]:
    now = int(time.time())
    exp = now + (JWT_EXPIRE_MINUTES * 60)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": username, "iat": now, "exp": exp, "adm": bool(is_admin)}
    if user_id:
        payload["uid"] = user_id
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    token = f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"
    return token, exp


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
        provided = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, provided):
            raise _unauthorized()

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        exp = int(payload.get("exp", 0))
        if exp <= int(time.time()):
            raise _unauthorized()
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        raise _unauthorized() from exc


def verify_access_token(token: str) -> str:
    payload = decode_access_token(token)
    sub = str(payload.get("sub", ""))
    if not sub:
        raise _unauthorized()
    return sub


def is_admin_token(token: str) -> bool:
    payload = decode_access_token(token)
    return bool(payload.get("adm"))


def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AuthContext | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return require_user(credentials=credentials, session=session)


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    payload = decode_access_token(credentials.credentials)
    username = str(payload.get("sub", ""))
    is_admin = bool(payload.get("adm"))
    user_id = payload.get("uid")
    if not username:
        raise _unauthorized()

    if is_admin:
        return AuthContext(username=username, user_id=user_id or ADMIN_USER_ID, is_admin=True)

    user: User | None = None
    if user_id:
        user = session.exec(select(User).where(User.user_id == user_id)).first()
    if user is None:
        user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise _unauthorized()
    return AuthContext(username=user.username, user_id=user.user_id, is_admin=False)


def require_admin(auth: AuthContext = Depends(require_user)) -> AuthContext:
    if not auth.is_admin:
        raise _unauthorized()
    return auth
