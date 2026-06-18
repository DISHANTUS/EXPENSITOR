"""Developer-only tools: calendar preview seeder (gated)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_calendar_preview_seeds_events_for_developer(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")   # developer (allow-list)
    res = await client.post("/api/v1/dev/calendar-preview", headers=h)
    assert res.status_code == 200 and res.json()["created"] == 7

    # The seeded events are real — they surface on the timeline.
    titles = " ".join(
        e["title"] for c in (await client.get("/api/v1/timeline", headers=h)).json()["chapters"]
        for e in c["entries"]).lower()
    assert "kyoto" in titles or "birthday" in titles or "mia" in titles


async def test_calendar_preview_forbidden_for_non_developer(client: AsyncClient):
    h = await _auth(client, "normal_user@example.com")
    res = await client.post("/api/v1/dev/calendar-preview", headers=h)
    assert res.status_code == 403
