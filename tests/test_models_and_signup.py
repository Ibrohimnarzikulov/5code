"""Signup, model tanlash va bulk ai_in_pc testlari."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.anyio


# --- Ro'yxatdan o'tish -----------------------------------------------------


async def test_signup_creates_plain_user(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"username": "yangi_user", "password": "parol123"},
    )
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["token_type"] == "bearer"
    # Yangi hisob hech qachon admin yoki ai_in_pc bilan kelmaydi
    assert body["user"]["role"] == "user"
    assert body["user"]["ai_in_pc"] is False


async def test_signup_token_works_immediately(client: httpx.AsyncClient) -> None:
    token = (
        await client.post(
            "/api/auth/register",
            json={"username": "darhol", "password": "parol123"},
        )
    ).json()["access_token"]

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "darhol"


async def test_signup_rejects_duplicate(client: httpx.AsyncClient) -> None:
    payload = {"username": "takrorchi", "password": "parol123"}
    assert (await client.post("/api/auth/register", json=payload)).status_code == 201
    assert (await client.post("/api/auth/register", json=payload)).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "ab", "password": "parol123"},  # login juda qisqa
        {"username": "yaxshi", "password": "123"},  # parol juda qisqa
        {"username": "yomon nom", "password": "parol123"},  # probel
    ],
)
async def test_signup_validation(client: httpx.AsyncClient, payload: dict) -> None:
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 422


# --- Bulk ai_in_pc ---------------------------------------------------------


async def test_grant_ai_in_pc_to_everyone(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    for name in ("aziz", "bobur", "davron"):
        await client.post(
            "/api/auth/register", json={"username": name, "password": "parol123"}
        )

    users = (await client.get("/api/users", headers=auth_headers)).json()
    assert sum(u["ai_in_pc"] for u in users) == 1  # faqat admin

    granted = await client.post(
        "/api/users/ai-in-pc/all?enabled=true", headers=auth_headers
    )
    assert granted.status_code == 200
    assert all(u["ai_in_pc"] for u in granted.json())
    assert len(granted.json()) == 4

    revoked = await client.post(
        "/api/users/ai-in-pc/all?enabled=false", headers=auth_headers
    )
    assert not any(u["ai_in_pc"] for u in revoked.json())


async def test_bulk_grant_is_admin_only(client: httpx.AsyncClient) -> None:
    token = (
        await client.post(
            "/api/auth/register",
            json={"username": "oddiy_user", "password": "parol123"},
        )
    ).json()["access_token"]

    response = await client.post(
        "/api/users/ai-in-pc/all?enabled=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# --- Modellar --------------------------------------------------------------


async def test_list_models(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/models", headers=auth_headers)
    assert response.status_code == 200

    models = response.json()
    names = {m["model"] for m in models}
    assert "5code" in names  # lokal model har doim ro'yxatda

    five = next(m for m in models if m["model"] == "5code")
    assert five["provider"] == "ollama"
    assert five["local"] is True
    assert five["recommended"] is True

    # Gemini kalitsiz — ko'rinadi, lekin tanlab bo'lmaydi
    gemini = next(m for m in models if m["provider"] == "gemini")
    assert gemini["available"] is False


async def test_choose_and_reset_model(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    chosen = await client.put(
        "/api/models/selection",
        json={"provider": "ollama", "model": "5code"},
        headers=auth_headers,
    )
    assert chosen.status_code == 200
    assert chosen.json()["ai_provider"] == "ollama"
    assert chosen.json()["ai_model"] == "5code"

    # /me ham yangi tanlovni ko'rsatadi
    me = (await client.get("/api/auth/me", headers=auth_headers)).json()
    assert me["ai_model"] == "5code"

    reset = await client.put(
        "/api/models/selection",
        json={"provider": None, "model": None},
        headers=auth_headers,
    )
    assert reset.json()["ai_provider"] is None


async def test_choose_model_validation(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    only_provider = await client.put(
        "/api/models/selection",
        json={"provider": "ollama"},
        headers=auth_headers,
    )
    assert only_provider.status_code == 400

    unknown = await client.put(
        "/api/models/selection",
        json={"provider": "skynet", "model": "x"},
        headers=auth_headers,
    )
    assert unknown.status_code == 400


async def test_models_require_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/models")).status_code == 401


async def test_ollama_models_use_ollama_base_url(monkeypatch) -> None:
    """Lokal modellar ro'yxati Ollama manzilidan so'raladi (Groq'dan emas)."""
    from app.routers import models as models_router

    called: list[str] = []

    class FakeResponse:
        @staticmethod
        def raise_for_status() -> None: ...

        @staticmethod
        def json() -> dict:
            return {"models": [{"name": "5code:latest"}]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def get(self, url: str):
            called.append(url)
            return FakeResponse()

    monkeypatch.setattr(models_router.httpx, "AsyncClient", lambda **_: FakeClient())

    result = await models_router._ollama_models()

    assert result == ["5code:latest"]
    assert called == ["http://localhost:11434/api/tags"]
    assert "groq" not in called[0]
