"""Tests for profile assembly: dimensions, composite, SWOR, signals, advisor, facts."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior.data import (
    BehaviorData,
    CategoryInfo,
    ExpenseRow,
    IncomeRow,
    ReceivableRow,
    SessionRow,
    build_window,
)
from app.intelligence.behavior.profile import FACTS_SCHEMA_VERSION
from app.intelligence.behavior.registry import DIMENSION_ORDER, METRIC_REGISTRY
from app.intelligence.behavior.scoring import build_profile_from_data

TODAY = date(2026, 6, 15)
ESS = uuid.uuid4()
DISC = uuid.uuid4()
SHOP = uuid.uuid4()
CATS = {
    ESS: CategoryInfo("Rent & Housing", True),
    DISC: CategoryInfo("Food & Dining", False),
    SHOP: CategoryInfo("Shopping", False),
}
COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=None, starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset({SHOP}),
    )
    base.update(over)
    return BehaviorData(**base)


def test_registry_metric_count_across_six_dimensions():
    assert len(METRIC_REGISTRY) == 33  # 16 (B1) + 5 (B1.5a) + 5 (B1.5b) + 7 (B1.5c)
    dims = {spec.dimension for spec in METRIC_REGISTRY.values()}
    assert dims == set(DIMENSION_ORDER)


def test_cold_start_is_neutral_and_low_confidence():
    profile = build_profile_from_data(_data())
    assert len(profile.metrics) == 33
    assert all(m.confidence == "low" for m in profile.metrics)
    assert profile.composite_score == 50
    assert profile.confidence == "low"
    assert profile.strengths == () and profile.weaknesses == ()


def test_full_profile_structure():
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    exp = [ExpenseRow(date(y, m, 10), Decimal("7000"), DISC) for (y, m) in COMPLETE]
    exp += [ExpenseRow(date(y, m, 11), Decimal("1500"), ESS) for (y, m) in COMPLETE]
    # rate-window daily spend so 90-day metrics have data
    d = TODAY - timedelta(days=80)
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("120" if d.weekday() >= 5 else "100"), DISC))
        if d.day % 6 == 0:
            exp.append(ExpenseRow(d, Decimal("300"), SHOP))
        d += timedelta(days=1)
    sessions = [
        SessionRow(Decimal("1000"), Decimal("800"), date(2026, 5, 1)),
        SessionRow(Decimal("1000"), Decimal("700"), date(2026, 5, 10)),
        SessionRow(Decimal("1000"), Decimal("950"), date(2026, 5, 20)),
    ]
    recs = [
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 2), date(2026, 4, 20), 0, Decimal("1000")),
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 3), date(2026, 4, 20), 0, Decimal("1000")),
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 4), date(2026, 4, 20), 0, Decimal("1000")),
    ]
    profile = build_profile_from_data(_data(
        incomes=tuple(inc), expenses=tuple(exp), sessions=tuple(sessions), receivables=tuple(recs),
        monthly_threshold=Decimal("12000"), monthly_income_estimate=Decimal("10000"),
        starting_balance=Decimal("50000"), salary_days=frozenset({1}),
    ))
    assert len(profile.metrics) == 33
    assert set(profile.dimensions) == set(DIMENSION_ORDER)
    assert 0 <= profile.composite_score <= 100
    normal = sum(1 for m in profile.metrics if m.confidence == "normal")
    assert normal >= 10  # rich data lights up most metrics
    assert profile.confidence == "normal"
    # all dimension scores in range
    assert all(0 <= dim.score <= 100 for dim in profile.dimensions.values())


def test_swor_and_signals():
    # Strong savings (positive every month), weak weekend control (2x).
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    exp = [ExpenseRow(date(y, m, 10), Decimal("6000"), DISC) for (y, m) in COMPLETE]
    d = TODAY - timedelta(days=70)
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("200" if d.weekday() >= 5 else "100"), DISC))
        d += timedelta(days=1)
    profile = build_profile_from_data(_data(incomes=tuple(inc), expenses=tuple(exp)))

    strong_keys = {s.metric_key for s in profile.strengths}
    weak_keys = {w.metric_key for w in profile.weaknesses}
    assert "savings_consistency" in strong_keys
    assert "weekend_overspending" in weak_keys

    signals = profile.signals()
    assert any(s["key"] == "weekend_overspending" for s in signals)
    for s in signals:
        assert 0.0 <= s["impact"] <= 1.0
        assert s["severity"] in {"low", "medium", "high"}


def test_advisor_view_surfaces_cuttable_categories():
    exp = [ExpenseRow(date(y, m, 10), Decimal("8000"), DISC) for (y, m) in COMPLETE]
    exp += [ExpenseRow(date(y, m, 11), Decimal("1000"), ESS) for (y, m) in COMPLETE]
    profile = build_profile_from_data(_data(expenses=tuple(exp), salary_days=frozenset({1})))
    view = profile.advisor_view()
    assert set(view) >= {
        "overspending_categories", "best_categories_to_cut", "low_impact_categories",
        "likely_impulse_periods", "strongest_savings_opportunities",
    }
    cuttable = view["best_categories_to_cut"]
    assert cuttable and all(c["controllable"] for c in cuttable)
    assert cuttable[0]["category"] == "Food & Dining"  # biggest controllable share
    assert any(p["type"] == "post_salary" for p in view["likely_impulse_periods"])


def test_to_facts_shape():
    profile = build_profile_from_data(_data())
    facts = profile.to_facts()
    assert facts["schema_version"] == FACTS_SCHEMA_VERSION
    assert facts["currency"] == "INR"
    assert len(facts["metrics"]) == 33
    assert set(facts) >= {
        "today", "window", "composite_score", "confidence", "dimensions",
        "metrics", "strengths", "weaknesses", "opportunities", "risks", "signals", "advisor",
    }
    # personality_inputs exposes the dimension vector for the future C10 engine
    pinputs = profile.personality_inputs()
    assert set(pinputs["dimensions"]) == set(DIMENSION_ORDER)
