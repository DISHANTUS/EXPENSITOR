"""Budget derivation: monthly/weekly/daily from income − commitments − goals.

Applying it writes ``settings.monthly_threshold`` so the calendar's derived
daily budget (Sprint 3) reflects the user's real profile.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IncomeSource, RecurringRule, SavingsGoal
from app.models.enums import IncomeKind, SavingsGoalKind, SavingsGoalStatus
from app.schemas.budget import BudgetSummary
from app.schemas.settings import UserSettingsUpdate
from app.services import calendar_service, settings_service

_Q = Decimal("0.0001")
_ZERO = Decimal("0")


async def _sum(db: AsyncSession, column, *conditions) -> Decimal:
    value = await db.scalar(select(func.coalesce(func.sum(column), 0)).where(*conditions))
    return Decimal(value or 0)


async def summary(db: AsyncSession, user_id: uuid.UUID) -> BudgetSummary:
    settings = await settings_service.get_settings(db, user_id)

    income = await _sum(
        db, IncomeSource.converted_amount,
        IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None),
        IncomeSource.is_active.is_(True), IncomeSource.kind == IncomeKind.recurring,
    )
    if income == _ZERO and settings.monthly_income_estimate:
        income = settings.monthly_income_estimate

    commitments = await _sum(
        db, RecurringRule.converted_amount,
        RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None),
        RecurringRule.is_active.is_(True),
    )
    goals = await _sum(
        db, SavingsGoal.converted_amount,
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active, SavingsGoal.kind == SavingsGoalKind.monthly_target,
    )

    discretionary = income - commitments - goals
    if discretionary < _ZERO:
        discretionary = _ZERO

    today = await calendar_service.user_today(db, user_id)
    days = _cal.monthrange(today.year, today.month)[1]
    weekly = (discretionary / Decimal("4.33")).quantize(_Q)
    daily = (discretionary / Decimal(days)).quantize(_Q)

    return BudgetSummary(
        base_currency=settings.base_currency,
        monthly_income=income.quantize(_Q),
        monthly_commitments=commitments.quantize(_Q),
        monthly_goal_contributions=goals.quantize(_Q),
        monthly_discretionary=discretionary.quantize(_Q),
        weekly_budget=weekly,
        daily_budget=daily,
    )


async def apply(db: AsyncSession, user_id: uuid.UUID) -> BudgetSummary:
    """Persist the derived monthly discretionary as the spending threshold."""
    s = await summary(db, user_id)
    await settings_service.update_settings(
        db, user_id, UserSettingsUpdate(monthly_threshold=s.monthly_discretionary)
    )
    return s
