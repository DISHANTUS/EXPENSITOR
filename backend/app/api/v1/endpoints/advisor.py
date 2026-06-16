"""Advisor endpoints: the daily brief (life-easier context + explanations)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.intelligence.proactive import MONTHLY, WEEKLY
from app.services import adaptive_service, advisor_service, proactive_service

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/brief")
async def get_brief(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Context block + concise advisor explanations (guidance / risk / behavior)."""
    return await advisor_service.daily_brief(db, current_user.id)


@router.get("/dependencies")
async def get_dependencies(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Derived plan→income dependencies + concise explanations of each."""
    return await advisor_service.dependencies(db, current_user.id)


@router.get("/proactive")
async def get_proactive(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """The proactive feed: the most important things to know now (ranked). [] at cold start."""
    items = await proactive_service.feed(db, current_user.id)
    return {"items": items, "most_important": items[0] if items else None}


@router.get("/review")
async def get_review(
    current_user: CurrentUser, db: DbSession,
    period: str = Query(default="weekly", description="weekly | monthly"),
) -> dict[str, Any]:
    """A deterministic weekly/monthly review composed from existing intelligence."""
    return await proactive_service.review(db, current_user.id, period=MONTHLY if period == "monthly" else WEEKLY)


@router.get("/adaptive-plan")
async def get_adaptive_plan(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Recommendations reranked + annotated by outcome history (ordering only)."""
    return await adaptive_service.adaptive_plan(db, current_user.id)


@router.get("/learning-review")
async def get_learning_review(
    current_user: CurrentUser, db: DbSession,
    period: str = Query(default="monthly", description="weekly | monthly"),
) -> dict[str, Any]:
    """E5: what worked / didn't / goals progressed / what to do differently."""
    return await adaptive_service.learning_review(db, current_user.id, period=period)
