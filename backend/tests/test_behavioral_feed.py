"""DB + endpoint tests for the Companion behavioral feed (B2)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, User

pytestmark = pytest.mark.asyncio

REFRESH = "/api/v1/companion/behavioral-refresh"
FEED = "/api/v1/companion/feed"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed_spending(db: AsyncSession, email: str) -> None:
    uid = await db.scalar(select(User.id).where(User.email == email))
    food = await db.scalar(select(Category.id).where(Category.name == "Food & Dining", Category.is_system.is_(True)))
    today = date.today()
    d = today - timedelta(days=70)
    while d <= today:
        amt = "200" if d.weekday() >= 5 else "100"  # heavy weekend skew -> a clear weakness
        db.add(Expense(user_id=uid, category_id=food, original_amount=Decimal(amt), original_currency="INR",
                       exchange_rate=Decimal("1"), converted_amount=Decimal(amt), base_currency="INR", expense_date=d))
        d += timedelta(days=1)
    await db.commit()


async def test_behavioral_refresh_creates_feed(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "bfeed@e.com")
    await _seed_spending(db_session, "bfeed@e.com")

    resp = await client.post(REFRESH, headers=h)
    assert resp.status_code == 200, resp.text
    insights = resp.json()
    assert insights and all(i["type"].startswith("behavior.") for i in insights)
    # actionable payload rides in facts
    assert all({"finding", "impact", "recommendation", "consequences"} <= set(i["facts"]) for i in insights)

    feed = (await client.get(FEED, headers=h)).json()
    assert any(i["type"].startswith("behavior.") for i in feed["items"])


async def test_refresh_supersedes_and_does_not_flood(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "bflood@e.com")
    await _seed_spending(db_session, "bflood@e.com")

    first = (await client.post(REFRESH, headers=h)).json()
    second = (await client.post(REFRESH, headers=h)).json()
    assert len(first) == len(second)  # stable snapshot

    feed = (await client.get(FEED, headers=h)).json()
    active_behavior = [i for i in feed["items"] if i["type"].startswith("behavior.")]
    assert len(active_behavior) == len(second)  # prior snapshot superseded, no accumulation


async def test_cold_start_user_gets_no_behavioral_insights(client: AsyncClient):
    h = await _auth(client, "bcold@e.com")
    resp = await client.post(REFRESH, headers=h)
    assert resp.status_code == 200 and resp.json() == []
