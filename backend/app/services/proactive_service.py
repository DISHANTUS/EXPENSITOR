"""Proactive Advisor service: assemble the ProactiveContext from already-computed
intelligence (no recompute beyond the standard compute-on-read builds), then run
the deterministic engine. Produces the feed and weekly/monthly reviews."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.health import build_health_score
from app.intelligence.proactive import ProactiveContext, build_review, generate
from app.models import Expense, Income
from app.services import behavior_service, projection_service, recommendation_service


async def _has_activity(db: AsyncSession, user_id: uuid.UUID) -> bool:
    if await db.scalar(select(exists().where(Expense.user_id == user_id, Expense.deleted_at.is_(None)))):
        return True
    return bool(await db.scalar(select(exists().where(Income.user_id == user_id, Income.deleted_at.is_(None)))))


async def build_context(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> ProactiveContext:
    profile = await behavior_service.build_profile(db, user_id, today=today)
    today = profile.today
    has_history = await _has_activity(db, user_id)
    health = build_health_score(profile).as_dict()

    scenario = await projection_service.get_scenario(db, user_id, today=today)
    deps, _ = await projection_service.analyze_dependencies(db, user_id, today=today)
    net = await recommendation_service._net_so_far(db, user_id, scenario.today)
    goal_states = await recommendation_service._goal_states(db, user_id, scenario, net)
    goals = tuple({"kind": gs.kind, "name": gs.name, "status": gs.status, "shortfall": str(gs.shortfall)}
                  for gs in goal_states)

    ev = scenario.income_events[0] if scenario.income_events else None
    next_income = None
    if ev is not None:
        exact = None
        if ev.exact_time is not None:
            hour = ev.exact_time.hour % 12 or 12
            suffix = "AM" if ev.exact_time.hour < 12 else "PM"
            exact = f"{hour}:{ev.exact_time.minute:02d} {suffix}" if ev.exact_time.minute else f"{hour} {suffix}"
        next_income = {"amount": str(ev.amount_base), "currency": scenario.base_currency,
                       "date": ev.date.isoformat(), "window": ev.time_window, "exact": exact}

    rec_result = await recommendation_service.build(db, user_id, today=today)

    return ProactiveContext(
        today=today, currency=scenario.base_currency, has_history=has_history, health=health,
        behavioral_memory=tuple(profile.behavioral_memory()),
        metrics={m.key: {"score": m.score, "trend": m.trend, "trend_duration_months": m.trend_duration_months,
                         "confidence": m.confidence, "facts": m.facts} for m in profile.metrics},
        dependencies=tuple(d.as_dict() for d in deps),
        goals=goals, goal_sacrifice=(profile.advisor or {}).get("goal_sacrifice"),
        next_income=next_income, recommendations=tuple(rec_result["recommendations"]),
        excluded_levers=tuple(rec_result.get("excluded_levers", [])),
    )


async def feed(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> list[dict[str, Any]]:
    ctx = await build_context(db, user_id, today=today)
    return [item.as_dict() for item in generate(ctx)]


async def review(db: AsyncSession, user_id: uuid.UUID, *, period: str, today: date | None = None) -> dict[str, Any]:
    ctx = await build_context(db, user_id, today=today)
    return build_review(ctx, period).as_dict()
