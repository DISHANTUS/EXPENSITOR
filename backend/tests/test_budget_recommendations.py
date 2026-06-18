"""Recommendation Engine (Budget Intelligence System — Phase 4).

Conservative/Balanced/Aggressive option sets with full math (daily + monthly),
confidence, reasons; essentials protected (food only on aggressive-goal + insist);
grow-income when cuts fall short; honest "why not" when a target is unrealistic.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "rec@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def _income(client, h, amount, source_type="salary", label="Income"):
    await client.post("/api/v1/income-sources", json={
        "label": label, "source_type": source_type, "kind": "recurring",
        "original_amount": amount, "original_currency": "INR", "recurrence_day": 1}, headers=h)


async def _sub(client, h, label, amount):
    await client.post("/api/v1/recurring-rules", json={
        "rule_type": "subscription", "label": label, "original_amount": amount,
        "original_currency": "INR", "recurrence_day": 5, "start_date": "2026-01-01"}, headers=h)


async def _goal(client, h, amount):
    await client.post("/api/v1/savings-goals", json={
        "name": "Savings", "kind": "monthly_target", "original_amount": amount, "original_currency": "INR"}, headers=h)


async def test_three_tiers_with_full_math_and_no_essential_cuts(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "50000")
    await client.patch("/api/v1/users/me/profile", json={
        "life_stage": "pg_student", "food_monthly": "12000", "transport_monthly": "3000",
        "lifestyle_monthly": "8000"}, headers=h)
    await _sub(client, h, "Netflix", "1500")
    await _goal(client, h, "30000")     # gap is large → not reachable by cuts alone

    r = (await client.get("/api/v1/budget/recommendations", headers=h)).json()
    assert r["on_track"] is False
    assert [t["style"] for t in r["tiers"]] == ["conservative", "balanced", "aggressive"]
    # Difficulty/confidence ladder.
    assert r["tiers"][0]["difficulty"] == "easy" and r["tiers"][0]["confidence"] == "high"
    assert r["tiers"][2]["difficulty"] == "hard"
    # Every change carries the 5 fields; lifestyle shows a daily figure; no essentials touched.
    for t in r["tiers"]:
        for c in t["changes"]:
            assert c["reason"] and c["confidence"] in ("high", "medium", "low")
            assert "monthly_impact" in c
            assert c["protected"] is False
            assert "food" not in c["label"].lower()
    assert any(c["current_daily"] is not None for c in r["tiers"][2]["changes"])   # daily impact shown


async def test_grow_income_and_why_not_when_cuts_fall_short(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "50000")
    await client.patch("/api/v1/users/me/profile", json={
        "life_stage": "pg_student", "food_monthly": "12000", "transport_monthly": "3000",
        "lifestyle_monthly": "8000"}, headers=h)
    await _sub(client, h, "Netflix", "1500")
    await _goal(client, h, "40000")     # gap far exceeds what any cut can free → must grow income

    r = (await client.get("/api/v1/budget/recommendations", headers=h)).json()
    assert r["why_not"] and ("food" in r["why_not"].lower() or "essential" in r["why_not"].lower())
    labels = {g["label"] for g in r["grow_income"]}
    assert any("part-time" in lbl.lower() for lbl in labels)   # student, no part-time income → suggested


async def test_conservative_tier_can_reach_a_small_gap(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "50000")
    await client.patch("/api/v1/users/me/profile",
                       json={"food_monthly": "10000", "lifestyle_monthly": "10000"}, headers=h)
    await _sub(client, h, "Spotify", "2000")
    await _goal(client, h, "30000")     # small gap above the comfortable surplus

    r = (await client.get("/api/v1/budget/recommendations", headers=h)).json()
    assert r["on_track"] is False
    assert r["tiers"][0]["reaches_goal"] is True
    assert "conservative" in r["summary"].lower()


async def test_on_track_needs_no_cuts(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "50000")
    await client.patch("/api/v1/users/me/profile",
                       json={"food_monthly": "10000", "lifestyle_monthly": "10000"}, headers=h)
    await _goal(client, h, "20000")     # within comfortable surplus
    r = (await client.get("/api/v1/budget/recommendations", headers=h)).json()
    assert r["on_track"] is True and r["tiers"] == []
    assert "on track" in r["summary"].lower()


async def test_essentials_protected_unless_aggressive_and_insist(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "5000")
    await client.patch("/api/v1/users/me/profile",
                       json={"food_monthly": "3000", "optimization_style": "aggressive_goal"}, headers=h)
    await _goal(client, h, "2500")      # just beyond the comfortable surplus → cuts are needed

    # Default: food never suggested.
    base = (await client.get("/api/v1/budget/recommendations", headers=h)).json()
    assert all(not c["protected"] for t in base["tiers"] for c in t["changes"])

    # Insist (aggressive-goal): a careful food trim appears, clearly flagged.
    ins = (await client.get("/api/v1/budget/recommendations?insist=true", headers=h)).json()
    food_lines = [c for t in ins["tiers"] for c in t["changes"] if c["protected"]]
    assert food_lines and "food" in food_lines[0]["label"].lower()
    assert "asked" in (ins["essential_protection_note"] or "").lower()


async def test_target_override_via_query(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "50000")
    await client.patch("/api/v1/users/me/profile", json={"food_monthly": "10000"}, headers=h)
    # No saved goal, but ask for a specific target.
    r = (await client.get("/api/v1/budget/recommendations?target=45000", headers=h)).json()
    assert r["target_monthly"] == "45000.0000"
