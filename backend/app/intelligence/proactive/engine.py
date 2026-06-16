"""Proactive Advisor engine — generate the feed + build periodic reviews.

Deterministic, no LLM, no new financial math. Surfaces already-computed
intelligence only. Cold-start is silent (R4): with no real history the feed is [].
Reviews reuse Health Score + Behavioral Memory + goals + recommendations and
explain movement from trends/durations (Decision 2 — no snapshot storage).
"""

from __future__ import annotations

from app.intelligence.proactive import generators, ranking
from app.intelligence.proactive.context import ProactiveContext
from app.intelligence.proactive.item import REVIEW, ProactiveItem

WEEKLY, MONTHLY = "weekly", "monthly"


def generate(ctx: ProactiveContext) -> list[ProactiveItem]:
    """The proactive feed — ranked, most-important-first. [] at cold start (R4)."""
    if not ctx.has_history:
        return []
    items: list[ProactiveItem] = []
    for gen in generators.GENERATORS:
        items.extend(gen(ctx))
    return ranking.rank(items)


def most_important(ctx: ProactiveContext) -> ProactiveItem | None:
    feed = generate(ctx)
    return feed[0] if feed else None


def _movement_line(ctx: ProactiveContext) -> str:
    h = ctx.health
    parts = []
    if h.get("improving_area"):
        parts.append(f"your {h['improving_area'].replace('_', ' ')} improved")
    if h.get("worsening_area"):
        parts.append(f"your {h['worsening_area'].replace('_', ' ')} slipped")
    stress = ctx.metrics.get("financial_stress_index")
    if stress and stress.get("confidence") == "normal" and stress.get("trend") == "worsening":
        dur = stress.get("trend_duration_months") or 0
        parts.append(f"financial stress has been rising for {dur} month{'s' if dur != 1 else ''}")
    return ("; ".join(parts) + ".") if parts else "nothing moved significantly."


def build_review(ctx: ProactiveContext, period: str) -> ProactiveItem:
    label = "This week" if period == WEEKLY else "This month"
    h = ctx.health

    # Cold start: an honest status, not weak advice (R4) — explicitly requested surface.
    if not ctx.has_history:
        return ProactiveItem(
            kind=REVIEW, category="review", title=f"{label}'s review",
            what_happened="There isn't enough activity yet to review.",
            why_it_matters="A meaningful review needs a bit more recorded spending and income.",
            what_next="As you record more, this will fill in automatically.",
            most_useful_number=None, severity="info", priority=0.3,
            eligible_for_notification=False, expires_at=None, trigger_reason=f"{period}_review_coldstart",
            evidence={},
        )

    drag = h.get("biggest_drag")
    contrib = h.get("biggest_contributor")
    helped = (f"{contrib['statement'].capitalize()} helped the most." if contrib else "")
    hurt = (f"{drag['statement'].capitalize()} was the biggest drag." if drag else "")
    behind = [g.get("name") for g in ctx.goals if g.get("status") == "behind"]
    rec = next((r for r in ctx.recommendations if r.get("lever_key") not in set(ctx.excluded_levers)), None)
    next_focus = rec.get("action") if rec else "Keep doing what's working."
    overall = h.get("overall_score")

    why = " ".join(p for p in (helped, hurt) if p) or "Your savings held about steady."
    goal_line = (f" Watch: behind on {', '.join(behind)}." if behind else "")
    severity = {"weak": "warning", "fair": "info", "strong": "success"}.get(h.get("overall_state"), "info")

    return ProactiveItem(
        kind=REVIEW, category="review", title=f"{label}'s review",
        what_happened=f"{label}, {_movement_line(ctx)}{goal_line}",
        why_it_matters=why,
        what_next=f"Suggested focus: {next_focus}",
        most_useful_number=(f"Financial health: {overall}/100 ({h.get('overall_state')})." if overall is not None else None),
        severity=severity, priority=0.55, eligible_for_notification=True, expires_at=None,
        trigger_reason=f"{period}_review",
        evidence={"biggest_contributor": contrib, "biggest_drag": drag,
                  "improving_area": h.get("improving_area"), "worsening_area": h.get("worsening_area"),
                  "behind_goals": behind},
    )
