"""Reason interpretation endpoint (deterministic; powers 'Other -> specify')."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.intelligence.nlp import reason as reason_nlp
from app.schemas.reason import ReasonInterpretIn, ReasonInterpretOut

router = APIRouter(prefix="/reason", tags=["reason"])


@router.post("/interpret", response_model=ReasonInterpretOut, summary="Interpret a free-text reason")
async def interpret_reason(data: ReasonInterpretIn, current_user: CurrentUser) -> ReasonInterpretOut:
    return ReasonInterpretOut(**reason_nlp.interpret(data.text))
