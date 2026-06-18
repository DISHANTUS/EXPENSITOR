"""Voice Conversation endpoint (Sprint 5c): POST /voice/ask.

The spoken client sends a transcript; we route it to the right brain and return a
concise spoken reply + a paced VoicePlan + the structured turn for on-screen detail.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.voice import VoiceAskIn, VoiceAskOut
from app.services import voice_ask_service

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/ask", response_model=VoiceAskOut, summary="Spoken question/command → concise spoken reply")
async def voice_ask(data: VoiceAskIn, current_user: CurrentUser, db: DbSession) -> VoiceAskOut:
    return VoiceAskOut(**await voice_ask_service.ask(
        db, current_user.id, text=data.text, session=data.session, answers=data.answers,
        confirm=data.confirm, request_id=data.request_id, command_text=data.command_text))
