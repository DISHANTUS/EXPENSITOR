"""Reset / Clean-Slate (pre-Sprint-8): soft keeps settings, full clears them,
demo seeds a fictional sample — all orphan-free."""

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


async def _seed(client: AsyncClient, h: dict[str, str]) -> None:
    await client.post("/api/v1/incomes", json={
        "source_type": "salary", "original_amount": "50000", "original_currency": "INR",
        "received_date": "2026-01-05"}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000", "original_currency": "INR",
        "target_date": (date.today() + timedelta(days=400)).isoformat()}, headers=h)
    await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "3000", "original_currency": "INR", "expected_date": "2026-06-10"}, headers=h)
    await client.post("/api/v1/life-events", json={
        "title": "Move to Japan", "event_date": "2028-04-01", "kind": "move", "icon": "✈️"}, headers=h)


def _titles(tl: dict) -> list[str]:
    return [e["title"] for c in tl["chapters"] for e in c["entries"]]


async def test_soft_reset_wipes_story_keeps_settings(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")
    await client.patch("/api/v1/users/me/settings", json={"companion_name": "Kai"}, headers=h)
    await _seed(client, h)
    assert (await client.get("/api/v1/timeline", headers=h)).json()["chapters"]   # populated

    r = (await client.post("/api/v1/reset", json={"mode": "soft"}, headers=h)).json()
    assert r["ok"] and r["mode"] == "soft"

    assert (await client.get("/api/v1/timeline", headers=h)).json()["chapters"] == []
    assert (await client.get("/api/v1/incomes", headers=h)).json()["total"] == 0
    assert (await client.get("/api/v1/relationships", headers=h)).json()["people"] == []
    # settings kept
    s = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert s["companion_name"] == "Kai" and s["base_currency"] == "INR"


async def test_full_reset_also_clears_settings_to_default(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")
    await client.patch("/api/v1/users/me/settings", json={"companion_name": "Kai"}, headers=h)
    await _seed(client, h)

    await client.post("/api/v1/reset", json={"mode": "full"}, headers=h)
    assert (await client.get("/api/v1/timeline", headers=h)).json()["chapters"] == []
    s = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert s["companion_name"] is None                       # back to default identity
    # mood now reflects the default companion name
    assert (await client.get("/api/v1/companion/mood?hour=9", headers=h)).json()["companion_name"] == "Advary"


async def test_demo_seed_populates_a_fictional_user(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")
    await _seed(client, h)   # the owner's real data first

    await client.post("/api/v1/reset", json={"mode": "demo"}, headers=h)
    titles = _titles((await client.get("/api/v1/timeline", headers=h)).json())
    # owner's data gone, fictional sample present
    assert not any("Ravi" in t or "Japan" in t for t in titles)
    assert any("Dream Trip" in t for t in titles)
    people = {p["name"] for p in (await client.get("/api/v1/relationships", headers=h)).json()["people"]}
    assert "Sam" in people or "Mia" in people


async def test_reset_voice_and_profile_behaviour(client: AsyncClient):
    """Voice settings + financial profile survive a soft reset (they're identity,
    not story) and are cleared by a full reset — no orphaned profile left behind."""
    h = await _auth(client, "advary2006@gmail.com")
    await client.patch("/api/v1/users/me/settings",
                       json={"selected_voice": "en-us-x-sfg#female_1-local", "voice_locale": "en-US"}, headers=h)
    await client.patch("/api/v1/users/me/profile",
                       json={"life_stage": "pg_student", "current_country": "jp"}, headers=h)
    await _seed(client, h)

    # Soft: story gone, but the chosen voice and profile remain.
    await client.post("/api/v1/reset", json={"mode": "soft"}, headers=h)
    s = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert s["selected_voice"] == "en-us-x-sfg#female_1-local" and s["voice_locale"] == "en-US"
    p = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert p["life_stage"] == "pg_student" and p["current_country"] == "JP"

    # Full: voice cleared to default, profile wiped (no orphan).
    await client.post("/api/v1/reset", json={"mode": "full"}, headers=h)
    s2 = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert s2["selected_voice"] is None and s2["voice_locale"] is None
    p2 = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert p2["life_stage"] is None and p2["current_country"] is None


async def test_reset_forbidden_for_non_developer(client: AsyncClient):
    h = await _auth(client, "normal_user@example.com")     # not a developer
    await _seed(client, h)
    for mode in ("soft", "full", "demo"):
        res = await client.post("/api/v1/reset", json={"mode": mode}, headers=h)
        assert res.status_code == 403
    # data untouched by the forbidden calls
    assert (await client.get("/api/v1/timeline", headers=h)).json()["chapters"]


async def test_me_reports_developer_status(client: AsyncClient):
    dev = await _auth(client, "advary2006@gmail.com")
    assert (await client.get("/api/v1/users/me", headers=dev)).json()["is_developer"] is True
    normal = await _auth(client, "someone_else@example.com")
    assert (await client.get("/api/v1/users/me", headers=normal)).json()["is_developer"] is False
