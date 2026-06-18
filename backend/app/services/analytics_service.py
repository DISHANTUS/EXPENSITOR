"""Analytics: resolve a period, then build a ReportSession (graph + summary +
Beginning/Middle/End story + timeline hooks + confidence). Reuses the calendar
classification/budget logic so a 'red day' means the same thing everywhere.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, DailyPlan, Expense, Income, Receivable, RecurringRule, SavingsGoal
from app.models.enums import ReceivableKind, ReceivableStatus
from app.schemas.analytics import (
    CategoryDelta,
    DrilldownItem,
    DrilldownResult,
    GraphPoint,
    GraphSeries,
    PeriodDelta,
    ReportSession,
    ReportStory,
    ReportSummary,
    TimelineEvent,
)
from app.services import calendar_service, category_service, settings_service

_ZERO = Decimal("0")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CZK": "Kč"}


def _d(day: date) -> str:
    return f"{day.day} {_MONTHS[day.month - 1]}"


def _fmt(amount: Decimal, currency: str) -> str:
    sym = _SYMBOLS.get(currency.upper())
    n = f"{int(amount.quantize(Decimal('1'))):,}"
    return f"{sym}{n}" if sym else f"{currency} {n}"


def resolve_period(kind: str, ref: str, today: date) -> tuple[date, date, str, str]:
    """(start, end, label, granularity) for kind in {week, month}, ref in {this, last}."""
    if kind == "week":
        monday = today - timedelta(days=today.weekday())
        if ref == "this":
            start, end = monday, today
        else:
            start, end = monday - timedelta(days=7), monday - timedelta(days=1)
        return start, end, f"{_d(start)}–{_d(end)}", "day"
    first = today.replace(day=1)
    if ref == "this":
        start, end = first, today
    else:
        prev_last = first - timedelta(days=1)
        start, end = prev_last.replace(day=1), prev_last
    return start, end, f"{_MONTHS[start.month - 1]} {start.year}", "week"


async def _sum_by_day(db, model, date_col, amount_col, user_id, start, end) -> dict[date, Decimal]:
    rows = await db.execute(
        select(date_col, func.coalesce(func.sum(amount_col), 0))
        .where(model.user_id == user_id, model.deleted_at.is_(None), date_col >= start, date_col <= end)
        .group_by(date_col)
    )
    return {r[0]: Decimal(r[1]) for r in rows.all()}


def _budget_for(settings, plan_budget: Decimal | None, day: date) -> Decimal | None:
    if plan_budget is not None:
        return plan_budget
    return calendar_service._derived_budget(settings.monthly_threshold, day)  # noqa: SLF001


def _confidence(days_with_data: int) -> str:
    if days_with_data == 0:
        return "insufficient"
    if days_with_data >= 5:
        return "high"
    if days_with_data >= 2:
        return "medium"
    return "low"


def _series(spent_by, income_by, saved_by, start, end, granularity) -> GraphSeries:
    points: list[GraphPoint] = []
    if granularity == "day":
        d = start
        while d <= end:
            points.append(GraphPoint(label=_d(d), spent=spent_by.get(d, _ZERO),
                                     income=income_by.get(d, _ZERO), saved=saved_by.get(d, _ZERO)))
            d += timedelta(days=1)
    else:  # weekly buckets
        d, wk = start, 1
        while d <= end:
            bucket_end = min(d + timedelta(days=6), end)
            s = i = sv = _ZERO
            cur = d
            while cur <= bucket_end:
                s += spent_by.get(cur, _ZERO)
                i += income_by.get(cur, _ZERO)
                sv += saved_by.get(cur, _ZERO)
                cur += timedelta(days=1)
            points.append(GraphPoint(label=f"Wk {wk}", spent=s, income=i, saved=sv))
            d, wk = bucket_end + timedelta(days=1), wk + 1
    return GraphSeries(granularity=granularity, points=points)


async def _timeline(db, user_id, start, end, today) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    goals = (await db.execute(
        select(SavingsGoal.name, SavingsGoal.start_date).where(
            SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
            SavingsGoal.start_date >= start, SavingsGoal.start_date <= end)
    )).all()
    for name, sdate in goals:
        events.append(TimelineEvent(date=sdate, label=f"Started {name}", kind="goal"))

    recs = (await db.execute(
        select(Receivable.source_name, Receivable.expected_date).where(
            Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
            Receivable.status == ReceivableStatus.pending, Receivable.kind == ReceivableKind.one_time,
            Receivable.expected_date.is_not(None), Receivable.expected_date >= start,
            Receivable.expected_date <= end, Receivable.expected_date < today)
    )).all()
    for source_name, edate in recs:
        events.append(TimelineEvent(date=edate, label=f"{source_name} loan overdue", kind="receivable_overdue"))

    # Largest single expense in the period (aggressive timeline collection).
    biggest = (await db.execute(
        select(Expense.expense_date, Expense.description, Expense.converted_amount).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= start, Expense.expense_date <= end)
        .order_by(Expense.converted_amount.desc()).limit(1)
    )).first()
    if biggest is not None:
        bdate, bdesc, bamt = biggest
        events.append(TimelineEvent(date=bdate, label=f"Largest expense: {bdesc or 'expense'}", kind="big_expense"))
    return events


def _story(label, currency, spent_by, start, end, total_spent, total_income, saved, red, crown) -> ReportStory:
    mid = start + (end - start) // 2
    first = sum((v for d, v in spent_by.items() if d <= mid), _ZERO)
    second = sum((v for d, v in spent_by.items() if d > mid), _ZERO)
    if second > first * Decimal("1.15"):
        middle = "Spending picked up in the second half of the period."
    elif second < first * Decimal("0.85"):
        middle = "You eased off on spending in the second half."
    else:
        middle = "Your spending stayed fairly steady throughout."

    beginning = (f"Over {label} you brought in {_fmt(total_income, currency)} and spent "
                 f"{_fmt(total_spent, currency)}.")
    if red == 0 and crown > 0:
        end_line = f"A clean run — {crown} day(s) under budget and {_fmt(saved, currency)} saved. Nice work."
    elif red > 0:
        end_line = (f"There were {red} over-budget day(s), but {crown} day(s) came in under, "
                    f"saving {_fmt(saved, currency)}.")
    else:
        end_line = f"You stayed close to plan, saving {_fmt(saved, currency)}."
    return ReportStory(beginning=beginning, middle=middle, end=end_line)


async def build_report(
    db: AsyncSession, user_id: uuid.UUID, *, kind: str, start: date, end: date, label: str,
    granularity: str, today: date,
) -> ReportSession:
    settings = await settings_service.get_settings(db, user_id)
    currency = settings.base_currency

    spent_by = await _sum_by_day(db, Expense, Expense.expense_date, Expense.converted_amount, user_id, start, end)
    income_by = await _sum_by_day(db, Income, Income.received_date, Income.converted_amount, user_id, start, end)
    plan_rows = (await db.execute(
        select(DailyPlan.plan_date, DailyPlan.planned_budget).where(
            DailyPlan.user_id == user_id, DailyPlan.plan_date >= start, DailyPlan.plan_date <= end)
    )).all()
    budget_by = {r[0]: r[1] for r in plan_rows}

    red = crown = days_with_data = 0
    saved = _ZERO
    saved_by: dict[date, Decimal] = {}
    d = start
    while d <= end:
        spent = spent_by.get(d, _ZERO)
        income = income_by.get(d, _ZERO)
        if spent > _ZERO or income > _ZERO:
            days_with_data += 1
        budget = _budget_for(settings, budget_by.get(d), d)
        cls = calendar_service.classify(spent, budget, d, today)
        if cls == "over":
            red += 1
        elif cls == "saved":
            crown += 1
            if budget is not None:
                surplus = budget - spent
                saved += surplus
                saved_by[d] = surplus
        d += timedelta(days=1)

    total_spent = sum(spent_by.values(), _ZERO)
    total_income = sum(income_by.values(), _ZERO)

    return ReportSession(
        kind=kind, period_from=start, period_to=end, period_label=label, currency=currency,
        series=_series(spent_by, income_by, saved_by, start, end, granularity),
        summary=ReportSummary(currency=currency, total_spent=total_spent, total_income=total_income,
                              saved=saved, red_days=red, crown_days=crown),
        story=_story(label, currency, spent_by, start, end, total_spent, total_income, saved, red, crown),
        timeline_events=await _timeline(db, user_id, start, end, today),
        confidence=_confidence(days_with_data),
    )


# --- 4b-2: comparisons + drilldowns ----------------------------------------

def _pct(cur: Decimal, prev: Decimal) -> float | None:
    if prev == _ZERO:
        return None
    return round(float((cur - prev) / prev * 100), 1)


async def _category_sums(db: AsyncSession, user_id: uuid.UUID, start: date, end: date) -> dict[str, Decimal]:
    name_map = {c.id: c.name for c in await category_service.list_for_user(db, user_id)}
    rows = await db.execute(
        select(Expense.category_id, func.coalesce(func.sum(Expense.converted_amount), 0))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None),
               Expense.expense_date >= start, Expense.expense_date <= end)
        .group_by(Expense.category_id)
    )
    out: dict[str, Decimal] = {}
    for cid, total in rows.all():
        label = name_map.get(cid, "Uncategorized") if cid else "Uncategorized"
        out[label] = out.get(label, _ZERO) + Decimal(total)
    return out


def _category_deltas(cur: dict[str, Decimal], prev: dict[str, Decimal]) -> list[CategoryDelta]:
    deltas = [
        CategoryDelta(label=label, current=cur.get(label, _ZERO), previous=prev.get(label, _ZERO),
                      change_pct=_pct(cur.get(label, _ZERO), prev.get(label, _ZERO)))
        for label in (cur.keys() | prev.keys())
    ]
    deltas.sort(key=lambda d: abs(d.current - d.previous), reverse=True)
    return deltas[:6]


async def _span_confidence(db: AsyncSession, user_id: uuid.UUID) -> str:
    months = await db.scalar(
        select(func.count(func.distinct(func.date_trunc("month", Expense.expense_date))))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
    ) or 0
    if months >= 6:
        return "high"
    if months >= 2:
        return "medium"
    return "low" if months >= 1 else "insufficient"


def _comparison_story(cur_label, prev_label, cur: ReportSummary, prev: ReportSummary,
                      delta: PeriodDelta, currency) -> ReportStory:
    beginning = (f"Compared to {prev_label}, you spent {_fmt(cur.total_spent, currency)} vs "
                 f"{_fmt(prev.total_spent, currency)}.")
    bits = []
    if delta.biggest_increase and delta.biggest_increase.change_pct:
        bits.append(f"{delta.biggest_increase.label} rose {abs(delta.biggest_increase.change_pct):.0f}%")
    if delta.biggest_decrease and delta.biggest_decrease.change_pct:
        bits.append(f"{delta.biggest_decrease.label} fell {abs(delta.biggest_decrease.change_pct):.0f}%")
    middle = (", ".join(bits) + ".") if bits else "Spending was broadly similar across categories."
    if delta.saved_change_pct is None:
        end_line = f"You saved {_fmt(cur.saved, currency)} this period."
    elif delta.saved_change_pct >= 0:
        end_line = f"Savings improved {delta.saved_change_pct:.0f}% — nice."
    else:
        end_line = f"Savings dropped {abs(delta.saved_change_pct):.0f}% versus {prev_label}."
    return ReportStory(beginning=beginning, middle=middle[:1].upper() + middle[1:], end=end_line)


def _prev_period(kind: str, cur_start: date) -> tuple[date, date, str]:
    prev_end = cur_start - timedelta(days=1)
    if kind == "week":
        prev_start = prev_end - timedelta(days=6)
        return prev_start, prev_end, f"{_d(prev_start)}–{_d(prev_end)}"
    prev_start = prev_end.replace(day=1)
    return prev_start, prev_end, f"{_MONTHS[prev_start.month - 1]} {prev_start.year}"


async def build_comparison(db: AsyncSession, user_id: uuid.UUID, *, kind: str, ref: str, today: date) -> ReportSession:
    cur_start, cur_end, cur_label, gran = resolve_period(kind, ref, today)
    prev_start, prev_end, prev_label = _prev_period(kind, cur_start)

    current = await build_report(db, user_id, kind=kind, start=cur_start, end=cur_end, label=cur_label,
                                 granularity=gran, today=today)
    previous = await build_report(db, user_id, kind=kind, start=prev_start, end=prev_end, label=prev_label,
                                  granularity=gran, today=today)
    cats = _category_deltas(await _category_sums(db, user_id, cur_start, cur_end),
                            await _category_sums(db, user_id, prev_start, prev_end))
    ups = [c for c in cats if c.current > c.previous]
    downs = [c for c in cats if c.previous > c.current]
    delta = PeriodDelta(
        spent_change_pct=_pct(current.summary.total_spent, previous.summary.total_spent),
        income_change_pct=_pct(current.summary.total_income, previous.summary.total_income),
        saved_change_pct=_pct(current.summary.saved, previous.summary.saved),
        biggest_increase=max(ups, key=lambda c: c.current - c.previous, default=None),
        biggest_decrease=max(downs, key=lambda c: c.previous - c.current, default=None),
        categories=cats,
    )
    return current.model_copy(update={
        "comparison_from": prev_start, "comparison_to": prev_end, "delta": delta,
        "story": _comparison_story(cur_label, prev_label, current.summary, previous.summary, delta, current.currency),
        "confidence": await _span_confidence(db, user_id),
    })


async def drilldown(db: AsyncSession, user_id: uuid.UUID, *, kind: str, arg: str | None,
                    start: date, end: date, today: date) -> DrilldownResult:
    settings = await settings_service.get_settings(db, user_id)
    currency = settings.base_currency

    if kind in ("red_days", "crown_days"):
        want = "over" if kind == "red_days" else "saved"
        plans = {r[0]: (r[1], r[2]) for r in (await db.execute(
            select(DailyPlan.plan_date, DailyPlan.planned_budget, DailyPlan.overspend_reason)
            .where(DailyPlan.user_id == user_id, DailyPlan.plan_date >= start, DailyPlan.plan_date <= end)
        )).all()}
        spent_by = await _sum_by_day(db, Expense, Expense.expense_date, Expense.converted_amount, user_id, start, end)
        items: list[DrilldownItem] = []
        d = start
        while d <= end:
            spent = spent_by.get(d, _ZERO)
            pb, reason = plans.get(d, (None, None))
            budget = _budget_for(settings, pb, d)
            if calendar_service.classify(spent, budget, d, today) == want:
                items.append(DrilldownItem(label=_d(d), when=d, amount=spent, currency=currency,
                                           subtitle=reason if kind == "red_days" else "under budget"))
            d += timedelta(days=1)
        noun = "over-budget" if kind == "red_days" else "money-saved"
        title = "Red days" if kind == "red_days" else "Crown days"
        return DrilldownResult(kind=kind, title=title, currency=currency, items=items,
                               explanation=f"{len(items)} {noun} day(s) in this period.")

    if kind in ("subscription", "emi", "loan", "bill", "insurance"):
        rows = (await db.execute(
            select(RecurringRule).where(RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None),
                                        RecurringRule.is_active.is_(True),
                                        RecurringRule.rule_type == kind).order_by(RecurringRule.recurrence_day)
        )).scalars().all()
        items = [DrilldownItem(label=r.label, amount=r.converted_amount, currency=currency,
                               subtitle=f"every month on day {r.recurrence_day}") for r in rows]
        total = sum((r.converted_amount for r in rows), _ZERO)
        return DrilldownResult(kind=kind, title=f"{kind.capitalize()}s", currency=currency, total=total,
                               items=items, explanation=f"{len(items)} active {kind}(s), {_fmt(total, currency)}/month.")

    if kind == "person":
        rows = (await db.execute(
            select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
                                     Receivable.source_name.ilike(f"%{arg or ''}%"))
            .order_by(Receivable.expected_date)
        )).scalars().all()
        items = [DrilldownItem(label=r.title, amount=r.converted_amount, currency=currency,
                               when=r.expected_date, subtitle=r.status.value) for r in rows]
        total = sum((r.converted_amount for r in rows), _ZERO)
        return DrilldownResult(kind=kind, title=f"Money with {arg}", currency=currency, total=total,
                               items=items, explanation=f"{len(items)} record(s) involving {arg}.")

    term = arg or ""
    rows = (await db.execute(
        select(Expense.expense_date, Expense.description, Expense.converted_amount)
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None),
               Expense.expense_date >= start, Expense.expense_date <= end,
               Expense.description.ilike(f"%{term}%"))
        .order_by(Expense.expense_date.desc()).limit(50)
    )).all()
    items = [DrilldownItem(label=(desc or "Expense"), amount=amt, currency=currency, when=edate)
             for edate, desc, amt in rows]
    total = sum((i.amount or _ZERO for i in items), _ZERO)
    return DrilldownResult(kind="keyword", title=f"“{term}” spending", currency=currency, total=total,
                           items=items, explanation=f"{len(items)} expense(s) matching “{term}”, {_fmt(total, currency)}.")
