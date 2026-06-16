"""C7b integration: feedback → repersonalized recommendations; policy → C9/C7a.

Critical guard: policy changes ORDERING only — never any financial fact and
never an auto-applied plan/goal/expense change."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, User, UserSettings
from app.services import decision_service, preference_service as ps

pytestmark = pytest.mark.asyncio

RECS = "/api/v1/recommendations"
PREFS = "/api/v1/preferences"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _seed(db: AsyncSession, email: str) -> uuid.UUID:
    uid = await db.scalar(select(User.id).where(User.email == email))
    food = await db.scalar(select(Category.id).where(Category.name == "Food & Dining", Category.is_system.is_(True)))
    d = date.today() - timedelta(days=70)
    while d <= date.today():
        amt = "250" if d.weekday() >= 5 else "120"
        db.add(Expense(user_id=uid, category_id=food, original_amount=Decimal(amt), original_currency="INR",
                       exchange_rate=Decimal("1"), converted_amount=Decimal(amt), base_currency="INR", expense_date=d))
        d += timedelta(days=1)
    await db.commit()
    return uid


async def test_three_rejects_strongly_exclude_lever(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "pref1@e.com")
    await _seed(db_session, "pref1@e.com")
    rid = "spending_reduction:reduce_food"
    last = None
    for _ in range(3):
        last = (await client.post(f"{RECS}/feedback", json={
            "recommendation_id": rid, "action": "rejected", "reason": "dislike_approach"}, headers=h)).json()
    assert "reduce_food" not in {r["lever_key"] for r in last["recommendations"]}
    assert "reduce_food" in last["policy_influence"]["excluded_by_policy"]


async def test_patch_preferences_excludes_and_is_visible(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "pref2@e.com")
    await _seed(db_session, "pref2@e.com")
    patched = (await client.patch(PREFS, json={"excluded_levers": ["reduce_food"]}, headers=h)).json()
    assert "reduce_food" in patched["policy"]["explicit_excluded"]

    recs = (await client.get(RECS, headers=h)).json()
    assert "reduce_food" not in {r["lever_key"] for r in recs["recommendations"]}
    assert "reduce_food" in recs["policy_influence"]["excluded_by_policy"]


async def test_feedback_never_mutates_finances(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "pref3@e.com")
    uid = await _seed(db_session, "pref3@e.com")
    before = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    await client.post(f"{RECS}/feedback", json={
        "recommendation_id": "spending_reduction:reduce_food", "action": "rejected"}, headers=h)
    after = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    assert before == after  # facts/plans untouched — policy affects ordering only


async def test_policy_excludes_decision_strategy(db_session: AsyncSession):
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    db_session.add(UserSettings(user_id=user.id, base_currency="INR", timezone="UTC",
                                starting_balance=Decimal("100000"), monthly_threshold=Decimal("30000"),
                                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    await db_session.commit()

    today = date(2026, 6, 1)
    before = await decision_service.quote(db_session, user.id, item_label="x", original_amount=Decimal("5000"),
                                          original_currency="INR", today=today)
    assert "use_savings" in {s["strategy_kind"] for s in before["result"]["strategies"]}

    await ps.update_policy(db_session, user.id, excluded_levers=["use_savings"])
    after = await decision_service.quote(db_session, user.id, item_label="x", original_amount=Decimal("5000"),
                                         original_currency="INR", today=today)
    assert "use_savings" not in {s["strategy_kind"] for s in after["result"]["strategies"]}
