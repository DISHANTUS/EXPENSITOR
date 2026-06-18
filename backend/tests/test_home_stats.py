"""Home Memory Strip stats (UI-X) — deterministic, degrades on a thin account."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "homestats@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_new_account_has_safe_defaults(client: AsyncClient):
    h = await _auth(client)
    s = (await client.get("/api/v1/companion/home-stats", headers=h)).json()
    assert s["days_with_advary"] >= 1
    assert s["goals_completed"] == 0 and s["goals_active"] == 0
    assert s["relationship_count"] == 0
    assert s["total_saved"] == "0.0000"
    assert s["strongest_habit"] is None and s["biggest_win"] is None


async def test_counts_goals_people_and_biggest_win(client: AsyncClient):
    h = await _auth(client)
    # An active goal → biggest_win falls back to it; a person → relationship_count.
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "monthly_target", "original_amount": "2000", "original_currency": "INR"}, headers=h)
    await client.post("/api/v1/persons", json={"name": "Ravi", "relationship_type": "friend"}, headers=h)

    s = (await client.get("/api/v1/companion/home-stats", headers=h)).json()
    assert s["goals_active"] == 1
    assert s["relationship_count"] == 1
    assert s["biggest_win"] == "Japan Fund"
    assert s["currency"] == "INR"
