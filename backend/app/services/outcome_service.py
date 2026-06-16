"""Outcome service (Phase E): record user-reported outcomes, lazily DERIVE
objective outcomes on read (no workers), list them, and compute per-lever
effectiveness. Evidence-only — never fabricates; missing -> unknown/absent.

Derivation is idempotent (dedup by subject/lever + period_month). The advisor
layer consumes outcomes for ordering/annotations only — never to change facts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.outcomes import build_effectiveness, types as T
from app.intelligence.outcomes.types import classify_circumstance
from app.models import (
    BudgetSession,
    Category,
    Expense,
    Income,
    Outcome,
    PlannedExpense,
    RecommendationFeedback,
    SavingsGoal,
    SessionExpense,
    UserSettings,
)
from app.models.enums import (
    BudgetSessionStatus,
    PlannedExpenseStatus,
    RecommendationAction,
    SavingsGoalKind,
    SavingsGoalStatus,
)
from app.schemas.outcome import OutcomeReportIn
from app.services import projection_service

_REDUCE_SUCCESS, _REDUCE_PARTIAL = Decimal("0.15"), Decimal("0.01")   # share reduced vs baseline


async def _today(db: AsyncSession, user_id: uuid.UUID) -> date:
    tz = await db.scalar(select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo(tz or "UTC")).date()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _months_back(today: date, n: int) -> list[tuple[int, int]]:
    out = []
    for i in range(1, n + 1):
        idx = today.month - 1 - i
        out.append((today.year + (idx // 12), idx % 12 + 1))
    return out


# --- record (user-reported) -------------------------------------------------
async def record(db: AsyncSession, user_id: uuid.UUID, data: OutcomeReportIn, *, today: date | None = None) -> Outcome:
    data.validate_enums()
    today = today or await _today(db, user_id)
    variance = None
    if data.expected_value is not None and data.actual_value is not None:
        variance = data.actual_value - data.expected_value
    row = Outcome(
        user_id=user_id, kind=data.kind, subject_type=data.subject_type, subject_id=data.subject_id,
        lever_key=data.lever_key, category_id=data.category_id, expected_value=data.expected_value,
        actual_value=data.actual_value, variance=variance, outcome=data.outcome,
        outcome_reason=data.outcome_reason, circumstance=classify_circumstance(data.outcome_reason),
        source=T.USER_REPORTED, period_month=today.replace(day=1), evaluated_at=_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# --- lazy derivation (objective evidence only) ------------------------------
async def _existing(db: AsyncSession, user_id: uuid.UUID) -> tuple[set, set]:
    rows = (await db.execute(
        select(Outcome.kind, Outcome.subject_id, Outcome.lever_key, Outcome.period_month).where(
            Outcome.user_id == user_id, Outcome.source == T.DERIVED, Outcome.deleted_at.is_(None)))).all()
    by_subject = {(k, str(sid), pm.isoformat() if pm else None) for k, sid, _lv, pm in rows if sid}
    by_lever = {(k, lv, pm.isoformat() if pm else None) for k, _sid, lv, pm in rows if lv}
    return by_subject, by_lever


async def sync(db: AsyncSession, user_id: uuid.UUID, today: date) -> int:
    by_subject, by_lever = await _existing(db, user_id)
    added = 0

    # --- budget sessions (PLAN) ---
    sess = (await db.execute(select(BudgetSession.id, BudgetSession.converted_amount, BudgetSession.ended_at).where(
        BudgetSession.user_id == user_id, BudgetSession.deleted_at.is_(None),
        BudgetSession.status == BudgetSessionStatus.completed))).all()
    sids = [s[0] for s in sess]
    spent: dict[uuid.UUID, Decimal] = {}
    if sids:
        srows = (await db.execute(
            select(SessionExpense.session_id, func.coalesce(func.sum(Expense.converted_amount), 0))
            .join(Expense, Expense.id == SessionExpense.expense_id)
            .where(SessionExpense.session_id.in_(sids), Expense.deleted_at.is_(None))
            .group_by(SessionExpense.session_id))).all()
        spent = {sid: Decimal(t) for sid, t in srows}
    for sid, budget, ended in sess:
        if ended is None:
            continue
        month = ended.date().replace(day=1)
        if (T.PLAN, str(sid), month.isoformat()) in by_subject:
            continue
        sp = spent.get(sid, Decimal("0"))
        db.add(Outcome(user_id=user_id, kind=T.PLAN, subject_type="budget_session", subject_id=sid,
                       expected_value=budget, actual_value=sp, variance=budget - sp,
                       outcome=T.SUCCESS if sp <= budget else T.FAILED, source=T.DERIVED,
                       period_month=month, evaluated_at=_now()))
        added += 1

    # --- planned expenses (PLAN) ---
    pes = (await db.execute(select(PlannedExpense.id, PlannedExpense.status, PlannedExpense.planned_date,
                                   PlannedExpense.converted_amount).where(
        PlannedExpense.user_id == user_id, PlannedExpense.deleted_at.is_(None),
        PlannedExpense.planned_date <= today,
        PlannedExpense.status.in_([PlannedExpenseStatus.completed, PlannedExpenseStatus.cancelled])))).all()
    for pid, status, pdate, amt in pes:
        month = pdate.replace(day=1)
        if (T.PLAN, str(pid), month.isoformat()) in by_subject:
            continue
        outcome = T.SUCCESS if status == PlannedExpenseStatus.completed else T.ABANDONED
        db.add(Outcome(user_id=user_id, kind=T.PLAN, subject_type="planned_expense", subject_id=pid,
                       actual_value=amt, outcome=outcome, source=T.DERIVED,
                       period_month=month, evaluated_at=_now()))
        added += 1

    # --- goals (GOAL) ---
    added += await _derive_goals(db, user_id, today, by_subject)
    # --- category-reduction recommendations (RECOMMENDATION) ---
    added += await _derive_category_reductions(db, user_id, today, by_lever)

    if added:
        await db.commit()
    return added


async def _monthly_net(db: AsyncSession, user_id: uuid.UUID) -> dict[tuple[int, int], Decimal]:
    inc = (await db.execute(select(extract("year", Income.received_date), extract("month", Income.received_date),
                                   func.coalesce(func.sum(Income.converted_amount), 0)).where(
        Income.user_id == user_id, Income.deleted_at.is_(None)).group_by(
        extract("year", Income.received_date), extract("month", Income.received_date)))).all()
    exp = (await db.execute(select(extract("year", Expense.expense_date), extract("month", Expense.expense_date),
                                   func.coalesce(func.sum(Expense.converted_amount), 0)).where(
        Expense.user_id == user_id, Expense.deleted_at.is_(None)).group_by(
        extract("year", Expense.expense_date), extract("month", Expense.expense_date)))).all()
    net: dict[tuple[int, int], Decimal] = {}
    for y, m, t in inc:
        net[(int(y), int(m))] = net.get((int(y), int(m)), Decimal("0")) + Decimal(t)
    for y, m, t in exp:
        net[(int(y), int(m))] = net.get((int(y), int(m)), Decimal("0")) - Decimal(t)
    return net


async def _derive_goals(db, user_id, today, by_subject) -> int:
    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status.in_([SavingsGoalStatus.active, SavingsGoalStatus.completed])))).scalars().all()
    if not goals:
        return 0
    net = await _monthly_net(db, user_id)
    added = 0
    current_balance = None
    for g in goals:
        if g.kind == SavingsGoalKind.monthly_target:
            for (y, m) in _months_back(today, 12):
                month = date(y, m, 1)
                if g.start_date.replace(day=1) > month or (T.GOAL, str(g.id), month.isoformat()) in by_subject:
                    continue
                got = net.get((y, m), Decimal("0"))
                db.add(Outcome(user_id=user_id, kind=T.GOAL, subject_type="savings_goal", subject_id=g.id,
                               expected_value=g.converted_amount, actual_value=got, variance=got - g.converted_amount,
                               outcome=T.SUCCESS if got >= g.converted_amount else T.MISSED, source=T.DERIVED,
                               metric="net_savings", base_currency=g.base_currency, period_month=month,
                               evaluated_at=_now()))
                added += 1
        elif g.kind == SavingsGoalKind.custom_goal and g.target_date is not None and g.target_date < today:
            month = g.target_date.replace(day=1)
            if (T.GOAL, str(g.id), month.isoformat()) in by_subject:
                continue
            if current_balance is None:
                current_balance = (await projection_service.get_scenario(db, user_id, today=today)).current_balance
            db.add(Outcome(user_id=user_id, kind=T.GOAL, subject_type="savings_goal", subject_id=g.id,
                           expected_value=g.converted_amount, actual_value=current_balance,
                           variance=current_balance - g.converted_amount,
                           outcome=T.SUCCESS if current_balance >= g.converted_amount else T.MISSED,
                           source=T.DERIVED, metric="goal_balance", base_currency=g.base_currency,
                           period_month=month, evaluated_at=_now()))
            added += 1
    return added


def _norm(text: str) -> str:
    return text.lower().replace("reduce_", "").replace("reduce ", "").replace("_", " ").strip()


async def _derive_category_reductions(db, user_id, today, by_lever) -> int:
    accepted = (await db.execute(select(RecommendationFeedback.lever_key, RecommendationFeedback.created_at).where(
        RecommendationFeedback.user_id == user_id,
        RecommendationFeedback.action == RecommendationAction.accepted))).all()
    if not accepted:
        return 0
    cat_rows = (await db.execute(select(Category.id, Category.name).where(
        (Category.user_id == user_id) | (Category.user_id.is_(None))))).all()
    by_name = {_norm(name): cid for cid, name in cat_rows}
    added = 0
    for lever, accepted_at in accepted:
        cid = by_name.get(_norm(lever or ""))
        if cid is None:
            continue
        acc_month = accepted_at.date().replace(day=1)
        after = (acc_month.year + (acc_month.month // 12), acc_month.month % 12 + 1)
        after_month = date(after[0], after[1], 1)
        if after_month >= today.replace(day=1) or (T.RECOMMENDATION, lever, after_month.isoformat()) in by_lever:
            continue
        spend = await _category_monthly_spend(db, user_id, cid)
        baseline_months = _months_back(acc_month.replace(day=15), 3)   # 3 months before acceptance
        prior = [spend.get(ym, Decimal("0")) for ym in baseline_months]
        baseline = sum(prior, Decimal("0")) / len(prior) if prior else Decimal("0")
        actual = spend.get(after, Decimal("0"))
        if baseline <= 0:
            continue
        reduced_share = (baseline - actual) / baseline
        outcome = (T.SUCCESS if reduced_share >= _REDUCE_SUCCESS
                   else T.PARTIAL if reduced_share >= _REDUCE_PARTIAL else T.FAILED)
        db.add(Outcome(user_id=user_id, kind=T.RECOMMENDATION, subject_type="recommendation_lever",
                       lever_key=lever, category_id=cid, expected_value=baseline, actual_value=actual,
                       variance=actual - baseline, outcome=outcome, source=T.DERIVED,
                       metric="monthly_category_spend", period_month=after_month, evaluated_at=_now()))
        added += 1
    return added


async def _category_monthly_spend(db, user_id, category_id) -> dict[tuple[int, int], Decimal]:
    rows = (await db.execute(select(extract("year", Expense.expense_date), extract("month", Expense.expense_date),
                                    func.coalesce(func.sum(Expense.converted_amount), 0)).where(
        Expense.user_id == user_id, Expense.deleted_at.is_(None), Expense.category_id == category_id).group_by(
        extract("year", Expense.expense_date), extract("month", Expense.expense_date)))).all()
    return {(int(y), int(m)): Decimal(t) for y, m, t in rows}


# --- list + effectiveness ---------------------------------------------------
async def list_outcomes(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> list[dict[str, Any]]:
    today = today or await _today(db, user_id)
    await sync(db, user_id, today)
    rows = (await db.execute(select(Outcome).where(Outcome.user_id == user_id, Outcome.deleted_at.is_(None))
                             .order_by(Outcome.evaluated_at.desc()))).scalars().all()
    return [_outcome_dict(o) for o in rows]


def _outcome_dict(o: Outcome) -> dict[str, Any]:
    return {"id": str(o.id), "kind": o.kind, "subject_type": o.subject_type,
            "subject_id": str(o.subject_id) if o.subject_id else None, "lever_key": o.lever_key,
            "outcome": o.outcome, "outcome_reason": o.outcome_reason, "circumstance": o.circumstance,
            "source": o.source, "expected_value": str(o.expected_value) if o.expected_value is not None else None,
            "actual_value": str(o.actual_value) if o.actual_value is not None else None,
            "period_month": o.period_month.isoformat() if o.period_month else None}


async def effectiveness_map(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None):
    """Per-lever LeverEffectiveness objects (decay-weighted, E7-aware)."""
    today = today or await _today(db, user_id)
    await sync(db, user_id, today)

    rows = (await db.execute(select(Outcome).where(
        Outcome.user_id == user_id, Outcome.kind == T.RECOMMENDATION, Outcome.deleted_at.is_(None)))).scalars().all()
    by_lever: dict[str, list[dict[str, Any]]] = {}
    for o in rows:
        if not o.lever_key:
            continue
        by_lever.setdefault(o.lever_key, []).append(
            {"outcome": o.outcome, "circumstance": o.circumstance, "source": o.source,
             "evaluated_on": (o.period_month or o.evaluated_at.date())})

    fb = (await db.execute(select(RecommendationFeedback.lever_key, RecommendationFeedback.action).where(
        RecommendationFeedback.user_id == user_id))).all()
    accepted: dict[str, int] = {}
    total: dict[str, int] = {}
    for lever, action in fb:
        total[lever] = total.get(lever, 0) + 1
        if action == RecommendationAction.accepted:
            accepted[lever] = accepted.get(lever, 0) + 1

    levers = set(by_lever) | set(total)
    return {lever: build_effectiveness(lever, by_lever.get(lever, []), today=today,
                                       accepted=accepted.get(lever, 0), total_feedback=total.get(lever, 0))
            for lever in levers}


async def effectiveness(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    return {lever: eff.as_dict() for lever, eff in (await effectiveness_map(db, user_id, today=today)).items()}
