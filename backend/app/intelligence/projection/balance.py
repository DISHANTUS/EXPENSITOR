"""Capability #1 — Current Balance.

current_balance = starting_balance
               + Σ income(received_date >= onboarding_date)
               - Σ expense(expense_date >= onboarding_date)
All base currency, soft-deleted rows excluded (filtered explicitly). DC5 cutoff
= the date user_settings was created (user-local).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, Income, UserSettings


@dataclass(frozen=True)
class BalanceBreakdown:
    onboarding_date: date
    starting_balance: Decimal
    total_income: Decimal
    total_expense: Decimal
    current_balance: Decimal
    as_of: date


def onboarding_date_for(settings: UserSettings) -> date:
    tz = ZoneInfo(settings.timezone or "UTC")
    return settings.created_at.astimezone(tz).date()


async def compute_balance(db: AsyncSession, user_id: uuid.UUID, today: date, settings: UserSettings) -> BalanceBreakdown:
    onboarding = onboarding_date_for(settings)

    income_total = await db.scalar(
        select(func.coalesce(func.sum(Income.converted_amount), 0)).where(
            Income.user_id == user_id,
            Income.deleted_at.is_(None),
            Income.received_date >= onboarding,
        )
    )
    expense_total = await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id,
            Expense.deleted_at.is_(None),
            Expense.expense_date >= onboarding,
        )
    )

    starting = Decimal(settings.starting_balance or 0)
    income_total = Decimal(income_total or 0)
    expense_total = Decimal(expense_total or 0)
    current = starting + income_total - expense_total
    return BalanceBreakdown(
        onboarding_date=onboarding,
        starting_balance=starting,
        total_income=income_total,
        total_expense=expense_total,
        current_balance=current,
        as_of=today,
    )


async def current_balance(db: AsyncSession, user_id: uuid.UUID, today: date) -> BalanceBreakdown:
    """Standalone entry point (loads settings itself)."""
    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")
    return await compute_balance(db, user_id, today, settings)
