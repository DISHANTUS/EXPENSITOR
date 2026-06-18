"""Explainability schemas (4b-3): claims defended with evidence + confidence."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat_primitives import ChatContext


class ExplainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: str = Field(min_length=1, max_length=120)   # e.g. impact:red_days | relationship:Ravi | category:Food
    session: ChatContext | None = None


class EvidenceItem(BaseModel):
    label: str
    value: str | None = None      # already currency-formatted when monetary
    when: date | None = None


class Explanation(BaseModel):
    claim: str                    # the statement being defended
    confidence: str               # high | medium | low | insufficient
    confidence_word: str | None   # consistently | often | may | None
    reasoning: str
    why_it_matters: str | None = None
    evidence: list[EvidenceItem]
