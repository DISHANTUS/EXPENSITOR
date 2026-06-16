"""Pure tests for the C8 Financial Health Score (aggregator over a profile)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import metrics  # noqa: F401  (register)
from app.intelligence.behavior.data import BehaviorData, CategoryInfo, ExpenseRow, IncomeRow, build_window
from app.intelligence.behavior.profile import BehavioralMetric
from app.intelligence.behavior.registry import DESCRIPTIVE, METRIC_REGISTRY
from app.intelligence.behavior.scoring import build_profile_from_data
from app.intelligence.health import METRIC_PILLAR, PILLAR_ORDER, build_health_score
from app.intelligence.health.score import _establishment

TODAY = date(2026, 6, 15)
ESS, DISC = uuid.uuid4(), uuid.uuid4()
CATS = {ESS: CategoryInfo("Rent & Housing", True), DISC: CategoryInfo("Food & Dining", False)}
COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=Decimal("10000"), starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset(), goals=(),
        long_monthly={}, long_months=(), decision_events=(),
    )
    base.update(over)
    return BehaviorData(**base)


def _healthy_profile():
    exp = []
    d = build_window(TODAY).month_start
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("100"), DISC))
        if d.day == 11:
            exp.append(ExpenseRow(d, Decimal("2000"), ESS))
        d += timedelta(days=1)
    inc = [IncomeRow(date(y, m, 1), Decimal("12000"), "salary") for (y, m) in COMPLETE]
    return build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))


# --- structure / H1 ---------------------------------------------------------
def test_six_pillars_each_decomposable():
    h = build_health_score(_healthy_profile())
    assert [p.key for p in h.pillars] == list(PILLAR_ORDER)
    for p in h.pillars:
        assert 0 <= p.score <= 100 and p.confidence in {"low", "normal"}
        assert p.state in {"strong", "fair", "weak"}
        for key in ("warning_eligible", "achievement_eligible", "reminder_eligible"):
            assert isinstance(getattr(p, key), bool)


def test_overall_carries_facts_not_just_a_number():
    h = build_health_score(_healthy_profile()).as_dict()
    assert "overall_score" in h and "pillars" in h
    # every pillar with a score exposes contributors (facts) — score never stands alone
    scored = [p for p in h["pillars"] if p["confidence"] == "normal"]
    assert scored and all(p["contributors"] for p in scored)
    assert "contributor_index" in h and "biggest_contributor" in h and "biggest_drag" in h


# --- H2 mapping completeness / H11 descriptive exclusion --------------------
def test_every_scoring_metric_mapped_exactly_once():
    scoring_keys = {k for k, s in METRIC_REGISTRY.items() if s.direction != DESCRIPTIVE}
    assert set(METRIC_PILLAR) == scoring_keys
    assert len(METRIC_PILLAR) == len(set(METRIC_PILLAR))   # one pillar per metric


def test_descriptive_metrics_never_scored():
    descriptive = {k for k, s in METRIC_REGISTRY.items() if s.direction == DESCRIPTIVE}
    assert descriptive and not (descriptive & set(METRIC_PILLAR))
    h = build_health_score(_healthy_profile())
    seen = {c["metric_key"] for p in h.pillars for c in p.contributors}
    assert not (descriptive & seen)


# --- H7 confidence / cold start ---------------------------------------------
def test_cold_start_is_neutral_low():
    h = build_health_score(build_profile_from_data(_data()))
    assert h.overall_score == 50 and h.overall_confidence == "low"
    assert all(p.confidence == "low" for p in h.pillars)


# --- H3 establishment (8 months > 1 month) ----------------------------------
def test_establishment_rewards_sustained_behavior():
    long = BehavioralMetric("x", "d", None, 80, "good", "flat", "normal", trend_duration_months=8)
    short = BehavioralMetric("x", "d", None, 80, "good", "flat", "normal", trend_duration_months=1)
    assert _establishment(long, 5) > _establishment(short, 5)
    assert _establishment(long, 5) == 1.0       # capped at 4 months


def test_low_confidence_contributes_less():
    normal_m = BehavioralMetric("x", "d", None, 80, "good", "flat", "normal", trend_duration_months=4)
    low_m = BehavioralMetric("x", "d", None, 80, "good", "flat", "low", trend_duration_months=4)
    from app.intelligence.health.score import _conf_weight
    assert _conf_weight(normal_m.confidence) > _conf_weight(low_m.confidence)


# --- H8 advisor-ready outputs -----------------------------------------------
def test_biggest_drag_and_worsening_area_for_struggling_user():
    # rising discretionary + threshold breaches -> drag + worsening area
    exp = []
    counts = {(2026, 1): 4, (2026, 2): 6, (2026, 3): 8, (2026, 4): 10, (2026, 5): 12}
    for (y, m), k in counts.items():
        exp += [ExpenseRow(date(y, m, 1 + i), Decimal("500"), DISC) for i in range(k)]
        exp.append(ExpenseRow(date(y, m, 25), Decimal("2000"), ESS))
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    h = build_health_score(build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc))))
    assert h.biggest_drag is not None and h.biggest_drag["contribution"] < 0
    assert h.worsening_area in PILLAR_ORDER
