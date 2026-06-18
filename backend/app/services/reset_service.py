"""Reset / Clean-Slate (pre-Sprint-8) — hand the app to a friend without exposing
personal data. Three modes:
  * soft  — wipe all the personal story; keep account + settings (currency, name).
  * full  — wipe the story AND reset settings to defaults; keep only the account/auth.
  * demo  — wipe, then seed a fictional sample user so a friend sees it populated.

All FKs between domain tables are SET NULL / CASCADE, so a straight per-table
delete (session_expenses cascade from expenses/budget_sessions) leaves no orphans.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdviceMemory,
    BudgetSession,
    CompanionEvent,
    CompanionInsight,
    DailyPlan,
    Expense,
    FinancialProfile,
    Income,
    IncomeSource,
    LifeEvent,
    LifeLesson,
    Outcome,
    Person,
    PlannedExpense,
    Receivable,
    RecommendationFeedback,
    RecurringRule,
    SavingsGoal,
    UserSettings,
)
from app.schemas.income import IncomeCreate
from app.schemas.life_event import LifeEventCreate
from app.schemas.planned_expense import PlannedExpenseCreate
from app.schemas.receivable import ReceivableCreate
from app.schemas.savings import SavingsGoalCreate
from app.services import (
    calendar_service,
    income_service,
    life_event_service,
    life_lesson_service,
    planned_expense_service,
    receivables_service,
    savings_service,
    settings_service,
)

# Order: parents whose children CASCADE first (budget_sessions/expenses → session_expenses).
_DOMAIN = [
    BudgetSession, Outcome, RecommendationFeedback, CompanionInsight, CompanionEvent,
    AdviceMemory, LifeLesson, LifeEvent, DailyPlan, RecurringRule, PlannedExpense,
    Expense, Receivable, Income, IncomeSource, SavingsGoal, Person,
]


async def _wipe(db: AsyncSession, user_id: uuid.UUID) -> None:
    for model in _DOMAIN:
        await db.execute(delete(model).where(model.user_id == user_id))


async def soft_reset(db: AsyncSession, user_id: uuid.UUID) -> None:
    await _wipe(db, user_id)
    await db.commit()


async def full_reset(db: AsyncSession, user_id: uuid.UUID) -> None:
    await _wipe(db, user_id)
    s = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if s is not None:  # keep base_currency/timezone (operational) — reset the rest
        s.companion_name = None
        s.display_name = None
        s.companion_style = "balanced"
        s.voice_length = "normal"
        s.selected_voice = None
        s.voice_locale = None
        s.notification_preferences = {}
        s.monthly_threshold = None
        s.monthly_income_estimate = None
        s.tour_completed_at = None        # a fresh identity replays the tour
    await db.execute(delete(FinancialProfile).where(FinancialProfile.user_id == user_id))
    await db.commit()


async def demo_seed(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> None:
    """Wipe, then populate a fictional sample (neutral names — not the owner's data)."""
    await _wipe(db, user_id)
    await db.execute(delete(FinancialProfile).where(FinancialProfile.user_id == user_id))
    today = today or await calendar_service.user_today(db, user_id)
    cur = (await settings_service.get_settings(db, user_id)).base_currency

    await income_service.create(db, user_id, IncomeCreate(
        source_type="salary", original_amount="42000", original_currency=cur,
        received_date=today - timedelta(days=120)))
    await savings_service.create(db, user_id, SavingsGoalCreate(
        name="Dream Trip", kind="custom_goal", original_amount="150000", original_currency=cur,
        target_date=today + timedelta(days=300)), today=today)
    await receivables_service.create(db, user_id, ReceivableCreate(
        title="Loan to Sam", source_name="Sam", source_type="friend", kind="one_time",
        original_amount="2000", original_currency=cur, expected_date=today + timedelta(days=20)))
    await planned_expense_service.create(db, user_id, PlannedExpenseCreate(
        title="Coffee with Mia", planned_date=today + timedelta(days=3), occasion_type="outing",
        original_amount="600", original_currency=cur))
    await life_event_service.create(db, user_id, LifeEventCreate(
        title="Started a new job", event_date=today - timedelta(days=60), kind="career", icon="💼"))
    await life_event_service.create(db, user_id, LifeEventCreate(
        title="Move to a new city", event_date=today + timedelta(days=400), kind="move", icon="✈️"))
    await life_lesson_service.teach(db, user_id, source_text="plan ahead for big purchases", today=today)
    await db.commit()
