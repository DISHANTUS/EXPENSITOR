"""Conversational advisor endpoint (4b): POST /advisor/chat | /explain | /forecast."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.advisor_chat import ChatIn, ChatTurn
from app.schemas.explain import ExplainIn, Explanation
from app.schemas.forecast import Forecast, ForecastIn
from app.schemas.future_me import FutureMeView
from app.services import advisor_chat_service, explain_service, forecast_service, future_me_service

router = APIRouter(prefix="/advisor", tags=["advisor-chat"])


@router.post("/chat", response_model=ChatTurn, summary="Conversational financial intelligence")
async def advisor_chat(data: ChatIn, current_user: CurrentUser, db: DbSession) -> ChatTurn:
    return await advisor_chat_service.chat(db, current_user.id, message=data.message, session=data.session)


@router.post("/explain", response_model=Explanation, summary="Defend a claim with evidence + confidence")
async def advisor_explain(data: ExplainIn, current_user: CurrentUser, db: DbSession) -> Explanation:
    return await explain_service.explain(db, current_user.id, ref=data.ref, session=data.session)


@router.post("/forecast", response_model=Forecast, summary="Forward-looking forecast: ETAs, levers, opportunity cost")
async def advisor_forecast(data: ForecastIn, current_user: CurrentUser, db: DbSession) -> Forecast:
    return await forecast_service.forecast(
        db, current_user.id,
        question=data.question, goal_id=data.goal_id, levers=data.levers,
        target_date=data.target_date, expected_cost=data.expected_cost, event_type=data.event_type,
        session=data.session,
    )


@router.get("/future-me", response_model=FutureMeView, summary="Future Me: current/optimistic/conservative paths + milestones ahead")
async def advisor_future_me(current_user: CurrentUser, db: DbSession) -> FutureMeView:
    return FutureMeView.model_validate(await future_me_service.get_future_me(db, current_user.id))
