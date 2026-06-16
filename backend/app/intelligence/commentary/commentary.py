"""Commentary Layer (C5) — the structured output.

`Commentary` is the single-voice result: the six advisor answers as explicit
fields plus the concise rendered prose (1-4 short paragraphs). It carries no new
financial math — every number it speaks came verbatim from a `CommentaryContext`.
`facts["grounding"]` is the whitelist of allowed tokens the future Ollama narrator
(Phase 3b) must stay within.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Commentary:
    headline: str
    paragraphs: tuple[str, ...]              # the product — 1..4 short paragraphs
    what_happened: str
    why_it_matters: str
    life_effect: str | None = None           # A1 — real-life translation
    attention: str | None = None             # what to pay attention to (A7 hierarchy)
    unchanged: str | None = None             # what stays the same
    next_step: str | None = None             # most useful next step (option, never a command)
    most_useful_number: str | None = None    # A2 — the number for this situation
    preference_note: str | None = None       # A4/A8 — acknowledging the user's choices
    confidence_note: str | None = None       # A9/req8 — honest about certainty
    timing_note: str | None = None           # A5/req9 — useful timing, only when known
    severity: str = "info"                   # info | success | warning | alert
    expanded: bool = False
    health: dict[str, Any] | None = None      # C8 summary (facts lead; score summarizes)
    facts: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        return "\n\n".join(p for p in self.paragraphs if p)

    def texts(self) -> list[str]:
        """All human strings (for tone-linting)."""
        out = list(self.paragraphs) + [
            self.what_happened, self.why_it_matters, self.life_effect or "",
            self.attention or "", self.unchanged or "", self.next_step or "",
            self.most_useful_number or "", self.preference_note or "",
            self.confidence_note or "", self.timing_note or "",
        ]
        return [t for t in out if t]

    def as_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "paragraphs": list(self.paragraphs),
            "text": self.render(),
            "what_happened": self.what_happened,
            "why_it_matters": self.why_it_matters,
            "life_effect": self.life_effect,
            "attention": self.attention,
            "unchanged": self.unchanged,
            "next_step": self.next_step,
            "most_useful_number": self.most_useful_number,
            "preference_note": self.preference_note,
            "confidence_note": self.confidence_note,
            "timing_note": self.timing_note,
            "severity": self.severity,
            "expanded": self.expanded,
            "health": self.health,
            "facts": self.facts,
        }
