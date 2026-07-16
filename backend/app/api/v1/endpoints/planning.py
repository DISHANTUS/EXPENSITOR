"""Planning-intent endpoint (deterministic, with optional Ollama assist)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.core.config import settings as app_settings
from app.intelligence.companion import planning_intent
from app.schemas.planning import PlanningInterpretIn, PlanningInterpretOut
from app.services import ollama_service

router = APIRouter(prefix="/planning", tags=["planning"])


@router.post(
    "/interpret",
    response_model=PlanningInterpretOut,
    summary="Interpret a free-text planning sentence",
)
async def interpret_planning(data: PlanningInterpretIn, current_user: CurrentUser) -> PlanningInterpretOut:
    generate = ollama_service.complete if app_settings.OLLAMA_ENABLED else None
    result = await planning_intent.interpret(data.text, generate=generate)
    return PlanningInterpretOut(**result)
