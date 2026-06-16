"""Active budget-session state for the projection engine.

Reports utilization for active sessions so Risk/Guidance can flag overruns.
This does NOT add to the projection's money math — linked expenses are already
counted in the expenses table (no double accounting).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BudgetSession, Expense, SessionExpense
from app.models.enums import BudgetSessionStatus


@dataclass(frozen=True)
class ActiveSession:
    session_id: uuid.UUID
    title: str
    budget_base: Decimal
    spent_base: Decimal
    utilization_percent: Decimal


async def load_active_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[ActiveSession]:
    stmt = (
        select(
            BudgetSession.id,
            BudgetSession.title,
            BudgetSession.converted_amount,
            func.coalesce(func.sum(Expense.converted_amount), 0),
        )
        .select_from(BudgetSession)
        .outerjoin(SessionExpense, SessionExpense.session_id == BudgetSession.id)
        .outerjoin(Expense, and_(Expense.id == SessionExpense.expense_id, Expense.deleted_at.is_(None)))
        .where(
            BudgetSession.user_id == user_id,
            BudgetSession.status == BudgetSessionStatus.active,
            BudgetSession.deleted_at.is_(None),
        )
        .group_by(BudgetSession.id, BudgetSession.title, BudgetSession.converted_amount)
    )
    sessions: list[ActiveSession] = []
    for session_id, title, budget, spent in (await db.execute(stmt)).all():
        budget = Decimal(budget)
        spent = Decimal(spent)
        utilization = (spent / budget * 100) if budget > 0 else Decimal("0")
        sessions.append(ActiveSession(session_id, title, budget, spent, utilization))
    return sessions
