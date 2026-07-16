"""spending_pattern_service: rolling per-category baselines, sustained-shift
detection, and its wiring into the 4b-5a advice_memory loop (real DB queries,
matching test_behavior_service.py's style)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdviceMemory, Category, Expense, User, UserSettings
from app.models.enums import AdviceKind, AdviceStatus
from app.services import advice_memory_service as ams
from app.services import spending_pattern_service as sps

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


async def test_has_min_history_gates_on_earliest_expense_date(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")

    assert await sps.has_min_history(db_session, uid, TODAY) is False

    db_session.add(_expense(uid, "100", TODAY - timedelta(days=13), food))
    await db_session.commit()
    assert await sps.has_min_history(db_session, uid, TODAY) is False  # 13 days, still short

    db_session.add(_expense(uid, "100", TODAY - timedelta(days=14), food))
    await db_session.commit()
    assert await sps.has_min_history(db_session, uid, TODAY) is True


async def test_no_shift_recorded_when_spending_is_flat(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    # ~100/day, flat, for the full 21-day window (baseline + recent).
    for i in range(21):
        db_session.add(_expense(uid, "100", TODAY - timedelta(days=i), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert created == []


async def test_sustained_increase_is_detected_and_recorded_as_advice(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    # Baseline: days -21..-8 at 100/day. Recent: days -6..0 (7 days) at 200/day.
    for i in range(8, 22):
        db_session.add(_expense(uid, "100", TODAY - timedelta(days=i), food))
    for i in range(0, 7):
        db_session.add(_expense(uid, "200", TODAY - timedelta(days=i), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY, base_currency="INR")
    assert len(created) == 1
    row = created[0]
    assert row.kind == AdviceKind.spending_shift.value
    assert row.subject_type == "category"
    assert row.subject_label == "Food & Dining"
    assert row.category_id == food
    assert row.status == AdviceStatus.pending.value
    assert row.follow_up_due == TODAY  # due immediately, not the generic 30-day category cadence
    assert "higher" in row.claim


async def test_sustained_decrease_is_also_detected(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    for i in range(8, 22):
        db_session.add(_expense(uid, "200", TODAY - timedelta(days=i), food))
    for i in range(0, 7):
        db_session.add(_expense(uid, "50", TODAY - timedelta(days=i), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert len(created) == 1
    assert "lower" in created[0].claim


async def test_calling_twice_does_not_duplicate_the_advice_row(db_session: AsyncSession):
    """record_advice()'s existing 30-day dedup makes repeated derive-on-read
    calls (e.g. every Home load) safe — this just confirms that still holds."""
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    for i in range(8, 22):
        db_session.add(_expense(uid, "100", TODAY - timedelta(days=i), food))
    for i in range(0, 7):
        db_session.add(_expense(uid, "200", TODAY - timedelta(days=i), food))
    await db_session.commit()

    first = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    second = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id

    all_rows = (await db_session.execute(
        select(AdviceMemory).where(AdviceMemory.user_id == uid, AdviceMemory.kind == AdviceKind.spending_shift.value)
    )).scalars().all()
    assert len(all_rows) == 1


async def test_an_answered_shift_is_not_immediately_re_raised(db_session: AsyncSession):
    """Regression: found via live testing — answering a shift question used
    to get asked again on the very next brief load, since record_advice()'s
    dedup only reuses a still-PENDING row and the underlying weekly averages
    don't change between page loads."""
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    for i in range(8, 22):
        db_session.add(_expense(uid, "100", TODAY - timedelta(days=i), food))
    for i in range(0, 7):
        db_session.add(_expense(uid, "200", TODAY - timedelta(days=i), food))
    await db_session.commit()

    first = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert len(first) == 1
    await ams.answer(db_session, uid, first[0].id, answer="explained",
                     detail="had a friend visiting this week, ordered more takeout", today=TODAY)

    again = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert again == []


async def test_a_monthly_bill_is_never_reported_as_a_daily_drop(db_session: AsyncSession):
    """Regression: found on realistic seeded data — rent hits once a month, so
    a week with no rent read as "Rent & Housing has been running lower lately
    — about 0/day this week". Episodic spending has no daily rhythm to model;
    month-scale movement is the BehavioralProfile's job, not this one."""
    uid = await _make_user(db_session)
    rent = await _category(db_session, "Rent & Housing")
    food = await _category(db_session, "Food & Dining")

    # Rent: a single big charge inside the baseline window, none since.
    db_session.add(_expense(uid, "12000", TODAY - timedelta(days=12), rent))
    # Food every day, perfectly flat — so nothing else should fire either.
    for i in range(0, 22):
        db_session.add(_expense(uid, "180", TODAY - timedelta(days=i), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert [c.subject_label for c in created] == []


async def test_a_real_daily_shift_still_fires_alongside_a_monthly_bill(db_session: AsyncSession):
    """The episodic filter must not silence genuine daily-habit shifts."""
    uid = await _make_user(db_session)
    rent = await _category(db_session, "Rent & Housing")
    food = await _category(db_session, "Food & Dining")

    db_session.add(_expense(uid, "12000", TODAY - timedelta(days=12), rent))
    for i in range(8, 22):
        db_session.add(_expense(uid, "180", TODAY - timedelta(days=i), food))
    for i in range(0, 7):
        db_session.add(_expense(uid, "340", TODAY - timedelta(days=i), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert [c.subject_label for c in created] == ["Food & Dining"]
    assert "higher" in created[0].claim


async def test_uncategorized_and_near_zero_baselines_are_skipped(db_session: AsyncSession):
    uid = await _make_user(db_session)
    food = await _category(db_session, "Food & Dining")
    # Uncategorized (category_id=None) expenses should never generate advice.
    db_session.add(Expense(
        user_id=uid, category_id=None, original_amount=Decimal("500"), original_currency="INR",
        exchange_rate=Decimal("1"), converted_amount=Decimal("500"), base_currency="INR",
        expense_date=TODAY - timedelta(days=10),
    ))
    # A near-zero baseline category (well under the 1/day floor) shouldn't
    # trigger even though the relative jump looks huge.
    db_session.add(_expense(uid, "1", TODAY - timedelta(days=20), food))
    await db_session.commit()

    created = await sps.detect_and_record_shifts(db_session, uid, today=TODAY)
    assert created == []
