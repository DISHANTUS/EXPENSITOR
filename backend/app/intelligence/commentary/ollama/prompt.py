"""Prompt builder (C5 Phase 3b) — deterministic, domain-agnostic.

Builds the rephrase-only instruction for a local Ollama model from a
`NarrationRequest`. It receives ONLY the already-computed narrative layer
(paragraphs + grounding facts), never raw DB data. English wording is isolated
here so other languages can be added later without touching the guard/narrator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.intelligence.commentary.ollama.narrator import NarrationRequest

_STYLE = {
    "concise": "as short as possible while keeping every fact",
    "balanced": "clear and natural, roughly the same length",
    "detailed": "a little more explanatory, but introduce no new facts",
}

_SYSTEM = (
    "You are a rephrasing engine, not a financial advisor. You will be given a financial "
    "summary that is ALREADY final, correct, and complete. Your only job is to rewrite it so "
    "it reads more naturally.\n"
    "Strict rules:\n"
    "- Do NOT add, remove, or change any number, money amount, percentage, date, time, or name.\n"
    "- Do NOT add advice, warnings, recommendations, or opinions.\n"
    "- Do NOT remove any warning or risk that is present.\n"
    "- Do NOT change the order of importance, the priority, or how certain it sounds.\n"
    "- Do NOT translate; keep the same language.\n"
    "- Keep the same number of paragraphs.\n"
    "Output only the rewritten text — no preamble, no notes."
)


def build_messages(req: NarrationRequest) -> list[dict[str, str]]:
    preserve = "\n".join(f"- {t}" for t in req.grounding.grounding_tokens) or "- (none)"
    style_hint = _STYLE.get(req.style, _STYLE["balanced"])
    user = (
        f"Rewrite the following {req.kind} to read more naturally.\n"
        f"Keep exactly {req.grounding.paragraph_count} paragraph(s), separated by a blank line.\n"
        f"Style: {style_hint}.\n\n"
        f"Facts you must preserve EXACTLY (never add to or alter this list):\n{preserve}\n\n"
        f"Text to rewrite:\n" + "\n\n".join(req.paragraphs)
    )
    return [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}]
