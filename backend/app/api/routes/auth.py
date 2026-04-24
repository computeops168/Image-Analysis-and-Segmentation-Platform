from __future__ import annotations

import time
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.config import ADMIN_USERNAME
from app.db.session import get_session
from app.models.user import User
from app.observability import record_login_attempt
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserCreate, UserRead
from app.security import (
    ADMIN_USER_ID,
    create_access_token,
    hash_password,
    require_admin,
    verify_admin_credentials,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    if verify_admin_credentials(payload.username, payload.password):
        record_login_attempt(True)
        token, exp = create_access_token(
            payload.username,
            user_id=ADMIN_USER_ID,
            is_admin=True,
        )
        return TokenResponse(
            access_token=token,
            expires_in=max(0, exp - int(time.time())),
            username=payload.username,
            user_id=ADMIN_USER_ID,
            is_admin=True,
        )

    user: User | None = session.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_login_attempt(False)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    record_login_attempt(True)
    token, exp = create_access_token(
        user.username,
        user_id=user.user_id,
        is_admin=user.is_admin,
    )
    return TokenResponse(
        access_token=token,
        expires_in=max(0, exp - int(time.time())),
        username=user.username,
        user_id=user.user_id,
        is_admin=user.is_admin,
    )


@router.post("/register", response_model=UserRead, dependencies=[Depends(require_admin)])
def register_user(payload: UserCreate, session: Session = Depends(get_session)):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")
    if username.lower() == ADMIN_USERNAME.lower():
        raise HTTPException(status_code=409, detail="Username reserved")

    existing = session.exec(select(User).where(User.username == username)).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        user_id=str(uuid4()),
        username=username,
        password_hash=hash_password(payload.password),
        is_admin=bool(payload.is_admin),
        created_at=datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    return UserRead(
        user_id=user.user_id,
        username=user.username,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
