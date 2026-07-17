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
    utc_offset_minutes: int | None = Query(default=None, ge=-840, le=840),
) -> FestivalsOut:
    # The device's UTC offset, sent by the client — the "you've moved country"
    # signal, for free. Deliberately not GPS: this costs no permission, no
    # battery and no Play Store declaration, works offline, and answers the only
    # question we actually have (which calendar?) just as well. An explicit
    # setting always beats it.
    return FestivalsOut(
        **await festival_service.insights(
            db, current_user.id, limit=limit, utc_offset_minutes=utc_offset_minutes
        )
    )
