"""Ma'lumotlar bazasi ulanishi (SQLAlchemy 2.0 async)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Barcha modellar uchun asosiy klass."""


def _create_engine():
    path = settings.sqlite_path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(settings.database_url, echo=settings.debug, future=True)


engine = _create_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — har so'rov uchun alohida sessiya."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Jadvallarni yaratadi (migratsiyasiz, MVP+ uchun yetarli)."""
    # Modellar import qilinishi shart — aks holda metadata bo'sh bo'ladi.
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
