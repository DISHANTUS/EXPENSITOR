"""Behavioral trend engine (B1.5a) — real trend + trend_duration_months.

Replaces the binary recent-vs-prior `classify_trend` for metrics that can supply
a monthly value series. `run_length` walks the series newest-first and counts how
many consecutive monthly steps moved the same way toward the healthy direction —
that count IS the trend duration in months. Pure, deterministic.
"""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import registry

DEADBAND = 0.05  # relative change below this is treated as flat


def series_for_months(month_map: dict, months: tuple) -> list[Decimal]:
    """Ordered (oldest -> newest) value list for the given months."""
    return [month_map.get(ym, Decimal("0")) for ym in months]


def _step_direction(prev: float, cur: float, direction: str) -> str:
    if direction == registry.DESCRIPTIVE:
        return "flat"
    if prev == 0:
        if abs(cur) < 1e-9:
            return "flat"
        rose = cur > 0
    else:
        change = (cur - prev) / abs(prev)
        if abs(change) < DEADBAND:
            return "flat"
        rose = change > 0
    if direction == registry.HIGHER_BETTER:
        return "improving" if rose else "worsening"
    return "worsening" if rose else "improving"


def run_length(values: list[Decimal], direction: str) -> tuple[str, int]:
    """Return (trend, duration_months). duration = consecutive trailing months in
    the current direction (or the trailing flat run). ('unknown', 0) if < 2 points."""
    pts = [float(v) for v in values]
    if len(pts) < 2:
        return "unknown", 0
    steps = [_step_direction(pts[i - 1], pts[i], direction) for i in range(1, len(pts))]
    last = steps[-1]
    duration = 0
    for step in reversed(steps):
        if step == last:
            duration += 1
        else:
            break
    return last, duration


def trend_of(month_map: dict, months: tuple, direction: str) -> tuple[str, int]:
    return run_length(series_for_months(month_map, months), direction)
