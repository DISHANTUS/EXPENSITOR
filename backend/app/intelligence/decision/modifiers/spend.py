"""Spend-modifier analyzers: free delivery, offer/cashback, bundle, hidden cost,
decision change. Generic — gated by influence flags / attributes, not products."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.decision.modifiers.base import (
    AnalyzerCtx,
    ModifierFinding,
    Question,
    recovery_time_days,
    register,
)

_NON_MONETARY = {"urgency", "social_pressure", "emotional"}
_CHANGE_TRIGGERS = {"offer", "cashback", "free_delivery", "bundle", *_NON_MONETARY}


def _has(ctx: AnalyzerCtx, *flags: str) -> bool:
    return bool(ctx.inputs.involves) and any(f in ctx.inputs.involves for f in flags)


def _q(analyzer: str, key: str, prompt: str, type_: str = "amount", options=(), why="") -> Question:
    return Question(analyzer, key, prompt, type_, tuple(options), why)


# --------------------------------------------------------------------------- #
def _free_delivery_required(ctx: AnalyzerCtx) -> list[Question]:
    i, qs = ctx.inputs, []
    if i.original_amount is None:
        qs.append(_q("free_delivery", "original_amount", "What did you originally intend to spend?",
                     why="Separates your real need from the delivery top-up."))
    if i.delivery_fee is None:
        qs.append(_q("free_delivery", "delivery_fee", "What is the delivery charge?"))
    if i.free_delivery_threshold is None:
        qs.append(_q("free_delivery", "free_delivery_threshold", "What is the free-delivery threshold?"))
    if i.final_amount is None:
        qs.append(_q("free_delivery", "final_amount", "What is your final order amount?"))
    if i.items_useful is None:
        qs.append(_q("free_delivery", "items_useful", "Are the extra items something you'd buy anyway?",
                     "choice", ("yes", "maybe", "no")))
    return qs


def _free_delivery_run(ctx: AnalyzerCtx) -> ModifierFinding:
    i, cur = ctx.inputs, ctx.currency
    added = i.final_amount - i.original_amount
    reached = i.final_amount >= i.free_delivery_threshold
    saved = i.delivery_fee if reached else Decimal("0")
    net = added - saved
    useful = i.items_useful == "yes"
    recovery = recovery_time_days(ctx.scenario, added, ctx.when) if added > 0 else 0
    reason = ("the extra items are things you'd buy anyway" if useful
              else "the extra items were added mainly to reach free delivery")
    if net > 0 and not useful:
        rec = f"Ordering only your original items keeps about {ph.money(net, cur)} available for other goals."
        alts = (f"Keep the original {ph.money(i.original_amount, cur)} order.",)
    else:
        rec = "This works either way." if net <= 0 else "Proceeding is fine if you'll use the extra items."
        alts = ()
    return ModifierFinding(
        analyzer="free_delivery",
        finding=f"You added {ph.money(added, cur)} to avoid a {ph.money(i.delivery_fee, cur)} delivery charge.",
        impact=(f"Net effect: about {ph.money(net, cur)} extra spend." if net > 0
                else f"Net effect: about {ph.money(-net, cur)} saved."),
        reasoning=f"Because {reason}.", recommendation=rec, alternatives=alts,
        recovery_time_days=recovery,
        facts={"added": str(added), "delivery_saved": str(saved), "net": str(net), "items_useful": i.items_useful},
    )


register("free_delivery", trigger=lambda c: _has(c, "free_delivery"),
         required_inputs=_free_delivery_required, run=_free_delivery_run)


# --------------------------------------------------------------------------- #
def _offer_required(ctx: AnalyzerCtx) -> list[Question]:
    i, qs = ctx.inputs, []
    if i.original_amount is None:
        qs.append(_q("offer", "original_amount", "What did you originally plan to spend?"))
    if i.final_amount is None:
        qs.append(_q("offer", "final_amount", "What is your final spend with the offer?"))
    if i.offer is None:
        qs.append(_q("offer", "offer", "What are the offer terms? (cashback / % off / spend-get / points)",
                     "offer_terms", why="Determines the real saving vs extra spend."))
    if i.items_useful is None:
        qs.append(_q("offer", "items_useful", "Were the extra items already on your list?", "choice",
                     ("yes", "maybe", "no")))
    return qs


def _offer_saving(offer: dict, final: Decimal) -> Decimal:
    kind = offer.get("kind")
    if kind == "percent":
        return (final * Decimal(str(offer.get("percent", 0))) / 100)
    for key in ("cashback", "discount", "points_value"):
        if offer.get(key) is not None:
            return Decimal(str(offer[key]))
    return Decimal("0")


def _offer_run(ctx: AnalyzerCtx) -> ModifierFinding:
    i, cur = ctx.inputs, ctx.currency
    saving = _offer_saving(i.offer, i.final_amount)
    extra = i.final_amount - i.original_amount
    net = extra - saving
    changed = extra > 0
    useful = i.items_useful == "yes"
    recovery = recovery_time_days(ctx.scenario, extra, ctx.when) if extra > 0 else 0
    if changed and not useful:
        reason = f"the offer encouraged {ph.money(extra, cur)} of extra spend for a {ph.money(saving, cur)} saving"
        rec = f"Keeping your original purchase leaves about {ph.money(net, cur)} more available."
        alts = (f"Buy the original {ph.money(i.original_amount, cur)} of items.",)
    else:
        reason = "the offer reduces the cost of things you were buying anyway"
        rec = f"The offer genuinely saves you {ph.money(saving, cur)}."
        alts = ()
    return ModifierFinding(
        analyzer="offer",
        finding=f"This offer changed your spend from {ph.money(i.original_amount, cur)} to {ph.money(i.final_amount, cur)}."
                if changed else f"The offer saves {ph.money(saving, cur)} on your planned purchase.",
        impact=(f"Net effect: about {ph.money(net, cur)} extra." if net > 0 else f"Net saving: about {ph.money(-net, cur)}."),
        reasoning=f"Because {reason}.", recommendation=rec, alternatives=alts, recovery_time_days=recovery,
        facts={"saving": str(saving), "extra_spend": str(extra), "net": str(net), "decision_changed": changed},
    )


register("offer", trigger=lambda c: _has(c, "offer", "cashback"),
         required_inputs=_offer_required, run=_offer_run)


# --------------------------------------------------------------------------- #
def _bundle_required(ctx: AnalyzerCtx) -> list[Question]:
    if ctx.inputs.bundle_add_ons is None:
        return [_q("bundle", "bundle_add_ons", "List the add-ons/accessories (name, cost, needed?).",
                   "money_list", why="Separates required items from optional extras.")]
    return []


def _bundle_run(ctx: AnalyzerCtx) -> ModifierFinding:
    cur = ctx.currency
    add_ons = ctx.inputs.bundle_add_ons
    required = sum((Decimal(str(a["cost"])) for a in add_ons if a.get("required")), Decimal("0"))
    optional = sum((Decimal(str(a["cost"])) for a in add_ons if not a.get("required")), Decimal("0"))
    required_total = ctx.amount + required
    recovery = recovery_time_days(ctx.scenario, optional, ctx.when) if optional > 0 else 0
    return ModifierFinding(
        analyzer="bundle",
        finding=f"The bundle adds {ph.money(required + optional, cur)} in extras.",
        impact=f"About {ph.money(optional, cur)} of that is optional.",
        reasoning="Based on which add-ons you marked as needed.",
        recommendation=(f"Buying the base plus only the required items costs {ph.money(required_total, cur)}."
                        if optional > 0 else "Everything in the bundle is needed."),
        alternatives=((f"Skip the optional extras to keep {ph.money(optional, cur)}.",) if optional > 0 else ()),
        recovery_time_days=recovery,
        facts={"required_extras": str(required), "optional_extras": str(optional), "base": str(ctx.amount)},
    )


register("bundle", trigger=lambda c: _has(c, "bundle"),
         required_inputs=_bundle_required, run=_bundle_run)


# --------------------------------------------------------------------------- #
def _hidden_required(ctx: AnalyzerCtx) -> list[Question]:
    if ctx.inputs.hidden_items is None:
        return [_q("hidden_cost", "hidden_items",
                   "Any added costs (shipping, setup, taxes, maintenance, recurring fees)?",
                   "money_list", why="Shows the true total, not just the sticker price.")]
    return []


def _hidden_run(ctx: AnalyzerCtx) -> ModifierFinding | None:
    cur = ctx.currency
    items = ctx.inputs.hidden_items
    if not items:
        return None  # user confirmed no hidden costs
    one_time = sum((Decimal(str(x["cost"])) for x in items if not x.get("recurring")), Decimal("0"))
    recurring = sum((Decimal(str(x["cost"])) for x in items if x.get("recurring")), Decimal("0"))
    expected_total = ctx.amount + one_time
    return ModifierFinding(
        analyzer="hidden_cost",
        finding=f"The real cost is about {ph.money(expected_total, cur)}, not {ph.money(ctx.amount, cur)}.",
        impact=(f"Plus about {ph.money(recurring, cur)} of recurring cost." if recurring > 0
                else f"That's {ph.money(one_time, cur)} of added one-time costs."),
        reasoning="Based on the extra costs you listed.",
        recommendation=f"Plan for {ph.money(expected_total, cur)} up front.",
        recovery_time_days=recovery_time_days(ctx.scenario, one_time, ctx.when) if one_time > 0 else 0,
        facts={"expected_total": str(expected_total), "one_time": str(one_time), "recurring_monthly": str(recurring)},
    )


register("hidden_cost", trigger=lambda c: getattr(c.attributes, "liquidity_class", "") == "durable_asset",
         required_inputs=_hidden_required, run=_hidden_run)


# --------------------------------------------------------------------------- #
def _decision_change_required(ctx: AnalyzerCtx) -> list[Question]:
    i, qs = ctx.inputs, []
    if i.original_amount is None:
        qs.append(_q("decision_change", "original_amount", "What did you originally intend to spend?"))
    if i.final_amount is None:
        qs.append(_q("decision_change", "final_amount", "What are you actually spending now?"))
    if i.items_useful is None:
        qs.append(_q("decision_change", "items_useful", "Would you have bought this anyway?", "choice",
                     ("yes", "maybe", "no")))
    return qs


def _decision_change_run(ctx: AnalyzerCtx) -> ModifierFinding:
    i, cur = ctx.inputs, ctx.currency
    trigger = i.change_trigger or next((t for t in (i.involves or ()) if t in _CHANGE_TRIGGERS), "an offer")
    change_cost = (i.final_amount - i.original_amount)
    would_anyway = i.items_useful == "yes"
    changed = change_cost != 0 or trigger in _NON_MONETARY
    recovery = recovery_time_days(ctx.scenario, change_cost, ctx.when) if change_cost > 0 else 0
    rec = (f"If you wouldn't have bought the extra otherwise, keeping the original leaves {ph.money(change_cost, cur)}."
           if changed and change_cost > 0 and not would_anyway else "No change needed — this matches your intent.")
    return ModifierFinding(
        analyzer="decision_change",
        finding=(f"Your decision changed because of {trigger.replace('_', ' ')}." if changed
                 else "This matches what you originally intended."),
        impact=(f"It added about {ph.money(change_cost, cur)} to your spend." if change_cost > 0
                else "No extra spend from the change."),
        reasoning=("You'd have bought this anyway." if would_anyway
                   else f"The {trigger.replace('_', ' ')} prompted the change."),
        recommendation=rec, recovery_time_days=recovery,
        facts={"decision_changed": changed, "change_cost": str(change_cost),
               "change_reason": trigger, "would_have_bought_anyway": would_anyway},
    )


register("decision_change",
         trigger=lambda c: _has(c, *_CHANGE_TRIGGERS),
         required_inputs=_decision_change_required, run=_decision_change_run)
