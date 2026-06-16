"""Commentary Layer (C5) — the deterministic renderer (mandatory fallback).

Turns a `CommentaryContext` into a single-voice `Commentary`. It SELECTS, ORDERS,
and PHRASES already-computed facts — it never calculates. Every number it emits
is passed through `phrasing` from an input field; no arithmetic happens here.
This layer is the product: the app reads like a real advisor with Ollama off.

Ordering follows the A7 hierarchy:
  1 immediate risk · 2 blocked goals · 3 dependencies · 4 recommendations · 5 behavior
"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import Any

from app.intelligence.advisor import phrasing as ph
from app.intelligence.advisor import tone
from app.intelligence.commentary import context as ctxmod
from app.intelligence.commentary.commentary import Commentary
from app.intelligence.commentary.context import CommentaryContext

_SEVERITY_ORDER = {"alert": 0, "warning": 1, "success": 2, "info": 3}
_EFFORT_PHRASE = {
    "low": "one of the easiest things to adjust",
    "medium": "a manageable change",
    "high": "a bigger change",
}
_HEADLINES = {
    ctxmod.DAILY_BRIEF: "Here's where things stand.",
    ctxmod.RECOMMENDATIONS: "A few ways to strengthen your position.",
    ctxmod.GOAL_REVIEW: "Your goal, at a glance.",
    ctxmod.DEPENDENCY_ALERT: "A plan worth keeping an eye on.",
    ctxmod.ACTION_PREVIEW: "Here's what this would do.",
    ctxmod.DECISION: "About this purchase.",
    ctxmod.AFTER_ACTION: "Done.",
}


# --- small parse/format helpers (no math) ----------------------------------
def _money(value: Any, currency: str) -> str:
    return ph.money(Decimal(str(value)), currency)


def _fmt_date(value: Any) -> str:
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return ph.on_date(d)


def _fmt_time(value: Any) -> str:
    t = time.fromisoformat(value) if isinstance(value, str) else value
    hour = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    return f"{hour}:{t.minute:02d} {suffix}" if t.minute else f"{hour} {suffix}"


def _pos(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001 - defensive against missing/odd facts
        return Decimal("0")


# --- selectors --------------------------------------------------------------
def _lead_explanation(ctx: CommentaryContext) -> dict[str, Any] | None:
    if not ctx.explanations:
        return None
    return sorted(ctx.explanations, key=lambda e: _SEVERITY_ORDER.get(e.get("severity"), 3))[0]


def _headline(ctx: CommentaryContext) -> str:
    return ctx.headline_hint or _HEADLINES.get(ctx.trigger, "Here's where things stand.")


def _lead(ctx: CommentaryContext) -> tuple[str, str]:
    """Returns (what_happened, why_it_matters)."""
    if ctx.trigger == ctxmod.AFTER_ACTION and ctx.headline_hint:
        return ctx.headline_hint, "I checked this against today's budget, your goals and upcoming plans."
    le = _lead_explanation(ctx)
    if le:
        return le.get("headline") or _headline(ctx), le.get("impact") or ""
    return _headline(ctx), ""


def _risk_text(ctx: CommentaryContext) -> str | None:
    r = ctx.risk or {}
    level = r.get("risk_level")
    if level in (None, "none", "low"):
        return None
    low = r.get("min_expected_balance")
    when = r.get("min_expected_balance_date") or r.get("date")
    if low is not None and when is not None:
        return (f"Heads up — your projected low point is {_money(low, ctx.currency)} "
                f"on {_fmt_date(when)}, so there's a little less slack than usual.")
    return "Heads up — there's a little less slack than usual over the coming weeks."


def _goal_text(goal: dict[str, Any], ctx: CommentaryContext) -> str:
    name = goal.get("name", "this goal")
    shortfall = goal.get("shortfall")
    if shortfall and _pos(shortfall) > 0:
        return f"Your {name} goal is a little behind — about {_money(shortfall, ctx.currency)} short of where it needs to be."
    return f"Your {name} goal is a little behind right now."


def _dependency_text(dep: dict[str, Any], ctx: CommentaryContext) -> str:
    """A5 — natural, specific, actionable dependency phrasing."""
    amount = _money(dep.get("income_amount", 0), ctx.currency)
    src = dep.get("source_label")
    src_clause = f" from {src}" if src else ""
    when = _fmt_date(dep["income_date"]) if dep.get("income_date") else "its expected date"
    if dep.get("income_time_exact"):
        when += f" around {_fmt_time(dep['income_time_exact'])}"
    elif dep.get("income_time_window"):
        when += f" in the {dep['income_time_window']}"
    return (f"This plan currently relies on the {amount} expected{src_clause} on {when}. "
            "If that arrives later than expected, you may need to use savings or trim the plan budget.")


def _attention(ctx: CommentaryContext) -> tuple[str | None, str | None]:
    """The single most important thing to hear first (A7 hierarchy)."""
    level = (ctx.risk or {}).get("risk_level")
    if level in ("high", "critical"):
        return "risk", _risk_text(ctx)
    behind = [g for g in ctx.goals if g.get("status") == "behind"]
    if behind:
        return "goal", _goal_text(behind[0], ctx)
    deps = [d for d in ctx.dependencies if d.get("risk") in ("moderate", "high")]
    if deps:
        deps.sort(key=lambda d: 0 if d.get("risk") == "high" else 1)
        return "dependency", _dependency_text(deps[0], ctx)
    if level == "moderate":
        return "risk", _risk_text(ctx)
    return None, None


def _rec_step(rec: dict[str, Any]) -> tuple[str, str | None]:
    """A3 — the action plus a brief justification of why it surfaced."""
    action = rec.get("action") or rec.get("title") or "Consider this option"
    effort = _EFFORT_PHRASE.get(rec.get("effort_level"), "an option to consider")
    unaffected = (rec.get("life_impact") or {}).get("unchanged")
    reason = f"This comes up because it's currently {effort}"
    if unaffected:
        reason += f", without affecting {unaffected.rstrip('.').lower()}"
    reason += "."
    return action, reason


def _next_step(ctx: CommentaryContext) -> tuple[str | None, str | None]:
    excluded = set(ctx.policy_influence.get("excluded", []))
    for rec in ctx.recommendations:
        if rec.get("lever_key") in excluded:
            continue
        return _rec_step(rec)
    le = _lead_explanation(ctx)
    if le and le.get("best_next_action"):
        return le["best_next_action"].get("detail"), None
    return None, None


_PREF_PHRASE = {
    "move_date": "keeping important plans fixed",
    "reduce_discretionary": "smaller, steady cuts over larger changes",
    "use_savings": "leaving your savings untouched",
    "wait_for_income": "not waiting on future income",
}


def _preference_note(ctx: CommentaryContext) -> str | None:
    """A4/A8 — acknowledge the user's prior choices warmly; never invent context."""
    if not ctx.alternatives_applied:
        return None
    excluded = ctx.policy_influence.get("excluded", [])
    lever = excluded[0] if excluded else None
    prov = ctx.policy_provenance.get(lever, {}) if lever else {}
    reason_context = prov.get("reason_context")
    if reason_context:
        return (f"Because you've previously marked {reason_context} as fixed, "
                "I looked for other options first.")
    phrase = _PREF_PHRASE.get(lever, "your earlier preferences")
    return f"You've previously preferred {phrase}, so I looked at other options first."


def _confidence_note(ctx: CommentaryContext) -> str | None:
    """A9/req8 — patient on cold start, honest about thin data, never overstated."""
    if not ctx.has_history:
        return ("I don't have enough history yet to spot your spending patterns, "
                "but I'll start tracking them as more activity is recorded.")
    if ctx.confidence != "normal":
        return "This read is based on limited history so far."
    return None


def _life_effect(ctx: CommentaryContext) -> str:
    """A1 — translate the financial state into a real-life effect."""
    level = (ctx.risk or {}).get("risk_level")
    days = ctx.context.get("days_until_next_income")
    behind = [g for g in ctx.goals if g.get("status") == "behind"]
    if level in ("high", "critical"):
        return "It's worth being a little more careful with discretionary spending for a while."
    if level == "moderate":
        if isinstance(days, int) and days > 0:
            return f"You may want to be a little more careful with discretionary spending for the next {days} days."
        return "You may want to be a little more careful with discretionary spending for now."
    if behind:
        return "Your day-to-day spending is fine — the goal just needs a little attention."
    return "You still have room for your usual spending, and your daily routine is unchanged."


def _unchanged(ctx: CommentaryContext) -> str | None:
    parts: list[str] = []
    behind = [g for g in ctx.goals if g.get("status") == "behind"]
    if ctx.goals and not behind:
        parts.append("your savings goals stay on track")
    if ctx.trigger in (ctxmod.AFTER_ACTION,) and ctx.headline_hint:
        parts.append("your monthly plan is essentially unchanged")
    if not parts:
        return None
    return "Unchanged: " + ", ".join(parts) + "."


def _decision_gap(ctx: CommentaryContext) -> Decimal | None:
    for e in ctx.explanations:
        facts = e.get("facts") or {}
        if facts.get("verdict") in ("unaffordable", "not_now") and facts.get("shortfall"):
            gap = _pos(facts["shortfall"])
            if gap > 0:
                return gap
    return None


def _most_useful_number(ctx: CommentaryContext) -> str | None:
    """A2 — the single most useful number for this situation (always from inputs)."""
    cur = ctx.currency
    if ctx.trigger == ctxmod.GOAL_REVIEW:
        behind = [g for g in ctx.goals if g.get("status") == "behind"]
        if behind and behind[0].get("shortfall") and _pos(behind[0]["shortfall"]) > 0:
            return f"About {_money(behind[0]['shortfall'], cur)} still needed for your {behind[0].get('name', 'goal')}."
    if ctx.trigger == ctxmod.DEPENDENCY_ALERT and ctx.dependencies:
        return f"Amount riding on that money: {_money(ctx.dependencies[0].get('income_amount', 0), cur)}."
    if ctx.trigger == ctxmod.RECOMMENDATIONS and ctx.recommendations:
        benefit = ctx.recommendations[0].get("expected_benefit")
        if benefit:
            return f"Expected benefit: {benefit}."
    if ctx.trigger == ctxmod.DECISION:
        gap = _decision_gap(ctx)
        if gap is not None:
            return f"Affordability gap: {_money(gap, cur)}."
    daily = ctx.context.get("daily_remaining")
    if daily is not None:
        return f"{_money(daily, cur)} left to spend today."
    return None


def _timing_note(ctx: CommentaryContext) -> str | None:
    """A5/req9 — surface useful timing only when it is actually known."""
    ni = ctx.next_income
    if not ni or ni.get("amount") in (None, "") or not ni.get("date"):
        return None
    amount = _money(ni["amount"], ni.get("currency") or ctx.currency)
    src = ni.get("source_label")
    src_clause = f" from {src}" if src else ""
    when = _fmt_date(ni["date"])
    if ni.get("exact"):
        when += f" around {_fmt_time(ni['exact'])}"
    elif ni.get("window"):
        when += f" in the {ni['window']}"
    return f"Your next expected income is {amount}{src_clause} on {when}."


def _severity(ctx: CommentaryContext, attention_kind: str | None) -> str:
    level = (ctx.risk or {}).get("risk_level")
    if level in ("high", "critical"):
        return "alert"
    if level == "moderate" or attention_kind in ("goal", "dependency"):
        return "warning"
    if ctx.trigger == ctxmod.AFTER_ACTION:
        return "success"
    return "info"


def _grounding(ctx: CommentaryContext) -> list[str]:
    """Whitelist of facts the future Ollama narrator (3b) must stay within."""
    tokens: set[str] = set()

    def add_money(value: Any) -> None:
        if value not in (None, ""):
            tokens.add(str(value))

    for key in ("daily_remaining", "weekly_remaining", "monthly_discretionary_remaining",
                "amount_still_needed", "next_income_amount"):
        add_money(ctx.context.get(key))
    if ctx.next_income:
        add_money(ctx.next_income.get("amount"))
        for k in ("date", "exact", "window", "source_label"):
            if ctx.next_income.get(k):
                tokens.add(str(ctx.next_income[k]))
    for dep in ctx.dependencies:
        add_money(dep.get("income_amount"))
        for k in ("income_date", "source_label", "income_time_window", "income_time_exact"):
            if dep.get(k):
                tokens.add(str(dep[k]))
    for g in ctx.goals:
        add_money(g.get("shortfall"))
        if g.get("name"):
            tokens.add(str(g["name"]))
    if ctx.risk:
        add_money(ctx.risk.get("min_expected_balance"))
    return sorted(tokens)


# --- top level --------------------------------------------------------------
def _facts(ctx: CommentaryContext, sources: list[str]) -> dict[str, Any]:
    return {"trigger": ctx.trigger, "sources_used": sources, "grounding": _grounding(ctx)}


def _safe(text: str | None) -> str | None:
    """Render-time tone net: drop a string only if it slips a banned phrase."""
    if text and tone.lint(text):
        return None
    return text


def render_commentary(ctx: CommentaryContext, *, expand: bool = False) -> Commentary:
    what, why = _lead(ctx)
    conf_note = _confidence_note(ctx)
    useful = _most_useful_number(ctx)
    timing = _timing_note(ctx)

    # A6 action preview: a factual "what would change / stay the same" — shown
    # regardless of history (it is not advice or pattern-based).
    if ctx.trigger == ctxmod.ACTION_PREVIEW and ctx.action_preview is not None:
        ap = ctx.action_preview
        paragraphs = [f"{ap.summary} {ap.would_change}".strip(), ap.would_stay_same]
        if ap.consequence:
            paragraphs.append(ap.consequence)
        if useful:
            paragraphs.append(useful)
        return Commentary(
            headline=_headline(ctx), paragraphs=tuple(p for p in paragraphs if _safe(p)),
            what_happened=ap.summary, why_it_matters=ap.would_change,
            unchanged=ap.would_stay_same, most_useful_number=useful, timing_note=timing,
            severity="info", expanded=expand, health=ctx.health_score, facts=_facts(ctx, ["action_preview"]),
        )

    # A9 cold-start: a single patient message, no advice spam.
    if not ctx.has_history:
        paragraphs = [what, conf_note]
        if useful:
            paragraphs.append(useful)
        if timing:
            paragraphs.append(timing)
        return Commentary(
            headline=_headline(ctx), paragraphs=tuple(p for p in paragraphs if _safe(p)),
            what_happened=what, why_it_matters="I'll have more to say as your history grows.",
            most_useful_number=useful, confidence_note=conf_note, timing_note=timing,
            severity="info", expanded=expand, health=ctx.health_score, facts=_facts(ctx, ["cold_start"]),
        )

    attention_kind, attention = _attention(ctx)
    # One voice, no echo: if the lead is already the risk explanation, don't repeat
    # the risk as a separate attention line (after-action leads with the action, so
    # the risk attention there is still new information).
    lead_exp = _lead_explanation(ctx)
    lead_is_risk = bool(lead_exp and (lead_exp.get("facts") or {}).get("risk_level"))
    if attention_kind == "risk" and lead_is_risk and ctx.trigger != ctxmod.AFTER_ACTION:
        attention, attention_kind = None, None

    step, step_reason = _next_step(ctx)
    pref = _preference_note(ctx)
    life = _life_effect(ctx)
    unchanged = _unchanged(ctx)
    severity = _severity(ctx, attention_kind)

    # --- compose ≤4 short paragraphs, richest-first ---
    paragraphs: list[str] = []
    paragraphs.append(f"{what} {why}".strip() if why and why not in what else what)

    if attention:
        paragraphs.append(attention)

    if step:
        bits = [step]
        if step_reason:
            bits.append(step_reason)
        sentence = " ".join(bits)
        paragraphs.append(f"{pref} {sentence}" if pref else sentence)
    elif pref:
        paragraphs.append(pref)

    tail = [life, unchanged, useful]
    if attention_kind != "dependency" and timing:   # dependency text already carries timing
        tail.append(timing)
    if conf_note:
        tail.append(conf_note)
    tail_text = " ".join(b for b in tail if b)
    if tail_text:
        paragraphs.append(tail_text)

    paragraphs = [p for p in paragraphs if _safe(p)]
    sources = ["explanations", "risk", "goals", "dependencies", "recommendations", "behavior"]
    if not expand:
        paragraphs = paragraphs[:4]
    else:
        for ins in ctx.behavioral_insights[:3]:
            extra = _safe(ins.get("finding"))
            if extra:
                paragraphs.append(extra)

    return Commentary(
        headline=_headline(ctx), paragraphs=tuple(paragraphs),
        what_happened=what, why_it_matters=why or (attention or ""),
        life_effect=life, attention=attention, unchanged=unchanged,
        next_step=step, most_useful_number=useful, preference_note=pref,
        confidence_note=conf_note, timing_note=timing, severity=severity,
        expanded=expand, health=ctx.health_score, facts=_facts(ctx, sources),
    )
