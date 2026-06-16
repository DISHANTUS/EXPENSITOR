"""B1.5b profile features: goal sacrifice (S12), recovery personalities (S4/S11),
root-cause across all evidence (S7), and composite stability (R5)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from app.intelligence.behavior import metrics  # noqa: F401  (register)
from app.intelligence.behavior.data import (
    BehaviorData,
    CategoryInfo,
    ExpenseRow,
    GoalRow,
    IncomeRow,
    build_window,
)
from app.intelligence.behavior.profile import WEAK_SCORE
from app.intelligence.behavior.scoring import build_profile_from_data

TODAY = date(2026, 6, 15)
ESS, DISC = uuid.uuid4(), uuid.uuid4()
CATS = {ESS: CategoryInfo("Rent & Housing", True), DISC: CategoryInfo("Food & Dining", False)}
COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]
_NEW_KEYS = {"financial_stress_index", "goal_interference_rate", "savings_recovery_rate",
             "spending_recovery_speed", "income_dependency_concentration"}


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=Decimal("10000"), starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset(), goals=(),
    )
    base.update(over)
    return BehaviorData(**base)


def _dense(monthly_disc: dict, essential="2000") -> list[ExpenseRow]:
    exp = []
    for (y, m), total in monthly_disc.items():
        each = Decimal(total) / 5
        exp += [ExpenseRow(date(y, m, 10), each, DISC) for _ in range(5)]
        if essential != "0":
            exp.append(ExpenseRow(date(y, m, 11), Decimal(essential), ESS))
    return exp


def test_goal_sacrifice_detected():
    # net ~3000/mo; two goals whose combined pace exceeds it -> one is sacrificed (S12)
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    exp = _dense({ym: "7000" for ym in COMPLETE}, essential="0")
    goals = (GoalRow("monthly_target", "Phone fund", Decimal("2500"), None, date(2025, 12, 1), "active"),
             GoalRow("monthly_target", "Emergency fund", Decimal("2500"), None, date(2025, 12, 1), "active"))
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc), goals=goals))
    sac = profile.advisor_view().get("goal_sacrifice")
    assert sac and "Phone fund" in sac["statement"] and "Emergency fund" in sac["statement"]


def test_recovery_and_stress_recovery_profiles_in_personality_inputs():
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    spend = {(2026, 1): "12000", (2026, 2): "5000", (2026, 3): "12000", (2026, 4): "5000", (2026, 5): "5000"}
    profile = build_profile_from_data(_data(expenses=tuple(_dense(spend, essential="0")), incomes=tuple(inc)))
    pin = profile.personality_inputs()
    assert pin["recovery_profile"] in {"fast", "average", "slow"}
    assert "stress_recovery_profile" in pin


def test_root_cause_includes_stress_evidence():
    exp = _dense({(2026, 1): "9000", (2026, 2): "11000", (2026, 3): "13000",
                  (2026, 4): "14000", (2026, 5): "15000"})
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc),
                                            monthly_threshold=Decimal("11000")))
    rc = profile.advisor_view().get("root_cause")
    assert rc and "biggest pressure on your finances" in rc["statement"]


def test_composite_stability_healthy_user_not_dragged():
    inc = [IncomeRow(date(y, m, 1), Decimal("12000"), "salary") for (y, m) in COMPLETE]
    exp = _dense({ym: "3000" for ym in COMPLETE})   # flat, comfortable
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))
    healthy_new = [m for m in profile.metrics if m.key in _NEW_KEYS and m.confidence == "normal"]
    for m in healthy_new:
        assert m.score >= WEAK_SCORE, f"{m.key} dragged a healthy user to {m.score}"
    assert profile.composite_score >= 50
