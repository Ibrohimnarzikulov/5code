"""Yuklab olish endpoint'lari — arxiv tarkibi va maxfiylik."""

from __future__ import annotations

import io
import zipfile

import httpx
import pytest

pytestmark = pytest.mark.anyio


async def test_download_info(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/download/info", headers=auth_headers)
    assert response.status_code == 200

    info = response.json()
    assert info["local_model"] == "5code"
    assert info["base_model"].startswith("qwen")
    assert info["backend_port"] == 1221
    assert info["frontend_port"] == 1991


async def test_download_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/download/info")).status_code == 401
    assert (await client.get("/api/download/source")).status_code == 401


async def test_source_archive_contains_code(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/download/source", headers=auth_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert ".zip" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()

    # Manba kodi bor
    assert "codeassistant/app/main.py" in names
    assert "codeassistant/ollama/Modelfile" in names
    assert "codeassistant/web/src/App.jsx" in names
    assert "codeassistant/README.md" in names


async def test_source_archive_excludes_secrets_and_bulk(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """.env, baza, virtual muhit va node_modules arxivga tushmasligi shart."""
    response = await client.get("/api/download/source", headers=auth_headers)

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()

    forbidden = (".venv/", "node_modules/", "/data/", "/workspace/", "/.git/")
    for fragment in forbidden:
        assert not any(fragment in name for name in names), fragment

    assert not any(name.endswith("/.env") for name in names)
    assert not any(name.endswith(".db") for name in names)
    assert not any(name.endswith(".pyc") for name in names)

    # .env.example esa bo'lishi kerak (namuna sifatida)
    assert "codeassistant/.env.example" in names


async def test_archive_is_reasonably_small(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Katta papkalar chiqarilgani uchun arxiv bir necha MB dan oshmasligi kerak."""
    response = await client.get("/api/download/source", headers=auth_headers)
    assert len(response.content) < 5 * 1024 * 1024
