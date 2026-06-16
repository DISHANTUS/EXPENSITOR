"""Pure tests for the Affordability Engine (synthetic Scenarios)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.projection.affordability import evaluate
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", sigma="0", horizon_days=30, income=()):
    return Scenario(
        today=TODAY,
        horizon=TODAY + timedelta(days=horizon_days),
        base_currency="INR",
        current_balance=Decimal(balance),
        spending=SpendingModel(Decimal(mu), Decimal(sigma), "normal", 90, 90),
        income_events=tuple(income),
        outflows=(),
    )


def _income(day, amount, reliability):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(reliability), uuid.uuid4())


def test_green_band():
    res = evaluate(_scn(balance="10000", mu="0"), Decimal("1000"), TODAY + timedelta(days=10))
    assert res.verdict == "affordable" and res.affordable is True
    assert res.min_after["worst"] >= 0


def test_amber_band():
    # Sub-threshold income makes expected OK but worst (drops it) negative.
    s = _scn(balance="0", mu="0", income=[_income(5, "5000", "0.5")])
    res = evaluate(s, Decimal("2000"), TODAY + timedelta(days=10))
    assert res.verdict == "conditional"
    assert res.min_after["worst"] < 0 <= res.min_after["expected"]


def test_red_band():
    res = evaluate(_scn(balance="0", mu="0"), Decimal("5000"), TODAY + timedelta(days=10))
    assert res.verdict == "unaffordable" and res.affordable is False
    assert res.min_after["expected"] < 0
    assert res.shortfall == Decimal("5000")


def test_probability_bounds():
    s = _scn(balance="1000", mu="10", sigma="50", income=[_income(5, "3000", "0.6")])
    res = evaluate(s, Decimal("500"), TODAY + timedelta(days=10))
    assert Decimal("0") <= res.probability <= Decimal("1")


def test_assumption_tracing():
    s = _scn(balance="0", mu="0", income=[_income(5, "5000", "0.5"), _income(6, "9000", "0.95")])
    res = evaluate(s, Decimal("2000"), TODAY + timedelta(days=10))
    rels = {a.reliability for a in res.assumptions}
    # only the sub-threshold (0.5) income is an assumption; guaranteed (0.95) is not
    assert Decimal("0.5") in rels
    assert all(a.reliability < Decimal("0.85") for a in res.assumptions)


def test_downstream_dip_detection():
    # Affordable ON the date but mu drives the balance negative LATER -> not green.
    s = _scn(balance="2000", mu="50", horizon_days=40)
    res = evaluate(s, Decimal("500"), TODAY + timedelta(days=5))
    assert res.balance_on_date["worst"] > 0          # positive on the target date
    assert res.min_after["worst"] < 0                # but dips later
    assert res.verdict != "affordable"


def test_verdict_independent_of_probability():
    # A clearly green case still reports a probability, but the verdict stands alone.
    res = evaluate(_scn(balance="100000", mu="0"), Decimal("100"), TODAY + timedelta(days=3))
    assert res.verdict == "affordable"
    assert Decimal("0") <= res.probability <= Decimal("1")
