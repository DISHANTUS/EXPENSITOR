"""Pure tests for the Advisor Explanation Layer (explainers + tone guard)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.advisor import explainers, tone
from app.intelligence.advisor.explanation import AdvisorExplanation
from app.intelligence.behavior.profile import BehavioralProfile
from app.intelligence.decision import engine
from app.intelligence.decision.request import DecisionRequest
from app.intelligence.projection.affordability import AffordabilityResult
from app.intelligence.projection.goal_feasibility import GoalFeasibilityResult
from app.intelligence.projection.guidance import GuidanceResult
from app.intelligence.projection.reschedule import CandidateDate, RescheduleResult, ScoringFactor
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _assert_clean(exp: AdvisorExplanation) -> None:
    for text in exp.texts():
        assert tone.lint(text) == [], f"judgmental language in: {text!r}"
    assert exp.render()  # non-empty, concise


def test_tone_guard_flags_judgmental_language():
    assert tone.lint("This is a bad idea and wasteful") != []
    assert tone.lint("Waiting would keep ₹5,000 in reserve.") == []


def test_explain_guidance():
    g = GuidanceResult(Decimal("650"), Decimal("4550"), Decimal("2000"), [])
    exp = explainers.explain_guidance(g, currency="INR")
    assert "650" in exp.key_number
    assert exp.best_next_action is not None
    _assert_clean(exp)


def test_explain_affordability_three_verdicts():
    base = dict(amount=Decimal("2000"), target_date=TODAY, balance_on_date={}, probability=Decimal("0.9"), assumptions=[])
    ok = AffordabilityResult(verdict="affordable", affordable=True, min_after={"worst": Decimal("5000"), "expected": Decimal("6000")}, shortfall=Decimal("0"), **base)
    cond = AffordabilityResult(verdict="conditional", affordable=False, min_after={"worst": Decimal("-500"), "expected": Decimal("400")}, shortfall=Decimal("0"), **base)
    no = AffordabilityResult(verdict="unaffordable", affordable=False, min_after={"worst": Decimal("-9000"), "expected": Decimal("-5000")}, shortfall=Decimal("5000"), **base)
    e_ok = explainers.explain_affordability(ok, currency="INR", item_label="the game")
    e_no = explainers.explain_affordability(no, currency="INR", item_label="the phone")
    assert e_ok.severity == "success"
    assert e_no.severity == "alert" and "5,000" in e_no.impact
    for e in (e_ok, explainers.explain_affordability(cond, currency="INR"), e_no):
        _assert_clean(e)


def test_explain_goal():
    g = GoalFeasibilityResult(
        goal_amount=Decimal("50000"), target_date=TODAY + timedelta(days=60), feasible=False,
        probability=Decimal("0.4"), confidence="low", required_daily_saving=Decimal("200"),
        required_weekly_saving=Decimal("1400"), required_monthly_saving=Decimal("6000"),
        projected_surplus_or_shortfall={"worst": Decimal("-5000"), "expected": Decimal("-1000"), "best": Decimal("0")},
    )
    exp = explainers.explain_goal(g, currency="INR")
    assert exp.best_next_action.action == "save_daily" and "200" in exp.key_number
    _assert_clean(exp)


def test_explain_reschedule_reasoning_from_factors():
    best = TODAY + timedelta(days=12)
    candidate = CandidateDate(best, 80, True, Decimal("8000"), 10, [ScoringFactor("receivable_arrival", Decimal("5000"))])
    result = RescheduleResult(TODAY, 30, [candidate], best, [], [])
    exp = explainers.explain_reschedule(result, currency="INR", item_label="the outing")
    assert exp.reason is not None and "5,000" in exp.reason and "arrives before then" in exp.reason
    _assert_clean(exp)


def test_explain_behavior_minimal_profile():
    profile = BehavioralProfile(
        today=TODAY, base_currency="INR", window={}, composite_score=78, confidence="normal",
        metrics=(), dimensions={}, strengths=(), weaknesses=(), opportunities=(), risks=(),
        recommendation_signals=(), advisor={},
    )
    exp = explainers.explain_behavior(profile)
    assert "78" in exp.impact
    _assert_clean(exp)


def test_explain_decision_end_to_end():
    scn = Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
        current_balance=Decimal("100000"), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
        income_events=(), outflows=(),
    )
    result = engine.evaluate(scn, DecisionRequest(item_label="a game", amount_base=Decimal("2000")))
    exp = explainers.explain_decision(result)
    assert exp.best_next_action is not None
    assert exp.severity in ("success", "warning", "alert", "info")
    _assert_clean(exp)
