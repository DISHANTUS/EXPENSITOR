"""Adapter (C5 Phase 3b) — the only commentary-aware part of the narrator.

Turns a deterministic `Commentary.as_dict()` into a domain-agnostic
`NarrationRequest` + `GroundingSpec`. Other producers (reminders, alerts,
notifications) will add their own adapters; the guard/narrator/prompt stay generic.
"""

from __future__ import annotations

from typing import Any

from app.intelligence.commentary import GROUNDING_VERSION
from app.intelligence.commentary.ollama import guard
from app.intelligence.commentary.ollama.narrator import NarrationRequest


def from_commentary(commentary: dict[str, Any], *, style: str = "balanced") -> NarrationRequest:
    paragraphs = tuple(commentary.get("paragraphs", ()))
    det_text = "\n\n".join(paragraphs)
    grounding_tokens = tuple(commentary.get("facts", {}).get("grounding", ()))

    allowed = guard.extract_facts(det_text + " " + " ".join(grounding_tokens))

    # The figures/markers that MUST survive: the risk/attention line, the timing
    # line, and the headline number the user relies on (A2/A5/A7 substance).
    required_src = " ".join(
        t for t in (commentary.get("attention"), commentary.get("timing_note"),
                    commentary.get("most_useful_number")) if t
    )
    required = guard.extract_facts(required_src)

    spec = guard.GroundingSpec(
        allowed=allowed,
        required=required,
        grounding_tokens=grounding_tokens,
        escalation_markers=guard.escalation_markers(det_text),
        confidence_hedged=bool(commentary.get("confidence_note")),
        paragraph_count=len(paragraphs),
        ordered_items=(),  # commentary prose enumerates no list; ranking lives in the recs array
        severity=commentary.get("severity", "info"),
        version=GROUNDING_VERSION,
    )
    return NarrationRequest(paragraphs=paragraphs, grounding=spec, style=style, kind="commentary")
