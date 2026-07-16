"""daily_habit_service: learned "is the ₹200 for travel over?" predictions —
the 2-week gate, weekday/weekend separation, consistency/frequency thresholds,
and never re-asking about something already logged today."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, User, UserSettings
from app.services import daily_habit_service as dhs

pytestmark = pytest.mark.asyncio

# A Wednesday — so "today" is a weekday in every test unless stated otherwise.
WEDNESDAY = date(2026, 6, 17)
SATURDAY = date(2026, 6, 20)


async def _make_user(db: AsyncSession) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db.add(user)
    await db.flush()
    db.add(UserSettings(
        user_id=user.id, base_currency="INR", timezone="UTC",
        starting_balance=Decimal("50000"),
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


async def _seed_weekday_habit(db, uid, category_id, *, today=WEDNESDAY, amount="200", days=28):
    """A consistent commute on every weekday in the window."""
    for i in range(1, days + 1):
        day = today - timedelta(days=i)
        if day.weekday() < 5:
            db.add(_expense(uid, amount, day, category_id))
    await db.commit()


async def test_nothing_predicted_before_two_weeks_of_history(db_session: AsyncSession):
    uid = await _make_user(db_session)
    transport = await _category(db_session, "Transportation")
    for i in range(1, 10):                       # only 9 days of history
        db_session.add(_expense(uid, "200", WEDNESDAY - timedelta(days=i), transport))
    await db_session.commit()

    assert await dhs.predict_today(db_session, uid, today=WEDNESDAY) == []


async def test_a_consistent_weekday_habit_is_predicted_with_its_typical_amount(db_session: AsyncSession):
    uid = await _make_user(db_session)
    transport = await _category(db_session, "Transportation")
    await _seed_weekday_habit(db_session, uid, transport, amount="200")

    out = await dhs.predict_today(db_session, uid, today=WEDNESDAY)
    assert len(out) == 1
    assert out[0]["label"] == "Transportation"
    assert out[0]["amount"] == 200.0
    assert out[0]["day_type"] == "weekday"
    assert out[0]["confidence"] == "high"


async def test_a_weekday_habit_is_not_predicted_on_a_weekend(db_session: AsyncSession):
    """The user called this out explicitly: weekdays and weekends differ, so a
    Mon–Fri commute must not be offered on a Saturday."""
    uid = await _make_user(db_session)
    transport = await _category(db_session, "Transportation")
    await _seed_weekday_habit(db_session, uid, transport, today=SATURDAY)

    assert await dhs.predict_today(db_session, uid, today=SATURDAY) == []


async def test_erratic_amounts_are_not_predicted(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    amounts = ["50", "600", "80", "900", "40", "750", "60", "800", "55", "700",
               "90", "650", "45", "850", "70", "720", "65", "780", "85", "690"]
    i = 0
    for d in range(1, 29):
        day = WEDNESDAY - timedelta(days=d)
        if day.weekday() < 5:
            db_session.add(_expense(uid, amounts[i % len(amounts)], day, food))
            i += 1
    await db_session.commit()

    assert await dhs.predict_today(db_session, uid, today=WEDNESDAY) == []


async def test_an_occasional_expense_is_not_a_habit(db_session: AsyncSession):
    uid = await _make_user(db_session)
    shopping = await _category(db_session, "Shopping")
    # Consistent amount, but only 3 times in 4 weeks — a habit needs frequency.
    for i in (3, 10, 17):
        db_session.add(_expense(uid, "500", WEDNESDAY - timedelta(days=i), shopping))
    db_session.add(_expense(uid, "10", WEDNESDAY - timedelta(days=25), shopping))  # history gate
    await db_session.commit()

    assert await dhs.predict_today(db_session, uid, today=WEDNESDAY) == []


async def test_a_habit_already_logged_today_is_not_re_asked(db_session: AsyncSession):
    uid = await _make_user(db_session)
    transport = await _category(db_session, "Transportation")
    await _seed_weekday_habit(db_session, uid, transport)
    assert len(await dhs.predict_today(db_session, uid, today=WEDNESDAY)) == 1

    db_session.add(_expense(uid, "200", WEDNESDAY, transport))   # user logs it
    await db_session.commit()
    assert await dhs.predict_today(db_session, uid, today=WEDNESDAY) == []


async def test_uncategorized_spending_is_never_predicted(db_session: AsyncSession):
    uid = await _make_user(db_session)
    for i in range(1, 29):
        day = WEDNESDAY - timedelta(days=i)
        if day.weekday() < 5:
            db_session.add(Expense(
                user_id=uid, category_id=None, original_amount=Decimal("200"), original_currency="INR",
                exchange_rate=Decimal("1"), converted_amount=Decimal("200"), base_currency="INR",
                expense_date=day,
            ))
    await db_session.commit()

    assert await dhs.predict_today(db_session, uid, today=WEDNESDAY) == []
