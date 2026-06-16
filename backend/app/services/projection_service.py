"""Orchestration for the Projection Engine.

Owns the contract's "Scenario built once per request" rule and the timezone
derivation of `today`. Builds one Scenario, then calls the pure engines.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection import affordability, dependency, goal_feasibility, guidance, risk
from app.intelligence.projection.calendar_utils import days_in_month
from app.intelligence.projection.scenario import MAX_HORIZON_DAYS, Scenario, build_scenario
from app.models import UserSettings
from app.services.exceptions import ResourceNotFoundError

DEFAULT_HORIZON_DAYS = 92


async def _today_for(db: AsyncSession, user_id: uuid.UUID) -> date:
    tz = await db.scalar(select(UserSettings.timezone).where(UserSettings.user_id == user_id))
    return datetime.now(ZoneInfo(tz or "UTC")).date()


async def get_scenario(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    today: date | None = None,
    horizon: date | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> Scenario:
    if today is None:
        today = await _today_for(db, user_id)
    if horizon is None:
        horizon = today + timedelta(days=horizon_days)
    return await build_scenario(db, user_id, today=today, horizon=horizon)


async def assess_risk(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> risk.RiskAssessment:
    scenario = await get_scenario(db, user_id, today=today)
    return risk.assess(scenario)


async def analyze_dependencies(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> tuple[list[dependency.Dependency], str]:
    """Derived plan→income dependencies (never stored) + the base currency."""
    scenario = await get_scenario(db, user_id, today=today, horizon_days=DEFAULT_HORIZON_DAYS + 60)
    return dependency.analyze(scenario), scenario.base_currency


async def evaluate_affordability(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    target_date: date,
    *,
    today: date | None = None,
) -> affordability.AffordabilityResult:
    if today is None:
        today = await _today_for(db, user_id)
    horizon = max(target_date, today + timedelta(days=DEFAULT_HORIZON_DAYS))
    scenario = await build_scenario(db, user_id, today=today, horizon=horizon)
    return affordability.evaluate(scenario, Decimal(amount), target_date)


async def evaluate_planned_expense(
    db: AsyncSession,
    user_id: uuid.UUID,
    planned_id: uuid.UUID,
    *,
    today: date | None = None,
) -> affordability.AffordabilityResult:
    """Evaluate an existing planned expense: build the world, remove this item,
    then test whether it fits given everything else."""
    if today is None:
        today = await _today_for(db, user_id)
    # Wide horizon so any in-range plan is present; build_scenario caps at MAX.
    horizon = today + timedelta(days=MAX_HORIZON_DAYS)
    scenario = await build_scenario(db, user_id, today=today, horizon=horizon)

    target = next((o for o in scenario.outflows if o.planned_id == planned_id), None)
    if target is None:
        raise ResourceNotFoundError("Planned expense")

    remaining = tuple(o for o in scenario.outflows if o.planned_id != planned_id)
    scenario_without = dataclasses.replace(scenario, outflows=remaining)
    return affordability.evaluate(scenario_without, target.amount_base, target.date)


async def compute_guidance_and_risk(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> tuple[guidance.GuidanceResult, risk.RiskAssessment]:
    """Build the Scenario once and return both guidance and the risk it uses."""
    scenario = await get_scenario(db, user_id, today=today)
    risk_assessment = risk.assess(scenario)

    # Affordability of planned expenses falling within the current month — all
    # in-memory off the single Scenario (no extra DB queries).
    anchor = scenario.today
    month_end = anchor.replace(day=days_in_month(anchor.year, anchor.month))
    planned_affordability = []
    for outflow in scenario.outflows:
        if anchor <= outflow.date <= month_end:
            without = dataclasses.replace(
                scenario,
                outflows=tuple(o for o in scenario.outflows if o.planned_id != outflow.planned_id),
            )
            result = affordability.evaluate(without, outflow.amount_base, outflow.date)
            planned_affordability.append((outflow.planned_id, result))

    guidance_result = guidance.build(scenario, risk_assessment, planned_affordability=planned_affordability)
    return guidance_result, risk_assessment


async def compute_guidance(
    db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None
) -> guidance.GuidanceResult:
    guidance_result, _ = await compute_guidance_and_risk(db, user_id, today=today)
    return guidance_result


async def evaluate_goal(
    db: AsyncSession,
    user_id: uuid.UUID,
    amount: Decimal,
    target_date: date,
    *,
    today: date | None = None,
) -> goal_feasibility.GoalFeasibilityResult:
    if today is None:
        today = await _today_for(db, user_id)
    horizon = max(target_date, today + timedelta(days=DEFAULT_HORIZON_DAYS))
    scenario = await build_scenario(db, user_id, today=today, horizon=horizon)
    return goal_feasibility.evaluate(scenario, Decimal(amount), target_date)
