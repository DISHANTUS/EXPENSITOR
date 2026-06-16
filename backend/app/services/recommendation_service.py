"""Recommendation service (C9): assemble already-computed intelligence into a
RecommendationContext, then run the pure engine. No recomputation of money math —
every input comes from an existing engine/service. Compute-on-read, stateless."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import explainers
from app.intelligence.behavior.insights import InsightContext, build_behavioral_insights
from app.intelligence.decision import funding
from app.intelligence.health import build_health_score
from app.intelligence.projection import dependency
from app.intelligence.recommendation import build_recommendations
from app.intelligence.recommendation.recommendation import GoalState, RecommendationContext
from app.intelligence.savings import engine as savings_engine
from app.models import Expense, Income, SavingsGoal
from app.models.enums import SavingsGoalKind, SavingsGoalStatus
from app.services import behavior_service, preference_service, projection_service


async def _net_so_far(db: AsyncSession, user_id: uuid.UUID, today: date) -> Decimal:
    month_start = today.replace(day=1)
    income = await db.scalar(
        select(func.coalesce(func.sum(Income.converted_amount), 0)).where(
            Income.user_id == user_id, Income.deleted_at.is_(None),
            Income.received_date >= month_start, Income.received_date <= today)
    )
    expense = await db.scalar(
        select(func.coalesce(func.sum(Expense.converted_amount), 0)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None),
            Expense.expense_date >= month_start, Expense.expense_date <= today)
    )
    return Decimal(income or 0) - Decimal(expense or 0)


async def _goal_states(db: AsyncSession, user_id, scenario, net: Decimal) -> tuple[GoalState, ...]:
    rows = (
        await db.execute(
            select(SavingsGoal).where(
                SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
                SavingsGoal.status == SavingsGoalStatus.active)
        )
    ).scalars().all()
    states: list[GoalState] = []
    for g in rows:
        if g.kind == SavingsGoalKind.monthly_target:
            st = savings_engine.evaluate_monthly_target(
                scenario, base_target=g.converted_amount, net_so_far=net,
                carried_deficit=g.carried_deficit,
                recovery_mode=g.recovery_mode.value if g.recovery_mode else None,
                distribute_months=g.distribute_months)
        elif g.target_date is not None and g.target_date <= scenario.horizon:
            st = savings_engine.evaluate_custom_goal(scenario, target_amount=g.converted_amount, target_date=g.target_date)
        else:
            continue
        states.append(GoalState(
            kind=g.kind.value, name=g.name, status=st.status, shortfall=st.shortfall,
            target_date=g.target_date.isoformat() if g.target_date else None, facts=st.as_dict()))
    return tuple(states)


async def build(
    db: AsyncSession, user_id: uuid.UUID, *, excluded_levers: tuple[str, ...] = (),
    include_levers: tuple[str, ...] = (), today: date | None = None
) -> dict[str, Any]:
    scenario = await projection_service.get_scenario(db, user_id, today=today)
    net = await _net_so_far(db, user_id, scenario.today)
    profile = await behavior_service.build_profile(db, user_id, today=scenario.today)

    deps = dependency.analyze(scenario)
    dep_dicts = tuple(d.as_dict() for d in deps)
    goal_states = await _goal_states(db, user_id, scenario, net)
    goal_refs = tuple((gs.kind, gs.name) for gs in goal_states)

    insights = build_behavioral_insights(profile, context=InsightContext(goals=goal_refs, dependencies=dep_dicts))

    load_metric = profile.metric("recurring_cost_load")
    recurring_load = load_metric.facts if (load_metric and load_metric.confidence == "normal") else None
    next_event = scenario.income_events[0] if scenario.income_events else None
    next_income = {"date": next_event.date.isoformat(), "amount": str(next_event.amount_base)} if next_event else None

    # C7b: the user's policy reranks/excludes/boosts OPTIONS only (never facts).
    policy_row = await preference_service.get_policy(db, user_id)
    levers = preference_service.policy_levers(policy_row.policy or {})
    strong = set(levers["strong"]) | set(excluded_levers)

    ctx = RecommendationContext(
        currency=scenario.base_currency, behavioral_insights=tuple(insights), goals=goal_states,
        dependencies=dep_dicts, advisor_view=profile.advisor or {}, recurring_load=recurring_load,
        available_savings=funding.available_now(scenario), next_income=next_income,
        excluded_levers=tuple(sorted(strong)), soft_excluded_levers=tuple(sorted(levers["soft"])),
        boosts=levers["boosts"], include_levers=tuple(include_levers),
    )
    result = build_recommendations(ctx)

    # C8 (H9): expose health pillars + contributor_index so recommendations can
    # reference what they'd strengthen ("improving X would raise your Resilience").
    health = build_health_score(profile)
    health_ref = {
        "overall_score": health.overall_score, "overall_state": health.overall_state,
        "pillars": [{"key": p.key, "label": p.label, "score": p.score, "state": p.state} for p in health.pillars],
        "contributor_index": health.contributor_index,
    }

    return {
        "recommendations": [r.as_dict() for r in result["recommendations"]],
        "bundles": [b.as_dict() for b in result["bundles"]],
        "explanations": [explainers.explain_recommendation(r).as_dict() for r in result["recommendations"]],
        "bundle_explanations": [explainers.explain_bundle(b).as_dict() for b in result["bundles"]],
        "excluded_levers": result["excluded_levers"],
        "alternatives_applied": result["alternatives_applied"],
        "policy_influence": result["policy_influence"],
        "health": health_ref,
    }
