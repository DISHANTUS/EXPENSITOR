"""Planning-intent extractor — turns one free-text sentence ("am planning to buy
a new headphone for 3k by december") into the structured fields the Planning
flow needs, so the flow can ask only what's still missing instead of marching
everyone through the same fixed script.

Same discipline as `reason_judge`: deterministic first (fast, offline, always
available), escalate to the local Ollama model only for what the rules couldn't
work out, and fall back to the deterministic result on ANY model failure. The
model is here to widen the range of phrasings we understand — it is never the
source of truth for a number.

Grounding rule (the important one): the model may only *name* things that are
already in the user's sentence. An amount it returns is dropped unless those
digits literally appear in the text, and an item is dropped unless it echoes a
word the user actually typed. A model that hallucinates "headphones cost 5000"
would otherwise quietly plant a fake price into a real savings goal.
"""

from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date
from typing import Any, Awaitable, Callable

# Ordered most-specific first: "netflix subscription" is a subscription even
# though it also contains a buy-ish verb; "save for a phone" is saving, not a
# straight purchase. First list to match wins.
_KIND_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "subscription",
        (
            "subscription", "subscribe", "subscribing", "membership", "renewal",
            "monthly plan", "netflix", "spotify", "prime", "youtube premium",
            "hotstar", "gym", "icloud", "patreon",
        ),
    ),
    (
        "save",
        ("save", "saving", "savings", "set aside", "put aside", "emergency fund", "goal of"),
    ),
    (
        "buy",
        (
            "buy", "buying", "purchase", "purchasing", "order", "ordering",
            "get a", "getting a", "want a", "need a", "upgrade", "planning on a",
        ),
    ),
)

_MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)

_MULTIPLIERS = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "l": 100_000}

# A bare 4-digit number in this range, with no currency marker, is a year not a
# price ("by 2027"). Real prices in that range still parse when they carry a
# symbol or a currency word (₹2027 / 2027 rupees).
_YEAR_MIN, _YEAR_MAX = 2000, 2100

_CURRENCY_WORDS = ("rs", "rs.", "inr", "rupees", "rupee", "usd", "dollars", "eur", "euros", "yen", "jpy", "bucks")

# A bare number only counts as a price if something in the sentence frames it as
# one. Without this, "pulling the trigger on a switch 2" reads as a ₹2 purchase —
# product names are full of numbers (switch 2, iphone 15, pixel 9), and a ₹2 goal
# is worse than simply asking "how much?".
_PRICE_CUES = frozenset(
    {
        "for", "cost", "costs", "costing", "at", "around", "about", "worth",
        "under", "is", "was", "budget", "price", "priced", "roughly", "like",
        "just", "nearly", "approx", "approximately", "spend", "spending", "pay",
        "paying", "only", "some",
    }
)

_AMOUNT_RE = re.compile(
    r"(?P<sym>[₹$€£¥])?\s*(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<mult>k|thousand|lakhs?|l\b)?",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_IN_N_UNITS_RE = re.compile(r"\bin\s+(\d{1,2})\s+(day|week|month|year)s?\b", re.IGNORECASE)
_MONTH_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")\b", re.IGNORECASE)

_MAX_ITEM_WORDS = 3

# The verb after which the thing being planned is usually named. The LAST one
# wins: in "my phone died so I need to replace it", "replace" sits closer to the
# noun slot than "need" does.
_ITEM_ANCHORS = (
    "buy", "buying", "purchase", "purchasing", "get", "getting", "order",
    "ordering", "replace", "replacing", "want", "need", "upgrade", "start",
    "starting", "subscribe", "join",
)
# Words that end the noun phrase — past them lies price, timing or a new clause,
# never part of the item's name.
_ITEM_BOUNDARY = frozenset(
    {
        "for", "by", "before", "within", "and", "so", "but", "because", "then",
        "at", "with", "around", "about", "costing", "worth", "next", "this",
        "every", "each", "per", "from", "on", "until", "till", "when", "since",
    }
)
# Dropped only when they LEAD the phrase ("a new headphone" -> "headphone");
# kept mid-phrase, so "trip to japan" survives intact.
_LEADING_FILLER = frozenset({"a", "an", "the", "my", "our", "some", "new", "another", "to", "up", "of"})
# A phrase built only from these names nothing. Better to hand it to the model
# (and failing that, just ask) than to write "it" into a goal as the item.
_PRONOUNS = frozenset({"it", "one", "that", "this", "these", "them", "they", "thing", "things", "stuff"})

_SYSTEM = """You extract what someone is planning from one sentence. Reply with ONE compact
JSON object and NOTHING else:
{"kind": "buy"|"subscription"|"save"|"other", "item": "<short name>"|null, "amount": <number>|null}

kind:
  "buy"          — a one-off purchase (a phone, a bike, shoes)
  "subscription" — a recurring paid service (Netflix, a gym membership)
  "save"         — putting money aside toward a goal or a trip
  "other"        — anything that is not a plan to spend or save money, e.g. money
                   someone owes them, a bill already paid, or a general question.
                   Use "other" when unsure — do NOT force a guess.

item: the thing itself, 1-3 words, lowercase, no price and no date. null if not named.
amount: ONLY a number that literally appears in the sentence. NEVER guess or
  estimate a price. If no number is written, use null.

Output JSON only — no prose, no markdown fences."""

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_VALID_KINDS = ("buy", "subscription", "save", "other")

# What each kind needs before the Planning flow can actually create something.
_REQUIRED: dict[str, tuple[str, ...]] = {
    "buy": ("item", "amount", "target_date"),
    "save": ("item", "amount", "target_date"),
    "subscription": ("item", "amount"),
    "other": (),
}


def _add_months(d: date, n: int) -> date:
    """Month arithmetic with day clamping (Jan 31 + 1 month -> Feb 28/29)."""
    month_index = d.month - 1 + n
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def _parse_date(text: str, today: date) -> tuple[date | None, tuple[int, int] | None]:
    """Returns (date, span-consumed-in-text). The span lets the amount parser
    skip over digits that were really part of a date."""
    low = text.lower()

    m = _ISO_DATE_RE.search(low)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), m.span()
        except ValueError:
            pass

    m = _IN_N_UNITS_RE.search(low)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit == "day":
            return date.fromordinal(today.toordinal() + n), m.span()
        if unit == "week":
            return date.fromordinal(today.toordinal() + n * 7), m.span()
        if unit == "month":
            return _add_months(today, n), m.span()
        return _add_months(today, n * 12), m.span()

    m = _MONTH_RE.search(low)
    if m:
        month = _MONTHS.index(m.group(1).lower()) + 1
        # The next time that month comes around — "by december" said in
        # December means this December, not next year.
        year = today.year if month >= today.month else today.year + 1
        return date(year, month, monthrange(year, month)[1]), m.span()

    if "next year" in low:
        return _add_months(today, 12), None
    if "next month" in low:
        return _add_months(today, 1), None
    if "next week" in low:
        return date.fromordinal(today.toordinal() + 7), None
    if "end of the month" in low or "end of month" in low:
        return date(today.year, today.month, monthrange(today.year, today.month)[1]), None

    return None, None


def _parse_amount(text: str, skip: tuple[int, int] | None) -> float | None:
    for m in _AMOUNT_RE.finditer(text):
        if skip and not (m.end() <= skip[0] or m.start() >= skip[1]):
            continue  # these digits belong to the date
        raw = m.group("num").replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue

        mult = (m.group("mult") or "").lower().rstrip(".")
        symbol = m.group("sym")
        trailing = text[m.end() : m.end() + 12].lower().strip()
        has_currency_word = any(trailing.startswith(w) for w in _CURRENCY_WORDS)
        preceding = re.findall(r"[a-z]+", text[: m.start()].lower())
        has_cue = bool(preceding) and preceding[-1] in _PRICE_CUES
        explicit = bool(symbol) or has_currency_word or bool(mult)

        if not (explicit or has_cue):
            continue  # a number, but nothing says it's money — e.g. "switch 2"

        if mult:
            value *= _MULTIPLIERS.get(mult, 1)
        elif not explicit and value.is_integer() and _YEAR_MIN <= value <= _YEAR_MAX and len(raw) == 4:
            continue  # a year, not a price

        if value > 0:
            return value
    return None


def _detect_kind(text: str) -> str | None:
    low = f" {text.lower()} "
    for kind, words in _KIND_WORDS:
        if any(w in low for w in words):
            return kind
    return None


def _extract_item(text: str, kind: str | None, date_span: tuple[int, int] | None) -> str | None:
    """Pull the noun out of the sentence with a cheap, honest heuristic: find the
    verb that introduces it, then read the noun phrase that follows.

    Deliberately conservative — it returns None rather than a guess. An eager
    version of this returned junk like "something came need one", which is worse
    than nothing twice over: the junk becomes the name of a real savings goal,
    AND a non-None item stops us ever asking the model, which would have got it
    right. When this can't see the noun, the model gets a turn; failing that, we
    simply ask the user.
    """
    low = text.lower()
    if date_span:
        low = low[: date_span[0]] + " " + low[date_span[1] :]
    low = _AMOUNT_RE.sub(" ", low)  # "headphones for 3000" -> "headphones for"
    tokens = re.findall(r"[a-z]+", low)

    start: int | None = None
    if kind == "save":
        # "save for a trip to japan" / "saving up for an emergency fund" — the
        # thing being saved for comes after "for"/"toward", not after "save".
        for i, tok in enumerate(tokens):
            if tok in ("for", "toward", "towards"):
                start = i + 1
                break
    if start is None:
        for i, tok in enumerate(tokens):
            if tok in _ITEM_ANCHORS:
                start = i + 1
    if start is None:
        return None

    rest = tokens[start:]
    while rest and rest[0] in _LEADING_FILLER:
        rest.pop(0)

    words: list[str] = []
    for tok in rest:
        if tok in _ITEM_BOUNDARY or len(words) >= _MAX_ITEM_WORDS:
            break
        words.append(tok)

    if not words or all(w in _PRONOUNS or w in _LEADING_FILLER for w in words):
        return None
    return " ".join(words)


def _grounded_amount(value: Any, text: str) -> float | None:
    """A model-supplied amount is only trusted if its digits are actually in the
    sentence — otherwise it invented a price."""
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    digits = re.sub(r"[^\d]", "", text)
    whole = str(int(amount)) if amount.is_integer() else str(amount)
    # 3000 written as "3k" won't appear literally, so also accept the leading
    # digits of the number ("3" from "3k" -> "3000" is grounded in "3k").
    if whole in digits:
        return amount
    stripped = whole.rstrip("0")
    return amount if stripped and stripped in digits else None


def _grounded_item(value: Any, text: str) -> str | None:
    """A model-supplied item must echo a word the user typed (allowing for
    plural/tense drift: "a new headphone" -> "headphones")."""
    if not isinstance(value, str):
        return None
    item = " ".join(value.strip().lower().split())[:40]
    if not item:
        return None
    text_tokens = re.findall(r"[a-z]+", text.lower())
    for token in re.findall(r"[a-z]+", item):
        if len(token) < 3:
            continue
        if any(t == token or t[:4] == token[:4] for t in text_tokens):
            return item
    return None


def _parse_model(raw: str, text: str) -> dict[str, Any]:
    if not raw:
        return {}
    m = _JSON_RE.search(raw)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
    except (ValueError, TypeError):
        return {}
    if not isinstance(obj, dict):
        return {}

    out: dict[str, Any] = {}
    kind = obj.get("kind")
    if isinstance(kind, str) and kind.lower() in _VALID_KINDS:
        out["kind"] = kind.lower()
    item = _grounded_item(obj.get("item"), text)
    if item:
        out["item"] = item
    amount = _grounded_amount(obj.get("amount"), text)
    if amount is not None:
        out["amount"] = amount
    return out


def missing_fields(kind: str, item: str | None, amount: float | None, target_date: date | None) -> list[str]:
    have = {"item": item, "amount": amount, "target_date": target_date}
    return [f for f in _REQUIRED.get(kind, ()) if have.get(f) in (None, "")]


async def interpret(
    text: str,
    *,
    today: date | None = None,
    generate: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """Read one free-text planning sentence. `generate` is an injected callable
    (messages -> str), same contract as `llm_router.route` / `judge_sufficiency`
    — pass None to stay fully deterministic."""
    today = today or date.today()
    clean = (text or "").strip()

    target_date, date_span = _parse_date(clean, today)
    amount = _parse_amount(clean, date_span)
    kind = _detect_kind(clean)
    item = _extract_item(clean, kind, date_span)
    used_model = False

    # Only pay for the model when the rules left something genuinely open —
    # a fully-understood sentence never round-trips.
    if generate is not None and clean and (kind is None or item is None):
        messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": clean}]
        try:
            parsed = _parse_model(await generate(messages), clean)
        except Exception:  # noqa: BLE001 — any model/transport failure => rules-only result
            parsed = {}
        if parsed:
            # Deterministic wins where it was confident; the model only fills gaps.
            if kind is None and "kind" in parsed:
                kind, used_model = parsed["kind"], True
            if item is None and "item" in parsed:
                item, used_model = parsed["item"], True
            if amount is None and "amount" in parsed:
                amount, used_model = parsed["amount"], True

    kind = kind or "other"
    return {
        "kind": kind,
        "item": item,
        "amount": amount,
        "target_date": target_date,
        "missing": missing_fields(kind, item, amount, target_date),
        "source": "model" if used_model else "rules",
    }
