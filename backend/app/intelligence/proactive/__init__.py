"""Proactive Advisor — deterministic engine that surfaces already-computed
intelligence as a single unified ProactiveItem (alert/warning/reminder/
achievement/opportunity/review). No new math, no LLM. Scheduler-ready outputs."""

from __future__ import annotations

from app.intelligence.proactive.context import ProactiveContext
from app.intelligence.proactive.engine import MONTHLY, WEEKLY, build_review, generate, most_important
from app.intelligence.proactive.item import ProactiveItem

__all__ = [
    "ProactiveContext", "ProactiveItem", "generate", "most_important", "build_review", "WEEKLY", "MONTHLY",
]
