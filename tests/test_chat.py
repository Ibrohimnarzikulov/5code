"""Chat oqimi va suhbatlar tarixi testlari (Claude API mock qilingan)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from app.routers import chat as chat_router

pytestmark = pytest.mark.anyio


def _fake_stream(events: list[dict[str, Any]]):
    """`stream_reply` o'rniga qo'yiladigan soxta oqim yaratadi."""

    async def fake(**_: Any) -> AsyncIterator[dict[str, Any]]:
        for event in events:
            yield event

    return fake


async def _collect_sse(
    client: httpx.AsyncClient, headers: dict[str, str], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    """SSE oqimini o'qib, hodisalar ro'yxatini qaytaradi."""
    received: list[dict[str, Any]] = []
    async with client.stream(
        "POST", "/api/chat", json=payload, headers=headers
    ) as response:
        assert response.status_code == 200, await response.aread()
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                received.append(json.loads(line[6:]))
    return received


async def test_chat_creates_conversation_and_persists(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        chat_router,
        "stream_reply",
        _fake_stream(
            [
                {"type": "text", "text": "Salom! "},
                {"type": "text", "text": "Nima yordam kerak?"},
                {
                    "type": "assistant_message",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "Salom! Nima yordam kerak?"}
                            ],
                        }
                    ],
                },
            ]
        ),
    )

    events = await _collect_sse(
        client, auth_headers, {"message": "Salom, kim sen?"}
    )

    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert types[-1] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "text") == (
        "Salom! Nima yordam kerak?"
    )

    conversation_id = events[0]["conversation_id"]

    conversations = (
        await client.get("/api/conversations", headers=auth_headers)
    ).json()
    assert len(conversations) == 1
    assert conversations[0]["title"] == "Salom, kim sen?"

    messages = (
        await client.get(
            f"/api/conversations/{conversation_id}/messages", headers=auth_headers
        )
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Salom, kim sen?"


async def test_chat_tool_events_are_forwarded(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        chat_router,
        "stream_reply",
        _fake_stream(
            [
                {"type": "thinking", "text": "Papkani ko'ray..."},
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "list_dir",
                    "input": {"path": ""},
                },
                {
                    "type": "tool_result",
                    "id": "toolu_1",
                    "name": "list_dir",
                    "content": "(papka bo'sh)",
                    "is_error": False,
                },
                {"type": "text", "text": "Papka bo'sh."},
                {"type": "assistant_message", "messages": []},
            ]
        ),
    )

    events = await _collect_sse(client, auth_headers, {"message": "Papkani ko'rsat"})
    types = [e["type"] for e in events]

    assert "thinking" in types
    assert "tool_use" in types
    assert "tool_result" in types


async def test_chat_without_api_key_reports_error(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Kalit sozlanmagan bo'lsa — oqim uzilmasdan xato hodisasi keladi."""
    events = await _collect_sse(client, auth_headers, {"message": "Salom"})
    errors = [e for e in events if e["type"] == "error"]
    assert errors, events
    assert "GEMINI_API_KEY" in errors[0]["message"]


async def test_chat_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/chat", json={"message": "Salom"})
    assert response.status_code == 401


async def test_cannot_read_someone_elses_conversation(
    client: httpx.AsyncClient, auth_headers: dict[str, str], monkeypatch
) -> None:
    monkeypatch.setattr(
        chat_router,
        "stream_reply",
        _fake_stream([{"type": "assistant_message", "messages": []}]),
    )
    events = await _collect_sse(client, auth_headers, {"message": "Admin xabari"})
    conversation_id = events[0]["conversation_id"]

    await client.post(
        "/api/users",
        json={"username": "begona", "password": "parol123"},
        headers=auth_headers,
    )
    token = (
        await client.post(
            "/api/auth/login",
            json={"username": "begona", "password": "parol123"},
        )
    ).json()["access_token"]

    response = await client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


async def test_delete_conversation(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/conversations", json={"title": "Test"}, headers=auth_headers
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    deleted = await client.delete(
        f"/api/conversations/{conversation_id}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (await client.get("/api/conversations", headers=auth_headers)).json() == []
