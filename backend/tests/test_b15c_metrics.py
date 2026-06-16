"""Pure tests for B1.5c metrics (payday/drift/prediction/impulse/forecast/seasonal/offer)."""

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
    GoalRow,
    IncomeRow,
    PlannedRow,
    build_window,
)
from app.intelligence.behavior.registry import METRIC_REGISTRY

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


def _m(data, key):
    return METRIC_REGISTRY[key].compute(data)


# --- payday decay -----------------------------------------------------------
def test_payday_decay_front_loading():
    # salary on the 1st; spend heavily in the first 3 days of each cycle
    exp = []
    d = TODAY - timedelta(days=85)
    while d <= TODAY:
        amt = "400" if d.day <= 3 else "40"
        exp.append(ExpenseRow(d, Decimal(amt), DISC))
        d += timedelta(days=1)
    m = _m(_data(expenses=tuple(exp), salary_days=frozenset({1})), "payday_decay")
    assert m.confidence == "normal" and float(m.value) > 0.3 and m.score < 90


def test_payday_decay_no_salary_insufficient():
    assert _m(_data(), "payday_decay").confidence == "low"


# --- planned vs actual drift ------------------------------------------------
def test_planned_vs_actual_drift_overspend():
    planned = [PlannedRow(date(y, m, 5), Decimal("5000"), "planned", None, False) for (y, m) in COMPLETE]
    exp = [ExpenseRow(date(y, m, 10), Decimal("8000"), DISC) for (y, m) in COMPLETE]
    m = _m(_data(expenses=tuple(exp), planned=tuple(planned)), "planned_vs_actual_drift")
    assert m.confidence == "normal" and float(m.value) > 0 and m.score < 80


# --- expense prediction accuracy --------------------------------------------
def test_expense_prediction_accuracy_stable_high():
    exp = [ExpenseRow(date(y, m, 10), Decimal("5000"), DISC) for (y, m) in COMPLETE]
    m = _m(_data(expenses=tuple(exp)), "expense_prediction_accuracy")
    assert m.confidence == "normal" and m.score >= 80   # perfectly flat -> predictable


# --- impulse signals (timing proxy) -----------------------------------------
def test_impulse_signals_clusters():
    exp = []
    for k in range(8):
        day = TODAY - timedelta(days=k * 7)
        exp += [ExpenseRow(day, Decimal("100"), DISC) for _ in range(4)]   # 4 buys same day = cluster
    m = _m(_data(expenses=tuple(exp)), "impulse_purchase_signals")
    assert m.confidence == "normal" and m.facts["cluster_days"] >= 1 and m.facts["kind"] == "timing_proxy"


# --- savings forecast reliability -------------------------------------------
def test_savings_forecast_reliability_hit_rate():
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    exp = [ExpenseRow(date(y, m, 10), Decimal("6000"), DISC) for (y, m) in COMPLETE]   # net 4000 >= 3000
    goal = GoalRow("monthly_target", "Monthly", Decimal("3000"), None, date(2025, 12, 1), "active")
    m = _m(_data(expenses=tuple(exp), incomes=tuple(inc), goals=(goal,)), "savings_forecast_reliability")
    assert m.confidence == "normal" and m.facts["hit_rate"] == 1.0 and m.score == 100


def test_savings_forecast_reliability_no_target_insufficient():
    assert _m(_data(), "savings_forecast_reliability").label == "no_monthly_target"


# --- seasonal (descriptive) -------------------------------------------------
def test_seasonal_needs_history():
    assert _m(_data(), "seasonal_spending_pattern").label == "needs_more_history"


def test_seasonal_with_13_months():
    lm = {(2025, mo): Decimal("3000") for mo in range(6, 13)}
    lm.update({(2026, mo): Decimal("9000" if mo == 1 else "3000") for mo in range(1, 7)})  # Jan peak
    m = _m(_data(long_monthly=lm), "seasonal_spending_pattern")
    assert m.confidence == "normal" and 1 in m.facts["peak_months"]


# --- offer susceptibility proxy ---------------------------------------------
def test_offer_proxy_low_confidence_exposure():
    evs = tuple(DecisionEventRow(TODAY, i % 2 == 0, ("offer",) if i % 2 == 0 else ()) for i in range(6))
    m = _m(_data(decision_events=evs), "offer_susceptibility_proxy")
    assert m.confidence == "low"                       # ALWAYS low (exposure, not influence)
    assert m.facts["kind"] == "exposure_proxy" and 0 < m.facts["offer_exposure_rate"] <= 1


def test_offer_proxy_too_few_decisions_insufficient():
    evs = (DecisionEventRow(TODAY, True, ("offer",)),)
    assert _m(_data(decision_events=evs), "offer_susceptibility_proxy").label == "insufficient_decisions"
