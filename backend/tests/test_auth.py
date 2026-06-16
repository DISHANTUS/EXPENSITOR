"""Authentication endpoint tests (success + failure)."""

from __future__ import annotations

from httpx import AsyncClient

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/users/me"

EMAIL = "user@example.com"
PASSWORD = "Password123"


async def _register(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD, full_name: str | None = "Test User"):
    return await client.post(REGISTER, json={"email": email, "password": password, "full_name": full_name})


async def _login(client: AsyncClient, email: str = EMAIL, password: str = PASSWORD):
    return await client.post(LOGIN, json={"email": email, "password": password})


# --- register ---------------------------------------------------------------

async def test_register_success(client: AsyncClient):
    resp = await _register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["is_active"] is True
    assert "id" in body
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email(client: AsyncClient):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 409


async def test_register_duplicate_is_case_insensitive(client: AsyncClient):
    await _register(client, email="Mixed@Example.com")
    resp = await _register(client, email="mixed@example.com")
    assert resp.status_code == 409


async def test_register_invalid_email(client: AsyncClient):
    resp = await _register(client, email="not-an-email")
    assert resp.status_code == 422


async def test_register_short_password(client: AsyncClient):
    resp = await _register(client, password="short")
    assert resp.status_code == 422


# --- login ------------------------------------------------------------------

async def test_login_success(client: AsyncClient):
    await _register(client)
    resp = await _login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0


async def test_login_wrong_password(client: AsyncClient):
    await _register(client)
    resp = await _login(client, password="WrongPassword1")
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    resp = await _login(client, email="nobody@example.com")
    assert resp.status_code == 401


# --- refresh ----------------------------------------------------------------

async def test_refresh_success_and_rotation(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    resp = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 200
    new = resp.json()
    assert new["access_token"] and new["refresh_token"]
    assert new["refresh_token"] != tokens["refresh_token"]  # rotated


async def test_refresh_reuse_is_rejected(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    old = tokens["refresh_token"]
    assert (await client.post(REFRESH, json={"refresh_token": old})).status_code == 200
    # Replaying the now-revoked token is rejected (reuse detection).
    resp = await client.post(REFRESH, json={"refresh_token": old})
    assert resp.status_code == 401


async def test_refresh_rejects_garbage(client: AsyncClient):
    resp = await client.post(REFRESH, json={"refresh_token": "not.a.jwt"})
    assert resp.status_code == 401


async def test_access_token_cannot_be_used_to_refresh(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    resp = await client.post(REFRESH, json={"refresh_token": tokens["access_token"]})
    assert resp.status_code == 401


# --- logout -----------------------------------------------------------------

async def test_logout_then_refresh_fails(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    logout = await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})
    assert logout.status_code == 204
    resp = await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


async def test_logout_is_idempotent(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    assert (await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})).status_code == 204
    # Logging out again with the same token is still a no-op success.
    assert (await client.post(LOGOUT, json={"refresh_token": tokens["refresh_token"]})).status_code == 204


# --- get current user -------------------------------------------------------

async def test_me_success(client: AsyncClient):
    await _register(client)
    tokens = (await _login(client)).json()
    resp = await client.get(ME, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == EMAIL


async def test_me_requires_token(client: AsyncClient):
    resp = await client.get(ME)
    assert resp.status_code == 401


async def test_me_rejects_invalid_token(client: AsyncClient):
    resp = await client.get(ME, headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
