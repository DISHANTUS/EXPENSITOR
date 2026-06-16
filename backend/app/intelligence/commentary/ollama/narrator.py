"""Generic narrator (C5 Phase 3b) — orchestrates rephrase + grounding guard.

Domain-agnostic on purpose: it narrates any deterministic prose described by a
`NarrationRequest` (commentary today; reminders / dependency alerts / savings
alerts / companion notifications / scheduled insights later). The actual model
call is injected as a `generate` coroutine, so this module stays pure and fully
testable with no network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.intelligence.commentary.ollama import guard, prompt
from app.intelligence.commentary.ollama.guard import GroundingSpec

GenerateFn = Callable[[list[dict[str, str]]], Awaitable[str]]


@dataclass(frozen=True)
class NarrationRequest:
    paragraphs: tuple[str, ...]
    grounding: GroundingSpec
    style: str = "balanced"
    kind: str = "commentary"          # prompt flavour + metrics only; no logic depends on it


@dataclass(frozen=True)
class NarrationResult:
    ok: bool
    status: str                       # success | timeout | validation_failed | error
    paragraphs: tuple[str, ...] = ()
    text: str | None = None
    reason: str = ""
    offending_tokens: tuple[str, ...] = field(default_factory=tuple)


async def narrate(req: NarrationRequest, *, generate: GenerateFn) -> NarrationResult:
    """Rephrase req.paragraphs via `generate`, then validate. Never raises."""
    try:
        raw = await generate(prompt.build_messages(req))
    except asyncio.TimeoutError:
        return NarrationResult(False, "timeout", reason="timeout")
    except Exception as exc:  # noqa: BLE001 - any failure must fall back, never surface
        return NarrationResult(False, "error", reason=type(exc).__name__)

    text = (raw or "").strip()
    if not text:
        return NarrationResult(False, "error", reason="empty")

    verdict = guard.validate(text, req.grounding)
    if not verdict.ok:
        return NarrationResult(False, "validation_failed", reason=verdict.reason,
                               offending_tokens=verdict.offending_tokens)

    return NarrationResult(True, "success", paragraphs=guard.paragraphs_of(text), text=text)
