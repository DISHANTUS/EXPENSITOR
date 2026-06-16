"""Pure tests for the Recommendation Engine (C9)."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.advisor import tone
from app.intelligence.behavior.insights import BehavioralInsight
from app.intelligence.recommendation import build_recommendations
from app.intelligence.recommendation.recommendation import GoalState, RecommendationContext


def _insight(kind, metric, finding, recommendation, *, facts=None, goal_links=(), priority=0.6, conf="normal"):
    return BehavioralInsight(
        kind=kind, metric_key=metric, dimension="spending_discipline", finding=finding,
        impact="why it matters", reasoning="the reason", recommendation=recommendation,
        consequences="if it continues, less is saved", confidence_note=None, score=40, trend="worsening",
        trend_duration_months=None, confidence=conf, priority=priority, goal_links=tuple(goal_links),
        facts=facts or {},
    )


def _ctx(**over) -> RecommendationContext:
    opp = _insight("opportunity", "shopping_spend_share", "Room to improve shopping", "Trim shopping…",
                   facts={"suggested_cut": {"category": "Food & Dining", "monthly_avg": "5000"}}, priority=0.5)
    weak = _insight("weakness", "weekend_overspending", "Weekend spending needs attention", "Reduce weekend dining…",
                    facts={"suggested_cut": {"category": "Shopping", "monthly_avg": "4000"}},
                    goal_links=({"goal": "Phone", "kind": "custom_goal"},), priority=0.8)
    dep = _insight("dependency", "dependency", "A plan relies on ₹5,000", "Confirm it…",
                   facts={"income_origin": "receivable"}, priority=0.7)
    base = dict(
        currency="INR", behavioral_insights=(opp, weak, dep),
        goals=(GoalState("custom_goal", "Phone", "behind", Decimal("8000"), "2026-07-30", {}),),
        dependencies=({"risk": "high", "income_amount": "5000", "income_date": "2026-06-24",
                       "income_origin": "receivable", "income_time_window": "evening"},),
        advisor_view={"best_categories_to_cut": [{"category": "Shopping", "monthly_avg": "4000"}],
                      "low_impact_categories": [{"category": "Transportation", "monthly_avg": "1000"}]},
        recurring_load=None, available_savings=Decimal("20000"),
        next_income={"date": "2026-06-24", "amount": "15000"}, excluded_levers=(),
    )
    base.update(over)
    return RecommendationContext(**base)


def test_categories_and_structure():
    result = build_recommendations(_ctx())
    recs = result["recommendations"]
    assert recs
    cats = {r.category for r in recs}
    assert {"savings_opportunity", "spending_reduction", "dependency_risk", "timing_opportunity",
            "goal_recovery", "lifestyle_optimization"} <= cats
    for r in recs:
        assert {"improves", "daily_change", "unchanged"} <= set(r.life_impact.as_dict())
        assert {"goal_progress_change", "savings_change", "dependency_change", "risk_change",
                "daily_life_change", "projected_result"} <= set(r.outcome_preview.as_dict())
        assert tone.lint(" ".join(r.texts())) == []


def test_ranked_by_score_descending():
    recs = build_recommendations(_ctx())["recommendations"]
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_goal_recovery_bundle_makes_goal_affordable():
    bundles = build_recommendations(_ctx())["bundles"]
    assert bundles and bundles[0].title == "Phone Recovery Plan"
    assert "affordable" in bundles[0].outcome_preview
    levers = {r.lever_key for r in bundles[0].recommendations}
    assert "use_savings" in levers  # ₹20k savings covers the ₹8k gap


def test_excluded_levers_avoided_and_alternatives_used():
    result = build_recommendations(_ctx(excluded_levers=("use_savings", "reduce_shopping")))
    levers = {r.lever_key for r in result["recommendations"]}
    assert "use_savings" not in levers and "reduce_shopping" not in levers
    assert result["alternatives_applied"] is True
    bundle_levers = {r.lever_key for b in result["bundles"] for r in b.recommendations}
    assert "use_savings" not in bundle_levers and "wait_for_income" in bundle_levers


def test_dedup_keeps_one_per_lever():
    recs = build_recommendations(_ctx())["recommendations"]
    levers = [r.lever_key for r in recs]
    assert len(levers) == len(set(levers))


def test_cold_start_context_yields_nothing():
    empty = RecommendationContext(currency="INR")
    result = build_recommendations(empty)
    assert result["recommendations"] == [] and result["bundles"] == []
