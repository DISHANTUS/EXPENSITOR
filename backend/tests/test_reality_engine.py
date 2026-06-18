"""Reality Engine (Budget Intelligence System — Phase 2).

Income broken out by source + the 4-bucket taxonomy, with survival (essentials)
surfaced before savings. Covers the Tokyo multi-income case and the ₹5,000
survival-before-savings example.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "reality@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def _income(client, h, label, source_type, amount):
    await client.post("/api/v1/income-sources", json={
        "label": label, "source_type": source_type, "kind": "recurring",
        "original_amount": amount, "original_currency": "INR", "recurrence_day": 1}, headers=h)


async def _recurring(client, h, label, rule_type, amount):
    await client.post("/api/v1/recurring-rules", json={
        "rule_type": rule_type, "label": label, "original_amount": amount,
        "original_currency": "INR", "recurrence_day": 5, "start_date": "2026-01-01"}, headers=h)


async def test_multi_income_broken_out_by_source(client: AsyncClient):
    h = await _auth(client)
    await _income(client, h, "MEXT Scholarship", "scholarship", "110000")
    await _income(client, h, "Part-time job", "part_time", "110000")
    await _income(client, h, "Family support", "family_support", "50000")

    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    types = {s["source_type"] for s in r["income_sources"]}
    assert types == {"scholarship", "part_time", "family_support"}        # sources matter
    assert len(r["income_sources"]) == 3
    assert r["income_total"] == "270000.0000"


async def test_buckets_classify_profile_and_recurring(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile", json={
        "life_stage": "pg_student", "rent_monthly": "80000", "food_situation": "mostly_outside",
        "food_monthly": "35000", "transport_monthly": "10000", "lifestyle_monthly": "15000"}, headers=h)
    await _recurring(client, h, "Netflix", "subscription", "1500")   # adjustable
    await _recurring(client, h, "Electricity", "bill", "4000")       # protected (utility)
    await _recurring(client, h, "Health insurance", "insurance", "3000")  # committed

    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    # Protected = food + transport + electricity + rent (housing is protected, cut last)
    assert r["protected"]["total"] == "129000.0000"
    # Committed = insurance only (rent is now protected housing)
    assert r["committed"]["total"] == "3000.0000"
    # Adjustable = lifestyle + netflix
    assert r["adjustable"]["total"] == "16500.0000"
    # Essentials = protected + committed (unchanged total)
    assert r["essentials_total"] == "132000.0000"
    # Housing is surfaced separately (a different problem from food).
    assert r["housing_total"] == "80000.0000"


async def test_survival_before_savings_example(client: AsyncClient):
    """Income ₹5,000; food ₹3,000; transport ₹900; subscription ₹200 →
    essentials ₹3,900, ₹1,100 left (so a ₹2,000 goal is clearly short)."""
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "5000")
    await client.patch("/api/v1/users/me/profile", json={
        "food_situation": "mostly_outside", "food_monthly": "3000", "transport_monthly": "900"}, headers=h)
    await _recurring(client, h, "Subscription", "subscription", "200")

    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    assert r["income_total"] == "5000.0000"
    assert r["essentials_total"] == "3900.0000"           # food + transport
    assert r["available_after_essentials"] == "1100.0000"
    assert r["adjustable"]["total"] == "200.0000"


async def test_food_daily_is_annualised_to_month(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile",
                       json={"food_situation": "mostly_outside", "food_daily": "100"}, headers=h)
    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    food = next(ln for ln in r["protected"]["lines"] if "Food" in ln["label"])
    # 100/day × days-in-month (28..31)
    assert 2800.0 <= float(food["monthly"]) <= 3100.0


async def test_food_only_essential_when_mostly_outside(client: AsyncClient):
    """Food style is lifestyle, not a daily budget: a mixed/home eater's onboarding
    food amount must NOT inflate Essential Living — only a 'mostly outside' eater's
    does (real food spend is learned from logged expenses)."""
    h = await _auth(client)
    await _income(client, h, "Salary", "salary", "50000")
    # A mixed eater who happened to type an amount → food is NOT a protected essential.
    await client.patch("/api/v1/users/me/profile",
                       json={"food_situation": "mix", "food_daily": "200"}, headers=h)
    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    assert not any("Food" in ln["label"] for ln in r["protected"]["lines"])

    # The same amount under "mostly outside" → now it counts.
    await client.patch("/api/v1/users/me/profile",
                       json={"food_situation": "mostly_outside", "food_daily": "200"}, headers=h)
    r2 = (await client.get("/api/v1/budget/reality", headers=h)).json()
    assert any("Food" in ln["label"] for ln in r2["protected"]["lines"])


async def test_optimization_style_surfaced(client: AsyncClient):
    h = await _auth(client)
    await client.patch("/api/v1/users/me/profile", json={"optimization_style": "comfort_first"}, headers=h)
    r = (await client.get("/api/v1/budget/reality", headers=h)).json()
    assert r["optimization_style"] == "comfort_first"
