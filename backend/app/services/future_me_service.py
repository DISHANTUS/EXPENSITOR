"""Future Me service (Sprint 6b) — surfaces the existing forecast engine as the
forward half of the Life Timeline: the three paths (current / optimistic /
conservative) with ETAs, the levers that change them, and the milestones ahead
(goal targets, expected repayments, upcoming events, user life events, and
forecasted completions). Deterministic; no new math — it composes 4b-4 + 6a.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SavingsGoal
from app.models.enums import SavingsGoalStatus
from app.services import calendar_service, forecast_service, settings_service, timeline_service


async def _primary_goal_id(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    """The goal Future-Me centres on: the soonest-dated active goal, else any active one."""
    goals = (await db.execute(select(SavingsGoal).where(
        SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
        SavingsGoal.status == SavingsGoalStatus.active))).scalars().all()
    if not goals:
        return None
    dated = [g for g in goals if g.target_date is not None]
    chosen = min(dated, key=lambda g: g.target_date) if dated else goals[0]
    return str(chosen.id)


async def get_future_me(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict:
    today = today or await calendar_service.user_today(db, user_id)
    currency = (await settings_service.get_settings(db, user_id)).base_currency

    goal_id = await _primary_goal_id(db, user_id)
    try:
        fc = await forecast_service.forecast(db, user_id, goal_id=goal_id, question="future me")
    except Exception:  # noqa: BLE001 — forecast must never break the view
        fc = None

    paths, levers, headline, confidence, reasoning = [], [], "Your future, at a glance.", "insufficient", ""
    if fc is not None:
        headline, confidence, reasoning = fc.headline, fc.confidence, fc.reasoning
        fm = fc.future_me
        for p in ((fm.current_path, fm.optimistic_path, fm.conservative_path) if fm else ()):
            if p is not None:
                paths.append({"mode": p.mode, "label": p.label, "eta": p.eta,
                              "monthly_rate": p.monthly_rate, "narrative": p.narrative})
        levers = [{"label": c.label, "ref": c.ref} for c in fc.levers]

    # Milestones ahead: the future slice of the timeline + forecasted completions.
    future = [e for e in await timeline_service.gather(db, user_id, today=today) if e.when == "future"]
    milestones = [{"date": e.date, "title": e.title, "detail": e.detail, "kind": e.kind, "icon": e.icon}
                  for e in future]
    if fc is not None:
        for tc in fc.timeline_candidates:
            if tc.date and tc.date > today:
                milestones.append({"date": tc.date, "title": tc.label, "detail": "", "kind": "forecast", "icon": "🔮"})
    milestones.sort(key=lambda m: m["date"] or today)

    return {"headline": headline, "confidence": confidence, "reasoning": reasoning, "currency": currency,
            "paths": paths, "levers": levers, "milestones": milestones}
