"""Calendar aggregation schemas (month grid + single-day detail)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.expense import ExpenseRead
from app.schemas.income import IncomeRead
from app.schemas.planned_expense import PlannedExpenseRead


class MarkerTypeOut(BaseModel):
    """One entry of the marker registry (so clients render without hardcoding)."""

    key: str
    icon: str
    color: str
    title: str
    category: str
    commentary_template: str
    animation: str  # client animation name (heartbeat | shimmer | drift | …)


class DayCell(BaseModel):
    """A single day in the month grid."""

    date: date
    spent: Decimal
    income: Decimal
    event_count: int
    planned_budget: Decimal | None       # user-set, if any
    effective_budget: Decimal | None     # user-set or derived
    classification: str                  # over | saved | within | none
    markers: list[str]                   # marker-type keys


class MonthView(BaseModel):
    year: int
    month: int
    base_currency: str
    days: list[DayCell]


class DayDetail(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    date: date
    base_currency: str
    planned_budget: Decimal | None
    effective_budget: Decimal | None
    spent: Decimal
    income: Decimal
    remaining: Decimal | None
    classification: str
    markers: list[str]
    overspend_reason: str | None
    expenses: list[ExpenseRead]
    incomes: list[IncomeRead]
    events: list[PlannedExpenseRead]
