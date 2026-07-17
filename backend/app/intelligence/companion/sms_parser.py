"""Read a bank's transaction SMS into a structured candidate — the real way to
"connect to UPI".

There is no API that lets an app read GPay/PhonePe/Paytm. But every UPI payment,
card swipe and transfer makes the *bank* text you — "Rs 50 debited ... UPI to
zomato@paytm" — and that SMS is provider-agnostic (one parser catches every app)
and bank-sent (structured and hard to fake). So this parses that SMS.

Two hard rules:

1. **Never auto-create anything.** This returns a *candidate* the user confirms.
   SMS parsing has false positives, and silently inventing an expense from a
   misread text is worse than missing one. The app shows "you spent ₹50 — what
   for?" and the user taps a reason; nothing is recorded until they do.

2. **Reject aggressively.** An OTP, a promo, a balance alert and a delivery
   update all mention rupees. If it isn't clearly a debit or a credit with an
   amount, this returns None rather than guess. A wrong candidate erodes trust
   faster than no candidate.

Pure text in, structured dict out. No model, no network — testable to death,
and it runs the same offline.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# Money: "Rs.1,234.50", "INR 50", "₹2000". The currency marker is required —
# a bare number is not enough signal that this is a transaction.
_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

# Direction. Money leaving vs arriving. Ordered so the first hit wins.
_DEBIT_WORDS = ("debited", "debit", "spent", "paid", "withdrawn", "purchase", "sent", "deducted")
_CREDIT_WORDS = ("credited", "credit", "received", "deposited", "added")

# If ANY of these appear, it's almost certainly not a spend/receive we want:
# one-time passwords, promos, failed/pending, requests, reminders.
_REJECT_WORDS = (
    "otp", "one time password", "one-time password", "verification code",
    "will be debited", "will be credited",       # future/scheduled, not done
    "requesting", "requested", "collect request", "payment request",
    "failed", "declined", "unsuccessful", "reversed", "refund initiated",
    "e-mandate", "emandate", "due on", "overdue", "minimum amount due",
    "offer", "cashback offer", "discount", "sale", "win ", "congratulations",
    "available balance is", "avl bal",           # a pure balance ping, no txn
)

# Payee/merchant extraction. Tried in order; first match wins.
_MERCHANT_PATTERNS = (
    re.compile(r"\bto\s+vpa\s+([a-z0-9._-]+@[a-z0-9]+)", re.IGNORECASE),   # to VPA name@bank
    re.compile(r"\b(?:to|towards)\s+([a-z0-9._-]+@[a-z0-9]+)", re.IGNORECASE),  # to name@bank
    re.compile(r"\bat\s+([A-Z0-9][A-Z0-9 &._-]{1,30}?)(?:\s+on\b|\.|,|$)"),      # at MERCHANT on
    re.compile(r"\bto\s+([A-Z][A-Za-z0-9 &._-]{1,30}?)(?:\s+on\b|\.|,|$)"),      # to Name on
)

# For credits: who it came from.
_SENDER_PATTERNS = (
    re.compile(r"\bfrom\s+([a-z0-9._-]+@[a-z0-9]+)", re.IGNORECASE),
    re.compile(r"\bfrom\s+([A-Z][A-Za-z0-9 &._-]{1,30}?)(?:\s+on\b|\.|,|$)"),
)

_UPI_HINT = re.compile(r"\bupi\b|@[a-z0-9]+", re.IGNORECASE)


def _find_amount(text: str) -> Decimal | None:
    m = _AMOUNT_RE.search(text)
    if not m:
        return None
    try:
        value = Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    return value if value > 0 else None


def _direction(low: str) -> str | None:
    debit_at = min((low.find(w) for w in _DEBIT_WORDS if w in low), default=-1)
    credit_at = min((low.find(w) for w in _CREDIT_WORDS if w in low), default=-1)
    if debit_at < 0 and credit_at < 0:
        return None
    if credit_at < 0:
        return "debit"
    if debit_at < 0:
        return "credit"
    # Both present (rare) — the one that appears first is the headline action.
    return "debit" if debit_at <= credit_at else "credit"


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip(" .,-")


def _merchant(text: str, direction: str) -> str | None:
    patterns = _SENDER_PATTERNS if direction == "credit" else _MERCHANT_PATTERNS
    for pat in patterns:
        m = pat.search(text)
        if m:
            name = _clean(m.group(1))
            if name and name.lower() not in ("vpa", "upi", "a/c", "ac"):
                return name
    return None


def parse(text: str) -> dict[str, Any] | None:
    """Return a transaction candidate, or None if this SMS isn't one we act on.

    None is the common, correct outcome — most texts aren't spend/receive events.
    """
    if not text or not text.strip():
        return None
    low = text.lower()

    # Reject first: an OTP that says "Rs 500" must never become a ₹500 expense.
    if any(word in low for word in _REJECT_WORDS):
        return None

    direction = _direction(low)
    if direction is None:
        return None

    amount = _find_amount(text)
    if amount is None:
        return None

    merchant = _merchant(text, direction)
    is_upi = bool(_UPI_HINT.search(text))

    return {
        "kind": "expense" if direction == "debit" else "income",
        "direction": direction,
        "amount": str(amount),
        "merchant": merchant,          # may be None — the user still confirms
        "is_upi": is_upi,
        "raw": text.strip()[:500],
        # A starting reason guess ONLY when the merchant is known. Never invented
        # from thin air — an unknown merchant yields no guess, and the user's own
        # learned reasons (from reason_suggestion_service) fill the gap.
        "suggested_reason": merchant if (merchant and direction == "debit") else None,
    }
