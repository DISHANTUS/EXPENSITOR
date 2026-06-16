"""Advisor endpoints: the daily brief (life-easier context + explanations)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.services import advisor_service

router = APIRouter(prefix="/advisor", tags=["advisor"])


@router.get("/brief")
async def get_brief(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Context block + concise advisor explanations (guidance / risk / behavior)."""
    return await advisor_service.daily_brief(db, current_user.id)


@router.get("/dependencies")
async def get_dependencies(current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Derived plan→income dependencies + concise explanations of each."""
    return await advisor_service.dependencies(db, current_user.id)
