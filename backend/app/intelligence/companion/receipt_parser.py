"""Read a receipt's OCR text into a structured candidate.

The camera + on-device text recognition (ML Kit) run on the phone and hand this
the raw text; this turns that noisy text into {merchant, total, line items}. The
line items are the foundation of "learn the cost of each product" — every
"Milk 1L … 58.00" is one price observation for this user.

Same discipline as the SMS parser:

  - **A candidate, never an auto-record.** OCR is noisy — a mis-read total is a
    wrong expense. The app shows what it found and the user confirms or edits.
  - **Conservative.** When the total is ambiguous, prefer the line the receipt
    itself labels "total" over guessing the biggest number; when an item line
    doesn't clearly have a price, drop it rather than invent one.

Pure text in, structured dict out. No model, no network.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# A price token: "58.00", "₹58", "Rs.1,234.50", "90". Kept loose because OCR
# drops currency markers and decimals constantly.
_PRICE = r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)"
_PRICE_RE = re.compile(_PRICE, re.IGNORECASE)

# A line item: some name text, then a price at the END of the line. The name has
# to contain a letter (so "12.00" alone isn't an item) and the price is the last
# number on the line (quantities come earlier). The price gets its OWN named
# group — _PRICE already contains a group, so positional numbering here is a
# footgun (the named `name` group is 1, the price would be 2).
_ITEM_RE = re.compile(
    r"^(?P<name>.*?[a-zA-Z].*?)\s+(?:rs\.?|inr|₹)?\s*(?P<price>[0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*$",
    re.IGNORECASE,
)

# Total lines, most specific first — a receipt often has SUBTOTAL, TAX and TOTAL,
# and we must not pick the subtotal.
_TOTAL_KEYS = (
    "grand total", "net payable", "amount payable", "net amount",
    "total amount", "bill total", "total", "amount due", "to pay", "paid",
)

# Lines that carry a number but are NEVER the item total — skip them when
# scanning for line items and when picking the total.
_NON_TOTAL_KEYS = (
    "subtotal", "sub total", "tax", "gst", "cgst", "sgst", "vat", "cess",
    "discount", "savings", "round off", "change", "tender", "cash", "card",
    "balance", "points", "invoice", "bill no", "gstin", "phone", "tel",
    "date", "time", "qty", "quantity",
)

_DATE_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")


def _to_decimal(raw: str) -> Decimal | None:
    try:
        v = Decimal(raw.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None
    return v if v > 0 else None


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _labelled_total(lines: list[str]) -> Decimal | None:
    """A line the receipt itself labels as the total — the trustworthy source.
    Never a subtotal or tax line."""
    for key in _TOTAL_KEYS:
        for ln in lines:
            low = ln.lower()
            if key in low and not any(bad in low for bad in _NON_TOTAL_KEYS if bad != "paid"):
                nums = _PRICE_RE.findall(ln)
                if nums:
                    val = _to_decimal(nums[-1])
                    if val is not None:
                        return val
    return None


def _fallback_total(lines: list[str]) -> Decimal | None:
    """The largest standalone amount, ignoring obvious non-total lines. Only used
    when there ARE line items — a lone number in random text is not a total."""
    candidates: list[Decimal] = []
    for ln in lines:
        if any(bad in ln.lower() for bad in _NON_TOTAL_KEYS):
            continue
        for n in _PRICE_RE.findall(ln):
            v = _to_decimal(n)
            if v is not None:
                candidates.append(v)
    return max(candidates) if candidates else None


def _find_items(lines: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ln in lines:
        low = ln.lower()
        # Skip totals, taxes, headers — they look like items but aren't.
        if any(key in low for key in _NON_TOTAL_KEYS) or any(key in low for key in _TOTAL_KEYS):
            continue
        m = _ITEM_RE.match(ln)
        if not m:
            continue
        name = re.sub(r"\s+", " ", m.group("name")).strip(" .-:")
        price = _to_decimal(m.group("price"))
        # A plausible item: a real name, a real price, and not an absurd line.
        if price is None or len(name) < 2 or not re.search(r"[a-zA-Z]", name):
            continue
        items.append({"name": name, "price": str(price)})
    return items


def _find_merchant(lines: list[str]) -> str | None:
    """The store name is almost always in the first couple of lines, and isn't a
    number, a date or a GSTIN."""
    for ln in lines[:3]:
        low = ln.lower()
        if _PRICE_RE.fullmatch(ln) or _DATE_RE.search(ln):
            continue
        if any(k in low for k in ("gstin", "invoice", "bill no", "tel", "phone")):
            continue
        letters = re.sub(r"[^a-zA-Z]", "", ln)
        if len(letters) >= 3:
            return re.sub(r"\s+", " ", ln).strip(" .-*")
    return None


def _find_date(lines: list[str]) -> str | None:
    for ln in lines:
        m = _DATE_RE.search(ln)
        if m:
            d, mo, y = m.groups()
            year = int(y) + 2000 if len(y) == 2 else int(y)
            try:
                from datetime import date as _date
                return _date(year, int(mo), int(d)).isoformat()
            except ValueError:
                # Day/month swapped or garbage — leave the date out rather than
                # record the wrong one.
                continue
    return None


def parse(text: str) -> dict[str, Any] | None:
    """Return a receipt candidate, or None when the text doesn't look like a
    receipt at all (no total and no priced items)."""
    lines = _lines(text)
    if not lines:
        return None

    items = _find_items(lines)
    total = _labelled_total(lines)

    # A labelled total is enough on its own (a minimal "Total 500" receipt). With
    # no label, we ONLY trust a fallback amount when there are real line items —
    # otherwise a stray number in a chat message ("meeting at 5pm") would look
    # like a ₹5 receipt. No label and no items => not a receipt.
    if total is None:
        if not items:
            return None
        total = _fallback_total(lines)

    return {
        "merchant": _find_merchant(lines),
        "total": str(total) if total is not None else None,
        "date": _find_date(lines),
        "items": items,
        "item_count": len(items),
    }
