"""Dependency-free conversational primitives shared across advisor schemas.

Extracted so `ChatTurn` can embed `Forecast` (and `Forecast` can reuse these)
without an import cycle. `advisor_chat` re-exports both for backwards-compat.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class ChatContext(BaseModel):
    """Echoed conversation memory — client sends it back each turn (stateless)."""
    last_kind: str | None = None       # week | month
    last_ref: str | None = None        # this | last
    period_from: date | None = None
    period_to: date | None = None
    last_explain_ref: str | None = None  # so "why did you say that?" can re-explain
    pending_profile_text: str | None = None  # life-change awaiting "yes" to apply (Phase 5)


class ChatOption(BaseModel):
    label: str
    message: str       # what the client sends when the chip is tapped
