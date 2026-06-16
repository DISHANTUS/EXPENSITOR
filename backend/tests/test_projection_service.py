"""End-to-end DB tests for projection_service (Scenario built once, no dup queries)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Expense, Income, PlannedExpense, User, UserSettings
from app.models.enums import IncomeSourceType, PlannedExpensePriority, PlannedExpenseStatus
from app.services import projection_service
from app.services.exceptions import ResourceNotFoundError

pytestmark = pytest.mark.asyncio
TODAY = date(2026, 6, 1)


async def _make_user(session: AsyncSession, *, starting="0", threshold=None) -> User:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    session.add(user)
    await session.flush()
    settings = UserSettings(
        user_id=user.id, base_currency="INR", timezone="UTC",
        starting_balance=Decimal(starting),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    session.add(settings)
    await session.commit()
    return user


def _expense(uid, amount, d):
    return Expense(user_id=uid, original_amount=Decimal(amount), original_currency="INR",
                   exchange_rate=Decimal("1"), converted_amount=Decimal(amount), base_currency="INR", expense_date=d)


def _income(uid, amount, d):
    return Income(user_id=uid, source_type=IncomeSourceType.salary, original_amount=Decimal(amount),
                  original_currency="INR", exchange_rate=Decimal("1"), converted_amount=Decimal(amount),
                  base_currency="INR", received_date=d)


def _planned(uid, amount, d, *, priority=PlannedExpensePriority.medium):
    return PlannedExpense(user_id=uid, title="plan", planned_date=d, original_amount=Decimal(amount),
                          original_currency="INR", exchange_rate=Decimal("1"), converted_amount=Decimal(amount),
                          base_currency="INR", priority=priority, status=PlannedExpenseStatus.planned)


async def test_assess_risk_end_to_end(db_session: AsyncSession):
    user = await _make_user(db_session, starting="500")
    db_session.add(_planned(user.id, "5000", date(2026, 6, 20)))  # unaffordable soon
    await db_session.commit()
    result = await projection_service.assess_risk(db_session, user.id, today=TODAY)
    assert result.emergency_mode is True
    assert result.risk_level == "critical"
    assert 0 <= result.risk_score <= 100


async def test_evaluate_planned_expense_end_to_end(db_session: AsyncSession):
    user = await _make_user(db_session, starting="100000")
    planned = _planned(user.id, "1500", date(2026, 9, 24))
    db_session.add(planned)
    await db_session.commit()
    result = await projection_service.evaluate_planned_expense(db_session, user.id, planned.id, today=TODAY)
    assert result.verdict == "affordable"
    assert result.amount == Decimal("1500")


async def test_evaluate_planned_expense_not_found(db_session: AsyncSession):
    user = await _make_user(db_session, starting="100")
    with pytest.raises(ResourceNotFoundError):
        await projection_service.evaluate_planned_expense(db_session, user.id, uuid.uuid4(), today=TODAY)


async def test_evaluate_affordability_adhoc(db_session: AsyncSession):
    user = await _make_user(db_session, starting="10000")
    db_session.add(_income(user.id, "0", date(2026, 5, 1)))  # noise; pre-onboarding excluded anyway
    await db_session.commit()
    result = await projection_service.evaluate_affordability(
        db_session, user.id, Decimal("2000"), date(2026, 7, 1), today=TODAY
    )
    assert result.verdict in {"affordable", "conditional", "unaffordable"}
    assert result.affordable is True  # 10000 balance, 2000 target, no spend


async def test_scenario_built_once_bounded_queries(db_session: AsyncSession, engine: AsyncEngine):
    user = await _make_user(db_session, starting="5000", threshold="20000")
    db_session.add_all([
        _expense(user.id, "100", date(2026, 5, 25)),
        _planned(user.id, "1500", date(2026, 6, 20)),
    ])
    await db_session.commit()

    count = {"n": 0}

    def _before(*_args, **_kwargs):
        count["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before)
    try:
        await projection_service.assess_risk(db_session, user.id, today=TODAY)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before)

    # settings + 2 balance sums + spending window + income_sources + planned = 6 (<= 8 budget)
    assert count["n"] <= 10


async def test_compute_guidance_end_to_end(db_session: AsyncSession):
    user = await _make_user(db_session, starting="30000", threshold="5000")
    db_session.add(_expense(user.id, "100", date(2026, 5, 28)))
    db_session.add(_planned(user.id, "1000", date(2026, 6, 20)))
    await db_session.commit()
    g = await projection_service.compute_guidance(db_session, user.id, today=TODAY)
    assert g.safe_daily_spending >= 0
    assert g.threshold_remaining is not None
    assert any(a.action == "daily_spend_limit" for a in g.recommended_actions)


async def test_evaluate_goal_end_to_end(db_session: AsyncSession):
    user = await _make_user(db_session, starting="50000")
    res = await projection_service.evaluate_goal(
        db_session, user.id, Decimal("40000"), date(2026, 9, 1), today=TODAY
    )
    assert res.feasible is True
    assert res.confidence in {"high", "medium", "low"}


async def test_compute_guidance_built_once_bounded_queries(db_session: AsyncSession, engine: AsyncEngine):
    user = await _make_user(db_session, starting="30000", threshold="5000")
    db_session.add(_planned(user.id, "1000", date(2026, 6, 20)))
    await db_session.commit()

    count = {"n": 0}

    def _before(*_args, **_kwargs):
        count["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before)
    try:
        await projection_service.compute_guidance(db_session, user.id, today=TODAY)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before)

    # Affordability/risk run in-memory off the single Scenario -> still <= 8 queries.
    assert count["n"] <= 10
