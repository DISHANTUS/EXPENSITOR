"""Endpoint/DB tests for the Proactive Advisor (feed + reviews)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

TOMORROW = date.today() + timedelta(days=1)


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_cold_start_feed_is_empty(client: AsyncClient):
    h = await _auth(client, "pa1@e.com")
    res = (await client.get("/api/v1/advisor/proactive", headers=h)).json()
    assert res["items"] == [] and res["most_important"] is None


async def test_cold_start_review_is_honest(client: AsyncClient):
    h = await _auth(client, "pa2@e.com")
    res = (await client.get("/api/v1/advisor/review?period=weekly", headers=h)).json()
    assert res["kind"] == "review" and "enough activity" in res["what_happened"]


async def test_feed_surfaces_imminent_income(client: AsyncClient):
    h = await _auth(client, "pa3@e.com")
    await client.post("/api/v1/expenses", json={
        "original_amount": "200", "original_currency": "INR", "expense_date": date.today().isoformat()}, headers=h)
    await client.post("/api/v1/receivables", json={
        "title": "Loan", "source_name": "Rahul", "source_type": "friend", "kind": "one_time",
        "original_amount": "15000", "original_currency": "INR", "expected_date": TOMORROW.isoformat()}, headers=h)
    res = (await client.get("/api/v1/advisor/proactive", headers=h)).json()
    assert res["items"], "expected at least the income reminder"
    assert any(i["category"] == "income" and i["kind"] == "reminder" for i in res["items"])
    for i in res["items"]:   # R5 contract on every item
        assert {"kind", "priority", "eligible_for_notification", "expires_at", "trigger_reason", "evidence"} <= set(i)
        assert i["what_happened"] and i["why_it_matters"] and i["what_next"]   # R1 stands alone


async def test_review_endpoint_runs(client: AsyncClient):
    h = await _auth(client, "pa4@e.com")
    await client.post("/api/v1/expenses", json={
        "original_amount": "200", "original_currency": "INR", "expense_date": date.today().isoformat()}, headers=h)
    res = (await client.get("/api/v1/advisor/review?period=monthly", headers=h)).json()
    assert res["kind"] == "review" and "Suggested focus" in res["what_next"]
