"""Capability #6 — Spending model (mu, sigma) over a bounded trailing window.

Statistics may use pre-onboarding expenses (a rate, not a balance). Cold-start
falls back to threshold/income estimate with low confidence. Full history is
NEVER loaded (windowed query only).
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense

DEFAULT_WINDOW_DAYS = 90
_MIN_CONFIDENT_DAYS = 30
_MIN_CONFIDENT_DISTINCT = 14
_COLD_START_DISTINCT = 5
_COLD_START_DAYS = 14
_COLD_START_SPEND_RATIO = Decimal("0.7")


@dataclass(frozen=True)
class SpendingModel:
    mu: Decimal          # mean daily spend (base currency)
    sigma: Decimal       # std dev of daily spend
    confidence: str      # "low" | "normal"
    observed_days: int
    window_days: int


def _cold_start(window_days: int, threshold: Decimal | None, income_estimate: Decimal | None) -> SpendingModel:
    if threshold is not None and threshold > 0:
        mu = Decimal(threshold) / 30
    elif income_estimate is not None and income_estimate > 0:
        mu = (Decimal(income_estimate) * _COLD_START_SPEND_RATIO) / 30
    else:
        mu = Decimal(0)
    return SpendingModel(mu=mu, sigma=mu * Decimal("0.5"), confidence="low", observed_days=0, window_days=window_days)


async def compute_spending_model(
    db: AsyncSession,
    user_id: uuid.UUID,
    today: date,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    monthly_threshold: Decimal | None = None,
    monthly_income_estimate: Decimal | None = None,
) -> SpendingModel:
    window_start = today - timedelta(days=window_days - 1)
    rows = (
        await db.execute(
            select(Expense.expense_date, Expense.converted_amount).where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.expense_date >= window_start,
                Expense.expense_date <= today,
            )
        )
    ).all()

    if not rows:
        return _cold_start(window_days, monthly_threshold, monthly_income_estimate)

    daily: dict[date, Decimal] = {}
    for spend_date, amount in rows:
        daily[spend_date] = daily.get(spend_date, Decimal(0)) + amount

    distinct_days = len(daily)
    if distinct_days < _COLD_START_DISTINCT:
        earliest = min(daily)
        if (today - earliest).days + 1 < _COLD_START_DAYS:
            return _cold_start(window_days, monthly_threshold, monthly_income_estimate)

    earliest = min(daily)
    observed_days = max(1, min(window_days, (today - earliest).days + 1))
    total = sum(daily.values(), Decimal(0))
    mu = total / observed_days

    if observed_days >= 2:
        series = [float(daily.get(earliest + timedelta(days=i), Decimal(0))) for i in range(observed_days)]
        sigma = Decimal(str(statistics.stdev(series)))
    else:
        sigma = Decimal(0)

    confidence = "normal" if observed_days >= _MIN_CONFIDENT_DAYS and distinct_days >= _MIN_CONFIDENT_DISTINCT else "low"
    return SpendingModel(mu=mu, sigma=sigma, confidence=confidence, observed_days=observed_days, window_days=window_days)
