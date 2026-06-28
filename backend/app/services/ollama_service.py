"""Ollama narrator service (C5 Phase 3b) — the only I/O for narration.

Owns the shared httpx client, the hard timeout, the settings gate, and the
observability counters. Calls the pure generic narrator with a `generate`
callable. Narration can NEVER affect the request outcome: every failure
(disabled / timeout / HTTP / malformed / validation / exception) falls back to
the deterministic commentary, and the user never notices (B5).
"""

from __future__ import annotations

import asyncio
import logging
import re
import zlib
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.core.config import settings
from app.intelligence.commentary.ollama import adapter, guard, narrator
from app.intelligence.mood import greeting_narration

log = logging.getLogger("expensitor.ollama")
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SIMILARITY_THRESHOLD = 0.85

# Observability only (process-local; not analytics, no dashboards) — B8.
_METRICS: dict[str, int] = {
    "attempts": 0, "success": 0, "validation_failed": 0, "timeout": 0, "error": 0, "fallback": 0,
}

_client: httpx.AsyncClient | None = None


def metrics_snapshot() -> dict[str, int]:
    return dict(_METRICS)


def reset_metrics() -> None:
    for key in _METRICS:
        _METRICS[key] = 0


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT_SECONDS)
    return _client


async def aclose() -> None:
    """Close the shared client (wired to app shutdown)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _generate(messages: list[dict[str, str]]) -> str:
    """Real model call against a LOCAL Ollama, bounded by a hard timeout (B9)."""
    client = _get_client()

    async def _call() -> str:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={"model": settings.OLLAMA_MODEL, "messages": messages, "stream": False,
                  "options": {"temperature": 0.2, "seed": 7}},
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    return await asyncio.wait_for(_call(), timeout=settings.OLLAMA_TIMEOUT_SECONDS)


def _make_generate(*, temperature: float, seed: int):
    """A generate fn with greeting-friendly variety (higher temp, varying seed),
    that strips any <think> reasoning a thinking model (e.g. qwen3) may emit."""
    async def gen(messages: list[dict[str, str]]) -> str:
        client = _get_client()

        async def _call() -> str:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={"model": settings.OLLAMA_MODEL, "messages": messages, "stream": False,
                      "options": {"temperature": temperature, "seed": seed}},
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content", "")
            return _THINK_RE.sub("", content).strip()

        return await asyncio.wait_for(_call(), timeout=settings.OLLAMA_TIMEOUT_SECONDS)

    return gen


async def complete(messages: list[dict[str, str]]) -> str:
    """One-shot, low-temperature completion for structured/routing use (NOT
    narration). Disables a thinking model's reasoning for speed (≈2.5s vs ≈5s on
    qwen3:8b) and strips any leftover <think> block. Raises on disabled / timeout /
    HTTP error — the caller decides the fallback. The chat router gates on
    settings.OLLAMA_ENABLED before calling this."""
    client = _get_client()

    async def _post(think: bool | None) -> str:
        body: dict[str, Any] = {"model": settings.OLLAMA_MODEL, "messages": messages,
                                "stream": False, "options": {"temperature": 0.0, "seed": 7}}
        if think is not None:
            body["think"] = think
        resp = await client.post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=body)
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        return _THINK_RE.sub("", content).strip()

    async def _call() -> str:
        try:
            return await _post(False)          # fast path: reasoning off
        except httpx.HTTPStatusError:
            return await _post(None)            # a model/version that rejects "think" → plain call

    return await asyncio.wait_for(_call(), timeout=settings.OLLAMA_TIMEOUT_SECONDS)


_REPHRASE_SYSTEM = (
    "You make a personal-finance assistant's reply sound warm and natural. Keep EVERY "
    "number, money amount, percentage, date, time and name EXACTLY as written — never "
    "add, remove, change, or invent any figure or name. Same meaning, one or two short "
    "sentences. Reply with ONLY the rephrased text."
)


async def narrate_text(text: str, *, generate=None) -> str:
    """Rephrase a deterministic chat answer conversationally WITHOUT altering any
    grounded fact (number / money / percent / date / time). Returns the original on
    disabled / failure / guard rejection, so it can never change the meaning or invent
    a figure. The caller gates on settings.OLLAMA_ENABLED."""
    src = (text or "").strip()
    if not src or (generate is None and not settings.OLLAMA_ENABLED):
        return text
    facts = guard.extract_facts(src)
    spec = guard.GroundingSpec(
        allowed=dict(facts),
        required={k: facts[k] for k in ("money", "percent", "date", "time", "number")},
        escalation_markers=guard.escalation_markers(src),
        confidence_hedged=guard.is_hedged(src),
        enforce_paragraph_count=False,
        allow_new_entities=True,   # casual words ok; figures stay strictly grounded
    )
    gen = generate or complete
    _METRICS["attempts"] += 1
    try:
        out = (await gen([{"role": "system", "content": _REPHRASE_SYSTEM},
                          {"role": "user", "content": src}])).strip()
    except Exception:  # noqa: BLE001 — any model/transport failure => keep deterministic
        _METRICS["error"] += 1
        return text
    if out and guard.validate(out, spec).ok:
        _METRICS["success"] += 1
        return out
    _METRICS["fallback"] += 1
    return text


def _too_similar(text: str, recents: list[str]) -> bool:
    low = (text or "").lower()
    return any(SequenceMatcher(None, low, (r or "").lower()).ratio() >= _SIMILARITY_THRESHOLD
               for r in recents if r)


async def narrate_greeting(salutation: str, lines: list[str], *, style: str | None = None,
                           recent_texts: list[str] | None = None, generate=None) -> dict[str, Any]:
    """Rephrase a deterministic greeting via Ollama (rephrase-only, grounded).
    Returns {ok, status, text, source}. Falls back to deterministic on
    disabled/timeout/error/validation/too-similar — caller keeps the template."""
    if generate is None and not settings.OLLAMA_ENABLED:
        return {"ok": False, "status": "disabled", "text": None, "source": "deterministic"}
    style = style or settings.OLLAMA_NARRATION_STYLE
    recents = recent_texts or []
    req = greeting_narration.build_request(lines, style=style)
    _METRICS["attempts"] += 1
    base_seed = zlib.crc32(req.paragraphs[0].encode("utf-8"))

    def _compose(body: str) -> str:
        # Prepend the verbatim time salutation — never narrated, never reworded.
        return f"{salutation} {body}".strip() if salutation else body

    # Initial attempt + one regeneration if too similar to recent greetings.
    for attempt in range(2):
        gen = generate or _make_generate(temperature=0.7, seed=base_seed + attempt)
        result = await narrator.narrate(req, generate=gen)
        if not result.ok:
            _METRICS[result.status] = _METRICS.get(result.status, 0) + 1
            _METRICS["fallback"] += 1
            log.debug("greeting narration fallback: status=%s reason=%s offending=%s",
                      result.status, result.reason, list(result.offending_tokens))
            return {"ok": False, "status": result.status, "text": None, "source": "deterministic"}
        full = _compose(result.text)
        if not _too_similar(full, recents):
            _METRICS["success"] += 1
            return {"ok": True, "status": "success", "text": full, "source": "ollama"}
    # Both attempts looked like recent greetings — fall back to keep it fresh.
    _METRICS["fallback"] += 1
    return {"ok": False, "status": "too_similar", "text": None, "source": "deterministic"}


async def narrate_commentary(commentary: dict[str, Any], *, style: str | None = None, generate=None) -> dict[str, Any]:
    """Best-effort rephrase of an already-final commentary. Returns
    {ok, status, narrated}. Deterministic commentary is untouched (B1/B7)."""
    gen = generate or _generate
    style = style or settings.OLLAMA_NARRATION_STYLE
    req = adapter.from_commentary(commentary, style=style)

    _METRICS["attempts"] += 1
    result = await narrator.narrate(req, generate=gen)

    if result.ok:
        _METRICS["success"] += 1
        return {"ok": True, "status": "success",
                "narrated": {"paragraphs": list(result.paragraphs), "text": result.text,
                             "style": style, "source": "ollama"}}

    _METRICS[result.status] = _METRICS.get(result.status, 0) + 1
    _METRICS["fallback"] += 1
    # Validation diagnostics for debugging/observability — never shown to users.
    log.debug("ollama narration fallback: status=%s reason=%s offending=%s",
              result.status, result.reason, list(result.offending_tokens))
    return {"ok": False, "status": result.status, "narrated": None}
