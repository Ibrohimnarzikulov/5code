"""Test konfiguratsiyasi — izolyatsiyalangan baza va workspace."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# Sozlamalar keshlanishidan OLDIN muhitni tayyorlaymiz.
_TMP = Path(tempfile.mkdtemp(prefix="codeassistant-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["WORKSPACE_ROOT"] = str(_TMP / "workspace")
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_USERNAME"] = "macbookair_4"
os.environ["ADMIN_PASSWORD"] = "egoist"
os.environ["AI_PROVIDER"] = "gemini"
for _key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(_key, None)

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import engine, init_db  # noqa: E402
from app.main import app, seed_admin  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Toza bazali HTTP klient."""
    from app.database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    await seed_admin()
    settings.workspace_root.mkdir(parents=True, exist_ok=True)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def admin_token(client: httpx.AsyncClient) -> str:
    """Admin sifatida login qilib token oladi."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "macbookair_4", "password": "egoist"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
