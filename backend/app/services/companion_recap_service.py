"""Companion recap (Sprint 4b-5b) — the structured foundation for
"what do you know about me?".

Aggregates already-computed state into a companion-like profile led by a
Financial Identity section. Reuses existing data/services; computes no new
financial facts. Resilient on thin data (sections degrade to empty, never error).
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.learning import success as S
from app.models import Expense, Income, Receivable, SavingsGoal
from app.models.enums import ReceivableStatus, SavingsGoalStatus
from app.services import analytics_service, calendar_service, life_lesson_service, settings_service


async def build(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    today = today or await calendar_service.user_today(db, user_id)
    cur = (await settings_service.get_settings(db, user_id)).base_currency

    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()
    goal_names = [g.name for g in goals]
    goals_out = [{"name": g.name, "target": str(g.converted_amount), "currency": g.base_currency} for g in goals]

    cats = await analytics_service._category_sums(db, user_id, today.replace(day=1), today)  # noqa: SLF001
    top = max(cats.items(), key=lambda kv: kv[1], default=None)
    challenge = f"{top[0]} spending" if top else None

    # Relationships (who the user lends to).
    rec_rows = (await db.execute(select(
        Receivable.source_name, Receivable.status, func.count()).where(
        Receivable.user_id == user_id, Receivable.deleted_at.is_(None))
        .group_by(Receivable.source_name, Receivable.status))).all()
    rel: dict[str, dict[str, int]] = {}
    for name, status, n in rec_rows:
        rel.setdefault(name, {"loans": 0, "repaid": 0})
        rel[name]["loans"] += n
        if status == ReceivableStatus.received:
            rel[name]["repaid"] += n
    relationships = [{"name": k, **v} for k, v in rel.items()]

    # Achievements (only achievement-worthy wins).
    completed = (await db.execute(select(SavingsGoal.name, SavingsGoal.updated_at).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.completed))).all()
    repaid = [(name, None) for name, st, n in
              [(r[0], r[1], r[2]) for r in rec_rows] if st == ReceivableStatus.received]
    first_income = await db.scalar(select(func.min(Income.received_date)).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)))
    achievements = [
        {"type": a.type, "importance": a.importance, "label": a.label,
         "when": a.when.isoformat() if a.when else None}
        for a in S.detect(completed_goals=[(n, d.date() if d else None) for n, d in completed],
                          repaid_loans=repaid, first_salary=first_income, today=today)
    ]

    # Lessons (confirmed, user-taught).
    lessons = [lr for lr in await life_lesson_service.list_(db, user_id, today=today)
               if lr["status"] in ("active", "confirmed")]

    # Habits — light, derived signals.
    habits: list[str] = []
    if achievements and any(a["type"] == S.SAVINGS_STREAK for a in achievements):
        habits.append("Consistent goal saving")
    days_logged = await db.scalar(select(func.count(func.distinct(Expense.expense_date))).where(
        Expense.user_id == user_id, Expense.deleted_at.is_(None))) or 0
    if days_logged >= 10:
        habits.append("Regular expense logging")

    strongest_habit = habits[0] if habits else None
    financial_identity = {
        "focus_areas": goal_names,
        "strongest_habit": strongest_habit,
        "current_challenge": challenge,
        "currency": cur,
    }

    return {
        "financial_identity": financial_identity,
        "goals": goals_out,
        "habits": habits,
        "relationships": relationships,
        "lessons": lessons,
        "achievements": achievements,
        "preferences": {"base_currency": cur},
    }
