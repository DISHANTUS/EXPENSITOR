"""DB-backed tests for the event_service (Event Planner)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CompanionInsight, User, UserSettings
from app.models.enums import OccasionType
from app.schemas.planned_expense import PlannedExpenseCreate
from app.services import event_service

pytestmark = pytest.mark.asyncio

TODAY = date(2026, 6, 1)
EVENT_DATE = (TODAY + timedelta(days=30)).isoformat()


async def _make_user(db: AsyncSession, *, starting: str) -> uuid.UUID:
    user = User(email=f"{uuid.uuid4().hex}@e.com", password_hash="x")
    db.add(user)
    await db.flush()
    settings = UserSettings(
        user_id=user.id, base_currency="INR", timezone="UTC",
        starting_balance=Decimal(starting), created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db.add(settings)
    await db.commit()
    return user.id


def _event_data(**o) -> PlannedExpenseCreate:
    payload = {
        "title": "Outing with gf", "planned_date": EVENT_DATE, "original_amount": "1500",
        "original_currency": "INR", "occasion_type": "outing",
    }
    payload.update(o)
    return PlannedExpenseCreate(**payload)


async def _insight_types(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = (await db.execute(select(CompanionInsight.type).where(CompanionInsight.user_id == user_id))).all()
    return {r[0] for r in rows}


async def test_create_event_sets_occasion_and_returns_consequence(db_session: AsyncSession):
    uid = await _make_user(db_session, starting="100000")
    event, result = await event_service.create_event(db_session, uid, _event_data(), today=TODAY)
    assert event.occasion_type == OccasionType.outing
    assert result.affordable is True
    types = await _insight_types(db_session, uid)
    assert "event_created" in types and "event_affordable" in types


async def test_unaffordable_event_companion_and_adjustments(db_session: AsyncSession):
    uid = await _make_user(db_session, starting="0")
    event, result = await event_service.create_event(db_session, uid, _event_data(original_amount="50000"), today=TODAY)
    assert result.affordable is False
    assert any(a.action == "reduce_discretionary" for a in result.required_adjustments)
    types = await _insight_types(db_session, uid)
    assert "event_created" in types and "event_unaffordable" in types


async def test_analyze_consequences_and_reschedule(db_session: AsyncSession):
    uid = await _make_user(db_session, starting="100000")
    event, _ = await event_service.create_event(db_session, uid, _event_data(), today=TODAY)
    cons = await event_service.analyze_consequences(db_session, uid, event.id, today=TODAY)
    assert cons.affordable is True
    resched = await event_service.analyze_reschedule(db_session, uid, event.id, window_days=15, today=TODAY)
    assert resched.best_date is not None
    assert all(0 <= c.score <= 100 for c in resched.candidates)


async def test_analyze_unknown_event_404(db_session: AsyncSession):
    uid = await _make_user(db_session, starting="100")
    from app.services.exceptions import ResourceNotFoundError

    with pytest.raises(ResourceNotFoundError):
        await event_service.analyze_consequences(db_session, uid, uuid.uuid4(), today=TODAY)
