"""Date → Orb reaction (UI-X) — Advary's warm one-liner about a tapped day."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "react@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_income_day_reaction(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/incomes", json={
        "source_type": "scholarship", "original_amount": "50000", "original_currency": "INR",
        "received_date": "2026-05-01"}, headers=h)

    r = (await client.get("/api/v1/companion/date-reaction", params={"date": "2026-05-01"}, headers=h)).json()
    assert "scholarship" in r["line"].lower()
    assert r["mood"] == "celebrating"


async def test_quiet_day_has_a_gentle_default(client: AsyncClient):
    h = await _auth(client, email="react2@example.com")
    r = (await client.get("/api/v1/companion/date-reaction", params={"date": "2026-05-02"}, headers=h)).json()
    assert r["line"] and r["mood"] == "idle"
