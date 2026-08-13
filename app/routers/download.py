"""Loyiha kodini yuklab olish va o'rnatish ko'rsatmalari."""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response, status

from app.config import BASE_DIR, settings
from app.deps import CurrentUser

router = APIRouter(prefix="/api/download", tags=["download"])

# Arxivga TUSHMAYDIGAN papkalar — hajm va maxfiylik uchun
EXCLUDED_DIRS = frozenset(
    {
        ".venv",
        "node_modules",
        "dist",
        ".git",
        "data",
        "workspace",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
    }
)

# Maxfiy fayllar — hech qachon arxivga qo'shilmaydi
EXCLUDED_FILES = frozenset({".env", ".DS_Store", "codeassistant.db"})
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".log", ".db", ".sqlite3")

MAX_ZIP_BYTES = 60 * 1024 * 1024  # 60 MB — mo'l-ko'l zaxira bilan


def _skip(path: Path) -> bool:
    """Fayl arxivdan chiqarib tashlanadimi?"""
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True
    if path.name in EXCLUDED_FILES:
        return True
    return path.name.endswith(EXCLUDED_SUFFIXES)


def _build_archive() -> bytes:
    """Loyihani ZIP qilib xotirada yig'adi.

    Raises:
        HTTPException: arxiv juda katta bo'lsa (kutilmagan holat).
    """
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(BASE_DIR.rglob("*")):
            if not path.is_file() or _skip(path.relative_to(BASE_DIR)):
                continue
            archive.write(
                path,
                arcname=Path("codeassistant") / path.relative_to(BASE_DIR),
            )

        if buffer.tell() > MAX_ZIP_BYTES:
            raise HTTPException(
                status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
                detail="Arxiv juda katta — chiqarib tashlash ro'yxatini tekshiring",
            )

    return buffer.getvalue()


@router.get("/info")
async def download_info(_: CurrentUser) -> dict[str, object]:
    """O'rnatish uchun kerakli ma'lumot (buyruqlar frontendda shundan yig'iladi)."""
    modelfile = BASE_DIR / "ollama" / "Modelfile"
    base_model = "qwen2.5-coder:14b"

    if modelfile.is_file():
        for line in modelfile.read_text(encoding="utf-8").splitlines():
            if line.startswith("FROM "):
                base_model = line.split(maxsplit=1)[1].strip()
                break

    return {
        "local_model": settings.ollama_model,
        "base_model": base_model,
        "backend_port": settings.backend_port,
        "frontend_port": settings.frontend_port,
        "archive_name": "codeassistant.zip",
    }


@router.get("/source")
async def download_source(user: CurrentUser) -> Response:
    """Loyiha kodini `.zip` qilib qaytaradi.

    `.venv`, `node_modules`, `.env`, baza va workspace kirmaydi.
    """
    del user  # faqat autentifikatsiya uchun kerak

    data = _build_archive()
    stamp = datetime.now(UTC).strftime("%Y%m%d")

    return Response(
        content=data,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="codeassistant-{stamp}.zip"'
            ),
            "Content-Length": str(len(data)),
            "Cache-Control": "no-store",
        },
    )
