"""Pure tests for the B1.5a trend engine (real trend_duration_months)."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.behavior import trend
from app.intelligence.behavior.registry import DESCRIPTIVE, HIGHER_BETTER, LOWER_BETTER


def _d(*xs):
    return [Decimal(str(x)) for x in xs]


def test_monotonic_worsening_run_length_lower_better():
    # rising values, lower-is-better -> worsening, 4 consecutive steps
    t, dur = trend.run_length(_d(100, 120, 140, 160, 180), LOWER_BETTER)
    assert t == "worsening" and dur == 4


def test_monotonic_improving_higher_better():
    t, dur = trend.run_length(_d(10, 20, 30), HIGHER_BETTER)
    assert t == "improving" and dur == 2


def test_reversal_resets_duration():
    # ...rises then the latest step falls; lower-better -> latest improving, dur 1
    t, dur = trend.run_length(_d(100, 130, 160, 150), LOWER_BETTER)
    assert t == "improving" and dur == 1


def test_flat_within_deadband():
    t, dur = trend.run_length(_d(100, 101, 100), LOWER_BETTER)
    assert t == "flat" and dur >= 1


def test_too_short_is_unknown():
    assert trend.run_length(_d(100), LOWER_BETTER) == ("unknown", 0)


def test_descriptive_is_flat():
    t, _ = trend.run_length(_d(1, 5, 2), DESCRIPTIVE)
    assert t == "flat"


def test_series_for_months_orders_values():
    months = ((2026, 1), (2026, 2), (2026, 3))
    series = trend.series_for_months({(2026, 2): Decimal("5"), (2026, 1): Decimal("1")}, months)
    assert series == [Decimal("1"), Decimal("5"), Decimal("0")]
