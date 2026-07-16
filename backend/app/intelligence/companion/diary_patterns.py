"""What the diary adds up to — patterns derived from what the user actually
wrote, never from what a model imagines they meant.

Three questions this answers, and only when the evidence supports them:
  - what do you mention more than anything else?
  - is there a day of the week you keep writing about the same thing?
  - does something cluster in the first week of the month?

Everything here is counting. No model is involved, because a model asked to spot
patterns will always find one — the whole value is in refusing to.

The honesty rules that shape it:
  1. A pattern needs repetition across DIFFERENT days. The same word five times
     in one long note is one event, not a habit.
  2. It reports what it counted ("you've mentioned mango on 5 of your last 12
     days"), never a motive ("mango is your favourite"). Whether it's a
     favourite is the user's to say — so that gets asked, not assumed.
  3. Under the threshold, it says nothing. A wrong "pattern" told back to
     someone about their own life is worse than silence, because they can't
     easily tell it's wrong — it's about them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any, Iterable

# Evidence gates, mirroring daily_habit_service's discipline.
MIN_ENTRIES = 5           # below this there is no "usually" to speak of
MIN_MENTION_DAYS = 3      # a thing must recur across separate days
MIN_WEEKDAY_HITS = 3      # three Thursdays before Thursday means anything
MIN_WEEKDAY_RATE = 0.6    # ...and it must be most of the Thursdays we've seen
MIN_FIRST_WEEK_HITS = 3
MIN_FIRST_WEEK_RATE = 0.6

FIRST_WEEK_LAST_DAY = 7

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Words that carry no topic. Kept deliberately broad: a false "pattern" built on
# a filler word ("you mention 'today' a lot") is embarrassing and useless.
_STOPWORDS = frozenset(
    """
    a an the and or but so if then than that this these those there here it its
    is are was were be been being am do does did done doing have has had having
    i me my mine we us our you your he she they them his her their of to in on
    at by for with from into about as up down out off over under again very
    just only also too not no nor can could will would shall should may might
    must got get gets getting go goes going went gone come comes came make made
    take took see saw look looked want wanted need needed like liked feel felt
    today yesterday tomorrow day days week weeks month months year years time
    times morning evening night afternoon now later some any all more most much
    many little few lot lots bit really quite pretty good bad nice great okay ok
    thing things stuff back again home house place after before during while
    when where what which who why how bought buy paid pay spent spend cost costs
    price rs inr usd rupees bucks dollars around roughly about again still yet
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z]+")


def _content_words(text: str) -> set[str]:
    """Distinct topic words in one blob. A set, not a list: saying "mango mango
    mango" in a single note is one mention of mango, not three."""
    return {
        token
        for token in _TOKEN_RE.findall((text or "").lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _normalise(word: str) -> str:
    """Crude singularisation so "mangoes"/"mango" count as one thing.

    Crude on purpose — a real stemmer is a dependency and a lot of surprise for
    very little gain. But the order matters: a blanket "drop the s" turns
    "mangoes" into "mangoe" and a blanket "drop the es" turns "grapes" into
    "grap", either of which quietly splits one word into two and hides the very
    pattern this file exists to find."""
    if len(word) < 4:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"          # berries -> berry
    if word.endswith("oes") and len(word) > 4:
        return word[:-2]                # mangoes -> mango, potatoes -> potato
    if word.endswith(("ses", "xes", "zes", "ches", "shes")):
        return word[:-2]                # boxes -> box, dishes -> dish
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]                # grapes -> grape, but glass stays glass
    return word


def _entry_words(entry: dict[str, Any]) -> set[str]:
    parts = [entry.get("text") or ""]
    for d in entry.get("details") or []:
        # The user's own answers count; Advary's questions must not, or the
        # thing Advary keeps asking about becomes the thing the user "mentions".
        if (d or {}).get("answer"):
            parts.append(str(d["answer"]))
    return {_normalise(w) for w in _content_words(" ".join(parts))}


def top_mentions(entries: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    """The words that come up on the most separate days."""
    day_counts: dict[str, set[date]] = defaultdict(set)
    for entry in entries:
        day = entry.get("entry_date")
        if day is None:
            continue
        for word in _entry_words(entry):
            day_counts[word].add(day)

    ranked = sorted(
        ((word, len(days)) for word, days in day_counts.items() if len(days) >= MIN_MENTION_DAYS),
        key=lambda pair: (-pair[1], pair[0]),
    )
    total_days = len({e["entry_date"] for e in entries if e.get("entry_date")})
    return [
        {"word": word, "days": days, "of_days": total_days}
        for word, days in ranked[:limit]
    ]


def weekday_pattern(entries: list[dict[str, Any]], word: str) -> dict[str, Any] | None:
    """Does `word` land on one particular weekday most of the time it appears?"""
    days_with_word: set[date] = set()
    for entry in entries:
        day = entry.get("entry_date")
        if day is not None and word in _entry_words(entry):
            days_with_word.add(day)
    if len(days_with_word) < MIN_WEEKDAY_HITS:
        return None

    by_weekday: dict[int, int] = defaultdict(int)
    for day in days_with_word:
        by_weekday[day.weekday()] += 1
    weekday, hits = max(by_weekday.items(), key=lambda pair: pair[1])
    rate = hits / len(days_with_word)
    if hits < MIN_WEEKDAY_HITS or rate < MIN_WEEKDAY_RATE:
        return None
    return {
        "word": word,
        "weekday": _WEEKDAYS[weekday],
        "hits": hits,
        "total": len(days_with_word),
    }


def first_week_pattern(entries: list[dict[str, Any]], word: str) -> dict[str, Any] | None:
    """Does `word` cluster in the first week of the month?"""
    days_with_word = {
        entry["entry_date"]
        for entry in entries
        if entry.get("entry_date") is not None and word in _entry_words(entry)
    }
    if len(days_with_word) < MIN_FIRST_WEEK_HITS:
        return None
    hits = sum(1 for day in days_with_word if day.day <= FIRST_WEEK_LAST_DAY)
    rate = hits / len(days_with_word)
    if hits < MIN_FIRST_WEEK_HITS or rate < MIN_FIRST_WEEK_RATE:
        return None
    return {"word": word, "hits": hits, "total": len(days_with_word)}


def _plural_days(n: int) -> str:
    return "day" if n == 1 else "days"


# Where "often" becomes "usually". At the 0.6 floor a lean is 3-in-5, and
# calling that "usually" oversells it — the adverb has to move with the
# evidence, not sit at the strongest word the moment the gate opens.
STRONG_RATE = 0.75


def _frequency_word(hits: int, total: int) -> str:
    return "Usually" if total and hits / total >= STRONG_RATE else "Often"


def describe(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Everything worth saying about this diary, in the user's own vocabulary.

    `ask` is the one thing worth asking rather than assuming: we can count that
    someone writes "mango" a lot, but only they know whether it's a favourite,
    a chore, or their mum's."""
    dated = [e for e in entries if e.get("entry_date") is not None]
    total_days = len({e["entry_date"] for e in dated})
    if len(dated) < MIN_ENTRIES:
        return {
            "ready": False,
            "entries": len(dated),
            "needed": MIN_ENTRIES,
            "observations": [],
            "ask": None,
        }

    mentions = top_mentions(dated)
    observations: list[dict[str, Any]] = []

    for m in mentions:
        word, days = m["word"], m["days"]
        observations.append({
            "kind": "mention",
            "word": word,
            # "of the N days you've written", not "your last N days": we only
            # know about days they kept a note. Claiming the calendar would be
            # counting days they never told us anything about.
            "text": f"You've mentioned {word} on {days} of the {total_days} {_plural_days(total_days)} you've written.",
        })
        wp = weekday_pattern(dated, word)
        if wp:
            adverb = _frequency_word(wp["hits"], wp["total"])
            observations.append({
                "kind": "weekday",
                "word": word,
                "text": f"{adverb} a {wp['weekday']} — {wp['hits']} of the {wp['total']} times you mentioned it.",
            })
        fw = first_week_pattern(dated, word)
        if fw:
            lead = "Mostly" if _frequency_word(fw["hits"], fw["total"]) == "Usually" else "Often"
            observations.append({
                "kind": "first_week",
                "word": word,
                "text": f"{lead} early in the month — {fw['hits']} of {fw['total']} times in the first week.",
            })

    ask = None
    if mentions:
        top = mentions[0]["word"]
        # Counting says it comes up most. Only they can say why — so ask.
        ask = {"word": top, "question": f"You mention {top} a lot — is it a favourite, or just habit?"}

    return {
        "ready": True,
        "entries": len(dated),
        "days": total_days,
        "observations": observations,
        "ask": ask,
    }
