"""Per-day budget: set/adjust with the start-of-day lock rule."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyPlan, Expense
from app.schemas.daily_plan import DailyPlanUpsert
from app.services.exceptions import InvalidOperationError


async def get(db: AsyncSession, user_id: uuid.UUID, plan_date: date) -> DailyPlan | None:
    result = await db.execute(
        select(DailyPlan).where(DailyPlan.user_id == user_id, DailyPlan.plan_date == plan_date)
    )
    return result.scalar_one_or_none()


async def _has_spent(db: AsyncSession, user_id: uuid.UUID, day: date) -> bool:
    count = await db.scalar(
        select(func.count())
        .select_from(Expense)
        .where(
            Expense.user_id == user_id,
            Expense.expense_date == day,
            Expense.deleted_at.is_(None),
        )
    )
    return bool(count)


async def upsert(
    db: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date,
    data: DailyPlanUpsert,
    *,
    today: date,
) -> DailyPlan:
    row = await get(db, user_id, plan_date)
    changing_budget = data.planned_budget is not None

    if changing_budget:
        if plan_date < today:
            raise InvalidOperationError("Past daily budgets can't be changed.")
        if plan_date == today and await _has_spent(db, user_id, today) and not data.override:
            raise InvalidOperationError(
                "Today's budget is locked because spending has already begun. "
                "Changing it now reduces spending-analysis accuracy — confirm to override."
            )

    if row is None:
        row = DailyPlan(user_id=user_id, plan_date=plan_date)
        db.add(row)

    if changing_budget:
        row.planned_budget = data.planned_budget
        if plan_date == today and await _has_spent(db, user_id, today):
            row.modified_after_start = True
            if row.locked_at is None:
                row.locked_at = datetime.now(timezone.utc)

    if data.overspend_reason is not None:
        row.overspend_reason = data.overspend_reason

    await db.commit()
    await db.refresh(row)
    return row
