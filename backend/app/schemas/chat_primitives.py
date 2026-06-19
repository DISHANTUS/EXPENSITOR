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
    # Conversational action (Chat → Action Layer): a parsed command awaiting a
    # missing slot or a final "yes". Mirrors the voice command loop, echoed by the
    # client each turn so the multi-step confirm stays stateless server-side.
    pending_action_text: str | None = None       # the original command (e.g. "add 250 lunch")
    pending_action_field: str | None = None       # the slot we're waiting on (None => awaiting confirm)
    pending_action_answers: dict[str, str] | None = None  # slot answers gathered so far
    pending_action_request_id: str | None = None  # idempotency key across the confirm


class ChatOption(BaseModel):
    label: str
    message: str       # what the client sends when the chip is tapped
