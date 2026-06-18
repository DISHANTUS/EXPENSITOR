"""Country baselines (Budget Intelligence System — Phase 6).

Profile-specific reference data with confidence scores. Guidance only — the user's
real spending is always the truth; baselines never prescribe spending more.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.intelligence.budget import country_baselines as cb

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "baseline@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_baseline_is_profile_specific(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile",
                       json={"current_country": "jp", "life_stage": "pg_student"}, headers=h)
    b = (await client.get("/api/v1/budget/baseline", headers=h)).json()
    assert b["country"] == "JP" and b["group"] == "student"
    assert b["currency"] == "JPY" and b["confidence"] == "high"
    assert b["source"] == "bundled"
    student_food = float(b["food_daily"])

    # Same country, working professional → different (higher) baseline.
    await client.patch("/api/v1/users/me/profile", json={"life_stage": "working_professional"}, headers=h)
    bw = (await client.get("/api/v1/budget/baseline", headers=h)).json()
    assert bw["group"] == "working"
    assert float(bw["food_daily"]) > student_food


async def test_unknown_country_is_low_confidence(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile",
                       json={"current_country": "fr", "life_stage": "ug_student"}, headers=h)
    b = (await client.get("/api/v1/budget/baseline", headers=h)).json()
    assert b["confidence"] == "low" and b["food_daily"] is None and b["source"] == "none"


async def test_refresh_falls_back_to_bundled(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile",
                       json={"current_country": "in", "life_stage": "ug_student"}, headers=h)
    # No external provider wired → refresh must not break; bundled data returned.
    b = (await client.get("/api/v1/budget/baseline?refresh=true", headers=h)).json()
    assert b["country"] == "IN" and b["food_daily"] is not None and b["confidence"] == "high"


async def test_baseline_note_is_not_prescriptive(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile", json={"current_country": "jp"}, headers=h)
    b = (await client.get("/api/v1/budget/baseline", headers=h)).json()
    assert "real spending" in b["note"].lower()


async def test_compare_is_context_not_prescription():
    # below / typical / above / unknown — pure positioning, never "spend up to X".
    assert cb.compare(18000, 25000) == "below"
    assert cb.compare(80000, 25000) == "above"
    assert cb.compare(24000, 25000) == "typical"
    assert cb.compare(None, 25000) == "unknown"
    assert cb.compare(18000, None) == "unknown"
