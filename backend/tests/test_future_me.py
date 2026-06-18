"""Sprint 6b/6c — life events, Future Me surface, and the companion name."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


# ---- 6b: life events -------------------------------------------------------

async def test_life_event_crud_and_shows_on_timeline(client: AsyncClient):
    h = await _auth(client, "le_crud@example.com")
    future = (date.today() + timedelta(days=400)).isoformat()
    created = (await client.post("/api/v1/life-events", json={
        "title": "Planned move to Japan", "event_date": future, "kind": "move", "icon": "✈️"}, headers=h)).json()
    assert created["title"] == "Planned move to Japan"

    listed = (await client.get("/api/v1/life-events", headers=h)).json()
    assert len(listed) == 1

    tl = (await client.get("/api/v1/timeline", headers=h)).json()
    titles = [e["title"] for c in tl["chapters"] for e in c["entries"]]
    assert "Planned move to Japan" in titles and tl["future_count"] >= 1

    assert (await client.delete(f"/api/v1/life-events/{created['id']}", headers=h)).status_code == 204
    assert (await client.get("/api/v1/life-events", headers=h)).json() == []


# ---- 6b: Future Me ---------------------------------------------------------

async def test_future_me_returns_paths_and_milestones(client: AsyncClient):
    h = await _auth(client, "fm_main@example.com")
    # a positive savings picture so the forecast can project paths (honest engine
    # only emits paths when savings are positive) ...
    await client.patch("/api/v1/users/me/settings",
                       json={"monthly_income_estimate": "60000", "starting_balance": "20000"}, headers=h)
    for d in ("01", "05", "10"):
        await client.post("/api/v1/expenses", json={
            "original_amount": "500", "original_currency": "INR", "expense_date": f"2026-06-{d}"}, headers=h)
    # an active goal (gives the forecast something to centre on) ...
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000", "original_currency": "INR",
        "target_date": (date.today() + timedelta(days=500)).isoformat()}, headers=h)
    # ... and a future life event
    await client.post("/api/v1/life-events", json={
        "title": "Master’s begins", "event_date": (date.today() + timedelta(days=600)).isoformat(),
        "kind": "education", "icon": "🎓"}, headers=h)

    fm = (await client.get("/api/v1/advisor/future-me", headers=h)).json()
    assert {p["mode"] for p in fm["paths"]} >= {"current", "optimistic", "conservative"}
    titles = [m["title"] for m in fm["milestones"]]
    assert any("Japan Fund" in t for t in titles)
    assert "Master’s begins" in titles
    assert fm["currency"] == "INR"


async def test_future_me_survives_no_data(client: AsyncClient):
    h = await _auth(client, "fm_empty@example.com")
    fm = (await client.get("/api/v1/advisor/future-me", headers=h)).json()
    assert "paths" in fm and "milestones" in fm and fm["currency"] == "INR"


# ---- 6c: companion name ----------------------------------------------------

async def test_companion_name_persists_and_surfaces_in_mood(client: AsyncClient):
    h = await _auth(client, "name@example.com")
    await client.patch("/api/v1/users/me/settings", json={"companion_name": "  Kai  "}, headers=h)
    settings = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert settings["companion_name"] == "Kai"            # trimmed
    mood = (await client.get("/api/v1/companion/mood?hour=9", headers=h)).json()
    assert mood["companion_name"] == "Kai"
    # empty string clears it -> default identity (Advary) surfaces in mood
    await client.patch("/api/v1/users/me/settings", json={"companion_name": ""}, headers=h)
    assert (await client.get("/api/v1/users/me/settings", headers=h)).json()["companion_name"] is None
    assert (await client.get("/api/v1/companion/mood?hour=9", headers=h)).json()["companion_name"] == "Advary"
