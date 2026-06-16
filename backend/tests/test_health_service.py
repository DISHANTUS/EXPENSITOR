"""Endpoint/DB tests for C8 + its Commentary / Recommendation integration."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed_spend(client, h):
    cat = (await client.get("/api/v1/categories", headers=h)).json()
    food = next(c["id"] for c in (cat["items"] if isinstance(cat, dict) else cat) if c["name"] == "Food & Dining")
    base = date.today()
    for i in range(60):
        d = base - timedelta(days=i)
        await client.post("/api/v1/expenses", json={
            "original_amount": "150" if d.weekday() >= 5 else "90", "original_currency": "INR",
            "expense_date": d.isoformat(), "category_id": food}, headers=h)


async def test_financial_health_endpoint_decomposed(client: AsyncClient):
    h = await _auth(client, "fh1@e.com")
    res = (await client.get("/api/v1/financial-health", headers=h)).json()
    assert "overall_score" in res and len(res["pillars"]) == 6
    assert {"top_strengths", "top_weaknesses", "biggest_contributor", "biggest_drag",
            "contributor_index"} <= set(res)
    for p in res["pillars"]:
        assert {"score", "confidence", "state", "contributors",
                "warning_eligible", "achievement_eligible", "reminder_eligible"} <= set(p)


async def test_cold_start_health_is_neutral(client: AsyncClient):
    h = await _auth(client, "fh2@e.com")
    res = (await client.get("/api/v1/financial-health", headers=h)).json()
    assert res["overall_score"] == 50 and res["overall_confidence"] == "low"


async def test_commentary_includes_health_block(client: AsyncClient):
    h = await _auth(client, "fh3@e.com")
    env = (await client.get("/api/v1/commentary?surface=daily", headers=h)).json()
    det = env["deterministic_commentary"]
    assert "health" in det and det["health"] is not None and "overall_score" in det["health"]
    # facts still lead — the score is an attached summary, not a paragraph takeover
    assert det["paragraphs"]


async def test_recommendations_expose_health_contributors(client: AsyncClient):
    h = await _auth(client, "fh4@e.com")
    res = (await client.get("/api/v1/recommendations", headers=h)).json()
    assert "health" in res and "contributor_index" in res["health"] and "pillars" in res["health"]
