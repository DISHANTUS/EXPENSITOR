"""5a.5 tests: intelligence-driven companion reactions (mood.pending_reactions) —
overspend, achievement (+timeline label), and surface-once dedup."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

MOOD = "/api/v1/companion/mood"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def test_overspend_reaction_taps_to_plan_today(client: AsyncClient) -> None:
    h = await _auth(client, "rx1@example.com")
    today = _today().isoformat()
    await client.put(f"/api/v1/daily-plans/{today}", json={"planned_budget": "100"}, headers=h)
    await client.post("/api/v1/expenses",
                      json={"original_amount": "400", "original_currency": "INR", "expense_date": today}, headers=h)
    pending = (await client.get(MOOD, headers=h)).json()["pending_reactions"]
    over = next((r for r in pending if r["kind"] == "overspend"), None)
    assert over and over["tap_route"] == "/plan-today" and "over today" in over["headline"].lower()


async def test_achievement_reaction_has_timeline_label(client: AsyncClient) -> None:
    h = await _auth(client, "rx2@example.com")
    g = (await client.post("/api/v1/savings-goals",
                           json={"name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
                                 "original_currency": "INR",
                                 "target_date": (_today() + timedelta(days=400)).isoformat()}, headers=h)).json()
    await client.patch(f"/api/v1/savings-goals/{g['id']}", json={"status": "completed"}, headers=h)
    pending = (await client.get(MOOD, headers=h)).json()["pending_reactions"]
    ach = next((r for r in pending if r["kind"] == "achievement"), None)
    assert ach and ach["importance"] == "achievement"
    assert "Japan Fund" in (ach["timeline_label"] or "")     # feeds Sprint 6 Timeline


async def test_reactions_surface_only_once(client: AsyncClient) -> None:
    h = await _auth(client, "rx3@example.com")
    today = _today().isoformat()
    await client.put(f"/api/v1/daily-plans/{today}", json={"planned_budget": "100"}, headers=h)
    await client.post("/api/v1/expenses",
                      json={"original_amount": "400", "original_currency": "INR", "expense_date": today}, headers=h)
    first = (await client.get(MOOD, headers=h)).json()["pending_reactions"]
    second = (await client.get(MOOD, headers=h)).json()["pending_reactions"]
    assert any(r["kind"] == "overspend" for r in first)
    assert not any(r["kind"] == "overspend" for r in second)   # surfaced once, not repeated
