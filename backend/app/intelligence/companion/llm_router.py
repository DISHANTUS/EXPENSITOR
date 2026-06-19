"""LLM intent router — Stage 1 of the conversational upgrade.

The LLM is the *brain* of the chat: it reads a free-text message and decides WHICH
existing capability should handle it. It never does the math — for anything about
the user's own money it returns "passthrough" and the deterministic engines (the
source of truth) answer with real data.

Contract: on ANY failure (model disabled/unreachable, timeout, malformed JSON,
unknown kind) `route()` returns None, and the caller falls back to the deterministic
intent ladder. So production (no reachable model) behaves exactly as before, with
zero added latency — the chat service only calls this when settings.OLLAMA_ENABLED.

The action `command` follows a grammar the deterministic parser reliably handles
(verified against nlp.parse): add-expense / add-income / move-event. Lending and
goal-creation are intentionally left to passthrough until the parser supports them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

# Screens the router may open — must match app_router.dart / app_help routes.
_ROUTES = {
    "/home", "/settings", "/timeline", "/future-me", "/relationships", "/journey",
    "/budget-setup", "/plan", "/plan-today", "/convert", "/feedback", "/contact",
    "/appearance", "/advisor", "/voice-studio",
}

_SYSTEM = """You are the intent router for Advary, a personal-finance companion app.
Read the user's message and reply with ONE compact JSON object and NOTHING else.

Choose exactly one "kind":

- "action" — the user wants to DO something to their records. Put a SHORT canonical
  command in "command" using ONLY this grammar:
    * expense:  "add <amount> <category> expense"   (category optional)
    * income:   "received <amount> income"
    * move:     "move <event> to <YYYY-MM-DD>"
  Examples:
    "i spent like 250 on coffee" -> {"kind":"action","command":"add 250 coffee expense"}
    "got my 5000 paycheck today"  -> {"kind":"action","command":"received 5000 income"}
    "push my trip to july 1"      -> {"kind":"action","command":"move trip to 2026-07-01"}

- "navigate" — the user wants to OPEN a screen. Put the route in "route". Allowed:
  /home /settings /timeline /future-me /relationships /journey /budget-setup /plan
  /plan-today /convert /feedback /contact /appearance /advisor.
    "take me to settings" -> {"kind":"navigate","route":"/settings"}

- "answer" — a GENERAL question NOT about this user's own money/data (e.g. "what's the
  difference between a debit and credit card?", "what is APR?"), or friendly smalltalk.
  Put a short, correct, friendly reply in "text". NEVER invent numbers about the user.
    "what is a credit score?" -> {"kind":"answer","text":"A credit score is a number..."}

- "passthrough" — ANYTHING about THIS user's own money, spending, savings, budgets,
  reports, forecasts, who owes them, their habits — or if you are unsure. Reply exactly
  {"kind":"passthrough"}. The app's own engines will answer with real data; do not guess.

Rules: output JSON only — no prose, no markdown fences. When in doubt, "passthrough"."""


@dataclass(frozen=True)
class RouterDecision:
    kind: str                      # action | navigate | answer | passthrough
    command: str | None = None
    route: str | None = None
    text: str | None = None


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_decision(raw: str) -> RouterDecision | None:
    """Extract + validate the model's JSON. Pure (unit-tested); None if unusable."""
    if not raw:
        return None
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(obj, dict):
        return None
    kind = str(obj.get("kind") or "").strip().lower()
    if kind == "action":
        cmd = str(obj.get("command") or "").strip()
        return RouterDecision(kind="action", command=cmd) if cmd else None
    if kind == "navigate":
        route = str(obj.get("route") or "").strip()
        return RouterDecision(kind="navigate", route=route) if route in _ROUTES else None
    if kind == "answer":
        text = str(obj.get("text") or "").strip()
        return RouterDecision(kind="answer", text=text) if text else None
    if kind == "passthrough":
        return RouterDecision(kind="passthrough")
    return None


async def route(message: str, *, generate) -> RouterDecision | None:
    """Ask the LLM to classify `message`. `generate` is an injected callable
    (messages -> str) so this is testable without a live model. Returns a validated
    decision, or None on any failure (caller falls back to the deterministic ladder)."""
    messages = [{"role": "system", "content": _SYSTEM},
                {"role": "user", "content": (message or "").strip()[:2000]}]
    try:
        raw = await generate(messages)
    except Exception:  # noqa: BLE001 — any model/transport failure => deterministic fallback
        return None
    return parse_decision(raw)
