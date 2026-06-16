"""DB-backed tests for the projection data loaders (balance / spending / income /
planned / scenario). Data is inserted directly via the ORM for full control."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.balance import current_balance
from app.intelligence.projection.income_projection import expand_income_events
from app.intelligence.projection.planned_projection import expand_outflows
from app.intelligence.projection.scenario import MAX_HORIZON_DAYS, build_scenario
from app.intelligence.projection.spending_model import compute_spending_model
from app.models import Expense, Income, IncomeSource, PlannedExpense, User, UserSettings
from app.models.enums import (
    IncomeKind,
    IncomeSourceType,
    PlannedExpensePriority,
    PlannedExpenseStatus,
)

pytestmark = pytest.mark.asyncio


async def _make_user(
    session: AsyncSession,
    *,
    starting: str = "0",
    threshold: str | None = None,
    income_est: str | None = None,
    onboarding: datetime | None = None,
) -> User:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    session.add(user)
    await session.flush()
    settings = UserSettings(
        user_id=user.id,
        base_currency="INR",
        timezone="UTC",
        starting_balance=Decimal(starting),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
        monthly_income_estimate=Decimal(income_est) if income_est is not None else None,
    )
    if onboarding is not None:
        settings.created_at = onboarding
    session.add(settings)
    await session.commit()
    return user


def _expense(user_id, amount, d, *, deleted=False) -> Expense:
    e = Expense(
        user_id=user_id, original_amount=Decimal(amount), original_currency="INR",
        exchange_rate=Decimal("1"), converted_amount=Decimal(amount), base_currency="INR", expense_date=d,
    )
    if deleted:
        e.deleted_at = datetime.now(timezone.utc)
    return e


def _income(user_id, amount, d, *, deleted=False) -> Income:
    i = Income(
        user_id=user_id, source_type=IncomeSourceType.salary, original_amount=Decimal(amount),
        original_currency="INR", exchange_rate=Decimal("1"), converted_amount=Decimal(amount),
        base_currency="INR", received_date=d,
    )
    if deleted:
        i.deleted_at = datetime.now(timezone.utc)
    return i


def _source(user_id, amount, *, kind, day=None, expected=None, rel="0.9", active=True, deleted=False) -> IncomeSource:
    s = IncomeSource(
        user_id=user_id, label="src", source_type=IncomeSourceType.salary, kind=kind,
        original_amount=Decimal(amount), original_currency="INR", exchange_rate=Decimal("1"),
        converted_amount=Decimal(amount), base_currency="INR", recurrence_day=day, expected_date=expected,
        reliability=Decimal(rel), is_active=active,
    )
    if deleted:
        s.deleted_at = datetime.now(timezone.utc)
    return s


def _planned(user_id, amount, d, *, status=PlannedExpenseStatus.planned, deleted=False) -> PlannedExpense:
    p = PlannedExpense(
        user_id=user_id, title="plan", planned_date=d, original_amount=Decimal(amount),
        original_currency="INR", exchange_rate=Decimal("1"), converted_amount=Decimal(amount),
        base_currency="INR", priority=PlannedExpensePriority.medium, status=status,
    )
    if deleted:
        p.deleted_at = datetime.now(timezone.utc)
    return p


# --- balance ---------------------------------------------------------------

async def test_current_balance_cutoff_and_softdelete(db_session: AsyncSession):
    user = await _make_user(db_session, starting="1000", onboarding=datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.add_all([
        _income(user.id, "500", date(2026, 2, 1)),      # post-onboarding -> counts
        _income(user.id, "999", date(2025, 12, 1)),     # pre-onboarding -> excluded
        _expense(user.id, "200", date(2026, 2, 5)),      # post -> counts
        _expense(user.id, "888", date(2025, 11, 1)),     # pre -> excluded
        _expense(user.id, "50", date(2026, 2, 10), deleted=True),  # soft-deleted -> excluded
    ])
    await db_session.commit()

    b = await current_balance(db_session, user.id, date(2026, 6, 1))
    assert b.onboarding_date == date(2026, 1, 1)
    assert b.total_income == Decimal("500")
    assert b.total_expense == Decimal("200")
    assert b.current_balance == Decimal("1300")


# --- spending model --------------------------------------------------------

async def test_spending_model_basic(db_session: AsyncSession):
    user = await _make_user(db_session, onboarding=datetime(2025, 1, 1, tzinfo=timezone.utc))
    db_session.add_all([
        _expense(user.id, "100", date(2026, 6, 1)),
        _expense(user.id, "200", date(2026, 6, 2)),
        _expense(user.id, "30", date(2026, 6, 2), deleted=True),  # excluded
    ])
    await db_session.commit()

    model = await compute_spending_model(db_session, user.id, date(2026, 6, 30))
    # earliest 06-01 -> observed_days = 30; total 300 -> mu = 10
    assert model.observed_days == 30
    assert model.mu == Decimal("10")


async def test_spending_model_cold_start(db_session: AsyncSession):
    user = await _make_user(db_session, threshold="3000")
    model = await compute_spending_model(
        db_session, user.id, date(2026, 6, 30), monthly_threshold=Decimal("3000")
    )
    assert model.confidence == "low"
    assert model.observed_days == 0
    assert model.mu == Decimal("100")  # 3000 / 30


# --- income expansion ------------------------------------------------------

async def test_income_recurring_future_only(db_session: AsyncSession):
    user = await _make_user(db_session)
    db_session.add(_source(user.id, "5000", kind=IncomeKind.recurring, day=15))
    await db_session.commit()
    events = await expand_income_events(db_session, user.id, date(2026, 6, 10), date(2026, 8, 31))
    assert [e.date for e in events] == [date(2026, 6, 15), date(2026, 7, 15), date(2026, 8, 15)]


async def test_income_recurring_day31_clamps(db_session: AsyncSession):
    user = await _make_user(db_session)
    db_session.add(_source(user.id, "5000", kind=IncomeKind.recurring, day=31))
    await db_session.commit()
    events = await expand_income_events(db_session, user.id, date(2026, 1, 5), date(2026, 4, 30))
    assert [e.date for e in events] == [
        date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)
    ]


async def test_income_one_time_and_exclusions(db_session: AsyncSession):
    user = await _make_user(db_session)
    db_session.add_all([
        _source(user.id, "300", kind=IncomeKind.one_time, expected=date(2026, 7, 1)),     # future -> in
        _source(user.id, "300", kind=IncomeKind.one_time, expected=date(2026, 5, 1)),     # past -> out
        _source(user.id, "5000", kind=IncomeKind.recurring, day=15, active=False),         # inactive -> out
        _source(user.id, "5000", kind=IncomeKind.recurring, day=15, deleted=True),         # deleted -> out
    ])
    await db_session.commit()
    events = await expand_income_events(db_session, user.id, date(2026, 6, 10), date(2026, 12, 31))
    assert len(events) == 1 and events[0].date == date(2026, 7, 1)


# --- planned outflows ------------------------------------------------------

async def test_planned_outflows_overdue_and_filters(db_session: AsyncSession):
    user = await _make_user(db_session)
    today = date(2026, 6, 10)
    db_session.add_all([
        _planned(user.id, "1500", date(2026, 6, 20)),                              # future
        _planned(user.id, "800", date(2026, 6, 1)),                                # overdue
        _planned(user.id, "999", date(2026, 7, 1), status=PlannedExpenseStatus.completed),  # excluded
        _planned(user.id, "999", date(2026, 7, 5), deleted=True),                  # excluded
        _planned(user.id, "999", date(2027, 6, 1)),                                # beyond horizon
    ])
    await db_session.commit()
    events = await expand_outflows(db_session, user.id, today, date(2026, 12, 31))
    assert len(events) == 2
    overdue = next(e for e in events if e.overdue)
    assert overdue.date == today and overdue.days_overdue == 9 and overdue.amount_base == Decimal("800")


# --- scenario integration --------------------------------------------------

async def test_build_scenario_integration_and_horizon_clamp(db_session: AsyncSession):
    user = await _make_user(db_session, starting="1000", onboarding=datetime(2026, 1, 1, tzinfo=timezone.utc))
    db_session.add_all([
        _income(user.id, "5000", date(2026, 2, 1)),
        _expense(user.id, "300", date(2026, 6, 1)),
        _source(user.id, "5000", kind=IncomeKind.recurring, day=1),
        _planned(user.id, "1500", date(2026, 9, 24)),
    ])
    await db_session.commit()

    today = date(2026, 6, 1)
    scenario = await build_scenario(db_session, user.id, today=today, horizon=today + timedelta(days=1000))
    # current_balance = 1000 + 5000 - 300
    assert scenario.current_balance == Decimal("5700")
    assert scenario.horizon == today + timedelta(days=MAX_HORIZON_DAYS)  # clamped
    assert len(scenario.income_events) >= 1
    assert len(scenario.outflows) == 1
    assert scenario.base_currency == "INR"
