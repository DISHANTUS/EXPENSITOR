"""Repayment planning for borrowed money (Payable).

Reuses the affordability engine — "can I repay ₹X by date Y?" → a human verdict,
a monthly pace, the balance impact, and (when it's tight) realistic later dates
that work. No new forecasting logic; this just asks the existing engine.
"""

from __future__ import annotations

import calendar
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.advisor import phrasing as ph
from app.intelligence.projection import affordability
from app.services import advice_memory_service, payable_service, projection_service

_ZERO = Decimal("0")

# verdict → (feasible?, human phrase)
_VERDICT = {
    "affordable": (True, "looks doable"),
    "conditional": (True, "is tight but possible"),
    "unaffordable": (False, "looks difficult right now"),
}
_PREFERENCE_LINE = {
    "all_at_once": "You'd clear it in one payment.",
    "gradual": "You'd chip away at it over time.",
    "auto": None,
}


def _months_between(a: date, b: date) -> int:
    return max(1, (b.year - a.year) * 12 + (b.month - a.month))


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, mm = d.year + m // 12, m % 12 + 1
    return date(y, mm, min(d.day, calendar.monthrange(y, mm)[1]))


async def plan(
    db: AsyncSession,
    user_id: uuid.UUID,
    payable_id: uuid.UUID,
    *,
    target_date: date,
    preference: str = "auto",
) -> dict:
    payable = await payable_service.get(db, user_id, payable_id)  # raises ResourceNotFoundError
    cur = payable.base_currency
    cost = Decimal(payable.converted_amount)
    who = payable.source_name

    scenario = await projection_service.get_scenario(db, user_id)
    today = scenario.today

    primary = affordability.evaluate(scenario, cost, target_date)
    feasible, phrase = _VERDICT.get(primary.verdict, (False, "is hard to call"))
    months = _months_between(today, target_date)
    monthly = (cost / months).quantize(Decimal("1"))
    expected_low = primary.min_after.get("expected", _ZERO)

    headline = f"Repaying {ph.money(cost, cur)} to {who} by {target_date:%d %b} {phrase}."
    impact: list[str] = []
    pref_line = _PREFERENCE_LINE.get(preference)
    if pref_line:
        impact.append(pref_line)
    if months > 1:
        impact.append(f"That's about {ph.money(monthly, cur)}/month at a steady pace.")
    impact.append(
        f"Your lowest balance afterwards stays positive (around {ph.money(expected_low, cur)})."
        if expected_low >= _ZERO
        else f"It would pull your low point down to about {ph.money(expected_low, cur)}."
    )

    # When it's not comfortably affordable, offer realistic later dates that are.
    alternatives: list[dict] = []
    if primary.verdict != "affordable":
        for n in (1, 2, 3):
            alt = _add_months(target_date, n)
            r = affordability.evaluate(scenario, cost, alt)
            if r.verdict == "affordable":
                comfort = "comfortable" if r.min_after.get("worst", _ZERO) >= _ZERO else "doable"
                alternatives.append({"date": alt.isoformat(), "label": f"{alt:%d %b} — {comfort}"})
            if len(alternatives) >= 2:
                break
        alternatives.append(
            {"date": None, "label": f"…or trim a little discretionary spending to make {target_date:%d %b} work."}
        )

    return {
        "payable_id": str(payable_id),
        "who": who,
        "amount": str(cost),
        "currency": cur,
        "target_date": target_date.isoformat(),
        "preference": preference,
        "feasible": feasible,
        "verdict": primary.verdict,
        "headline": headline,
        "monthly_pace": ph.money(monthly, cur),
        "impact": impact,
        "alternatives": alternatives,
    }


async def commit(
    db: AsyncSession,
    user_id: uuid.UUID,
    payable_id: uuid.UUID,
    *,
    target_date: date,
    preference: str = "auto",
) -> dict:
    """The user accepted a plan → remember it as a generic commitment Fact via the
    existing advice_memory follow-up engine (so Advary later asks "did that
    happen?") and as a timeline entry. Same mechanism debt / goals / income
    verification will all reuse."""
    payable = await payable_service.get(db, user_id, payable_id)  # raises if not found
    cur = payable.base_currency
    cost = Decimal(payable.converted_amount)
    who = payable.source_name
    claim = f"repay {who} {ph.money(cost, cur)} by {target_date:%d %b %Y}"
    fact = {
        "type": "repayment_commitment",
        "person": who,
        "amount": str(cost),
        "target_date": target_date.isoformat(),
        "source": "borrowed_money_intervention",
        "preference": preference,
        "commitment_status": "active",  # active | completed | missed | cancelled (for later)
    }
    await advice_memory_service.record_advice(
        db, user_id, kind="commitment", subject_type="payable", subject_id=payable_id,
        subject_label=who, claim=claim, expected_value=cost, expected_date=target_date,
        assumptions=fact, base_currency=cur,
    )
    return {"committed": True, "claim": claim, "fact": fact}
