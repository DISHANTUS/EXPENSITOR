"""Life Timeline endpoint (Sprint 6a): GET /timeline."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.timeline import Timeline, TimelineEntry, TimelineSearchResult
from app.services import timeline_service

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("", response_model=Timeline, summary="The user's life timeline — past wins, present goals, what's ahead")
async def get_timeline(current_user: CurrentUser, db: DbSession) -> Timeline:
    return Timeline.model_validate(await timeline_service.get_timeline(db, current_user.id))


@router.get("/search", response_model=TimelineSearchResult, summary="Deterministic memory search over the timeline")
async def search_timeline(current_user: CurrentUser, db: DbSession,
                          q: str = Query(min_length=1, max_length=200)) -> TimelineSearchResult:
    entries, spec = await timeline_service.search(db, current_user.id, q=q)
    return TimelineSearchResult(
        summary=timeline_service.summarize_search(spec, entries),
        entries=[TimelineEntry.model_validate(e) for e in entries],
    )
