"""Offline evaluation of the adaptive reason-suggestion ranking.

This is the app's most defensible novel piece: given a spend's amount (and date),
rank the user's OWN past reasons so the right one is a single tap. This measures
whether it works, against the baselines a reviewer will demand.

Method (a standard held-out ranking eval):
  - Generate a synthetic-but-realistic spending history with latent patterns
    (chai ~₹50 most mornings, groceries ~₹1800 weekly, bus ~₹15 weekdays, …)
    plus noise, seeded for reproducibility.
  - Hold out a set of probes — "what is the user about to spend on" — each a
    (typical amount, true reason). The probe events are NOT in the history, so
    there's no leakage.
  - For each probe, rank reasons and record Hit@1, Hit@3 and MRR.
  - Compare the amount-aware ranking to: most-frequent, most-recent, random.

The point the numbers make: amount-awareness matters. A most-frequent baseline
answers a ₹1800 spend with "chai" (the most common reason); the ranking answers
"groceries".

Run inside the backend container:
    docker compose exec api python -m research.eval_reasons
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.expense import Expense
from app.models.user import User
from app.services import reason_suggestion_service as svc

logging.disable(logging.INFO)  # silence SQLAlchemy echo for a clean report

SEED = 7
TODAY = date(2026, 7, 17)
HISTORY_DAYS = 90

# (reason, typical amount, jitter, probability-per-eligible-day, weekday-only)
PATTERNS = [
    ("chai", 50, 6, 0.80, False),
    ("lunch", 120, 20, 0.70, False),
    ("bus", 15, 3, 0.65, True),
    ("groceries", 1800, 300, 0.14, False),   # ~weekly
    ("recharge", 299, 0, 0.03, False),        # ~monthly
    ("movie", 250, 40, 0.05, False),
    ("medicine", 180, 60, 0.04, False),
]

# Probes: a typical spend the user is about to make. True reason is what a human
# would obviously mean at that amount.
PROBES = [
    (52, "chai"),
    (48, "chai"),
    (125, "lunch"),
    (16, "bus"),
    (1750, "groceries"),
    (1950, "groceries"),
    (299, "recharge"),
    (240, "movie"),
    (200, "medicine"),
]


def _build_history(rng: random.Random) -> list[tuple[date, Decimal, str]]:
    events: list[tuple[date, Decimal, str]] = []
    for i in range(HISTORY_DAYS):
        day = TODAY - timedelta(days=HISTORY_DAYS - i)
        for reason, base, jitter, prob, weekday_only in PATTERNS:
            if weekday_only and day.weekday() >= 5:
                continue
            if rng.random() < prob:
                amt = max(1, base + rng.randint(-jitter, jitter))
                events.append((day, Decimal(amt), reason))
    # A little pure noise, so it's not a clean world.
    for _ in range(15):
        day = TODAY - timedelta(days=rng.randint(1, HISTORY_DAYS))
        events.append((day, Decimal(rng.randint(10, 2500)), rng.choice(["misc", "gift", "repair", "snack"])))
    return events


def _baseline_ranks(events, amount, on_date):
    """Baselines computed from the same history."""
    from collections import Counter, defaultdict
    freq = Counter(r for _, _, r in events)
    most_frequent = [r for r, _ in freq.most_common()]

    last_seen: dict[str, date] = {}
    for d, _, r in events:
        if r not in last_seen or d > last_seen[r]:
            last_seen[r] = d
    most_recent = sorted(last_seen, key=lambda r: last_seen[r], reverse=True)

    rng = random.Random(hash((amount, on_date.toordinal())) & 0xFFFF)
    rand = list(freq)
    rng.shuffle(rand)
    return {"most_frequent": most_frequent, "most_recent": most_recent, "random": rand}


def _hit_mrr(ranked: list[str], truth: str):
    if truth in ranked:
        rank = ranked.index(truth) + 1
        return int(rank == 1), int(rank <= 3), 1.0 / rank
    return 0, 0, 0.0


async def main() -> None:
    rng = random.Random(SEED)
    events = _build_history(rng)

    async with AsyncSessionLocal() as db:
        email = f"eval-reasons-{uuid.uuid4().hex[:8]}@example.com"
        user = User(email=email, password_hash=hash_password("x"), full_name="Eval")
        db.add(user)
        await db.flush()
        for day, amt, reason in events:
            db.add(Expense(
                user_id=user.id, original_amount=amt, original_currency="INR",
                exchange_rate=Decimal("1"), converted_amount=amt, base_currency="INR",
                expense_date=day, description=reason,
            ))
        await db.commit()

        methods = {"Expensitor (amount-aware)": [], "most_frequent": [], "most_recent": [], "random": []}
        for amount, truth in PROBES:
            rows = await svc.suggest(db, user.id, amount=Decimal(amount), on_date=TODAY, limit=50)
            model_ranked = [r["reason"] for r in rows]
            baselines = _baseline_ranks(events, amount, TODAY)

            for name, ranked in (
                ("Expensitor (amount-aware)", model_ranked),
                ("most_frequent", baselines["most_frequent"]),
                ("most_recent", baselines["most_recent"]),
                ("random", baselines["random"]),
            ):
                methods[name].append(_hit_mrr(ranked, truth))

        # cleanup
        await db.execute(delete(Expense).where(Expense.user_id == user.id))
        await db.execute(delete(User).where(User.id == user.id))
        await db.commit()

    n = len(PROBES)
    distinct = len({r for _, _, r in events})
    print(f"\nReason-suggestion ranking  —  {n} probes over a {HISTORY_DAYS}-day synthetic history "
          f"({len(events)} spends, {distinct} distinct reasons)\n")
    print(f"  {'method':<28}{'Hit@1':>8}{'Hit@3':>8}{'MRR':>8}")
    for name, results in methods.items():
        h1 = sum(a for a, _, _ in results) / n
        h3 = sum(b for _, b, _ in results) / n
        mrr = sum(c for _, _, c in results) / n
        print(f"  {name:<28}{h1:>8.3f}{h3:>8.3f}{mrr:>8.3f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
