"""Artifact tizimi testlari — yaratish, versiyalash, render, xavfsizlik."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from app.ai.client import stream_reply
from app.ai.providers.base import Provider, final_event
from app.ai.tools import ToolContext, execute_tool
from app.database import SessionLocal
from app.models import Artifact, User

pytestmark = pytest.mark.anyio

SAMPLE_HTML = """<!doctype html>
<html lang="uz"><head><meta charset="utf-8"><title>Test</title>
<style>:root{--accent:#5eead4}body{background:#06070b;color:#fff}</style></head>
<body><h1>Salom dunyo</h1><script>console.log('ok')</script></body></html>"""


class FakeProvider(Provider):
    """Oldindan belgilangan turlarni qaytaruvchi soxta provider."""

    name = "fake"

    def __init__(self, turns: list[list[dict[str, Any]]]) -> None:
        self._turns = turns
        self.calls = 0

    @property
    def model(self) -> str:
        return "fake-model"

    async def stream_turn(self, **_: Any) -> AsyncIterator[dict[str, Any]]:
        blocks = self._turns[min(self.calls, len(self._turns) - 1)]
        self.calls += 1
        has_tool = any(b["type"] == "tool_use" for b in blocks)
        for block in blocks:
            if block["type"] == "text":
                yield {"type": "text", "text": block["text"]}
        yield final_event(blocks, "tool_use" if has_tool else "end")


async def _first_user_id() -> int:
    async with SessionLocal() as db:
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.username == "macbookair_4"))
        return result.scalar_one().id


# --- Tool darajasi ---------------------------------------------------------


async def test_create_artifact_stores_row(client: httpx.AsyncClient) -> None:
    user_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        result = await execute_tool(
            "create_artifact", {"title": "Portfolio", "html": SAMPLE_HTML}, ctx
        )
        await db.commit()

    assert not result.is_error, result.content
    assert len(ctx.artifacts) == 1
    assert ctx.artifacts[0]["title"] == "Portfolio"
    assert ctx.artifacts[0]["version"] == 1
    assert ctx.artifacts[0]["token"]


async def test_create_artifact_rejects_tiny_html(client: httpx.AsyncClient) -> None:
    user_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        result = await execute_tool(
            "create_artifact", {"title": "Kichik", "html": "<p>hi</p>"}, ctx
        )
    assert result.is_error
    assert "juda qisqa" in result.content


async def test_update_artifact_bumps_version(client: httpx.AsyncClient) -> None:
    user_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        await execute_tool(
            "create_artifact", {"title": "V1", "html": SAMPLE_HTML}, ctx
        )
        artifact_id = ctx.artifacts[0]["id"]

        result = await execute_tool(
            "update_artifact",
            {"artifact_id": artifact_id, "html": SAMPLE_HTML + "<!-- v2 -->"},
            ctx,
        )
        await db.commit()

    assert not result.is_error, result.content
    assert ctx.artifacts[-1]["version"] == 2


async def test_cannot_update_someone_elses_artifact(
    client: httpx.AsyncClient,
) -> None:
    owner_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=owner_id, db=db)
        await execute_tool("create_artifact", {"title": "X", "html": SAMPLE_HTML}, ctx)
        artifact_id = ctx.artifacts[0]["id"]
        await db.commit()

    async with SessionLocal() as db:
        intruder = ToolContext(ai_in_pc=False, user_id=owner_id + 999, db=db)
        result = await execute_tool(
            "update_artifact",
            {"artifact_id": artifact_id, "html": SAMPLE_HTML},
            intruder,
        )
    assert result.is_error
    assert "topilmadi" in result.content


# --- To'liq oqim (stream_reply) --------------------------------------------


async def test_stream_reply_emits_artifact_event(client: httpx.AsyncClient) -> None:
    """Model create_artifact chaqirsa — UI ga `artifact` hodisasi boradi."""
    user_id = await _first_user_id()
    provider = FakeProvider(
        [
            [
                {"type": "text", "text": "Sayt yasayapman…"},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "create_artifact",
                    "input": {"title": "Landing", "html": SAMPLE_HTML},
                },
            ],
            [{"type": "text", "text": "Tayyor! Dark tema, animatsiyalar bilan."}],
        ]
    )

    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        events = [
            event
            async for event in stream_reply(
                history=[], user_message="Menga portfolio sayt yasab ber",
                ctx=ctx, provider=provider,
            )
        ]
        await db.commit()

    types = [e["type"] for e in events]
    assert "tool_use" in types
    assert "artifact" in types
    assert "tool_result" in types

    artifact_event = next(e for e in events if e["type"] == "artifact")
    assert artifact_event["title"] == "Landing"
    assert provider.calls == 2  # tool natijasidan keyin ikkinchi tur


# --- HTTP qatlami ----------------------------------------------------------


async def test_artifact_list_and_render(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    user_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        await execute_tool(
            "create_artifact", {"title": "Sayt", "html": SAMPLE_HTML}, ctx
        )
        await db.commit()
    token = ctx.artifacts[0]["token"]

    listed = await client.get("/api/artifacts", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Sayt"

    rendered = await client.get(f"/a/{token}")
    assert rendered.status_code == 200
    assert "Salom dunyo" in rendered.text
    # Sandbox — artifact bizning origin'imizga kira olmasligi shart
    assert "sandbox" in rendered.headers["content-security-policy"]
    assert "allow-same-origin" not in rendered.headers["content-security-policy"]


async def test_render_unknown_token_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/a/yoq-bunday-token")).status_code == 404


async def test_artifact_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/artifacts")).status_code == 401


async def test_delete_artifact(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    user_id = await _first_user_id()
    async with SessionLocal() as db:
        ctx = ToolContext(ai_in_pc=False, user_id=user_id, db=db)
        await execute_tool(
            "create_artifact", {"title": "O'chadi", "html": SAMPLE_HTML}, ctx
        )
        await db.commit()
    artifact_id = ctx.artifacts[0]["id"]

    deleted = await client.delete(
        f"/api/artifacts/{artifact_id}", headers=auth_headers
    )
    assert deleted.status_code == 204

    async with SessionLocal() as db:
        assert await db.get(Artifact, artifact_id) is None
