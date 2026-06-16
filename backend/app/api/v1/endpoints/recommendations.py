"""Recommendation Engine endpoint (C9): GET /recommendations (compute-on-read)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.preference import FeedbackIn
from app.services import preference_service, recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

_EFFORT_ORDER = {"low": 0, "medium": 1, "high": 2}


@router.get("")
async def list_recommendations(
    current_user: CurrentUser,
    db: DbSession,
    category: str | None = Query(default=None),
    view: str | None = Query(default=None, description="impact | easiest | goals | lifestyle"),
    excluded_levers: list[str] = Query(default_factory=list),
    include_levers: list[str] = Query(default_factory=list),
) -> dict[str, Any]:
    result = await recommendation_service.build(
        db, current_user.id, excluded_levers=tuple(excluded_levers), include_levers=tuple(include_levers)
    )
    recs = result["recommendations"]
    if category:
        recs = [r for r in recs if r["category"] == category]
    if view == "impact":
        recs = sorted(recs, key=lambda r: -r["impact"])
    elif view == "easiest":
        recs = sorted(recs, key=lambda r: _EFFORT_ORDER.get(r["effort_level"], 1))
    elif view == "goals":
        recs = [r for r in recs if r["category"] == "goal_recovery"]
    elif view == "lifestyle":
        recs = [r for r in recs if r["category"] == "lifestyle_optimization"]
    result["recommendations"] = recs
    return result


@router.post("/feedback")
async def submit_feedback(data: FeedbackIn, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Record accept/reject/defer (preference only — never executes or changes facts),
    then return the refreshed, repersonalized recommendations."""
    await preference_service.record_feedback(
        db, current_user.id, recommendation_id=data.recommendation_id, action=data.action,
        reason=data.reason, reason_context=data.reason_context,
        emotional_importance=data.emotional_importance, note=data.note,
    )
    return await recommendation_service.build(db, current_user.id)
