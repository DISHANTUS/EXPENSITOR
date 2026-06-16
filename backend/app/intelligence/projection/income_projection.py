"""Capabilities #3/#4/#5 — expand expected income into future events.

DC1 rule: project an occurrence only when its date is STRICTLY > today, so
already-due income (in current balance) is never double-counted.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.calendar_utils import clamp_day, iter_year_months
from app.models import IncomeSource
from app.models.enums import IncomeKind


@dataclass(frozen=True)
class IncomeEvent:
    date: date
    amount_base: Decimal
    reliability: Decimal
    source_id: uuid.UUID
    origin: str = "income"  # e.g. "income_source:salary", "receivable" (for factor classification)
    time_window: str | None = None  # rough arrival time-of-day, when known (Income Timing)
    exact_time: time | None = None  # exact arrival time, when known


async def expand_income_events(
    db: AsyncSession, user_id: uuid.UUID, today: date, horizon: date
) -> list[IncomeEvent]:
    sources = (
        await db.execute(
            select(IncomeSource).where(
                IncomeSource.user_id == user_id,
                IncomeSource.deleted_at.is_(None),
                IncomeSource.is_active.is_(True),
            )
        )
    ).scalars().all()

    events: list[IncomeEvent] = []
    for source in sources:
        window = source.expected_time_window.value if source.expected_time_window else None
        exact = source.expected_time
        if source.kind == IncomeKind.recurring:
            if source.recurrence_day is None:
                continue
            for year, month in iter_year_months(today, horizon):
                occurrence = clamp_day(year, month, source.recurrence_day)
                if today < occurrence <= horizon:  # strictly future
                    events.append(
                        IncomeEvent(
                            occurrence, source.converted_amount, source.reliability, source.id,
                            f"income_source:{source.source_type.value}", window, exact,
                        )
                    )
        else:  # one_time
            if source.expected_date is not None and today < source.expected_date <= horizon:
                events.append(
                    IncomeEvent(
                        source.expected_date, source.converted_amount, source.reliability, source.id,
                        f"income_source:{source.source_type.value}", window, exact,
                    )
                )

    events.sort(key=lambda event: event.date)
    return events
