"""Deterministic phrasing helpers for the Advisor layer.

Money/number/date formatting only — no judgement, no calculation. Keeps the
explanation builders concise and currency-aware.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CZK": "Kč"}


def money(amount: Decimal | int | float, currency: str) -> str:
    value = Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    symbol = _SYMBOLS.get(currency.upper())
    body = f"{int(value):,}"
    return f"{symbol}{body}" if symbol else f"{currency.upper()} {body}"


def per_day(amount: Decimal, currency: str) -> str:
    return f"{money(amount, currency)} per day"


def days(n: int) -> str:
    if n <= 0:
        return "today"
    if n == 1:
        return "tomorrow"
    return f"in {n} days"


def on_date(d: date) -> str:
    return f"{d:%b %d}"


def delta_phrase(before: Decimal, after: Decimal, currency: str) -> str:
    """'drops by ₹70' / 'rises by ₹40' / 'stays about the same' — neutral wording."""
    diff = (after - before).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if diff == 0:
        return "stays about the same"
    if diff < 0:
        return f"drops by {money(-diff, currency)}"
    return f"rises by {money(diff, currency)}"
