"""Conversational advisor schemas (4b)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analytics import DrilldownResult, ReportSession
from app.schemas.chat_primitives import ChatContext, ChatOption
from app.schemas.forecast import Forecast
from app.schemas.learning import CompanionRecap, FollowUpQuestion, ReflectionPrompt

__all__ = ["ChatContext", "ChatOption", "ChatIn", "ChatTurn"]


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session: ChatContext | None = None


class ChatTurn(BaseModel):
    type: str                          # clarify | report | comparison | drilldown | advisory | answer | unsupported | forecast | help | tour
    message: str | None = None
    route: str | None = None           # how-to / tour: a screen the client can offer to open
    options: list[ChatOption] = []     # for clarify
    report: ReportSession | None = None  # report (delta populated => comparison)
    drilldown: DrilldownResult | None = None
    forecast: Forecast | None = None   # forecast turn (4b-4)
    follow_up: FollowUpQuestion | None = None  # learning-loop check-in (4b-5a)
    reflection: ReflectionPrompt | None = None  # month-end / win reflection (4b-5b)
    recap: CompanionRecap | None = None         # structured "what do you know about me" (4b-5b)
    explain_ref: str | None = None     # client can ask "Show evidence" / "Why does this matter?"
    confidence: str | None = None      # high | medium | low | insufficient
    follow_ups: list[ChatOption] = []
    session: ChatContext = ChatContext()
