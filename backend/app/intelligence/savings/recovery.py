"""Savings recovery — structured options only (no prose, never auto-applied).

The system proposes; the user decides. Rejected choices can be excluded so the
same recommendation is not repeated (the advisor then surfaces alternatives).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.intelligence.savings.state import RecoveryOption

DEFAULT_DISTRIBUTE_MONTHS = 3


def recovery_options(
    shortfall: Decimal, *, distribute_months: int = DEFAULT_DISTRIBUTE_MONTHS, excluded: tuple[str, ...] = ()
) -> list[RecoveryOption]:
    months = max(1, distribute_months)
    per_month = (shortfall / months).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    options = [
        RecoveryOption("keep_unchanged", {"shortfall": str(shortfall)}),
        RecoveryOption("distribute", {"distribute_months": months, "per_month_add": str(per_month),
                                      "shortfall": str(shortfall)}),
        RecoveryOption("new_plan", {"shortfall": str(shortfall)}),
    ]
    return [o for o in options if o.choice not in excluded]
