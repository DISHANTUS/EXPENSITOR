"""Expand pending receivables into projection income events.

one_time future -> income on the date; one_time overdue -> clamped to today at
reduced reliability (conservative) + flagged overdue; recurring -> monthly
occurrences strictly after today (like income_sources), never overdue in C2.
received/cancelled/deleted contribute nothing.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.calendar_utils import clamp_day, iter_year_months
from app.intelligence.projection.income_projection import IncomeEvent
from app.models import Receivable
from app.models.enums import ReceivableKind, ReceivableStatus

OVERDUE_FACTOR = Decimal("0.5")


@dataclass(frozen=True)
class OverdueReceivable:
    receivable_id: uuid.UUID
    amount_base: Decimal
    days_overdue: int


async def expand_receivable_events(
    db: AsyncSession, user_id: uuid.UUID, today: date, horizon: date
) -> tuple[list[IncomeEvent], list[OverdueReceivable]]:
    rows = (
        await db.execute(
            select(Receivable).where(
                Receivable.user_id == user_id,
                Receivable.deleted_at.is_(None),
                Receivable.status == ReceivableStatus.pending,
            )
        )
    ).scalars().all()

    events: list[IncomeEvent] = []
    overdue: list[OverdueReceivable] = []

    for r in rows:
        window = r.expected_time_window.value if r.expected_time_window else None
        exact = r.expected_time
        if r.kind == ReceivableKind.one_time:
            if r.expected_date is None:
                continue
            if r.expected_date > today:
                events.append(IncomeEvent(r.expected_date, r.converted_amount, r.reliability, r.id, "receivable", window, exact))
            else:  # overdue -> clamp to today, conservative reliability
                events.append(IncomeEvent(today, r.converted_amount, r.reliability * OVERDUE_FACTOR, r.id, "receivable", window, exact))
                overdue.append(OverdueReceivable(r.id, r.converted_amount, (today - r.expected_date).days))
        else:  # recurring
            if r.recurrence_day is None:
                continue
            for year, month in iter_year_months(today, horizon):
                occurrence = clamp_day(year, month, r.recurrence_day)
                if today < occurrence <= horizon:
                    events.append(IncomeEvent(occurrence, r.converted_amount, r.reliability, r.id, "receivable", window, exact))

    return events, overdue
