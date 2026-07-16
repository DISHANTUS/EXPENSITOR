"""Reason-sufficiency judge — used when the companion asks "what changed?" after
a sustained category spending shift (learning loop extension).

Deterministic first: empty/very-short/filler answers are rejected outright, and
a reason that matches a known circumstance (E7's `classify_circumstance`) is
accepted outright — both fast, offline, and always available. Only genuinely
ambiguous text (not obviously filler, but not a recognized circumstance either)
is escalated to the local Ollama model for a real judgment call. On ANY model
failure (disabled, unreachable, timeout, malformed reply) this falls back to a
looser deterministic heuristic — so behavior is always defined, model or not.
"""

from __future__ import annotations

import json
import re
from typing import Awaitable, Callable

from app.intelligence.outcomes.types import classify_circumstance

_FILLER_PHRASES = (
    "idk", "i don't know", "dunno", "just did", "no reason", "nothing",
    "because", "just because", "no idea", "not sure", "dont know", "n/a",
)
# A little slack after the filler phrase, so "dunno really" / "nothing much"
# still count as filler — but a real explanation that happens to start with
# a hedge word ("not sure why, but I ordered takeout most nights") doesn't.
_FILLER_SLACK_CHARS = 8
_MIN_SUBSTANTIVE_LENGTH = 8
_MIN_FALLBACK_WORDS = 2
_MIN_FALLBACK_LENGTH = 12

_SYSTEM = """You judge whether a short answer plausibly explains a change in someone's
spending on a category. Reply with ONE compact JSON object and NOTHING else:
{"sufficient": true} or {"sufficient": false}

"sufficient": true  — the answer names a real reason, even a brief or mundane one
  (e.g. "ordering more takeout lately", "friend visiting this week", "gym fees went up").
"sufficient": false — the answer is empty, evasive, or doesn't actually explain anything
  (e.g. "idk", "just spending", "no reason", gibberish).

Output JSON only — no prose, no markdown fences."""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _contains_filler(text: str) -> bool:
    low = text.lower().strip().strip(".!?")
    return any(
        low == phrase or (low.startswith(phrase) and len(low) - len(phrase) <= _FILLER_SLACK_CHARS)
        for phrase in _FILLER_PHRASES
    )


def _deterministic_pass(reason: str) -> bool | None:
    """Fast path: returns True/False when confident, None when genuinely ambiguous."""
    text = (reason or "").strip()
    if len(text) < _MIN_SUBSTANTIVE_LENGTH or _contains_filler(text):
        return False
    if classify_circumstance(text) is not None:
        return True
    return None


def _fallback_heuristic(reason: str) -> bool:
    """Used only when the deterministic pass was ambiguous AND the model is
    unavailable — slightly looser than the fast-reject path above, but still
    rejects filler wrapped in extra words (e.g. "dunno really")."""
    text = (reason or "").strip()
    if _contains_filler(text):
        return False
    return len(text) >= _MIN_FALLBACK_LENGTH and len(text.split()) >= _MIN_FALLBACK_WORDS


def _parse(raw: str) -> bool | None:
    if not raw:
        return None
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict) or "sufficient" not in obj:
        return None
    return bool(obj["sufficient"])


async def judge_sufficiency(
    reason: str | None,
    *,
    category: str | None = None,
    generate: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
) -> bool:
    """Decide whether `reason` plausibly explains a spending change. `generate`
    is an injected callable (messages -> str), same contract as llm_router.route
    — pass None (or let it fail) to skip straight to the deterministic fallback."""
    fast = _deterministic_pass(reason or "")
    if fast is not None:
        return fast

    if generate is not None:
        prompt = f'Category: {category or "this category"}\nAnswer: "{(reason or "").strip()}"'
        messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": prompt}]
        try:
            raw = await generate(messages)
            parsed = _parse(raw)
            if parsed is not None:
                return parsed
        except Exception:  # noqa: BLE001 — any model/transport failure => deterministic fallback
            pass

    return _fallback_heuristic(reason or "")
