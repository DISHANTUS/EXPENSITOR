"""The tiny dev analytics pipe — POST /dev/track (any user), GET /dev/stats (dev only)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_track_records_event(client: AsyncClient) -> None:
    h = await _auth(client, "track@example.com")
    r = await client.post("/api/v1/dev/track",
                          json={"event": "intervention_opened", "props": {"trigger": "borrowedMoney"}}, headers=h)
    assert r.status_code == 204


async def test_stats_is_developer_only(client: AsyncClient) -> None:
    h = await _auth(client, "track2@example.com")
    r = await client.get("/api/v1/dev/stats", headers=h)
    assert r.status_code == 403  # non-developer is blocked
