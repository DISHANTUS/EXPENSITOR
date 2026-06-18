"""Financial profile (Budget Intelligence System — Phase 1: Profile Discovery).

One row per user, created lazily, every field editable anytime (the Tokyo-MEXT
PG-student case is the canonical shape).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "profile@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def test_new_user_has_empty_profile(client: AsyncClient):
    h = await _auth(client)
    p = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert p["life_stage"] is None
    assert p["moving_country"] is False
    assert p["current_country"] is None


async def test_update_builds_the_tokyo_profile(client: AsyncClient):
    h = await _auth(client)
    body = {
        "life_stage": "pg_student",
        "current_country": "jp",          # lowercased on input
        "current_city": "Tokyo",
        "living_situation": "alone",
        "food_situation": "home_cooked",
        "food_monthly": "35000",
        "transport_mode": "train",
        "transport_monthly": "10000",
        "tuition_responsibility": "scholarship_covered",
        "rent_monthly": "80000",
        "lifestyle_monthly": "15000",
    }
    p = (await client.patch("/api/v1/users/me/profile", json=body, headers=h)).json()
    assert p["life_stage"] == "pg_student"
    assert p["current_country"] == "JP"          # uppercased
    assert p["current_city"] == "Tokyo"
    assert p["rent_monthly"] == "80000.0000"
    assert p["tuition_responsibility"] == "scholarship_covered"

    # Persisted across a fresh GET.
    p2 = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert p2["food_monthly"] == "35000.0000" and p2["transport_mode"] == "train"


async def test_partial_update_leaves_other_fields(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile", json={"life_stage": "ug_student", "rent_monthly": "5000"}, headers=h)
    # change only the rent
    p = (await client.patch("/api/v1/users/me/profile", json={"rent_monthly": "6000"}, headers=h)).json()
    assert p["rent_monthly"] == "6000.0000"
    assert p["life_stage"] == "ug_student"        # untouched


async def test_future_move_and_other_note(client: AsyncClient):
    h = await _auth(client)
    p = (await client.patch("/api/v1/users/me/profile", json={
        "moving_country": True, "future_country": "jp", "future_move_year": 2028,
        "life_stage": "other", "life_stage_note": "Preparing for MEXT"}, headers=h)).json()
    assert p["moving_country"] is True and p["future_country"] == "JP" and p["future_move_year"] == 2028
    assert p["life_stage"] == "other" and p["life_stage_note"] == "Preparing for MEXT"


async def test_transport_other_and_new_modes(client: AsyncClient):
    h = await _auth(client, email="transport@example.com")
    # The onboarding blocker: "I ride a bike to college" is now a real option.
    p = (await client.patch("/api/v1/users/me/profile",
         json={"transport_mode": "motorcycle", "transport_monthly": "2000"}, headers=h)).json()
    assert p["transport_mode"] == "motorcycle" and p["transport_monthly"] == "2000.0000"
    # And anything unlisted is captured via Other → free text.
    p2 = (await client.patch("/api/v1/users/me/profile",
          json={"transport_mode": "other", "transport_note": "Carpool with neighbours"}, headers=h)).json()
    assert p2["transport_mode"] == "other" and p2["transport_note"] == "Carpool with neighbours"


async def test_editable_later_can_change_and_clear(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile", json={"life_stage": "ug_student", "current_city": "Chennai"}, headers=h)
    # "I moved" — change country/city later, clear nothing-is-locked
    p = (await client.patch("/api/v1/users/me/profile", json={
        "life_stage": "pg_student", "current_country": "jp", "current_city": "Tokyo"}, headers=h)).json()
    assert p["life_stage"] == "pg_student" and p["current_city"] == "Tokyo"
    cleared = (await client.patch("/api/v1/users/me/profile", json={"current_city": None}, headers=h)).json()
    assert cleared["current_city"] is None


async def test_invalid_enum_rejected(client: AsyncClient):
    h = await _auth(client)
    res = await client.patch("/api/v1/users/me/profile", json={"life_stage": "astronaut"}, headers=h)
    assert res.status_code == 422


async def test_full_reset_clears_profile(client: AsyncClient):
    h = await _auth(client, "advary2006@gmail.com")   # developer can reset
    await client.patch("/api/v1/users/me/profile", json={"life_stage": "pg_student", "rent_monthly": "80000"}, headers=h)
    await client.post("/api/v1/reset", json={"mode": "full"}, headers=h)
    p = (await client.get("/api/v1/users/me/profile", headers=h)).json()
    assert p["life_stage"] is None and p["rent_monthly"] is None
