"""Pure tests for individual behavioral metrics (synthetic BehaviorData)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior.data import (
    BehaviorData,
    CategoryInfo,
    ExpenseRow,
    IncomeRow,
    IncomeSourceRow,
    PlannedRow,
    ReceivableRow,
    SessionRow,
    build_window,
)
from app.intelligence.behavior.metrics.cashflow import average_monthly_surplus, spending_stability
from app.intelligence.behavior.metrics.income import income_reliability_score, recurring_income_dependency
from app.intelligence.behavior.metrics.lifestyle import discretionary_spend_ratio, recurring_cost_load
from app.intelligence.behavior.metrics.planning import (
    budget_session_success_rate,
    threshold_violation_frequency,
)
from app.intelligence.behavior.metrics.savings import receivable_recovery_rate, savings_consistency
from app.intelligence.behavior.metrics.spending import (
    salary_day_spending_spike,
    shopping_spend_share,
    weekend_overspending,
)

TODAY = date(2026, 6, 15)  # mid-month: current partial + 5 complete prior months
ESS = uuid.uuid4()
DISC = uuid.uuid4()
SHOP = uuid.uuid4()
CATS = {
    ESS: CategoryInfo("Rent & Housing", True),
    DISC: CategoryInfo("Food & Dining", False),
    SHOP: CategoryInfo("Shopping", False),
}


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=None, starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset({SHOP}),
    )
    base.update(over)
    return BehaviorData(**base)


def _daily(start: date, end: date, weekday_amt: int, weekend_amt: int, cid=DISC) -> list[ExpenseRow]:
    rows, d = [], start
    while d <= end:
        amt = weekend_amt if d.weekday() >= 5 else weekday_amt
        rows.append(ExpenseRow(d, Decimal(amt), cid))
        d += timedelta(days=1)
    return rows


def _monthly_expenses(amounts: dict[tuple[int, int], int], cid=DISC) -> list[ExpenseRow]:
    return [ExpenseRow(date(y, m, 10), Decimal(a), cid) for (y, m), a in amounts.items()]


def _monthly_incomes(amounts: dict[tuple[int, int], int]) -> list[IncomeRow]:
    return [IncomeRow(date(y, m, 1), Decimal(a), "salary") for (y, m), a in amounts.items()]


COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]


# --------------------------------------------------------------------------- #
def test_weekend_overspending_flags_heavy_weekend():
    rows = _daily(TODAY - timedelta(days=70), TODAY, weekday_amt=100, weekend_amt=200)
    m = weekend_overspending(_data(expenses=tuple(rows)))
    assert m.confidence == "normal"
    assert m.value is not None and m.value > Decimal("1.5")
    assert m.score <= 40 and m.label == "concern"


def test_weekend_overspending_cold_start():
    m = weekend_overspending(_data(expenses=()))
    assert m.confidence == "low" and m.score == 50 and m.label == "insufficient_data"


def test_salary_spike_detected():
    rows, d = [], TODAY - timedelta(days=84)
    while d <= TODAY:
        rows.append(ExpenseRow(d, Decimal(600 if d.day <= 3 else 100), DISC))
        d += timedelta(days=1)
    m = salary_day_spending_spike(_data(expenses=tuple(rows), salary_days=frozenset({1})))
    assert m.confidence == "normal"
    assert m.value is not None and m.value >= Decimal("2")
    assert m.score <= 20


def test_salary_spike_no_salary_data():
    rows = _daily(TODAY - timedelta(days=40), TODAY, 100, 100)
    m = salary_day_spending_spike(_data(expenses=tuple(rows)))
    assert m.confidence == "low" and m.label == "no_salary_data"


def test_shopping_share():
    rows = []
    d = TODAY - timedelta(days=60)
    while d <= TODAY:
        rows.append(ExpenseRow(d, Decimal(100), DISC))
        if d.day % 5 == 0:
            rows.append(ExpenseRow(d, Decimal(400), SHOP))
        d += timedelta(days=1)
    m = shopping_spend_share(_data(expenses=tuple(rows)))
    assert m.confidence == "normal" and m.value is not None and m.value > Decimal("0.2")


def test_discretionary_ratio_uses_is_essential():
    # >=20 rows so the metric clears its data threshold; 50/50 disc/essential.
    rows = []
    for (y, m) in COMPLETE:
        for day in range(1, 6):
            rows.append(ExpenseRow(date(y, m, day), Decimal("200"), DISC))
            rows.append(ExpenseRow(date(y, m, day), Decimal("200"), ESS))
    metric = discretionary_spend_ratio(_data(expenses=tuple(rows)))
    assert metric.confidence == "normal"
    assert metric.value == Decimal("0.500")  # 50/50 discretionary/essential


def test_threshold_violation_frequency():
    # 2 of 5 complete months exceed a 5000 threshold.
    amounts = {(2026, 1): 4000, (2026, 2): 6000, (2026, 3): 4500, (2026, 4): 7000, (2026, 5): 3000}
    m = threshold_violation_frequency(_data(expenses=tuple(_monthly_expenses(amounts)), monthly_threshold=Decimal("5000")))
    assert m.confidence == "normal"
    assert m.value == Decimal("0.400")
    assert m.facts["months_violated"] == 2


def test_threshold_no_threshold():
    m = threshold_violation_frequency(_data(expenses=(), monthly_threshold=None))
    assert m.confidence == "low" and m.label == "no_threshold"


def test_budget_session_success_rate():
    sessions = [
        SessionRow(Decimal("1000"), Decimal("800"), date(2026, 5, 1)),
        SessionRow(Decimal("1000"), Decimal("900"), date(2026, 5, 10)),
        SessionRow(Decimal("1000"), Decimal("1200"), date(2026, 5, 20)),
    ]
    m = budget_session_success_rate(_data(sessions=tuple(sessions)))
    assert m.confidence == "normal"
    assert m.facts["under_budget"] == 2 and m.facts["completed"] == 3


def test_savings_consistency_positive():
    inc = _monthly_incomes({ym: 10000 for ym in COMPLETE})
    exp = _monthly_expenses({ym: 7000 for ym in COMPLETE})
    m = savings_consistency(_data(incomes=tuple(inc), expenses=tuple(exp)))
    assert m.confidence == "normal"
    assert m.value == Decimal("1.000")  # positive every month
    assert m.score >= 80


def test_receivable_recovery_rate():
    recs = [
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 3), date(2026, 4, 25), 0, Decimal("1000")),
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 2), date(2026, 4, 25), 0, Decimal("1000")),
        ReceivableRow("received", "one_time", date(2026, 5, 1), date(2026, 5, 4), date(2026, 4, 25), 0, Decimal("1000")),
        ReceivableRow("cancelled", "one_time", date(2026, 5, 1), None, date(2026, 4, 25), 0, Decimal("1000")),
    ]
    m = receivable_recovery_rate(_data(receivables=tuple(recs)))
    assert m.confidence == "normal"
    assert m.value == Decimal("0.750")  # 3 received / 4 resolved


def test_average_monthly_surplus_and_stability():
    inc = _monthly_incomes({ym: 10000 for ym in COMPLETE})
    exp = _monthly_expenses({ym: 8000 for ym in COMPLETE})
    surplus = average_monthly_surplus(_data(incomes=tuple(inc), expenses=tuple(exp)))
    assert surplus.confidence == "normal" and surplus.value == Decimal("2000.00")
    stability = spending_stability(_data(incomes=tuple(inc), expenses=tuple(exp)))
    assert stability.confidence == "normal" and stability.score >= 90  # flat spend = stable


def test_recurring_cost_load_and_income_quality():
    sources = [
        IncomeSourceRow("salary", "recurring", 1, None, Decimal("20000"), Decimal("0.9")),
        IncomeSourceRow("gift", "one_time", None, date(2026, 6, 20), Decimal("5000"), Decimal("0.5")),
    ]
    planned = [PlannedRow(date(2026, 6, 20), Decimal("3000"), "planned", None, True)]
    data = _data(income_sources=tuple(sources), planned=tuple(planned),
                 incomes=tuple(_monthly_incomes({ym: 20000 for ym in COMPLETE})), monthly_income_estimate=Decimal("20000"))
    load = recurring_cost_load(data)
    assert load.confidence == "normal" and load.value == Decimal("0.150")  # 3000/20000

    rel = income_reliability_score(data)
    assert rel.confidence == "normal" and rel.value == Decimal("1.000")  # actual meets expected

    dep = recurring_income_dependency(data)
    assert dep.confidence == "normal" and dep.value == Decimal("0.800")  # 20000/25000
