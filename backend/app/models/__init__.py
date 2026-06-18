"""SQLAlchemy models.

Importing this package registers every model on the declarative ``Base`` so that
Alembic's ``target_metadata`` sees the full schema.
"""

from app.db.base import Base
from app.models.advice_memory import AdviceMemory
from app.models.budget_session import BudgetSession
from app.models.category import Category
from app.models.companion_event import CompanionEvent
from app.models.companion_insight import CompanionInsight
from app.models.currency import Currency
from app.models.daily_plan import DailyPlan
from app.models.exchange_rate import ExchangeRate
from app.models.expense import Expense
from app.models.financial_profile import FinancialProfile
from app.models.income import Income
from app.models.income_source import IncomeSource
from app.models.life_event import LifeEvent
from app.models.life_lesson import LifeLesson
from app.models.outcome import Outcome
from app.models.person import Person
from app.models.planned_expense import PlannedExpense
from app.models.receivable import Receivable
from app.models.recurring_rule import RecurringRule
from app.models.recommendation_feedback import RecommendationFeedback
from app.models.refresh_token import RefreshToken
from app.models.savings_goal import SavingsGoal
from app.models.session_expense import SessionExpense
from app.models.user import User
from app.models.user_policy import UserPolicy
from app.models.user_settings import UserSettings

__all__ = [
    "Base",
    "AdviceMemory",
    "BudgetSession",
    "Category",
    "CompanionEvent",
    "CompanionInsight",
    "Currency",
    "DailyPlan",
    "ExchangeRate",
    "Expense",
    "FinancialProfile",
    "Income",
    "IncomeSource",
    "LifeEvent",
    "LifeLesson",
    "Outcome",
    "Person",
    "PlannedExpense",
    "Receivable",
    "RecurringRule",
    "RecommendationFeedback",
    "RefreshToken",
    "SavingsGoal",
    "SessionExpense",
    "User",
    "UserPolicy",
    "UserSettings",
]
