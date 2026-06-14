"""SQLAlchemy models.

Importing this package registers every model on the declarative ``Base`` so that
Alembic's ``target_metadata`` sees the full schema.
"""

from app.db.base import Base
from app.models.category import Category
from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate
from app.models.expense import Expense
from app.models.income import Income
from app.models.income_source import IncomeSource
from app.models.planned_expense import PlannedExpense
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.user_settings import UserSettings

__all__ = [
    "Base",
    "Category",
    "Currency",
    "ExchangeRate",
    "Expense",
    "Income",
    "IncomeSource",
    "PlannedExpense",
    "RefreshToken",
    "User",
    "UserSettings",
]
