"""Capability #7 — expand planned expenses into future outflow events.

Only status='planned' (soft-deleted excluded). Overdue plans (planned_date <
today) are clamped to today (day 0) and flagged, per the approved Overdue policy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlannedExpense
from app.models.enums import PlannedExpenseStatus


@dataclass(frozen=True)
class OutflowEvent:
    date: date          # effective date (overdue clamped to today)
    amount_base: Decimal
    priority: str
    planned_id: uuid.UUID
    overdue: bool
    days_overdue: int


async def expand_outflows(
    db: AsyncSession, user_id: uuid.UUID, today: date, horizon: date
) -> list[OutflowEvent]:
    rows = (
        await db.execute(
            select(PlannedExpense).where(
                PlannedExpense.user_id == user_id,
                PlannedExpense.deleted_at.is_(None),
                PlannedExpense.status == PlannedExpenseStatus.planned,
            )
        )
    ).scalars().all()

    events: list[OutflowEvent] = []
    for row in rows:
        overdue = row.planned_date < today
        effective = today if overdue else row.planned_date
        if effective > horizon:
            continue
        days_overdue = (today - row.planned_date).days if overdue else 0
        events.append(
            OutflowEvent(
                date=effective,
                amount_base=row.converted_amount,
                priority=row.priority.value,
                planned_id=row.id,
                overdue=overdue,
                days_overdue=days_overdue,
            )
        )

    events.sort(key=lambda event: event.date)
    return events
