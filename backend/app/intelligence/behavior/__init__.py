"""Behavioral Intelligence (C6) — the foundation of the Financial Advisor Brain.

Importing this package ensures all metrics are registered and exposes the
profile builder. Deterministic, confidence-scored, derived from stored data
only — no LLM, no new tables.
"""

from __future__ import annotations

import app.intelligence.behavior.metrics  # noqa: F401  (registers metrics)
from app.intelligence.behavior.profile import BehavioralProfile
from app.intelligence.behavior.scoring import build_profile_from_data

__all__ = ["BehavioralProfile", "build_profile_from_data"]
