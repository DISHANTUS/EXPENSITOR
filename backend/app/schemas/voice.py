"""Voice Conversation schemas (Sprint 5c)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.advisor_chat import ChatTurn
from app.schemas.chat_primitives import ChatContext
from app.schemas.mood import VoicePlan


class VoiceAskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    session: ChatContext | None = None
    # Multi-turn write flow (5c-B):
    command_text: str | None = None    # the original command being clarified/confirmed
    answers: dict[str, str] | None = None  # accumulated raw spoken slot answers
    confirm: bool = False              # the user said "yes, go ahead"
    request_id: str | None = None      # idempotency for the final execute


class VoiceAskOut(BaseModel):
    type: str                          # turn type | clarification | preview | result | advisory | deferred
    speech: str                        # the concise spoken line
    voice: VoicePlan                   # paced, mood-aware delivery (5b)
    navigate: str | None = None        # screen to open AFTER speaking (e.g. "report")
    turn: ChatTurn | None = None       # full structured turn (queries), for on-screen detail
    session: ChatContext = ChatContext()
    # Multi-turn write flow (5c-B):
    awaiting: str | None = None        # the slot whose answer the next utterance fills
    command_text: str | None = None    # echo the original command for the client to resend
    request_id: str | None = None      # echo for the confirm/execute turn
    action: str | None = None          # the executed/previewed intent (-> reaction ack)
    requires_confirmation: bool = False  # speak summary, then listen for yes/no
