"""Advisor Explanation Layer — deterministic, tone-guarded, Ollama-off.

Turns structured engine outputs into concise advisor explanations (5 beats) +
action-oriented output (best_next_action / alternatives). The single source of
human phrasing that Companion / Recommendations / Ollama will consume later.
"""

from __future__ import annotations

from app.intelligence.advisor.context_block import LifeEasierContext, build_context
from app.intelligence.advisor.explanation import AdvisorAction, AdvisorExplanation

__all__ = ["AdvisorAction", "AdvisorExplanation", "LifeEasierContext", "build_context"]
