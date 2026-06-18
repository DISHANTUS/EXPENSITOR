"""Conversational profile mutation (Budget Intelligence System — Phase 5).

Tell Advary about a life change → preview → confirm → apply → recalculate → impact.
Covers multi-change utterances, past vs future moves, income changes, and the
chat preview/confirm round-trip.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "mut@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_parse_previews_without_applying(client: AsyncClient):
    h = await _auth(client)
    p = (await client.post("/api/v1/budget/profile/parse",
                           json={"text": "I moved to Tokyo and now pay 80000 rent"}, headers=h)).json()
    assert p["understood"] is True
    fields = {c["field"] for c in p["changes"]}
    assert {"current_country", "current_city", "rent_monthly"} <= fields
    # Nothing applied yet.
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert prof["current_country"] is None


async def test_apply_updates_and_reports_impact(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/income-sources", json={
        "label": "Stipend", "source_type": "scholarship", "kind": "recurring",
        "original_amount": "120000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    r = (await client.post("/api/v1/budget/profile/apply",
                           json={"text": "I moved to Tokyo and now pay 80000 rent"}, headers=h)).json()
    applied = {c["field"] for c in r["applied"]}
    assert {"current_country", "rent_monthly"} <= applied
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert prof["current_country"] == "JP" and prof["rent_monthly"] == "80000.0000"
    # Housing now consumes income → an impact note appears.
    assert r["impact"]["housing_ratio_after"] > r["impact"]["housing_ratio_before"]
    assert r["impact"]["notes"]


async def test_future_move_does_not_change_current_country(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/budget/profile/apply",
                      json={"text": "I'm moving to Tokyo next year"}, headers=h)
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert prof["current_country"] is None           # still here…
    assert prof["moving_country"] is True and prof["future_country"] == "JP"   # …but future noted
    assert prof["future_move_year"] == 2027          # today is 2026 in tests' fixture clock


async def test_part_time_income_added(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/budget/profile/apply",
                      json={"text": "I got a part-time job earning 110k"}, headers=h)
    sources = (await client.get("/api/v1/income-sources", headers=h)).json()
    items = sources if isinstance(sources, list) else sources.get("items", [])
    assert any(s["source_type"] == "part_time" for s in items)


async def test_family_support_removed(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/income-sources", json={
        "label": "Family", "source_type": "family_support", "kind": "recurring",
        "original_amount": "50000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    await client.post("/api/v1/budget/profile/apply",
                      json={"text": "my father stopped sending money"}, headers=h)
    reality = (await client.get("/api/v1/budget/reality", headers=h)).json()
    # The (now inactive) family income no longer counts.
    assert all(s["source_type"] != "family_support" for s in reality["income_sources"])


async def test_unrecognised_change_asks_for_clarity(client: AsyncClient):
    h = await _auth(client)
    p = (await client.post("/api/v1/budget/profile/parse",
                           json={"text": "what's the weather"}, headers=h)).json()
    assert p["understood"] is False and p["changes"] == []


async def test_chat_preview_then_confirm_applies(client: AsyncClient):
    h = await _auth(client)
    turn = (await client.post("/api/v1/advisor/chat",
                              json={"message": "I moved to Tokyo"}, headers=h)).json()
    assert turn["type"] == "profile_preview"
    assert turn["session"]["pending_profile_text"]            # pending change carried in session
    # Confirm with the session echoed back.
    confirm = (await client.post("/api/v1/advisor/chat",
                                 json={"message": "yes, update my profile", "session": turn["session"]}, headers=h)).json()
    assert confirm["type"] == "profile_updated"
    prof = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert prof["current_country"] == "JP"
