"""Autentifikatsiya endpoint'lari."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.deps import CurrentUser, DbSession
from app.models import Role, User
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    """Login qilib, JWT token oladi."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol noto'g'ri",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hisob bloklangan. Admin bilan bog'laning.",
        )

    token = create_access_token(user.username, extra={"role": user.role.value})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(payload: SignupRequest, db: DbSession) -> TokenResponse:
    """Ochiq ro'yxatdan o'tish.

    Yangi hisob har doim oddiy `user` roli va `ai_in_pc=False` bilan
    yaratiladi — kompyuter ruxsatini keyin faqat admin beradi.
    """
    if not settings.allow_signup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ro'yxatdan o'tish yopiq. Admin bilan bog'laning.",
        )

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=Role.USER,
        ai_in_pc=False,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.username}' allaqachon band",
        ) from None

    await db.refresh(user)
    token = create_access_token(user.username, extra={"role": user.role.value})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    """Joriy foydalanuvchi ma'lumotlari."""
    return UserOut.model_validate(user)
