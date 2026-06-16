"""B1.5c Behavioral Memory Signals + Memory Confidence/Stability + Budget Recovery
Confidence, and the descriptive-exclusion composite-stability guard (R5)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import metrics  # noqa: F401  (register)
from app.intelligence.behavior.data import (
    BehaviorData,
    CategoryInfo,
    DecisionEventRow,
    ExpenseRow,
    IncomeRow,
    build_window,
)
from app.intelligence.behavior.profile import WEAK_SCORE
from app.intelligence.behavior.registry import DESCRIPTIVE, METRIC_REGISTRY
from app.intelligence.behavior.scoring import build_profile_from_data

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


def _weekend_heavy():
    # 70 days of weekend-heavy discretionary -> weekend_overspending weakness
    exp = []
    d = TODAY - timedelta(days=80)
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("400" if d.weekday() >= 5 else "80"), DISC))
        d += timedelta(days=1)
    return exp


def test_behavioral_memory_has_confidence_and_stability():
    profile = build_profile_from_data(_data(expenses=tuple(_weekend_heavy())))
    mem = profile.behavioral_memory()
    assert mem, "expected at least one behavioral memory signal"
    sig = next((s for s in mem if s["evidence_metric"] == "weekend_overspending"), mem[0])
    # the full Memory Confidence schema (S-additions)
    assert set(sig) >= {"signal", "confidence", "evidence_metric", "first_observed", "trend",
                        "trend_duration_months", "stability"}
    assert sig["confidence"] in {"high", "normal", "low"}
    assert sig["stability"] in {"stable", "forming", "changing"}


def test_memory_exposed_in_all_surfaces():
    profile = build_profile_from_data(_data(expenses=tuple(_weekend_heavy())))
    assert "behavioral_memory" in profile.advisor_view()
    assert "behavioral_memory" in profile.personality_inputs()
    assert "behavioral_memory" not in profile.to_facts()  # carried inside the advisor block
    assert profile.to_facts()["advisor"]["behavioral_memory"] == profile.behavioral_memory()


def test_memory_first_observed_tracks_trend_duration():
    # rising discretionary -> lifestyle_inflation worsening with duration -> first_observed set
    exp = []
    counts = {(2026, 1): 4, (2026, 2): 6, (2026, 3): 8, (2026, 4): 10, (2026, 5): 12}
    for (y, m), k in counts.items():
        exp += [ExpenseRow(date(y, m, 10), Decimal("500"), DISC) for _ in range(k)]
        exp.append(ExpenseRow(date(y, m, 11), Decimal("2000"), ESS))
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))
    sig = next(s for s in profile.behavioral_memory() if s["evidence_metric"] == "lifestyle_inflation")
    assert sig["trend"] == "worsening" and sig["trend_duration_months"] == 4
    assert sig["first_observed"] == "2026-02-01"   # today(Jun) minus 4 months
    assert sig["stability"] == "stable"            # long-running worsening


def test_budget_recovery_confidence_statement():
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    # alternating dips that recover next month -> recovery metrics populate
    spend = {(2026, 1): "12000", (2026, 2): "5000", (2026, 3): "12000", (2026, 4): "5000", (2026, 5): "5000"}
    exp = [ExpenseRow(date(y, m, 10), Decimal(spend[(y, m)]), DISC) for (y, m) in COMPLETE]
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))
    brc = profile.advisor_view().get("budget_recovery_confidence")
    assert brc and "recover from overspending" in brc["statement"]


def test_descriptive_metrics_excluded_from_scoring():
    # seasonal + offer proxy are descriptive -> not in any dimension's metric_keys
    profile = build_profile_from_data(_data(
        long_monthly={(2025, mo): Decimal("3000") for mo in range(6, 13)} | {(2026, mo): Decimal("3000") for mo in range(1, 7)},
        decision_events=tuple(DecisionEventRow(TODAY, True, ("offer",)) for _ in range(6)),
    ))
    descriptive = {k for k, s in METRIC_REGISTRY.items() if s.direction == DESCRIPTIVE}
    assert descriptive  # there are descriptive metrics
    in_dims = {k for dim in profile.dimensions.values() for k in dim.metric_keys}
    assert not (descriptive & in_dims)               # never scored
    assert profile.composite_score == 50             # cold-start-ish data -> still neutral, undragged


def test_composite_stability_healthy_user_not_dragged():
    inc = [IncomeRow(date(y, m, 1), Decimal("12000"), "salary") for (y, m) in COMPLETE]
    exp = []
    d = build_window(TODAY).month_start
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("100"), DISC))
        if d.day == 11:
            exp.append(ExpenseRow(d, Decimal("2000"), ESS))
        d += timedelta(days=1)
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))
    new_keys = {"payday_decay", "planned_vs_actual_drift", "expense_prediction_accuracy",
                "impulse_purchase_signals", "savings_forecast_reliability"}
    for m in profile.metrics:
        if m.key in new_keys and m.confidence == "normal":
            assert m.score >= WEAK_SCORE, f"{m.key} dragged a healthy user to {m.score}"
    assert profile.composite_score >= 50
