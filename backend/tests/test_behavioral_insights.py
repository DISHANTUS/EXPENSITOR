"""Pure tests for the reusable behavioral insight layer (B2)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.intelligence.advisor import tone
from app.intelligence.behavior.insights import InsightContext, build_behavioral_insights
from app.intelligence.behavior.profile import BehavioralMetric, BehavioralProfile, SworItem

TODAY = date(2026, 6, 15)


def _metric(key, dim, score, trend="flat", conf="normal", facts=None):
    return BehavioralMetric(key=key, dimension=dim, value=Decimal("1"), score=score, label="x",
                            trend=trend, confidence=conf, facts=facts or {})


def _profile(**over) -> BehavioralProfile:
    base = dict(
        today=TODAY, base_currency="INR", window={"complete_months": 5, "rate_days": 90, "buckets": 6},
        composite_score=65, confidence="normal",
        metrics=(
            _metric("savings_consistency", "savings_resilience", 90, "improving", facts={"months_positive": 4}),
            _metric("receivable_recovery_rate", "savings_resilience", 80, "improving"),
            _metric("weekend_overspending", "spending_discipline", 20, "worsening"),
        ),
        dimensions={},
        strengths=(SworItem("savings_consistency", "savings_resilience", "Strong savings consistency", "strong", 90, "improving", "normal"),),
        weaknesses=(SworItem("weekend_overspending", "spending_discipline", "Weekend spending control needs attention", "high", 20, "worsening", "normal"),),
        opportunities=(SworItem("shopping_spend_share", "spending_discipline", "Room to improve shopping spending share", "high", 55, "flat", "normal"),),
        risks=(SworItem("discretionary_spend_ratio", "lifestyle_profile", "Discretionary spending ratio is trending the wrong way", "high", 30, "worsening", "normal"),),
        recommendation_signals=(),
        advisor={"overspending_categories": [{"category": "Food & Dining", "share": 0.3, "monthly_avg": "5000", "controllable": True, "direction": "worsening"}],
                 "best_categories_to_cut": [{"category": "Food & Dining", "share": 0.3, "monthly_avg": "5000", "controllable": True, "direction": "worsening"}],
                 "low_impact_categories": [], "likely_impulse_periods": [], "strongest_savings_opportunities": []},
    )
    base.update(over)
    return BehavioralProfile(**base)


def _by_kind(insights):
    out: dict[str, list] = {}
    for i in insights:
        out.setdefault(i.kind, []).append(i)
    return out


def test_actionable_fields_present_and_tone_clean():
    insights = build_behavioral_insights(_profile())
    assert insights
    for ins in insights:
        assert ins.finding and ins.impact and ins.reasoning and ins.recommendation and ins.consequences
        assert tone.lint(" ".join(ins.texts())) == []


def test_weakness_is_actionable_and_goal_linked():
    ctx = InsightContext(goals=(("custom_goal", "Phone"),))
    by = _by_kind(build_behavioral_insights(_profile(), context=ctx))
    weak = by["weakness"][0]
    assert "Food & Dining" in weak.reasoning and "5,000" in weak.reasoning   # quantified contributor
    assert "if saving more matters to you" in weak.recommendation            # conditional, not a command
    assert weak.consequences and any(g["goal"] == "Phone" for g in weak.goal_links)


def test_risk_is_behavioural_not_insolvency():
    by = _by_kind(build_behavioral_insights(_profile()))
    assert "not insolvency" in by["risk"][0].consequences


def test_achievement_and_improvement_from_facts():
    by = _by_kind(build_behavioral_insights(_profile()))
    achievements = {a.metric_key for a in by.get("achievement", [])}
    assert "savings_consistency" in achievements          # 4 straight positive months
    assert "receivable_recovery_rate" in achievements     # improving trend
    # receivable recovery (improving, not a strength) also surfaces as improvement
    assert any(i.metric_key == "receivable_recovery_rate" for i in by.get("improvement", []))


def test_dependency_insight_from_context():
    dep = {"income_origin": "receivable", "income_amount": "15000", "income_date": "2026-06-24",
           "income_time_window": "evening", "risk": "high"}
    by = _by_kind(build_behavioral_insights(_profile(), context=InsightContext(dependencies=(dep,))))
    d = by["dependency"][0]
    assert "15,000" in d.finding and "evening" in d.finding
    assert "tight" in d.consequences


def test_capped_three_per_kind():
    many = tuple(SworItem(f"m{i}", "spending_discipline", f"weak {i}", "high", 10 + i, "worsening", "normal") for i in range(6))
    by = _by_kind(build_behavioral_insights(_profile(weaknesses=many)))
    assert len(by["weakness"]) == 3


def test_low_confidence_adds_note():
    p = _profile(window={"complete_months": 1, "rate_days": 90, "buckets": 6})
    weak = _by_kind(build_behavioral_insights(p))["weakness"][0]
    assert weak.confidence_note == "Only one month of data available."


def test_cold_start_yields_nothing():
    empty = _profile(metrics=(), strengths=(), weaknesses=(), opportunities=(), risks=(), confidence="low")
    assert build_behavioral_insights(empty) == []
