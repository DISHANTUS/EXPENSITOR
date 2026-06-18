"""Home Memory Strip stats (UI-X).

A few deterministic, already-true numbers that make Home feel personal:
how long you've used Advary, goals completed, money saved, people you track,
your strongest habit, and your biggest win. Surfaces existing data — computes no
new financial facts; degrades gracefully on a thin account.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Expense, Person, SavingsGoal, User
from app.models.enums import SavingsGoalStatus
from app.services import calendar_service, settings_service

_ZERO = Decimal("0")


async def build(db: AsyncSession, user: User) -> dict:
    today = await calendar_service.user_today(db, user.id)
    cur = (await settings_service.get_settings(db, user.id)).base_currency

    created = user.created_at.date() if user.created_at else today
    days = max(1, (today - created).days + 1)

    completed = (await db.execute(select(SavingsGoal.name, SavingsGoal.converted_amount).where(
        SavingsGoal.user_id == user.id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.completed)
        .order_by(SavingsGoal.updated_at.desc()))).all()
    goals_completed = len(completed)
    total_saved = sum((row[1] for row in completed), _ZERO)

    goals_active = (await db.execute(select(SavingsGoal.name).where(
        SavingsGoal.user_id == user.id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()

    relationship_count = await db.scalar(select(func.count()).where(
        Person.user_id == user.id, Person.deleted_at.is_(None))) or 0

    days_logged = await db.scalar(select(func.count(func.distinct(Expense.expense_date))).where(
        Expense.user_id == user.id, Expense.deleted_at.is_(None))) or 0

    biggest_win = completed[0][0] if completed else (goals_active[0] if goals_active else None)
    if goals_completed >= 2:
        habit = "Saving consistently"
    elif days_logged >= 10:
        habit = "Tracking expenses regularly"
    else:
        habit = None

    return {
        "days_with_advary": days,
        "goals_completed": goals_completed,
        "goals_active": len(goals_active),
        "relationship_count": int(relationship_count),
        "total_saved": str(total_saved.quantize(Decimal("0.0001"))),
        "currency": cur,
        "strongest_habit": habit,
        "biggest_win": biggest_win,
    }
