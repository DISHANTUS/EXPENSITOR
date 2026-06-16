"""DB + endpoint tests for the Recommendation Engine (C9)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, User

pytestmark = pytest.mark.asyncio

RECS = "/api/v1/recommendations"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed(db: AsyncSession, email: str) -> None:
    uid = await db.scalar(select(User.id).where(User.email == email))
    food = await db.scalar(select(Category.id).where(Category.name == "Food & Dining", Category.is_system.is_(True)))
    d = date.today() - timedelta(days=70)
    while d <= date.today():
        amt = "250" if d.weekday() >= 5 else "120"
        db.add(Expense(user_id=uid, category_id=food, original_amount=Decimal(amt), original_currency="INR",
                       exchange_rate=Decimal("1"), converted_amount=Decimal(amt), base_currency="INR", expense_date=d))
        d += timedelta(days=1)
    await db.commit()


async def test_recommendations_end_to_end(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "rec@e.com")
    await _seed(db_session, "rec@e.com")
    # a behind monthly target -> goal recovery + bundle
    await client.post("/api/v1/savings-goals", json={
        "name": "Monthly savings", "kind": "monthly_target", "original_amount": "50000", "original_currency": "INR"}, headers=h)

    resp = await client.get(RECS, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"recommendations", "bundles", "explanations", "alternatives_applied"} <= set(body)
    assert body["recommendations"]  # seeded spending yields behavioral recommendations
    # every recommendation carries the advisor-ready, life-oriented payload
    r0 = body["recommendations"][0]
    assert {"life_impact", "outcome_preview", "expected_benefit", "effort_level", "urgency"} <= set(r0)
    assert body["bundles"] and "Recovery Plan" in body["bundles"][0]["title"]


async def test_view_and_exclusion_filters(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "recview@e.com")
    await _seed(db_session, "recview@e.com")

    impact_view = (await client.get(f"{RECS}?view=impact", headers=h)).json()["recommendations"]
    scores = [r["impact"] for r in impact_view]
    assert scores == sorted(scores, reverse=True)

    excluded = (await client.get(f"{RECS}?excluded_levers=reduce_food", headers=h)).json()
    assert all(r["lever_key"] != "reduce_food" for r in excluded["recommendations"])


async def test_cold_start_returns_empty_but_well_formed(client: AsyncClient):
    h = await _auth(client, "reccold@e.com")
    body = (await client.get(RECS, headers=h)).json()
    assert body["recommendations"] == [] and body["bundles"] == []
