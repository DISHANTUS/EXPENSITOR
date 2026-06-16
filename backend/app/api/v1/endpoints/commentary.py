"""Commentary endpoint (C5): GET /commentary — the single advisor voice.

Deterministic, compute-on-read narration over already-computed intelligence.
Fully functional with Ollama disabled.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.intelligence.commentary import context as ctxmod
from app.services import commentary_service

router = APIRouter(prefix="/commentary", tags=["commentary"])

_SURFACE_TO_TRIGGER = {
    "daily": ctxmod.DAILY_BRIEF,
    "recommendations": ctxmod.RECOMMENDATIONS,
    "goals": ctxmod.GOAL_REVIEW,
    "dependencies": ctxmod.DEPENDENCY_ALERT,
}


@router.get("")
async def get_commentary(
    current_user: CurrentUser,
    db: DbSession,
    surface: str = Query(default="daily", description="daily | recommendations | goals | dependencies"),
    expand: bool = Query(default=False, description="Allow more than the concise 1-4 paragraphs"),
    style: str | None = Query(default=None, description="concise | balanced | detailed (narration only)"),
) -> dict[str, Any]:
    trigger = _SURFACE_TO_TRIGGER.get(surface, ctxmod.DAILY_BRIEF)
    return await commentary_service.narrate(db, current_user.id, trigger=trigger, expand=expand, style=style)
