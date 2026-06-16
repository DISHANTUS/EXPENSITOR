"""Behavioral Intelligence — bounded data loaders + window helpers (C6/B1).

Loads every input the metric registry needs in one bounded pass (~9 queries),
mirroring the Projection Engine's "build once per request" contract. Pure,
deterministic; no new tables. All money is base-currency ``converted_amount``.

Windows (per the approved design):
  * rate window  = trailing 90 days (today-89 .. today)        -> rate metrics
  * monthly      = 6 calendar buckets (current + 5 prior)      -> trend / rate
  * complete_months = the 5 prior full months (current is partial, excluded
    from rate/trend math unless a metric pro-rates it explicitly)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection.calendar_utils import iter_year_months
from app.models import (
    BudgetSession,
    Category,
    Expense,
    Income,
    IncomeSource,
    PlannedExpense,
    Receivable,
    SessionExpense,
    UserSettings,
)
from app.models.enums import BudgetSessionStatus, IncomeKind, IncomeSourceType

RATE_WINDOW_DAYS = 90
MONTHLY_BUCKETS = 6  # current + 5 prior

YearMonth = tuple[int, int]


# --------------------------------------------------------------------------- #
#  Lightweight row records (primitives only -> trivially testable / picklable)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ExpenseRow:
    on: date
    amount: Decimal
    category_id: uuid.UUID | None


@dataclass(frozen=True)
class IncomeRow:
    on: date
    amount: Decimal
    source_type: str


@dataclass(frozen=True)
class IncomeSourceRow:
    source_type: str
    kind: str
    recurrence_day: int | None
    expected_date: date | None
    amount: Decimal
    reliability: Decimal


@dataclass(frozen=True)
class SessionRow:
    budget: Decimal
    spent: Decimal
    ended_on: date | None


@dataclass(frozen=True)
class ReceivableRow:
    status: str
    kind: str
    expected_date: date | None
    received_at: date | None
    created_on: date
    follow_up_count: int
    amount: Decimal


@dataclass(frozen=True)
class PlannedRow:
    planned_date: date
    amount: Decimal
    status: str
    occasion_type: str | None
    is_recurring: bool


@dataclass(frozen=True)
class CategoryInfo:
    name: str
    is_essential: bool


# --------------------------------------------------------------------------- #
#  Window
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BehaviorWindow:
    today: date
    rate_start: date
    rate_days: int
    month_start: date
    months: tuple[YearMonth, ...]          # 6 buckets, oldest -> newest
    complete_months: tuple[YearMonth, ...]  # full months only (current excluded)

    @property
    def current_month(self) -> YearMonth:
        return (self.today.year, self.today.month)


def build_window(today: date, *, rate_days: int = RATE_WINDOW_DAYS, buckets: int = MONTHLY_BUCKETS) -> BehaviorWindow:
    # First day of the bucket that is (buckets-1) months before the current one.
    index = today.month - 1 - (buckets - 1)
    year = today.year + (index // 12)
    month = index % 12 + 1
    month_start = date(year, month, 1)
    months = tuple(iter_year_months(month_start, today))
    current = (today.year, today.month)
    complete = tuple(ym for ym in months if ym != current)
    return BehaviorWindow(
        today=today,
        rate_start=date.fromordinal(today.toordinal() - (rate_days - 1)),
        rate_days=rate_days,
        month_start=month_start,
        months=months,
        complete_months=complete,
    )


# --------------------------------------------------------------------------- #
#  The loaded bundle
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BehaviorData:
    window: BehaviorWindow
    base_currency: str
    monthly_threshold: Decimal | None
    monthly_income_estimate: Decimal | None
    starting_balance: Decimal
    expenses: tuple[ExpenseRow, ...]
    incomes: tuple[IncomeRow, ...]
    income_sources: tuple[IncomeSourceRow, ...]
    sessions: tuple[SessionRow, ...]
    receivables: tuple[ReceivableRow, ...]
    planned: tuple[PlannedRow, ...]
    categories: dict[uuid.UUID, CategoryInfo] = field(default_factory=dict)
    salary_days: frozenset[int] = frozenset()
    shopping_category_ids: frozenset[uuid.UUID] = frozenset()

    @property
    def today(self) -> date:
        return self.window.today

    # -- convenience views used by several metrics --
    def expenses_in_rate_window(self) -> list[ExpenseRow]:
        start, today = self.window.rate_start, self.window.today
        return [e for e in self.expenses if start <= e.on <= today]

    def is_essential(self, category_id: uuid.UUID | None) -> bool:
        if category_id is None:
            return False  # unknown category is treated as discretionary
        info = self.categories.get(category_id)
        return bool(info and info.is_essential)


# --------------------------------------------------------------------------- #
#  Monthly aggregation helpers (shared by trend / rate metrics)
# --------------------------------------------------------------------------- #
def monthly_totals(rows: list[tuple[date, Decimal]], months: tuple[YearMonth, ...]) -> dict[YearMonth, Decimal]:
    totals: dict[YearMonth, Decimal] = {ym: Decimal("0") for ym in months}
    allowed = set(months)
    for on, amount in rows:
        ym = (on.year, on.month)
        if ym in allowed:
            totals[ym] += amount
    return totals


def monthly_expense_totals(data: BehaviorData, months: tuple[YearMonth, ...] | None = None) -> dict[YearMonth, Decimal]:
    months = months or data.window.complete_months
    return monthly_totals([(e.on, e.amount) for e in data.expenses], months)


def monthly_income_totals(data: BehaviorData, months: tuple[YearMonth, ...] | None = None) -> dict[YearMonth, Decimal]:
    months = months or data.window.complete_months
    return monthly_totals([(i.on, i.amount) for i in data.incomes], months)


# --------------------------------------------------------------------------- #
#  Loader
# --------------------------------------------------------------------------- #
async def load_behavior_data(db: AsyncSession, user_id: uuid.UUID, today: date) -> BehaviorData:
    window = build_window(today)
    m_start = window.month_start

    settings = await db.scalar(select(UserSettings).where(UserSettings.user_id == user_id))
    if settings is None:
        raise ValueError("User settings not found")

    # 1. categories visible to the user (system + own)
    cat_rows = (
        await db.execute(
            select(Category.id, Category.name, Category.is_essential).where(
                (Category.user_id == user_id) | (Category.user_id.is_(None))
            )
        )
    ).all()
    categories = {cid: CategoryInfo(name, bool(ess)) for cid, name, ess in cat_rows}
    shopping_ids = frozenset(cid for cid, info in categories.items() if info.name.strip().lower() == "shopping")

    # 2. expenses (6-month window)
    exp_rows = (
        await db.execute(
            select(Expense.expense_date, Expense.converted_amount, Expense.category_id).where(
                Expense.user_id == user_id,
                Expense.deleted_at.is_(None),
                Expense.expense_date >= m_start,
                Expense.expense_date <= today,
            )
        )
    ).all()
    expenses = tuple(ExpenseRow(d, amt, cid) for d, amt, cid in exp_rows)

    # 3. incomes (6-month window)
    inc_rows = (
        await db.execute(
            select(Income.received_date, Income.converted_amount, Income.source_type).where(
                Income.user_id == user_id,
                Income.deleted_at.is_(None),
                Income.received_date >= m_start,
                Income.received_date <= today,
            )
        )
    ).all()
    incomes = tuple(IncomeRow(d, amt, str(st.value if hasattr(st, "value") else st)) for d, amt, st in inc_rows)

    # 4. active income sources
    src_rows = (
        await db.execute(
            select(
                IncomeSource.source_type,
                IncomeSource.kind,
                IncomeSource.recurrence_day,
                IncomeSource.expected_date,
                IncomeSource.converted_amount,
                IncomeSource.reliability,
            ).where(
                IncomeSource.user_id == user_id,
                IncomeSource.deleted_at.is_(None),
                IncomeSource.is_active.is_(True),
            )
        )
    ).all()
    income_sources = tuple(
        IncomeSourceRow(
            source_type=str(st.value if hasattr(st, "value") else st),
            kind=str(kind.value if hasattr(kind, "value") else kind),
            recurrence_day=rday,
            expected_date=edate,
            amount=amt,
            reliability=rel,
        )
        for st, kind, rday, edate, amt, rel in src_rows
    )

    # salary days: recurring salary sources + actual salary receipts (proxy)
    salary_days: set[int] = {
        s.recurrence_day
        for s in income_sources
        if s.source_type == IncomeSourceType.salary.value and s.kind == IncomeKind.recurring.value and s.recurrence_day
    }
    for inc in incomes:
        if inc.source_type == IncomeSourceType.salary.value:
            salary_days.add(inc.on.day)

    # 5. completed budget sessions + spent (two bounded queries)
    sess_rows = (
        await db.execute(
            select(BudgetSession.id, BudgetSession.converted_amount, BudgetSession.ended_at).where(
                BudgetSession.user_id == user_id,
                BudgetSession.deleted_at.is_(None),
                BudgetSession.status == BudgetSessionStatus.completed,
            )
        )
    ).all()
    session_ids = [sid for sid, _, _ in sess_rows]
    spent_by_session: dict[uuid.UUID, Decimal] = {}
    if session_ids:
        spent_rows = (
            await db.execute(
                select(SessionExpense.session_id, func.coalesce(func.sum(Expense.converted_amount), 0))
                .join(Expense, Expense.id == SessionExpense.expense_id)
                .where(SessionExpense.session_id.in_(session_ids), Expense.deleted_at.is_(None))
                .group_by(SessionExpense.session_id)
            )
        ).all()
        spent_by_session = {sid: Decimal(total) for sid, total in spent_rows}
    sessions = tuple(
        SessionRow(
            budget=budget,
            spent=spent_by_session.get(sid, Decimal("0")),
            ended_on=ended.date() if ended else None,
        )
        for sid, budget, ended in sess_rows
    )

    # 6. receivables (all, not deleted)
    rec_rows = (
        await db.execute(
            select(
                Receivable.status,
                Receivable.kind,
                Receivable.expected_date,
                Receivable.received_at,
                Receivable.created_at,
                Receivable.follow_up_count,
                Receivable.converted_amount,
            ).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None))
        )
    ).all()
    receivables = tuple(
        ReceivableRow(
            status=str(st.value if hasattr(st, "value") else st),
            kind=str(kind.value if hasattr(kind, "value") else kind),
            expected_date=edate,
            received_at=rec_at.date() if rec_at else None,
            created_on=created.date() if created else today,
            follow_up_count=fu or 0,
            amount=amt,
        )
        for st, kind, edate, rec_at, created, fu, amt in rec_rows
    )

    # 7. planned expenses (6-month window)
    pl_rows = (
        await db.execute(
            select(
                PlannedExpense.planned_date,
                PlannedExpense.converted_amount,
                PlannedExpense.status,
                PlannedExpense.occasion_type,
                PlannedExpense.is_recurring,
            ).where(
                PlannedExpense.user_id == user_id,
                PlannedExpense.deleted_at.is_(None),
                PlannedExpense.planned_date >= m_start,
            )
        )
    ).all()
    planned = tuple(
        PlannedRow(
            planned_date=pd,
            amount=amt,
            status=str(st.value if hasattr(st, "value") else st),
            occasion_type=(str(occ.value if hasattr(occ, "value") else occ) if occ else None),
            is_recurring=bool(rec),
        )
        for pd, amt, st, occ, rec in pl_rows
    )

    return BehaviorData(
        window=window,
        base_currency=settings.base_currency,
        monthly_threshold=settings.monthly_threshold,
        monthly_income_estimate=settings.monthly_income_estimate,
        starting_balance=settings.starting_balance,
        expenses=expenses,
        incomes=incomes,
        income_sources=income_sources,
        sessions=sessions,
        receivables=receivables,
        planned=planned,
        categories=categories,
        salary_days=frozenset(salary_days),
        shopping_category_ids=shopping_ids,
    )
