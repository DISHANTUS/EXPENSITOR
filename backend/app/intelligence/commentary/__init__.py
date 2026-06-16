"""Commentary Layer (C5) — the single advisor voice.

A reusable, deterministic narration layer that CONSUMES already-computed
intelligence (advisor explanations, recommendations, behavioral insights,
dependencies, decisions, goals, the context block) and speaks with one voice.
It never calculates a financial fact. The deterministic renderer is the mandatory
product; an optional grounded Ollama narrator (Phase 3b) may only rephrase it.
"""

from __future__ import annotations

from app.intelligence.commentary.commentary import Commentary
from app.intelligence.commentary.context import ActionPreview, CommentaryContext
from app.intelligence.commentary.renderer import render_commentary

# Versioning the contracts so consumers (and the optional narrator) can detect drift.
COMMENTARY_SCHEMA_VERSION = "1.0"
GROUNDING_VERSION = "1.0"

__all__ = [
    "ActionPreview", "Commentary", "CommentaryContext", "render_commentary",
    "COMMENTARY_SCHEMA_VERSION", "GROUNDING_VERSION",
]
