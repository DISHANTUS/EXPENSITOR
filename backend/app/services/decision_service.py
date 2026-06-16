"""Decision service (C7a) — convert currency, build the world, run the engine.

Stateless: produces a quote (structured DecisionResult + advisor explanation).
No persistence; recommendation memory is a request-level hook only.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import explainers
from app.intelligence.decision import engine, modifier_engine
from app.intelligence.decision.modifiers.base import AnalyzerCtx, GoalRef, ModifierInputs
from app.intelligence.decision.request import (
    DecisionKind,
    DecisionRequest,
    EmotionalImportance,
    Flexibility,
    OutflowShape,
    UserConstraints,
)
from app.models import Expense, Income, SavingsGoal
from app.models.enums import SavingsGoalStatus
from app.services import behavior_service, currency_service, preference_service, projection_service

_RESCHEDULE_BUFFER_DAYS = 60
_BASE_HORIZON_DAYS = 92


async def quote(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    item_label: str,
    original_amount: Decimal,
    original_currency: str,
    decision_kind: DecisionKind = DecisionKind.purchase,
    outflow_shape: OutflowShape = OutflowShape.one_time,
    recurrence_months: int | None = None,
    tenure_months: int | None = None,
    target_date: date | None = None,
    flexibility: Flexibility = Flexibility.flexible,
    emotional_importance: EmotionalImportance = EmotionalImportance.medium,
    constraints: UserConstraints | None = None,
    excluded_strategies: tuple[str, ...] = (),
    modifier_inputs: ModifierInputs | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    horizon_days = _BASE_HORIZON_DAYS + _RESCHEDULE_BUFFER_DAYS
    scenario = await projection_service.get_scenario(db, user_id, today=today, horizon_days=horizon_days)
    # Extend the horizon if the target date is far out (so reschedule has room).
    if target_date is not None:
        needed = target_date + timedelta(days=_RESCHEDULE_BUFFER_DAYS)
        if needed > scenario.horizon:
            scenario = await projection_service.get_scenario(db, user_id, today=scenario.today, horizon=needed)

    rate, converted = await currency_service.convert_to_base(
        db, original_amount, original_currency, scenario.base_currency
    )

    # C7b: fold the user's policy-excluded strategies into the request (options only).
    policy_row = await preference_service.get_policy(db, user_id)
    policy_excluded = preference_service.excluded_strategies(policy_row.policy or {})
    excluded_strategies = tuple(sorted(set(excluded_strategies) | set(policy_excluded)))

    request = DecisionRequest(
        item_label=item_label,
        amount_base=converted,
        decision_kind=decision_kind,
        outflow_shape=outflow_shape,
        recurrence_months=recurrence_months,
        tenure_months=tenure_months,
        target_date=target_date,
        flexibility=flexibility,
        emotional_importance=emotional_importance,
        constraints=constraints or UserConstraints(),
        excluded_strategies=excluded_strategies,
    )

    # Behavioral advisor view powers smarter "reduce spending" suggestions (optional).
    profile = await behavior_service.build_profile(db, user_id, today=scenario.today)
    engine_view = profile.advisor_view() if profile.confidence == "normal" else None

    result = engine.evaluate(scenario, request, behavior_view=engine_view)
    explanation = explainers.explain_decision(result)

    # --- C7a-2 decision modifier analyzers ---
    # B1.5a: enrich the analyzer view with the behavioral METRICS the lifestyle /
    # upgrade analyzers read (each gates on its own confidence) — no recompute.
    analyzer_view = {**profile.advisor_view(),
                     "metrics": _metric_view(profile, ("lifestyle_inflation", "upgrade_replacement_behavior",
                                                       "spending_escalation_rate"))}
    intended = target_date if (target_date and target_date >= scenario.today) else scenario.today
    goals = await _active_goals(db, user_id)
    net_so_far = await _net_so_far(db, user_id, scenario.today) if goals else Decimal("0")
    ctx = AnalyzerCtx(
        request=request, attributes=result.attributes, scenario=scenario,
        inputs=modifier_inputs or ModifierInputs(), currency=scenario.base_currency,
        amount=converted, when=intended, behavior_view=analyzer_view, decision_result=result,
        goals=goals, net_so_far=net_so_far,
    )
    modifiers = modifier_engine.run(ctx)
    modifier_explanations = [explainers.explain_modifier(f).as_dict() for f in modifiers["_findings"]]

    return {
        "fx": {
            "original_amount": str(original_amount),
            "original_currency": original_currency.upper(),
            "exchange_rate": str(rate),
            "converted_amount": str(converted),
            "base_currency": scenario.base_currency,
        },
        "result": result.to_facts(),
        "explanation": explanation.as_dict(),
        "modifier_findings": modifiers["findings"],
        "pending_questions": modifiers["pending_questions"],
        "modifier_explanations": modifier_explanations,
    }


def _metric_view(profile, keys: tuple[str, ...]) -> dict[str, dict]:
    """Project selected behavioral metrics for the modifier analyzers (read-only)."""
    out: dict[str, dict] = {}
    for key in keys:
        m = profile.metric(key)
        if m is not None:
            out[key] = {"score": m.score, "trend": m.trend, "confidence": m.confidence,
                        "trend_duration_months": m.trend_duration_months, "facts": m.facts}
    return out


async def _active_goals(db: AsyncSession, user_id: uuid.UUID) -> tuple[GoalRef, ...]:
    rows = (
        await db.execute(
            select(SavingsGoal.kind, SavingsGoal.name, SavingsGoal.converted_amount, SavingsGoal.target_date).where(
                SavingsGoal.user_id == user_id,
                SavingsGoal.deleted_at.is_(None),
                SavingsGoal.status == SavingsGoalStatus.active,
            )
        )
    ).all()
    return tuple(
        GoalRef(kind=k.value if hasattr(k, "value") else str(k), name=name, target_amount=amt, target_date=tdate)
        for k, name, amt, tdate in rows
    )


async def _net_so_far(db: AsyncSession, user_id: uuid.UUID, today: date) -> Decimal:
    month_start = today.replace(day=1)
    income = await db.scalar(
        select(func.coalesce(func.sum(Income.converted_amount), 0)).where(
            Income.user_id == user_id, Income.deleted_at.is_(None),
            Income.received_date >= month_start, Income.received_date <= today,
        )
    )
    expense = await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= month_start, Expense.expense_date <= today,
        )
    )
    return Decimal(income or 0) - Decimal(expense or 0)
