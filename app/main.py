"""FastAPI ilovasi — kirish nuqtasi."""

from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.ai.providers import provider_info
from app.config import BASE_DIR, settings
from app.database import SessionLocal, init_db
from app.models import Role, User
from app.routers import artifacts, auth, chat, download, models, users
from app.security import hash_password

logger = logging.getLogger("codeassistant")
logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)

# Production: React build. Dev rejimida Vite 1991-portda alohida ishlaydi.
STATIC_DIR = BASE_DIR / "web" / "dist"


async def seed_admin() -> None:
    """Birinchi ishga tushishda admin hisobini yaratadi."""
    async with SessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is not None:
            return

        password = settings.admin_password or secrets.token_urlsafe(12)

        db.add(
            User(
                username=settings.admin_username,
                password_hash=hash_password(password),
                role=Role.ADMIN,
                ai_in_pc=True,
            )
        )
        await db.commit()

        if settings.admin_password:
            logger.info("Admin yaratildi: %s", settings.admin_username)
        else:
            # Parol .env da berilmagan — bir martalik tasodifiy parol
            logger.warning(
                "\n%s\n  ADMIN YARATILDI\n  login:  %s\n  parol:  %s\n"
                "  Bu parol FAQAT SHU YERDA ko'rsatiladi — saqlab qo'ying.\n%s",
                "=" * 52,
                settings.admin_username,
                password,
                "=" * 52,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up: baza + admin + workspace papkasi."""
    await init_db()
    await seed_admin()
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    logger.info("Workspace: %s", settings.workspace_root)
    yield


def create_app() -> FastAPI:
    """Ilova fabrikasi (testlarda ham shu ishlatiladi)."""
    app = FastAPI(
        title=settings.app_name,
        description="macbookair_4 ning shaxsiy AI tizimi",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(chat.router)
    app.include_router(artifacts.router)
    app.include_router(models.router)
    app.include_router(download.router)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, object]:
        """Tizim holati va joriy AI provider."""
        info = provider_info()
        return {"status": "ok", **info}

    if STATIC_DIR.is_dir():
        assets = STATIC_DIR / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/", include_in_schema=False)
        @app.get("/{spa_path:path}", include_in_schema=False)
        async def spa(spa_path: str = "") -> FileResponse:
            """React SPA — barcha noma'lum yo'llar index.html ga tushadi."""
            return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
