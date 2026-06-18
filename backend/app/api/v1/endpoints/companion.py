"""Companion endpoints: event ingestion + insights feed."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.intelligence.companion import tour_content
from app.schemas.common import Page
from app.schemas.companion import (
    CompanionEventCreate,
    CompanionEventResponse,
    CompanionInsightOut,
    UnreadCountOut,
)
from app.schemas.mood import MoodState
from app.schemas.tour import TourCompleteOut, TourOut, TourStepOut
from app.services import companion_service, mood_service, settings_service
from app.services.exceptions import ResourceNotFoundError

router = APIRouter(prefix="/companion", tags=["companion"])


@router.post("/events", response_model=CompanionEventResponse, summary="Ingest a UI event")
async def ingest_event(
    data: CompanionEventCreate, current_user: CurrentUser, db: DbSession
) -> CompanionEventResponse:
    event, messages = await companion_service.handle_event(db, current_user.id, data)
    return CompanionEventResponse(event_id=event.id, messages=messages)


@router.get("/mood", response_model=MoodState, summary="The companion's current mood + greeting")
async def mood(current_user: CurrentUser, db: DbSession, background_tasks: BackgroundTasks,
               hour: int | None = Query(default=None, ge=0, le=23)) -> MoodState:
    # `hour` is the device's local hour so the greeting's time-of-day matches what
    # the user sees. background_tasks lets the greeting return instantly (deterministic)
    # while the richer Ollama narration is generated + cached after the response.
    return MoodState.model_validate(
        await mood_service.get_mood(db, current_user.id, background=background_tasks, local_hour=hour))


@router.get("/tour", response_model=TourOut, summary="The first-launch guided tour")
async def tour(current_user: CurrentUser, db: DbSession) -> TourOut:
    s = await settings_service.get_settings(db, current_user.id)
    name = s.companion_name or "Advary"
    steps = tour_content.build_tour(s.companion_style, s.companion_name)
    return TourOut(
        companion_name=name,
        steps=[TourStepOut(key=st.key, route=st.route, icon=st.icon, title=st.title,
                           narration=st.narration, spoken_text=st.spoken_text) for st in steps],
    )


@router.post("/tour/complete", response_model=TourCompleteOut, summary="Mark the tour seen")
async def complete_tour(current_user: CurrentUser, db: DbSession) -> TourCompleteOut:
    await settings_service.mark_tour_completed(db, current_user.id)
    return TourCompleteOut()


@router.get("/feed", response_model=Page[CompanionInsightOut], summary="List insights feed")
async def list_feed(
    current_user: CurrentUser,
    db: DbSession,
    unread: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[CompanionInsightOut]:
    rows, total = await companion_service.list_feed(
        db, current_user.id, unread=unread, limit=limit, offset=offset
    )
    return Page[CompanionInsightOut](
        items=[CompanionInsightOut.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/behavioral-refresh", response_model=list[CompanionInsightOut],
             summary="Generate the behavioral-intelligence feed (on-read)")
async def behavioral_refresh(current_user: CurrentUser, db: DbSession) -> list[CompanionInsightOut]:
    rows = await companion_service.build_behavioral_feed(db, current_user.id)
    return [CompanionInsightOut.model_validate(row) for row in rows]


@router.get("/feed/unread-count", response_model=UnreadCountOut, summary="Count unread insights")
async def unread_count(current_user: CurrentUser, db: DbSession) -> UnreadCountOut:
    return UnreadCountOut(count=await companion_service.unread_count(db, current_user.id))


@router.patch("/feed/{insight_id}/read", response_model=CompanionInsightOut, summary="Mark an insight read")
async def mark_read(insight_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> CompanionInsightOut:
    try:
        row = await companion_service.mark_read(db, current_user.id, insight_id)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found") from exc
    return CompanionInsightOut.model_validate(row)
