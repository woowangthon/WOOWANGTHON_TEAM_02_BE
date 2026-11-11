"""Argon2 비밀번호 해시와 JWT access token 처리."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

ACCESS_TOKEN_MINUTES = 30
_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    """Argon2id 기본 파라미터로 비밀번호를 해시한다."""
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """비밀번호를 검증한다. 입력 해시가 깨졌거나 불일치하면 False를 돌려준다."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError):
        return False


def verify_unknown_user_password(password: str) -> None:
    """없는 계정도 Argon2 검증을 수행해 응답 시간 차이를 줄인다."""
    verify_password(_dummy_password_hash, password)


def create_access_token(user_id: int) -> str:
    """30분짜리 HS256 access token을 만든다."""
    secret = get_settings().jwt_secret
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET은 32바이트 이상으로 설정해야 합니다.")

    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        },
        secret,
        algorithm="HS256",
    )


def read_access_token(token: str) -> int | None:
    """서명을 검증하고 토큰의 사용자 ID를 반환한다."""
    secret = get_settings().jwt_secret
    if len(secret.encode("utf-8")) < 32:
        return None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdecimal():
        return None
    user_id = int(subject)
    return user_id if user_id > 0 else None
