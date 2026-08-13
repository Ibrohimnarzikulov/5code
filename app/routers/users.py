"""Foydalanuvchilarni boshqarish — faqat admin uchun."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import AdminUser, DbSession
from app.models import User
from app.schemas import UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


async def _get_user_or_404(db: DbSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Foydalanuvchi topilmadi"
        )
    return user


@router.get("", response_model=list[UserOut])
async def list_users(db: DbSession, _: AdminUser) -> list[UserOut]:
    """Barcha foydalanuvchilar ro'yxati."""
    result = await db.execute(select(User).order_by(User.id))
    return [UserOut.model_validate(u) for u in result.scalars()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DbSession, _: AdminUser) -> UserOut:
    """Yangi foydalanuvchi yaratadi."""
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        ai_in_pc=payload.ai_in_pc,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.username}' allaqachon mavjud",
        ) from None
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/ai-in-pc/all", response_model=list[UserOut])
async def grant_ai_in_pc_to_all(
    db: DbSession, _: AdminUser, enabled: bool = True
) -> list[UserOut]:
    """Barcha foydalanuvchilarga `ai_in_pc` ni yoqadi yoki o'chiradi.

    Example:
        POST /api/users/ai-in-pc/all?enabled=true
    """
    result = await db.execute(select(User).order_by(User.id))
    users = list(result.scalars())
    for user in users:
        user.ai_in_pc = enabled
    await db.flush()
    return [UserOut.model_validate(u) for u in users]


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int, payload: UserUpdate, db: DbSession, admin: AdminUser
) -> UserOut:
    """Foydalanuvchini yangilaydi (rol, ai_in_pc, parol, faollik)."""
    user = await _get_user_or_404(db, user_id)

    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizni bloklay olmaysiz",
        )

    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
    if payload.role is not None:
        user.role = payload.role
    if payload.ai_in_pc is not None:
        user.ai_in_pc = payload.ai_in_pc
    if payload.is_active is not None:
        user.is_active = payload.is_active

    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DbSession, admin: AdminUser) -> None:
    """Foydalanuvchini o'chiradi (suhbatlari bilan birga)."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O'zingizni o'chira olmaysiz",
        )
    user = await _get_user_or_404(db, user_id)
    await db.delete(user)
