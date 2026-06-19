"""Calendar aggregation: month grid + single-day detail + derived day class.

Classification (over/saved/within/none) is computed from budget-vs-actual at read
time and never stored. The daily budget is the user-set value if present, else a
derived split of the monthly threshold. Markers are emitted as registry keys.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyPlan, Expense, Income, PlannedExpense, Receivable, RecurringRule, UserSettings
from app.models.enums import OccasionType, PlannedExpenseStatus, ReceivableKind, ReceivableStatus
from app.schemas.calendar import DayCell, DayDetail, MonthView
from app.schemas.expense import ExpenseRead
from app.schemas.income import IncomeRead
from app.schemas.planned_expense import PlannedExpenseRead
from app.services import settings_service

_ZERO = Decimal("0")


async def user_today(db: AsyncSession, user_id: uuid.UUID) -> date:
    """Today in the user's timezone (matches the advisor's notion of 'today')."""
    tz = await db.scalar(select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    return datetime.now(ZoneInfo(tz or "UTC")).date()


async def _settings(db: AsyncSession, user_id: uuid.UUID):
    return await settings_service.get_settings(db, user_id)


def _derived_budget(monthly_threshold: Decimal | None, day: date) -> Decimal | None:
    if monthly_threshold is None:
        return None
    days = _cal.monthrange(day.year, day.month)[1]
    return (monthly_threshold / Decimal(days)).quantize(Decimal("0.0001"))


def classify(spent: Decimal, budget: Decimal | None, day: date, today: date) -> str:
    """over | saved | within | none. Future days and budget-less days are 'none'."""
    if day > today or budget is None:
        return "none"
    if spent > budget:
        return "over"
    if spent == _ZERO:
        return "none"  # no activity isn't a "saved" day
    if spent < budget:
        return "saved"
    return "within"  # spent == budget


# A planner event renders its OWN emoji on the calendar (🎂 birthday, ✈️ trip,
# ❤️ outing …) — never a generic 📅. A plain planned expense with no occasion
# still falls back to the generic event marker.
_OCCASION_MARKER: dict[OccasionType, str] = {
    OccasionType.outing: "outing",
    OccasionType.shopping: "expense_shopping",
    OccasionType.entertainment: "expense_entertainment",
    OccasionType.travel: "trip",
    OccasionType.date: "outing",
    OccasionType.birthday: "birthday",
    OccasionType.festival: "festival",
    OccasionType.vacation: "trip",
    OccasionType.celebration: "celebration",
    OccasionType.anniversary: "anniversary",
    OccasionType.graduation: "graduation",
    OccasionType.study: "study",
    OccasionType.medical: "expense_medical",
    OccasionType.gaming: "expense_entertainment",
    OccasionType.food: "expense_food",
    OccasionType.custom: "event",
}


def _event_marker(occasion: OccasionType | None) -> str:
    return _OCCASION_MARKER.get(occasion, "event") if occasion is not None else "event"


def markers_for(classification: str, income: Decimal, event_markers: list[str]) -> list[str]:
    markers: list[str] = []
    if classification == "over":
        markers.append("budget_over")
    elif classification == "saved":
        markers.append("budget_saved")
    elif classification == "within":
        markers.append("budget_within")
    if income > _ZERO:
        markers.append("income")
    for key in event_markers:
        if key not in markers:
            markers.append(key)
    return markers


# recurring_rule type -> marker key
_RULE_MARKER = {
    "subscription": "subscription",
    "emi": "emi",
    "loan": "emi",
    "bill": "bill",
    "insurance": "insurance",
    "borrowed": "emi",
}


def _enum_val(v) -> str:
    return v.value if hasattr(v, "value") else str(v)


async def _extra_markers(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date, today: date
) -> dict[date, list[str]]:
    """Per-day markers materialized from recurring_rules + receivables.
    ``start``/``end`` are within a single month (month grid or one day)."""
    out: dict[date, list[str]] = {}

    def add(day: date, key: str) -> None:
        bucket = out.setdefault(day, [])
        if key not in bucket:
            bucket.append(key)

    def day_in_month(day_n: int) -> date | None:
        try:
            return date(start.year, start.month, day_n)
        except ValueError:
            return None  # e.g. day 31 in a 30-day month

    rules = (
        await db.execute(
            select(RecurringRule.recurrence_day, RecurringRule.rule_type, RecurringRule.start_date).where(
                RecurringRule.user_id == user_id,
                RecurringRule.deleted_at.is_(None),
                RecurringRule.is_active.is_(True),
            )
        )
    ).all()
    for recurrence_day, rule_type, rule_start in rules:
        d = day_in_month(recurrence_day)
        if d is None or d < start or d > end or (rule_start and d < rule_start):
            continue
        add(d, _RULE_MARKER.get(_enum_val(rule_type), "bill"))

    receivables = (
        await db.execute(
            select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None))
        )
    ).scalars().all()
    for r in receivables:
        if r.status == ReceivableStatus.received and r.received_at is not None:
            rd = r.received_at.date()
            if start <= rd <= end:
                add(rd, "returned")
        elif r.status == ReceivableStatus.pending:
            if r.kind == ReceivableKind.one_time and r.expected_date is not None and start <= r.expected_date <= end:
                add(r.expected_date, "repay_overdue" if r.expected_date < today else "lent")
            elif r.kind == ReceivableKind.recurring and r.recurrence_day is not None:
                d = day_in_month(r.recurrence_day)
                if d is not None and start <= d <= end:
                    add(d, "lent")
    return out


async def _sum_by_day(db, model, date_col, amount_col, user_id, start, end) -> dict[date, Decimal]:
    result = await db.execute(
        select(date_col, func.coalesce(func.sum(amount_col), 0))
        .where(model.user_id == user_id, model.deleted_at.is_(None), date_col >= start, date_col <= end)
        .group_by(date_col)
    )
    return {row[0]: Decimal(row[1]) for row in result.all()}


async def month_view(db: AsyncSession, user_id: uuid.UUID, year: int, month: int, *, today: date) -> MonthView:
    settings = await _settings(db, user_id)
    last_day = _cal.monthrange(year, month)[1]
    start, end = date(year, month, 1), date(year, month, last_day)

    spent_by = await _sum_by_day(db, Expense, Expense.expense_date, Expense.converted_amount, user_id, start, end)
    income_by = await _sum_by_day(db, Income, Income.received_date, Income.converted_amount, user_id, start, end)

    ev_result = await db.execute(
        select(PlannedExpense.planned_date, PlannedExpense.occasion_type).where(
            PlannedExpense.user_id == user_id,
            PlannedExpense.deleted_at.is_(None),
            PlannedExpense.status != PlannedExpenseStatus.cancelled,
            PlannedExpense.planned_date >= start,
            PlannedExpense.planned_date <= end,
        )
    )
    events_by: dict[date, int] = {}
    event_markers_by: dict[date, list[str]] = {}
    for planned_date, occ in ev_result.all():
        events_by[planned_date] = events_by.get(planned_date, 0) + 1
        bucket = event_markers_by.setdefault(planned_date, [])
        key = _event_marker(occ)
        if key not in bucket:
            bucket.append(key)

    plan_result = await db.execute(
        select(DailyPlan.plan_date, DailyPlan.planned_budget).where(
            DailyPlan.user_id == user_id, DailyPlan.plan_date >= start, DailyPlan.plan_date <= end
        )
    )
    budget_by = {row[0]: row[1] for row in plan_result.all()}
    extra = await _extra_markers(db, user_id, start, end, today)

    days: list[DayCell] = []
    for d in (date(year, month, n) for n in range(1, last_day + 1)):
        spent = spent_by.get(d, _ZERO)
        income = income_by.get(d, _ZERO)
        event_count = events_by.get(d, 0)
        planned_budget = budget_by.get(d)
        effective = planned_budget if planned_budget is not None else _derived_budget(settings.monthly_threshold, d)
        cls = classify(spent, effective, d, today)
        days.append(
            DayCell(
                date=d,
                spent=spent,
                income=income,
                event_count=event_count,
                planned_budget=planned_budget,
                effective_budget=effective,
                classification=cls,
                markers=markers_for(cls, income, event_markers_by.get(d, [])) + extra.get(d, []),
            )
        )

    return MonthView(year=year, month=month, base_currency=settings.base_currency, days=days)


async def day_detail(db: AsyncSession, user_id: uuid.UUID, day: date, *, today: date) -> DayDetail:
    settings = await _settings(db, user_id)

    exp_rows = (
        await db.execute(
            select(Expense)
            .where(Expense.user_id == user_id, Expense.deleted_at.is_(None), Expense.expense_date == day)
            .order_by(Expense.created_at.desc())
        )
    ).scalars().all()
    inc_rows = (
        await db.execute(
            select(Income)
            .where(Income.user_id == user_id, Income.deleted_at.is_(None), Income.received_date == day)
            .order_by(Income.created_at.desc())
        )
    ).scalars().all()
    ev_rows = (
        await db.execute(
            select(PlannedExpense)
            .where(
                PlannedExpense.user_id == user_id,
                PlannedExpense.deleted_at.is_(None),
                PlannedExpense.status != PlannedExpenseStatus.cancelled,
                PlannedExpense.planned_date == day,
            )
            .order_by(PlannedExpense.created_at.desc())
        )
    ).scalars().all()

    spent = sum((e.converted_amount for e in exp_rows), _ZERO)
    income = sum((i.converted_amount for i in inc_rows), _ZERO)

    plan = (
        await db.execute(
            select(DailyPlan).where(DailyPlan.user_id == user_id, DailyPlan.plan_date == day)
        )
    ).scalar_one_or_none()
    planned_budget = plan.planned_budget if plan else None
    effective = planned_budget if planned_budget is not None else _derived_budget(settings.monthly_threshold, day)
    remaining = (effective - spent) if effective is not None else None
    cls = classify(spent, effective, day, today)
    extra = await _extra_markers(db, user_id, day, day, today)

    event_markers: list[str] = []
    for e in ev_rows:
        key = _event_marker(e.occasion_type)
        if key not in event_markers:
            event_markers.append(key)

    return DayDetail(
        date=day,
        base_currency=settings.base_currency,
        planned_budget=planned_budget,
        effective_budget=effective,
        spent=spent,
        income=income,
        remaining=remaining,
        classification=cls,
        markers=markers_for(cls, income, event_markers) + extra.get(day, []),
        overspend_reason=plan.overspend_reason if plan else None,
        expenses=[ExpenseRead.model_validate(e) for e in exp_rows],
        incomes=[IncomeRead.model_validate(i) for i in inc_rows],
        events=[PlannedExpenseRead.model_validate(e) for e in ev_rows],
    )
