"""Explainability (4b-3): defend a claim with evidence + confidence + impact.

Deterministic, no LLM. Refs:
  impact:red_days | impact:crown_days  -> day list + savings/goal impact
  relationship:<name>                  -> lending facts + recommendation (no judgement)
  category:<name>                      -> the expenses behind a category
Forecast/mood refs are reserved (4b-4 / Sprint 5).
"""

from __future__ import annotations

import calendar as _cal
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyPlan, Expense, Receivable, SavingsGoal
from app.models.enums import ReceivableStatus, SavingsGoalKind, SavingsGoalStatus
from app.schemas.advisor_chat import ChatContext
from app.schemas.explain import EvidenceItem, Explanation
from app.services import analytics_service, calendar_service, category_service, settings_service

_ZERO = Decimal("0")
_WORDS = {"high": "consistently", "medium": "often", "low": "may"}


def confidence_word(level: str) -> str | None:
    return _WORDS.get(level)


def _rel_confidence(loans: int) -> str:
    if loans >= 3:
        return "high"
    if loans == 2:
        return "medium"
    return "low" if loans == 1 else "insufficient"


def _period(session: ChatContext | None, today: date) -> tuple[date, date]:
    if session and session.period_from and session.period_to:
        return session.period_from, session.period_to
    return today.replace(day=1), today


async def _daily_goal_contribution(db: AsyncSession, user_id: uuid.UUID, day: date) -> Decimal:
    total = await db.scalar(
        select(func.coalesce(func.sum(SavingsGoal.converted_amount), 0)).where(
            SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
            SavingsGoal.status == SavingsGoalStatus.active, SavingsGoal.kind == SavingsGoalKind.monthly_target)
    ) or 0
    monthly = Decimal(total)
    if monthly == _ZERO:
        return _ZERO
    return monthly / Decimal(_cal.monthrange(day.year, day.month)[1])


def _fmt(amount: Decimal, currency: str) -> str:
    return analytics_service._fmt(amount, currency)  # noqa: SLF001


async def _explain_budget_days(db, user_id, kind, start, end, today, currency) -> Explanation:
    settings = await settings_service.get_settings(db, user_id)
    plans = {r[0]: r[1] for r in (await db.execute(
        select(DailyPlan.plan_date, DailyPlan.planned_budget).where(
            DailyPlan.user_id == user_id, DailyPlan.plan_date >= start, DailyPlan.plan_date <= end)
    )).all()}
    spent_by = await analytics_service._sum_by_day(  # noqa: SLF001
        db, Expense, Expense.expense_date, Expense.converted_amount, user_id, start, end)
    want = "over" if kind == "red_days" else "saved"

    evidence: list[EvidenceItem] = []
    impact = _ZERO
    d = start
    while d <= end:
        spent = spent_by.get(d, _ZERO)
        budget = analytics_service._budget_for(settings, plans.get(d), d)  # noqa: SLF001
        if budget is not None and calendar_service.classify(spent, budget, d, today) == want:
            diff = (spent - budget) if want == "over" else (budget - spent)
            impact += diff
            evidence.append(EvidenceItem(
                label=analytics_service._d(d),  # noqa: SLF001
                value=_fmt(spent, currency), when=d))
        d += timedelta(days=1)

    confidence = await analytics_service._span_confidence(db, user_id)  # noqa: SLF001
    if want == "over":
        claim = f"{len(evidence)} over-budget day(s) cost you {_fmt(impact, currency)}."
        daily_goal = await _daily_goal_contribution(db, user_id, start)
        why = f"That extra {_fmt(impact, currency)} reduced your savings this period."
        if daily_goal > _ZERO:
            delay = int((impact / daily_goal).quantize(Decimal("1")))
            why += f" At your current goal pace, it set your goal back roughly {delay} day(s)."
        reasoning = "Each red day is a day you spent more than that day's budget; the overage is summed here."
    else:
        claim = f"{len(evidence)} day(s) under budget saved you {_fmt(impact, currency)}."
        why = f"Those under-budget days added {_fmt(impact, currency)} toward your goals."
        reasoning = "Each crown day is a day you spent less than budget; the surplus is summed here."

    return Explanation(claim=claim, confidence=confidence, confidence_word=confidence_word(confidence),
                       reasoning=reasoning, why_it_matters=why, evidence=evidence)


async def _explain_relationship(db, user_id, name, currency) -> Explanation:
    rows = (await db.execute(
        select(Receivable).where(Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
                                 Receivable.source_name.ilike(f"%{name}%"))
    )).scalars().all()
    loans = len(rows)
    late = 0
    delays: list[int] = []
    outstanding = _ZERO
    for r in rows:
        if r.status == ReceivableStatus.received and r.received_at is not None and r.expected_date is not None:
            d = (r.received_at.date() - r.expected_date).days
            if d > 0:
                late += 1
                delays.append(d)
        elif r.status == ReceivableStatus.pending:
            outstanding += r.converted_amount
    avg_delay = round(sum(delays) / len(delays)) if delays else 0
    confidence = _rel_confidence(loans)

    if loans == 0:
        claim = f"I don’t have any lending history with {name} yet."
        why = None
    elif outstanding > _ZERO and (late >= 1 or loans >= 2):
        claim = (f"{name} still has {_fmt(outstanding, currency)} outstanding"
                 + (f" and has returned late {late} of {loans} times" if late else "")
                 + ". You may want to settle that before lending more.")
        why = "Lending more while money is still owed makes it harder to track who owes what."
    elif late == 0:
        claim = f"{name} has returned money on time {loans}/{loans} times — a reliable track record."
        why = None
    else:
        claim = f"{name} has returned late {late} of {loans} times (avg {avg_delay} days)."
        why = "Worth following up a few days before the due date."

    evidence = [
        EvidenceItem(label="Loans", value=str(loans)),
        EvidenceItem(label="Late repayments", value=str(late)),
        EvidenceItem(label="Average delay", value=f"{avg_delay} days"),
        EvidenceItem(label="Outstanding", value=_fmt(outstanding, currency)),
        EvidenceItem(label="Confidence", value=confidence),
    ]
    return Explanation(claim=claim, confidence=confidence, confidence_word=confidence_word(confidence),
                       reasoning="Based on this person's repayment history — facts only, no judgement.",
                       why_it_matters=why, evidence=evidence)


async def _explain_category(db, user_id, name, start, end, currency) -> Explanation:
    name_map = {c.name.lower(): c.id for c in await category_service.list_for_user(db, user_id)}
    cat_id = name_map.get(name.lower())
    stmt = select(Expense.expense_date, Expense.description, Expense.converted_amount).where(
        Expense.user_id == user_id, Expense.deleted_at.is_(None),
        Expense.expense_date >= start, Expense.expense_date <= end)
    stmt = stmt.where(Expense.category_id == cat_id) if cat_id else stmt.where(
        Expense.description.ilike(f"%{name}%"))
    rows = (await db.execute(stmt.order_by(Expense.converted_amount.desc()).limit(20))).all()
    items = []
    total = _ZERO
    for edate, desc, amt in rows:
        items.append(EvidenceItem(label=(desc or "Expense"), value=_fmt(Decimal(amt), currency), when=edate))
        total += Decimal(amt)
    confidence = await analytics_service._span_confidence(db, user_id)  # noqa: SLF001
    return Explanation(claim=f"{name}: {_fmt(total, currency)} across {len(items)} expense(s).",
                       confidence=confidence, confidence_word=confidence_word(confidence),
                       reasoning="These are the individual expenses behind that figure.",
                       why_it_matters=None, evidence=items)


async def explain(db: AsyncSession, user_id: uuid.UUID, *, ref: str, session: ChatContext | None) -> Explanation:
    today = await calendar_service.user_today(db, user_id)
    start, end = _period(session, today)
    currency = (await settings_service.get_settings(db, user_id)).base_currency

    head, _, arg = ref.partition(":")
    if head == "impact" and arg in ("red_days", "crown_days"):
        return await _explain_budget_days(db, user_id, arg, start, end, today, currency)
    if head == "relationship" and arg:
        return await _explain_relationship(db, user_id, arg, currency)
    if head == "category" and arg:
        return await _explain_category(db, user_id, arg, start, end, currency)
    if head == "mood":
        from app.services import mood_service
        return await mood_service.explain(db, user_id, today=today)

    return Explanation(claim="I can’t explain that yet.", confidence="insufficient", confidence_word=None,
                       reasoning="No evidence source is wired for this reference.", evidence=[])
