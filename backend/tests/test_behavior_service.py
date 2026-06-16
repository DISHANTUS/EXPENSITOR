"""DB-backed test for behavior_service.build_profile (real queries, seeded DB)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, Income, User, UserSettings
from app.models.enums import IncomeSourceType
from app.services import behavior_service

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 6, 15)


async def _make_user(db: AsyncSession) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db.add(user)
    await db.flush()
    db.add(UserSettings(
        user_id=user.id, base_currency="INR", timezone="UTC",
        starting_balance=Decimal("50000"), monthly_threshold=Decimal("12000"),
        monthly_income_estimate=Decimal("10000"),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    await db.commit()
    return user.id


async def _category(db: AsyncSession, name: str) -> uuid.UUID:
    return await db.scalar(select(Category.id).where(Category.name == name, Category.is_system.is_(True)))


def _expense(uid: uuid.UUID, amount: str, on: date, category_id: uuid.UUID) -> Expense:
    return Expense(
        user_id=uid, category_id=category_id, original_amount=Decimal(amount), original_currency="INR",
        exchange_rate=Decimal("1"), converted_amount=Decimal(amount), base_currency="INR", expense_date=on,
    )


def _income(uid: uuid.UUID, amount: str, on: date) -> Income:
    return Income(
        user_id=uid, source_type=IncomeSourceType.salary, original_amount=Decimal(amount), original_currency="INR",
        exchange_rate=Decimal("1"), converted_amount=Decimal(amount), base_currency="INR", received_date=on,
    )


async def test_build_profile_end_to_end(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    rent = await _category(db_session, "Rent & Housing")

    # 70 days of daily spend (weekend heavier) + monthly rent + monthly salary.
    d = TODAY - timedelta(days=70)
    while d <= TODAY:
        db_session.add(_expense(uid, "150" if d.weekday() >= 5 else "100", d, food))
        d += timedelta(days=1)
    for (y, m) in [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]:
        db_session.add(_expense(uid, "5000", date(y, m, 5), rent))
        db_session.add(_income(uid, "10000", date(y, m, 1)))
    await db_session.commit()

    profile = await behavior_service.build_profile(db_session, uid, today=TODAY)

    assert len(profile.metrics) == 16
    assert 0 <= profile.composite_score <= 100
    assert profile.confidence in {"low", "normal"}
    # weekend metric has plenty of rows -> normal confidence, real value
    weekend = profile.metric("weekend_overspending")
    assert weekend is not None and weekend.confidence == "normal" and weekend.value is not None

    facts = profile.to_facts()
    assert facts["schema_version"] == 1 and len(facts["metrics"]) == 16
    assert profile.base_currency == "INR"


async def test_build_profile_new_user_is_cold_start(db_session: AsyncSession):
    uid = await _make_user(db_session)
    profile = await behavior_service.build_profile(db_session, uid, today=TODAY)
    assert len(profile.metrics) == 16
    assert profile.composite_score == 50
    assert profile.confidence == "low"
