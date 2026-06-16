"""Pure tests for the B1.5a behavioral metrics."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.intelligence.behavior.data import BehaviorData, CategoryInfo, ExpenseRow, IncomeRow, PlannedRow, build_window

TODAY = date(2026, 6, 15)
ESS, DISC, SHOP = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
CATS = {ESS: CategoryInfo("Rent & Housing", True), DISC: CategoryInfo("Food & Dining", False),
        SHOP: CategoryInfo("Shopping", False)}
COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=Decimal("10000"), starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset({SHOP}),
    )
    base.update(over)
    return BehaviorData(**base)


def _metric(data, key):
    from app.intelligence.behavior import metrics  # noqa: F401  (register)
    from app.intelligence.behavior.registry import METRIC_REGISTRY
    return METRIC_REGISTRY[key].compute(data)


def _rising_discretionary() -> list[ExpenseRow]:
    exp: list[ExpenseRow] = []
    counts = {(2026, 1): 4, (2026, 2): 6, (2026, 3): 8, (2026, 4): 10, (2026, 5): 12}  # 500 each -> rising
    for (y, m), k in counts.items():
        exp += [ExpenseRow(date(y, m, 10), Decimal("500"), DISC) for _ in range(k)]
    return exp


# --- lifestyle inflation ----------------------------------------------------
def test_lifestyle_inflation_detects_rising_trend():
    m = _metric(_data(expenses=tuple(_rising_discretionary())), "lifestyle_inflation")
    assert m.confidence == "normal" and m.trend == "worsening" and m.trend_duration_months == 4
    assert m.value == Decimal("0.600")     # 6000 / 10000
    assert m.score <= 45                   # high + rising -> penalised


def test_lifestyle_inflation_cold_start_is_insufficient():
    m = _metric(_data(), "lifestyle_inflation")
    assert m.confidence == "low" and m.score == 50 and m.value is None


# --- spending escalation ----------------------------------------------------
def test_spending_escalation_rising():
    m = _metric(_data(expenses=tuple(_rising_discretionary())), "spending_escalation_rate")
    assert m.confidence == "normal" and m.trend == "worsening" and m.trend_duration_months == 4
    assert m.score <= 40


# --- category volatility ----------------------------------------------------
def test_category_volatility_flags_erratic_spending():
    exp = []
    disc = {(2026, 1): "1000", (2026, 2): "9000", (2026, 3): "1000", (2026, 4): "9000", (2026, 5): "1000"}
    shop = {(2026, 1): "9000", (2026, 2): "1000", (2026, 3): "9000", (2026, 4): "1000", (2026, 5): "9000"}
    for (y, m) in COMPLETE:
        exp.append(ExpenseRow(date(y, m, 10), Decimal(disc[(y, m)]), DISC))
        exp.append(ExpenseRow(date(y, m, 11), Decimal(shop[(y, m)]), SHOP))   # both erratic
    m = _metric(_data(expenses=tuple(exp)), "category_volatility")
    assert m.confidence == "normal" and float(m.value) > 0.4 and m.score < 80


# --- commitment pressure ----------------------------------------------------
def test_commitment_pressure_creep():
    planned = [PlannedRow(date(y, m, 1), Decimal("500"), "planned", None, True) for (y, m) in COMPLETE]
    m = _metric(_data(planned=tuple(planned)), "commitment_pressure")
    assert m.confidence == "normal" and m.trend == "worsening" and m.trend_duration_months == 4


def test_commitment_pressure_no_commitments_is_insufficient():
    m = _metric(_data(), "commitment_pressure")
    assert m.confidence == "low" and m.label == "no_commitment_data"


# --- upgrade / replacement --------------------------------------------------
def test_upgrade_replacement_detects_repeat_large_buys():
    exp = [ExpenseRow(date(2026, 4, 1 + (i % 20)), Decimal("100"), DISC) for i in range(20)]
    exp += [ExpenseRow(date(2026, 5, 1), Decimal("5000"), DISC), ExpenseRow(date(2026, 5, 28), Decimal("5000"), DISC)]
    m = _metric(_data(expenses=tuple(exp)), "upgrade_replacement_behavior")
    assert m.confidence == "normal" and m.facts["replacement_events"] >= 1 and m.score < 100
    assert "Food & Dining" in m.facts["categories"]


def test_upgrade_replacement_no_repeats_scores_high():
    exp = [ExpenseRow(date(2026, 5, 1 + (i % 20)), Decimal("100"), DISC) for i in range(22)]
    m = _metric(_data(expenses=tuple(exp)), "upgrade_replacement_behavior")
    assert m.facts["replacement_events"] == 0 and m.score == 100
