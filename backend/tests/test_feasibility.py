"""Feasibility Engine (Budget Intelligence System — Phase 3).

Survival-first waterfall, success-probability bands (never binary), emergency
buffer before goals, and structural diagnosis. Canonical cases: the Tokyo
₹270k/¥50k goal (Very High) and the ₹5,000 / save ₹2,000 case (clearly low).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "feas@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def _income(client, h, label, source_type, amount):
    await client.post("/api/v1/income-sources", json={
        "label": label, "source_type": source_type, "kind": "recurring",
        "original_amount": amount, "original_currency": "INR", "recurrence_day": 1}, headers=h)


async def _monthly_goal(client, h, name, amount):
    await client.post("/api/v1/savings-goals", json={
        "name": name, "kind": "monthly_target", "original_amount": amount, "original_currency": "INR"}, headers=h)


async def test_tokyo_goal_is_very_high(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "MEXT", "scholarship", "110000")
    await _income(client, h, "Part-time", "part_time", "110000")
    await _income(client, h, "Family", "family_support", "50000")
    await client.patch("/api/v1/users/me/profile", json={
        "life_stage": "pg_student", "current_country": "jp",
        "rent_monthly": "80000", "food_monthly": "30000", "transport_monthly": "15000",
        "lifestyle_monthly": "20000"}, headers=h)
    await _monthly_goal(client, h, "Japan Travel Fund", "50000")

    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    assert f["income_total"] == "270000.0000"
    assert f["essentials_total"] == "125000.0000"        # food+transport+rent
    assert f["goals"][0]["probability_band"] == "very_high"
    assert f["overall_band"] == "very_high"
    assert float(f["comfortable_surplus"]) > 50000        # plenty of room


async def test_five_thousand_save_two_thousand_is_low(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "5000")
    await client.patch("/api/v1/users/me/profile",
                       json={"food_monthly": "3000", "transport_monthly": "900"}, headers=h)
    await _monthly_goal(client, h, "Savings", "2000")

    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    g = f["goals"][0]
    assert g["probability_score"] < 50                    # low or very_low — not "impossible"
    assert g["probability_band"] in ("low", "very_low")
    assert "food" in g["reason"].lower() or "more" in g["reason"].lower()   # explains the gap


async def test_probability_is_a_band_not_binary(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "50000")
    await client.patch("/api/v1/users/me/profile",
                       json={"food_monthly": "12000", "transport_monthly": "3000", "lifestyle_monthly": "8000"}, headers=h)
    await _monthly_goal(client, h, "Goal", "30000")       # needs trimming lifestyle → mid band
    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    assert f["goals"][0]["probability_band"] in ("medium", "low", "high")
    assert 0 <= f["goals"][0]["probability_score"] <= 100


async def test_emergency_buffer_funded_before_goals(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "50000")
    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    labels = [s["label"] for s in f["waterfall"]]
    assert labels.index("Emergency buffer") < labels.index("Goals")
    assert float(f["emergency_buffer"]) > 0               # first-class, non-zero


async def test_structural_housing_flag(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "120000")
    await client.patch("/api/v1/users/me/profile", json={"rent_monthly": "80000"}, headers=h)
    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    housing = next(fl for fl in f["structural_flags"] if fl["kind"] == "housing_ratio")
    assert housing["severity"] == "high"                  # 67% → high
    assert "housing" in housing["message"].lower()


async def test_no_income_asks_for_income(client: AsyncClient):
    h = await _auth(client)
    f = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    assert f["income_total"] == "0.0000"
    assert "income" in f["summary"].lower()


async def test_buffer_scales_with_optimization_style(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "100000")
    await client.patch("/api/v1/users/me/profile", json={"optimization_style": "comfort_first"}, headers=h)
    comfort = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    await client.patch("/api/v1/users/me/profile", json={"optimization_style": "aggressive_goal"}, headers=h)
    aggressive = (await client.get("/api/v1/budget/feasibility", headers=h)).json()
    assert float(comfort["emergency_buffer"]) > float(aggressive["emergency_buffer"])
