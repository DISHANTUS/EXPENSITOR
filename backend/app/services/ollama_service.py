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
from typing import Any

import httpx

from app.core.config import settings
from app.intelligence.commentary.ollama import adapter, narrator

log = logging.getLogger("expensitor.ollama")

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
