"""Adaptive planning service (Phase E2/E5): rerank + annotate recommendations by
outcome history, and produce the monthly learning review. Reuses C9 + outcomes;
no duplicate calculations. Outcomes influence ordering/annotations only."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.health import build_health_score
from app.intelligence.outcomes import build_plan
from app.intelligence.outcomes.effectiveness import (
    USUALLY_DOESNT_WORK,
    USUALLY_WORKS,
    WORKS_BUT_CIRCUMSTANCES,
)
from app.services import behavior_service, outcome_service, recommendation_service


async def adaptive_plan(db: AsyncSession, user_id: uuid.UUID, *, today: date | None = None) -> dict[str, Any]:
    rec_result = await recommendation_service.build(db, user_id, today=today)
    eff_map = await outcome_service.effectiveness_map(db, user_id, today=today)
    plan = build_plan(list(rec_result["recommendations"]), eff_map)
    # easiest categories (advisor_view) + repeatedly-ignored levers (low acceptance) — service-side context
    plan["effectiveness"] = {lever: eff.as_dict() for lever, eff in eff_map.items()}
    plan["repeatedly_ignored"] = sorted(
        lever for lever, eff in eff_map.items()
        if eff.acceptance_rate is not None and eff.acceptance_rate <= 0.34 and eff.evidence_count >= 3
    )
    plan["policy_influence"] = rec_result.get("policy_influence", {})
    return plan


async def learning_review(db: AsyncSession, user_id: uuid.UUID, *, period: str = "monthly",
                          today: date | None = None) -> dict[str, Any]:
    """E5: what worked / didn't / which goals progressed / what to do differently."""
    profile = await behavior_service.build_profile(db, user_id, today=today)
    health = build_health_score(profile).as_dict()
    eff_map = await outcome_service.effectiveness_map(db, user_id, today=today)
    outcomes = await outcome_service.list_outcomes(db, user_id, today=today)

    worked = [lever for lever, e in eff_map.items() if e.conclusion == USUALLY_WORKS]
    didnt = [lever for lever, e in eff_map.items() if e.conclusion == USUALLY_DOESNT_WORK]
    circumstance = [lever for lever, e in eff_map.items() if e.conclusion == WORKS_BUT_CIRCUMSTANCES]
    goal_outcomes = [o for o in outcomes if o["kind"] == "goal"]
    goals_progressed = [o for o in goal_outcomes if o["outcome"] in ("success", "ahead", "on_track")]
    plans_failed = [o for o in outcomes if o["kind"] == "plan" and o["outcome"] in ("failed", "abandoned")]

    # what to do differently: a high-trust effective lever, else a downranked one to avoid
    next_focus = (f"Lean on {worked[0]} — it has worked for you." if worked
                  else f"Reconsider {didnt[0]} — it rarely works out." if didnt
                  else "Keep going; not enough evidence yet to change approach.")
    has_evidence = bool(eff_map) or bool(outcomes)

    label = "This month" if period == "monthly" else "This week"
    return {
        "period": period,
        "what_worked": worked,
        "what_didnt_work": didnt,
        "works_but_circumstances_interfere": circumstance,   # E7
        "goals_progressed": [o["subject_id"] for o in goals_progressed],
        "plans_repeatedly_failed": [o["subject_id"] for o in plans_failed],
        "health": {"overall_score": health["overall_score"], "overall_state": health["overall_state"],
                   "improving_area": health["improving_area"], "worsening_area": health["worsening_area"]},
        "do_differently": next_focus,
        "advisor_confidence": "Still learning." if not has_evidence else f"{label}'s review is based on your recorded outcomes.",
    }
