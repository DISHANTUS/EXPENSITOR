"""daily_brief's today_snapshot extension: actual today-spend by category,
distinct from the forward-looking daily_remaining allowance already covered
elsewhere — and that it opportunistically runs spending-shift detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models import Category

pytestmark = pytest.mark.asyncio

BRIEF = "/api/v1/advisor/brief"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def _category_id(db_session, name: str) -> str:
    return str(await db_session.scalar(select(Category.id).where(Category.name == name, Category.is_system.is_(True))))


async def test_today_snapshot_reflects_actual_spend_not_the_forward_allowance(
    client: AsyncClient, db_session
) -> None:
    h = await _auth(client, "snap1@example.com")
    food = await _category_id(db_session, "Food & Dining")
    today = _today()

    await client.post("/api/v1/expenses", json={
        "original_amount": "150", "original_currency": "INR",
        "expense_date": today.isoformat(), "category_id": food,
    }, headers=h)
    await client.post("/api/v1/expenses", json={
        "original_amount": "50", "original_currency": "INR",
        "expense_date": today.isoformat(), "category_id": food,
    }, headers=h)

    res = await client.get(BRIEF, headers=h)
    assert res.status_code == 200
    body = res.json()
    assert "today_snapshot" in body
    snap = body["today_snapshot"]
    assert snap["spent_today"] == 200.0
    assert snap["spent_today_by_category"][0]["label"] == "Food & Dining"
    assert snap["spent_today_by_category"][0]["amount"] == 200.0


async def test_brief_reports_how_many_spending_shifts_it_detected(client: AsyncClient, db_session) -> None:
    h = await _auth(client, "snap2@example.com")
    today = _today()
    food = await _category_id(db_session, "Food & Dining")

    # Not enough history yet -> zero shifts, no crash.
    await client.post("/api/v1/expenses", json={
        "original_amount": "100", "original_currency": "INR",
        "expense_date": today.isoformat(), "category_id": food,
    }, headers=h)
    res = await client.get(BRIEF, headers=h)
    assert res.status_code == 200
    assert res.json()["spending_shifts_detected"] == 0
