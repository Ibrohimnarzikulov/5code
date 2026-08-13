"""Autentifikatsiya va foydalanuvchi boshqaruvi testlari."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.anyio


async def test_health(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_login_success(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "macbookair_4", "password": "egoist"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert body["user"]["ai_in_pc"] is True


async def test_login_wrong_password(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "macbookair_4", "password": "noto'g'ri"},
    )
    assert response.status_code == 401


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (
        await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer soxta.token.xxx"}
        )
    ).status_code == 401


async def test_me_with_token(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "macbookair_4"


async def test_admin_creates_user_and_grants_ai_in_pc(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/api/users",
        json={"username": "dilmurod", "password": "parol123"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    user = created.json()
    assert user["role"] == "user"
    assert user["ai_in_pc"] is False

    updated = await client.patch(
        f"/api/users/{user['id']}",
        json={"ai_in_pc": True},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["ai_in_pc"] is True


async def test_duplicate_username_rejected(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    payload = {"username": "takror", "password": "parol123"}
    assert (
        await client.post("/api/users", json=payload, headers=auth_headers)
    ).status_code == 201
    assert (
        await client.post("/api/users", json=payload, headers=auth_headers)
    ).status_code == 409


async def test_plain_user_cannot_manage_users(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post(
        "/api/users",
        json={"username": "oddiy", "password": "parol123"},
        headers=auth_headers,
    )
    token = (
        await client.post(
            "/api/auth/login",
            json={"username": "oddiy", "password": "parol123"},
        )
    ).json()["access_token"]

    response = await client.get(
        "/api/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_admin_cannot_delete_self(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    me = (await client.get("/api/auth/me", headers=auth_headers)).json()
    response = await client.delete(f"/api/users/{me['id']}", headers=auth_headers)
    assert response.status_code == 400


async def test_blocked_user_cannot_login(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    user = (
        await client.post(
            "/api/users",
            json={"username": "bloklangan", "password": "parol123"},
            headers=auth_headers,
        )
    ).json()
    await client.patch(
        f"/api/users/{user['id']}", json={"is_active": False}, headers=auth_headers
    )
    response = await client.post(
        "/api/auth/login",
        json={"username": "bloklangan", "password": "parol123"},
    )
    assert response.status_code == 403
