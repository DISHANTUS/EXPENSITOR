"""Pure tests for the deterministic Commentary renderer (C5; Ollama-off).

These exercise the approved adjustments A1-A9 and the core invariants: one voice,
concise (<=4 paragraphs), never-calculates, preference-aware, confidence-honest.
No DB, no event loop — the renderer is pure over a CommentaryContext.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.advisor import tone
from app.intelligence.commentary import ActionPreview, CommentaryContext, render_commentary
from app.intelligence.commentary import context as ctxmod


def _ctx(**kw) -> CommentaryContext:
    base = dict(currency="INR", trigger=ctxmod.DAILY_BRIEF)
    base.update(kw)
    return CommentaryContext(**base)


_CALM_CONTEXT = {"daily_remaining": "420.0000", "weekly_remaining": "2500.0000",
                 "monthly_discretionary_remaining": "6000.0000", "days_until_next_income": 5}

_DEP = {"income_amount": "15000.0000", "income_date": "2026-06-24", "income_origin": "receivable",
        "income_source_id": "x", "income_time_window": "evening", "income_time_exact": "17:00",
        "source_label": "your father", "risk": "high"}

_NEXT_INCOME = {"amount": "15000.0000", "currency": "INR", "date": "2026-06-24",
                "window": "evening", "exact": "17:00", "source_label": "your father"}

_REC_MOVE = {"lever_key": "move_date", "action": "Move the outing to a later date", "title": "Move outing",
             "effort_level": "low", "life_impact": {"unchanged": "your budget"}, "expected_benefit": "Avoids the dip"}
_REC_FOOD = {"lever_key": "reduce_food", "action": "Trim food spending a little", "title": "Food spending",
             "effort_level": "low", "life_impact": {"unchanged": "your important plans"},
             "expected_benefit": "About ₹500/month"}


def _rupee_ints(text: str) -> set[str]:
    return {t.replace(",", "") for t in re.findall(r"₹([\d,]+)", text)}


# --- A4/A1/A2 & the six questions -------------------------------------------
def test_answers_six_questions_for_action():
    c = render_commentary(_ctx(trigger=ctxmod.AFTER_ACTION, headline_hint="₹250 expense added.",
                               context=_CALM_CONTEXT, next_income=_NEXT_INCOME))
    assert c.what_happened == "₹250 expense added."
    assert c.life_effect and c.most_useful_number          # A1, A2
    assert "left to spend today" in c.most_useful_number
    assert c.unchanged and "essentially unchanged" in c.unchanged


def test_concise_at_most_four_paragraphs():
    c = render_commentary(_ctx(
        trigger=ctxmod.AFTER_ACTION, headline_hint="Moved.", context=_CALM_CONTEXT,
        risk={"risk_level": "moderate", "min_expected_balance": "800.0000", "min_expected_balance_date": "2026-06-20"},
        goals=({"kind": "custom_goal", "name": "phone", "status": "behind", "shortfall": "1200.0000"},),
        dependencies=(_DEP,), recommendations=(_REC_FOOD,), next_income=_NEXT_INCOME))
    assert 1 <= len(c.paragraphs) <= 4
    assert len(render_commentary(_ctx(trigger=ctxmod.DAILY_BRIEF, context=_CALM_CONTEXT,
                                      dependencies=(_DEP,), recommendations=(_REC_FOOD,),
                                      behavioral_insights=({"finding": "Your savings are steady."},),
                                      ), expand=True).paragraphs) >= len(c.paragraphs)


# --- A1 life effect ---------------------------------------------------------
def test_life_effect_calm_vs_pressured():
    calm = render_commentary(_ctx(context=_CALM_CONTEXT))
    assert "usual spending" in calm.life_effect and "routine is unchanged" in calm.life_effect
    pressured = render_commentary(_ctx(
        context=_CALM_CONTEXT,
        risk={"risk_level": "moderate", "min_expected_balance": "300.0000", "min_expected_balance_date": "2026-06-20"}))
    assert "next 5 days" in pressured.life_effect          # uses days_until_next_income (an input, not computed)


# --- A2 most useful number per situation ------------------------------------
def test_most_useful_number_per_situation():
    goal = render_commentary(_ctx(trigger=ctxmod.GOAL_REVIEW, context=_CALM_CONTEXT,
        goals=({"kind": "custom_goal", "name": "phone", "status": "behind", "shortfall": "1200.0000"},)))
    assert "still needed for your phone" in goal.most_useful_number and "₹1,200" in goal.most_useful_number
    dep = render_commentary(_ctx(trigger=ctxmod.DEPENDENCY_ALERT, context=_CALM_CONTEXT, dependencies=(_DEP,)))
    assert "riding on that money" in dep.most_useful_number and "₹15,000" in dep.most_useful_number
    rec = render_commentary(_ctx(trigger=ctxmod.RECOMMENDATIONS, context=_CALM_CONTEXT, recommendations=(_REC_FOOD,)))
    assert "Expected benefit" in rec.most_useful_number


# --- A3 justify recommendations ---------------------------------------------
def test_recommendation_is_justified():
    c = render_commentary(_ctx(trigger=ctxmod.RECOMMENDATIONS, context=_CALM_CONTEXT, recommendations=(_REC_FOOD,)))
    assert c.next_step == "Trim food spending a little"
    joined = " ".join(c.paragraphs)
    assert "comes up because" in joined and "without affecting your important plans" in joined


# --- A4/req6 preference excludes a lever from suggestions -------------------
def test_excluded_lever_not_suggested():
    c = render_commentary(_ctx(trigger=ctxmod.RECOMMENDATIONS, context=_CALM_CONTEXT,
        recommendations=(_REC_MOVE, _REC_FOOD), policy_influence={"excluded": ["move_date"]}))
    assert c.next_step == "Trim food spending a little"
    assert "Move the outing" not in " ".join(c.paragraphs)


# --- A4/A8 acknowledge the user's choices -----------------------------------
def test_preference_note_generic_and_with_context():
    generic = render_commentary(_ctx(trigger=ctxmod.RECOMMENDATIONS, context=_CALM_CONTEXT,
        recommendations=(_REC_FOOD,), alternatives_applied=True, policy_influence={"excluded": ["move_date"]}))
    assert "keeping important plans fixed" in generic.preference_note
    with_ctx = render_commentary(_ctx(trigger=ctxmod.RECOMMENDATIONS, context=_CALM_CONTEXT,
        recommendations=(_REC_FOOD,), alternatives_applied=True, policy_influence={"excluded": ["move_date"]},
        policy_provenance={"move_date": {"reason_context": "your weekend outings"}}))
    assert "your weekend outings" in with_ctx.preference_note


# --- A5/req9 dependency phrasing & timing -----------------------------------
def test_dependency_phrasing_is_natural_and_specific():
    c = render_commentary(_ctx(trigger=ctxmod.DEPENDENCY_ALERT, context=_CALM_CONTEXT, dependencies=(_DEP,)))
    assert c.attention and "relies on" in c.attention
    assert "₹15,000" in c.attention and "from your father" in c.attention and "5 PM" in c.attention
    assert "use savings or trim the plan budget" in c.attention


def test_timing_note_only_when_known():
    known = render_commentary(_ctx(context=_CALM_CONTEXT, next_income=_NEXT_INCOME))
    assert known.timing_note and "₹15,000" in known.timing_note and "from your father" in known.timing_note
    assert render_commentary(_ctx(context=_CALM_CONTEXT, next_income=None)).timing_note is None


# --- A7 hierarchy: most important first -------------------------------------
def test_hierarchy_risk_before_goal_and_dependency():
    c = render_commentary(_ctx(trigger=ctxmod.DAILY_BRIEF, context=_CALM_CONTEXT,
        risk={"risk_level": "high", "min_expected_balance": "100.0000", "min_expected_balance_date": "2026-06-19"},
        goals=({"kind": "custom_goal", "name": "phone", "status": "behind", "shortfall": "1200.0000"},),
        dependencies=(_DEP,)))
    assert c.attention and "low point" in c.attention      # risk wins over goal/dependency


# --- A8/req8 confidence honesty ---------------------------------------------
def test_low_confidence_hedges():
    c = render_commentary(_ctx(context=_CALM_CONTEXT, confidence="low", has_history=True))
    assert c.confidence_note == "This read is based on limited history so far."


# --- A9 cold start is patient, not spammy -----------------------------------
def test_cold_start_is_patient_not_spammy():
    c = render_commentary(_ctx(trigger=ctxmod.DAILY_BRIEF, context=_CALM_CONTEXT, has_history=False,
        recommendations=(_REC_FOOD,), behavioral_insights=({"finding": "x"},)))
    assert "don't have enough history yet" in c.confidence_note
    assert c.next_step is None
    assert "Trim food" not in " ".join(c.paragraphs)
    assert len(c.paragraphs) <= 3


# --- A6 action preview ------------------------------------------------------
def test_action_preview():
    preview = ActionPreview(summary="Moving the outing to Jul 18", would_change="would ease the cash-flow pressure",
                            would_stay_same="the budget stays the same — only the date changes")
    c = render_commentary(_ctx(trigger=ctxmod.ACTION_PREVIEW, context=_CALM_CONTEXT, action_preview=preview))
    joined = " ".join(c.paragraphs)
    assert "Moving the outing to Jul 18" in joined and "only the date changes" in joined


# --- core invariants --------------------------------------------------------
def test_tone_is_always_clean():
    c = render_commentary(_ctx(trigger=ctxmod.AFTER_ACTION, headline_hint="₹250 expense added.",
        context=_CALM_CONTEXT, dependencies=(_DEP,), recommendations=(_REC_FOOD,), next_income=_NEXT_INCOME))
    assert tone.is_clean(*c.texts())


def test_never_calculates_only_input_numbers_spoken():
    ctx = _ctx(trigger=ctxmod.AFTER_ACTION, headline_hint="Done.", context=_CALM_CONTEXT,
               dependencies=(_DEP,), next_income=_NEXT_INCOME, recommendations=(_REC_FOOD,),
               goals=({"kind": "custom_goal", "name": "phone", "status": "behind", "shortfall": "1200.0000"},),
               risk={"risk_level": "moderate", "min_expected_balance": "800.0000",
                     "min_expected_balance_date": "2026-06-20"})
    rendered = render_commentary(ctx).render()

    allowed: set[str] = set()
    money_values = ["420.0000", "2500.0000", "6000.0000", "15000.0000", "1200.0000", "800.0000"]
    for v in money_values:
        allowed |= _rupee_ints(ph.money(Decimal(v), "INR"))
    allowed |= _rupee_ints(_REC_FOOD["expected_benefit"])   # rec benefit strings are inputs too

    spoken = _rupee_ints(rendered)
    assert spoken, "expected at least one money figure in the narration"
    assert spoken <= allowed, f"invented numbers: {spoken - allowed}"
