"""Companion Evolution / Reflection Engine (Sprint 8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "evo@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_evolution_always_reflects_days_with_advary(client: AsyncClient):
    h = await _auth(client)
    body = (await client.get("/api/v1/companion/evolution", headers=h)).json()
    assert body["days_with_advary"] >= 1
    # The first reflection is always the relationship-length observation.
    assert body["reflections"]
    assert "been with Advary" in body["reflections"][0]["text"]
    assert isinstance(body["milestones"], list)


async def test_evolution_surfaces_goals_and_milestones(client: AsyncClient):
    h = await _auth(client, email="evo2@example.com")
    await client.post("/api/v1/incomes", json={
        "source_type": "salary", "original_amount": "40000", "original_currency": "INR",
        "received_date": "2026-05-01"}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "monthly_target",
        "original_amount": "2000", "original_currency": "INR"}, headers=h)
    await client.patch("/api/v1/users/me/profile", json={
        "moving_country": True, "future_country": "jp", "future_move_year": 2028}, headers=h)

    body = (await client.get("/api/v1/companion/evolution", headers=h)).json()
    labels = " ".join(m["label"] for m in body["milestones"]).lower()
    tenses = {m["tense"] for m in body["milestones"]}
    assert "move to japan" in labels          # future milestone awareness
    assert "future" in tenses


async def test_monthly_reflection_empty_then_label(client: AsyncClient):
    h = await _auth(client, email="evo3@example.com")
    # A month with no activity → not available, but still labelled.
    body = (await client.get("/api/v1/companion/monthly-reflection",
                             params={"year": 2030, "month": 3}, headers=h)).json()
    assert body["month_label"] == "March 2030"
    assert body["available"] is False


async def test_monthly_reflection_populated(client: AsyncClient):
    h = await _auth(client, email="evo4@example.com")
    # A generous budget so a small spend lands "within"/"saved".
    await client.patch("/api/v1/users/me/settings", json={"monthly_threshold": "30000"}, headers=h)
    await client.post("/api/v1/expenses", json={
        "original_amount": "100", "original_currency": "INR", "expense_date": "2026-04-10"}, headers=h)

    body = (await client.get("/api/v1/companion/monthly-reflection",
                             params={"year": 2026, "month": 4}, headers=h)).json()
    assert body["month_label"] == "April 2026"
    assert body["available"] is True
    assert body["within_budget_days"] >= 1
    assert "within budget" in body["headline"]
