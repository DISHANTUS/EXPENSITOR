"""Companion endpoints: event ingestion + insights feed."""

from __future__ import annotations

import uuid
from datetime import date

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
from app.schemas.date_reaction import DateReaction
from app.schemas.evolution import EvolutionView, MonthlyReflection
from app.schemas.home_cards import HomeCards
from app.schemas.home_stats import HomeStats
from app.schemas.home_thought import HomeThought
from app.schemas.mood import MoodState
from app.schemas.tour import TourCompleteOut, TourOut, TourStepOut
from app.services import (
    companion_evolution_service,
    companion_service,
    date_reaction_service,
    home_cards_service,
    home_stats_service,
    home_thought_service,
    mood_service,
    settings_service,
)
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


@router.get("/home-stats", response_model=HomeStats, summary="Home Memory Strip — days/goals/saved/people")
async def home_stats(current_user: CurrentUser, db: DbSession) -> HomeStats:
    return HomeStats.model_validate(await home_stats_service.build(db, current_user))


@router.get("/home-thought", response_model=HomeThought, summary="Advary's contextual thought for the Home hero")
async def home_thought(current_user: CurrentUser, db: DbSession) -> HomeThought:
    return HomeThought.model_validate(await home_thought_service.build(db, current_user.id))


@router.get("/home-cards", response_model=HomeCards, summary="Living Quick Cards — Story/Future/People/Focus previews")
async def home_cards(current_user: CurrentUser, db: DbSession) -> HomeCards:
    return HomeCards.model_validate(await home_cards_service.build(db, current_user.id))


@router.get("/date-reaction", response_model=DateReaction, summary="Advary's reaction to a tapped calendar date")
async def date_reaction(current_user: CurrentUser, db: DbSession, day: date = Query(alias="date")) -> DateReaction:
    return DateReaction.model_validate(await date_reaction_service.build(db, current_user.id, day))


@router.get("/evolution", response_model=EvolutionView, summary="Advary's reflection on the user's journey (Sprint 8)")
async def evolution(current_user: CurrentUser, db: DbSession) -> EvolutionView:
    return EvolutionView.model_validate(await companion_evolution_service.evolution(db, current_user))


@router.get("/monthly-reflection", response_model=MonthlyReflection, summary="A deterministic month-in-review")
async def monthly_reflection(
    current_user: CurrentUser, db: DbSession,
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
) -> MonthlyReflection:
    return MonthlyReflection.model_validate(
        await companion_evolution_service.monthly_reflection(db, current_user.id, year, month))


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
