"""Importing this package registers every behavioral metric on the registry.

Order here defines the order metrics appear in the profile / to_facts().
"""

from __future__ import annotations

from app.intelligence.behavior.metrics import (  # noqa: F401
    cashflow,
    income,
    lifestyle,
    planning,
    savings,
    spending,
    advanced,     # B1.5a
    resilience,   # B1.5b
    forecasting,  # B1.5c — registered last
)
