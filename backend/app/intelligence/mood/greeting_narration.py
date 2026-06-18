"""Greeting narration adapter (Sprint 4c-B2, pure).

Turns a deterministic greeting (salutation + lines) into a grounded
`NarrationRequest` for the C5 Ollama narrator. The LLM may only REWORD — the
grounding guard rejects any added/dropped money/number/date/entity, so the
companion can never invent a salary date or amount. Also derives `spoken_text`
(plain, emoji-free) for Sprint 5 TTS.
"""

from __future__ import annotations

import re

from app.intelligence.commentary.ollama import guard
from app.intelligence.commentary.ollama.narrator import NarrationRequest

_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿️‍~]"
)


def _det_text(salutation: str, lines: list[str]) -> str:
    return " ".join([salutation, *lines]).strip()


def spoken_text(salutation: str, lines: list[str]) -> str:
    """Plain, emoji-free, fact-complete text for text-to-speech."""
    text = _EMOJI_RE.sub("", _det_text(salutation, lines))
    return re.sub(r"\s+", " ", text).strip()


def display_text(salutation: str, lines: list[str]) -> str:
    """The deterministic on-screen greeting (used as fallback + same shape as narrated)."""
    return "\n".join([salutation, *lines]) if lines else salutation


def build_request(lines: list[str], *, style: str = "balanced") -> NarrationRequest:
    # Narrate the FACT lines only — the time salutation ("Good evening 🌆") is kept
    # verbatim by the caller so the model can't reword the time-of-day away.
    det = " ".join(lines).strip()
    allowed = guard.extract_facts(det)
    spec = guard.GroundingSpec(
        allowed=allowed,
        required=allowed,                 # greetings: every number/amount/date must survive
        grounding_tokens=tuple(lines),    # the facts, shown to the model to preserve
        # Allow alarm words that the deterministic greeting ALREADY uses (e.g.
        # "overdue") — but the model still can't invent new ones.
        escalation_markers=guard.escalation_markers(det),
        confidence_hedged=False,
        paragraph_count=1,
        ordered_items=(),
        allow_new_entities=True,          # casual words ok; money/number/date still hard-grounded
        enforce_paragraph_count=False,    # greetings may re-flow line breaks; facts still grounded
    )
    return NarrationRequest(paragraphs=(det,), grounding=spec, style=style, kind="greeting")
