"""FastAPI dependency'lari — autentifikatsiya va ruxsatlar."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Avtorizatsiya talab qilinadi",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    db: DbSession,
    creds: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ] = None,
) -> User:
    """Bearer tokendan joriy foydalanuvchini aniqlaydi."""
    if creds is None or not creds.credentials:
        raise _UNAUTHORIZED

    payload = decode_access_token(creds.credentials)
    if payload is None or not payload.get("sub"):
        raise _UNAUTHORIZED

    result = await db.execute(select(User).where(User.username == payload["sub"]))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    """Faqat adminlar uchun."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu amal uchun admin huquqi kerak",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
