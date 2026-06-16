"""Pure tests for the B1.5b metrics + S11/S12 profile features."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import metrics  # noqa: F401  (register)
from app.intelligence.behavior.data import (
    BehaviorData,
    CategoryInfo,
    ExpenseRow,
    GoalRow,
    IncomeRow,
    IncomeSourceRow,
    PlannedRow,
    build_window,
)
from app.intelligence.behavior.registry import METRIC_REGISTRY
from app.intelligence.behavior.scoring import build_profile_from_data

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
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset({SHOP}), goals=(),
    )
    base.update(over)
    return BehaviorData(**base)


def _m(data, key):
    return METRIC_REGISTRY[key].compute(data)


def _dense(monthly_disc: dict, essential="2000") -> list[ExpenseRow]:
    exp = []
    for (y, m), total in monthly_disc.items():
        each = Decimal(total) / 5
        exp += [ExpenseRow(date(y, m, 10), each, DISC) for _ in range(5)]
        exp.append(ExpenseRow(date(y, m, 11), Decimal(essential), ESS))
    return exp


# --- financial stress (S1) --------------------------------------------------
def test_financial_stress_exposes_contributors():
    exp = _dense({(2026, 1): "9000", (2026, 2): "11000", (2026, 3): "13000",
                  (2026, 4): "14000", (2026, 5): "15000"})
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    m = _m(_data(expenses=tuple(exp), incomes=tuple(inc), monthly_threshold=Decimal("11000")), "financial_stress_index")
    assert m.confidence == "normal" and m.score < 60
    names = {c["name"] for c in m.facts["contributors"]}
    assert "savings_shortfall" in names and "threshold_breaches" in names
    assert m.trend in ("worsening", "flat", "improving")


def test_financial_stress_cold_start_insufficient():
    m = _m(_data(), "financial_stress_index")
    assert m.confidence == "low" and m.score == 50


# --- goal interference (S2) -------------------------------------------------
def test_goal_interference_names_culprits():
    exp = _dense({(2026, 1): "9000", (2026, 2): "9500", (2026, 3): "10000",
                  (2026, 4): "9500", (2026, 5): "9000"})
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    goal = GoalRow("monthly_target", "Monthly savings", Decimal("3000"), None, date(2025, 12, 1), "active")
    m = _m(_data(expenses=tuple(exp), incomes=tuple(inc), goals=(goal,)), "goal_interference_rate")
    assert m.confidence == "normal" and m.facts["interference_rate"] > 0
    assert m.facts["culprits"] and m.facts["culprits"][0]["category"] == "Food & Dining"


def test_goal_interference_no_goals_insufficient():
    m = _m(_data(expenses=tuple(_dense({ym: "5000" for ym in COMPLETE}))), "goal_interference_rate")
    assert m.confidence == "low" and m.label == "no_goals"


# --- recovery metrics (S3) --------------------------------------------------
def test_savings_recovery_rate_from_dips():
    # alternate negative / positive net -> dips that recover next month
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    spend = {(2026, 1): "12000", (2026, 2): "5000", (2026, 3): "12000", (2026, 4): "5000", (2026, 5): "5000"}
    exp = _dense(spend, essential="0")
    m = _m(_data(expenses=tuple(exp), incomes=tuple(inc)), "savings_recovery_rate")
    assert m.confidence == "normal" and m.facts["dip_events"] >= 2 and m.facts["recovery_rate"] > 0


def test_spending_recovery_speed_from_spikes():
    spend = {(2026, 1): "3000", (2026, 2): "9000", (2026, 3): "3000", (2026, 4): "3000", (2026, 5): "3000"}
    m = _m(_data(expenses=tuple(_dense(spend, essential="0"))), "spending_recovery_speed")
    assert m.confidence == "normal" and m.facts["spike_count"] >= 1 and m.facts["mean_recovery_months"] >= 1


def test_recovery_cold_start_insufficient():
    assert _m(_data(), "savings_recovery_rate").confidence == "low"
    assert _m(_data(), "spending_recovery_speed").confidence == "low"


# --- income concentration ---------------------------------------------------
def test_income_concentration_two_sources():
    srcs = (IncomeSourceRow("salary", "recurring", 1, None, Decimal("9000"), Decimal("0.95")),
            IncomeSourceRow("freelance", "one_time", None, date(2026, 6, 1), Decimal("1000"), Decimal("0.5")))
    m = _m(_data(income_sources=srcs), "income_dependency_concentration")
    assert m.confidence == "normal" and float(m.value) > 0.5   # heavily weighted to salary


def test_income_concentration_single_source_insufficient():
    srcs = (IncomeSourceRow("salary", "recurring", 1, None, Decimal("10000"), Decimal("0.95")),)
    m = _m(_data(income_sources=srcs), "income_dependency_concentration")
    assert m.confidence == "low" and m.label == "single_or_no_source"
