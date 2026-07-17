"""Festival endpoint — when they land, and what they cost this user last time."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.festivals import FestivalsOut
from app.services import festival_service

router = APIRouter(prefix="/festivals", tags=["festivals"])


@router.get("", response_model=FestivalsOut, summary="Festivals coming up, and what they cost you last time")
async def upcoming_festivals(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=3, ge=1, le=10),
) -> FestivalsOut:
    return FestivalsOut(**await festival_service.insights(db, current_user.id, limit=limit))
