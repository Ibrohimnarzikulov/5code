"""Parol xeshlash va JWT token bilan ishlash."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import settings

_BCRYPT_MAX_BYTES = 72  # bcrypt cheklovi


def hash_password(password: str) -> str:
    """Parolni bcrypt bilan xeshlaydi."""
    raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Parolni xesh bilan solishtiradi. Xato formatda ham `False` qaytaradi."""
    try:
        raw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    *,
    extra: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """JWT access token yaratadi.

    Args:
        subject: Token egasi (odatda username).
        extra: Qo'shimcha claim'lar (masalan, `role`).
        expires_delta: Muddat; berilmasa sozlamalardagi qiymat ishlatiladi.
    """
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, **(extra or {})}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Tokenni ochadi. Yaroqsiz yoki muddati o'tgan bo'lsa `None`."""
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
