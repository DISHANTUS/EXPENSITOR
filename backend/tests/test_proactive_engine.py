"""Pure tests for the Proactive Advisor engine (generators / ranking / reviews)."""

from __future__ import annotations

from datetime import date, timedelta

from app.intelligence.proactive import MONTHLY, WEEKLY, ProactiveContext, build_review, generate, most_important
from app.intelligence.proactive.item import REVIEW

TODAY = date(2026, 6, 15)

_STRESS = {"financial_stress_index": {"score": 30, "trend": "worsening", "trend_duration_months": 4,
                                      "confidence": "normal", "facts": {"contributors": [{"name": "savings_shortfall", "magnitude": 1.0}]}}}
_HEALTH = {"overall_score": 62, "overall_confidence": "normal", "overall_state": "fair",
           "pillars": [{"key": "discipline", "label": "Discipline", "score": 40, "state": "weak"}],
           "improving_area": None, "worsening_area": "discipline",
           "biggest_drag": {"statement": "lifestyle inflation", "pillar": "discipline", "contribution": -30},
           "biggest_contributor": {"statement": "savings consistency", "contribution": 20}}
_DEP_HIGH = {"income_amount": "15000.0000", "income_date": "2026-06-24", "risk": "high", "income_origin": "receivable"}
_REC_MOVE = {"lever_key": "move_date", "title": "Move the outing", "action": "Move it", "reasoning": "...", "expected_benefit": "x"}
_REC_FOOD = {"lever_key": "reduce_food", "title": "Trim food", "action": "Trim food a little", "reasoning": "easy", "expected_benefit": "₹500/mo"}


def _ctx(**kw) -> ProactiveContext:
    base = dict(today=TODAY, currency="INR", has_history=True)
    base.update(kw)
    return ProactiveContext(**base)


def test_cold_start_is_silent():
    ctx = _ctx(has_history=False, dependencies=(_DEP_HIGH,), metrics=_STRESS, health=_HEALTH,
               recommendations=(_REC_FOOD,), next_income={"amount": "9000", "date": (TODAY + timedelta(days=1)).isoformat()})
    assert generate(ctx) == [] and most_important(ctx) is None


def test_dependency_alert_stands_alone_and_scheduler_ready():
    item = next(i for i in generate(_ctx(dependencies=(_DEP_HIGH,))) if i.category == "dependency")
    assert item.kind == "alert" and item.severity == "alert"
    assert item.what_happened and item.why_it_matters and item.what_next  # R1
    assert "15,000" in item.most_useful_number
    # R5 scheduler contract
    d = item.as_dict()
    assert {"kind", "priority", "eligible_for_notification", "expires_at", "trigger_reason", "evidence"} <= set(d)
    assert d["eligible_for_notification"] is True and d["expires_at"] == "2026-06-24"


def test_income_reminder_only_when_imminent():
    soon = _ctx(next_income={"amount": "15000", "currency": "INR", "date": (TODAY + timedelta(days=1)).isoformat()})
    assert any(i.category == "income" and i.kind == "reminder" for i in generate(soon))
    far = _ctx(next_income={"amount": "15000", "currency": "INR", "date": (TODAY + timedelta(days=10)).isoformat()})
    assert not any(i.category == "income" for i in generate(far))


def test_stress_warning_with_duration():
    item = next(i for i in generate(_ctx(metrics=_STRESS)) if i.category == "stress")
    assert item.kind == "warning" and "4 months" in item.what_happened


def test_preference_respect_excludes_rejected_lever():
    items = generate(_ctx(recommendations=(_REC_MOVE, _REC_FOOD), excluded_levers=("move_date",)))
    opp = next(i for i in items if i.category == "recommendation")
    assert opp.title == "Trim food" and "Move the outing" not in opp.title


def test_ranking_puts_most_important_first():
    ctx = _ctx(dependencies=(_DEP_HIGH,), recommendations=(_REC_FOOD,), metrics=_STRESS)
    top = most_important(ctx)
    assert top.category == "dependency"   # high-risk dependency outranks stress/opportunity


def test_health_movement_warning_and_achievement():
    worse = next(i for i in generate(_ctx(health=_HEALTH)) if i.category == "health")
    assert worse.kind == "warning" and "Discipline" in worse.title
    improving = {**_HEALTH, "improving_area": "resilience", "worsening_area": None, "biggest_drag": None}
    ach = next(i for i in generate(_ctx(health=improving)) if i.category == "health")
    assert ach.kind == "achievement"


def test_savings_achievement():
    ctx = _ctx(metrics={"savings_consistency": {"score": 82, "trend": "flat", "trend_duration_months": None,
                                                "confidence": "normal", "facts": {}}})
    assert any(i.kind == "achievement" and i.category == "savings" for i in generate(ctx))


def test_review_composes_existing_intelligence():
    ctx = _ctx(health=_HEALTH, metrics=_STRESS, goals=({"kind": "monthly_target", "name": "Phone", "status": "behind", "shortfall": "1000"},),
               recommendations=(_REC_FOOD,))
    r = build_review(ctx, WEEKLY)
    assert r.kind == REVIEW and "62/100" in (r.most_useful_number or "")
    assert "Suggested focus" in r.what_next and r.eligible_for_notification is True
    assert "discipline" in r.what_happened  # worsening area surfaced


def test_review_cold_start_is_honest_status():
    r = build_review(_ctx(has_history=False), MONTHLY)
    assert r.kind == REVIEW and "enough activity" in r.what_happened and r.eligible_for_notification is False
