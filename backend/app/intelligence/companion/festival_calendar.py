"""When the festivals are — real dates, transcribed from real sources.

This is a baked dataset, not a live API call and not a computation. Three
reasons, in order:

1. **Indian festival dates cannot be derived.** They follow lunar calendars, so
   Diwali moves from 20 Oct 2025 to 8 Nov 2026 to 29 Oct 2027. Any formula
   simple enough to write here would be wrong, and wrong dates are worse than no
   dates — the whole feature is telling someone when to expect a big spend.
2. **No runtime dependency.** The app answers from its own data, offline, with
   no third party that can be down, rate-limit us, or start charging.
3. **It's checkable.** Every date below is in the file, next to its source. You
   can verify it against a panchang in ten seconds. An API response can't be.

The cost is honest and stated: **this data expires.** Past a region's last
covered date the calendar knows nothing, `covers()` returns False, and callers
say nothing rather than guess. Updating is a five-minute transcription job once
a year — see the docstring on `FESTIVALS`.

Regions are transcribed independently and do NOT cover the same years, which is
why coverage is per-region rather than one global span.

Sources (cross-checked; they disagreed, which is exactly why this is checked in
rather than trusted blind):
  - drikpanchang.com Indian calendar 2026 / 2027 / 2028 — the Hindu dates.
    Authoritative panchang; used to settle the conflicts below.
  - calendarr.com/india — Indian public holidays.
  - nippon.com's Japanese national holiday list for 2027 — the statutory dates
    and the substitute-holiday rule. japan-guide.com for Golden Week / Obon
    behaviour.
  - JR / smart-ex reservation rules — Shinkansen reserved seats open exactly one
    month before travel at 10:00 JST, which is why Golden Week's window starts
    30 days out. That is a mechanism, not a guess.
  - A general search claimed "Holi 2026 = 14 March" (that is 2025's date) and
    "Diwali 2026 = 9 November" (that is the public holiday, not Lakshmi Puja).
    Both were wrong. Do not re-introduce them.

Known gaps, stated rather than hidden:
  - India: regional festivals are missing — Onam, Pongal by name, Vishu, Durga
    Puja as distinct from Dussehra. Makar Sankranti covers the same mid-January
    harvest window that Tamil Nadu calls Pongal, but it is not the same word and
    a Kerala user gets nothing for Onam.
  - Japan: Obon's mid-August dates are the majority convention; Okinawa and
    parts of Tokyo keep different ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

REGION_INDIA = "IN"
REGION_JAPAN = "JP"

# Every region with a calendar on file. Anything outside this is rejected rather
# than stored: a setting naming a region we have no dates for is a promise we
# cannot keep.
KNOWN_REGIONS = (REGION_INDIA, REGION_JAPAN)

# Which region's festivals a user sees, derived from the currency they think in.
# A proxy, and an honest one: it needs no migration, no new question at signup,
# and no location permission — and someone budgeting in yen is overwhelmingly
# likely to care about Golden Week. A currency with no festivals on file simply
# gets none, which is the correct answer rather than a wrong region's.
_CURRENCY_REGION: dict[str, str] = {
    "INR": REGION_INDIA,
    "JPY": REGION_JAPAN,
}


def region_for_currency(currency: str | None) -> str | None:
    return _CURRENCY_REGION.get((currency or "").upper())


# The phone's UTC offset in minutes -> region. This is the "you've moved" signal,
# and it is deliberately NOT GPS.
#
# GPS costs the heaviest permission in the app, a prompt, battery, a Play Store
# location declaration, and it stops working offline — all to learn one fact that
# changes maybe once a decade. The phone's clock already knows: land in Tokyo and
# the offset becomes +9:00 by itself.
#
# It is only ever a HINT. An explicit setting always wins, because where someone
# IS and whose festivals are THEIRS are different questions — an Indian student in
# Tokyo wants Diwali and Golden Week, and no amount of location accuracy can work
# that out. Only asking can, once.
_UTC_OFFSET_REGION: dict[int, str] = {
    330: REGION_INDIA,   # +05:30 — India (shared only with Sri Lanka)
    540: REGION_JAPAN,   # +09:00 — Japan (shared with Korea; we only have JP on file)
}


def region_for_utc_offset(offset_minutes: int | None) -> str | None:
    """A guess at the region from the device's clock. None when the offset maps
    to somewhere we have no calendar for — an empty answer beats a wrong one."""
    if offset_minutes is None:
        return None
    return _UTC_OFFSET_REGION.get(offset_minutes)


@dataclass(frozen=True)
class Festival:
    name: str
    day: date
    region: str

    # The window in which the MONEY moves, which is not the festival itself:
    # Diwali shopping starts a fortnight out, Janmashtami costs what it costs on
    # the day. These are estimates used only to decide which days to MEASURE —
    # they are never quoted to the user as fact. Everything a user is told is a
    # number read out of their own ledger.
    lead_days: int = 5
    trail_days: int = 1

    # Moon-sighting festivals are announced a day or two ahead and can shift by
    # a day by region. Flagged so callers can hedge the wording instead of
    # stating a date they can't actually promise.
    approximate: bool = False


# Transcribed by hand from the sources above. To extend: open drikpanchang's
# Indian calendar for the year, read the dates off, add rows, bump
# LAST_COVERED_DATE, and add a test asserting the new year's Diwali. Do not
# compute these.
FESTIVALS: tuple[Festival, ...] = (
    # --- 2026 ---
    Festival("Makar Sankranti", date(2026, 1, 14), REGION_INDIA, lead_days=3, trail_days=1),
    Festival("Holi", date(2026, 3, 3), REGION_INDIA, lead_days=4, trail_days=1),
    Festival("Eid al-Fitr", date(2026, 3, 21), REGION_INDIA, lead_days=8, trail_days=1, approximate=True),
    Festival("Eid al-Adha", date(2026, 5, 28), REGION_INDIA, lead_days=6, trail_days=1, approximate=True),
    Festival("Raksha Bandhan", date(2026, 8, 28), REGION_INDIA, lead_days=5, trail_days=0),
    Festival("Janmashtami", date(2026, 9, 4), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Ganesh Chaturthi", date(2026, 9, 14), REGION_INDIA, lead_days=5, trail_days=2),
    Festival("Navratri", date(2026, 10, 11), REGION_INDIA, lead_days=3, trail_days=9),
    Festival("Dussehra", date(2026, 10, 20), REGION_INDIA, lead_days=5, trail_days=1),
    Festival("Diwali", date(2026, 11, 8), REGION_INDIA, lead_days=12, trail_days=2),
    Festival("Guru Nanak Jayanti", date(2026, 11, 24), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Christmas", date(2026, 12, 25), REGION_INDIA, lead_days=10, trail_days=1),
    # --- 2027 ---
    Festival("Makar Sankranti", date(2027, 1, 15), REGION_INDIA, lead_days=3, trail_days=1),
    Festival("Eid al-Fitr", date(2027, 3, 9), REGION_INDIA, lead_days=8, trail_days=1, approximate=True),
    Festival("Holi", date(2027, 3, 22), REGION_INDIA, lead_days=4, trail_days=1),
    Festival("Eid al-Adha", date(2027, 5, 17), REGION_INDIA, lead_days=6, trail_days=1, approximate=True),
    Festival("Raksha Bandhan", date(2027, 8, 17), REGION_INDIA, lead_days=5, trail_days=0),
    Festival("Janmashtami", date(2027, 8, 25), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Ganesh Chaturthi", date(2027, 9, 4), REGION_INDIA, lead_days=5, trail_days=2),
    Festival("Dussehra", date(2027, 10, 9), REGION_INDIA, lead_days=5, trail_days=1),
    Festival("Diwali", date(2027, 10, 29), REGION_INDIA, lead_days=12, trail_days=2),
    Festival("Guru Nanak Jayanti", date(2027, 11, 14), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Christmas", date(2027, 12, 25), REGION_INDIA, lead_days=10, trail_days=1),
    # --- 2028 (India) ---
    Festival("Makar Sankranti", date(2028, 1, 15), REGION_INDIA, lead_days=3, trail_days=1),
    Festival("Holi", date(2028, 3, 11), REGION_INDIA, lead_days=4, trail_days=1),
    Festival("Raksha Bandhan", date(2028, 8, 5), REGION_INDIA, lead_days=5, trail_days=0),
    Festival("Janmashtami", date(2028, 8, 13), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Ganesh Chaturthi", date(2028, 8, 23), REGION_INDIA, lead_days=5, trail_days=2),
    Festival("Dussehra", date(2028, 9, 27), REGION_INDIA, lead_days=5, trail_days=1),
    Festival("Diwali", date(2028, 10, 17), REGION_INDIA, lead_days=12, trail_days=2),
    Festival("Guru Nanak Jayanti", date(2028, 11, 2), REGION_INDIA, lead_days=2, trail_days=0),
    Festival("Christmas", date(2028, 12, 25), REGION_INDIA, lead_days=10, trail_days=1),

    # --- Japan ---------------------------------------------------------------
    # Japan's calendar is the opposite problem to India's: the dates barely move
    # (they're solar/statutory), but the SPEND is displaced much further from the
    # date than anywhere in the Indian calendar, because the whole country books
    # travel on the same day.
    #
    # Sources: nippon.com's national-holiday list for 2027 (the statutory dates
    # and the substitute-holiday rule), japan-guide on Golden Week and Obon.
    # `day` is the anchor of each cluster; the window is what matters here, not
    # the single date — see lead_days below.
    #
    # Shogatsu: only 1 Jan is statutory, but the country is shut through the 3rd.
    # The money goes on osechi boxes and otoshidama in the fortnight before.
    # 2026. Obon 13-16 Aug is the customary majority convention (not statutory).
    # Silver Week 2026 runs Sat 19 - Wed 23 Sep: Respect for the Aged Day is Mon
    # 21st, Autumnal Equinox is Wed 23rd, and the 22nd becomes a holiday under
    # the rule that a lone weekday between two holidays is itself a holiday.
    Festival("Obon", date(2026, 8, 13), REGION_JAPAN, lead_days=12, trail_days=5),
    Festival("Silver Week", date(2026, 9, 19), REGION_JAPAN, lead_days=14, trail_days=4),
    Festival("Shogatsu", date(2027, 1, 1), REGION_JAPAN, lead_days=14, trail_days=2),
    # Golden Week: four statutory holidays back to back (Showa Day 29 Apr,
    # Constitution Memorial 3 May, Greenery 4 May, Children's Day 5 May).
    # lead_days=30 is not a guess — JR opens Shinkansen seat reservations
    # EXACTLY one month ahead at 10:00 JST, so the fare is paid a month before
    # anyone travels. Measuring only the week itself would miss the biggest
    # single transaction of the whole event.
    Festival("Golden Week", date(2027, 4, 29), REGION_JAPAN, lead_days=30, trail_days=7),
    # Obon: not a statutory holiday at all — a customary return-to-hometown
    # period, mid-August across most of the country (Okinawa and parts of Tokyo
    # still keep other dates; this is the majority convention, not a universal).
    Festival("Obon", date(2027, 8, 13), REGION_JAPAN, lead_days=12, trail_days=5),
    Festival("Silver Week", date(2027, 9, 20), REGION_JAPAN, lead_days=10, trail_days=4),
    Festival("Shogatsu", date(2028, 1, 1), REGION_JAPAN, lead_days=14, trail_days=2),
    Festival("Golden Week", date(2028, 4, 29), REGION_JAPAN, lead_days=30, trail_days=7),
    Festival("Obon", date(2028, 8, 13), REGION_JAPAN, lead_days=12, trail_days=5),
)

# The last day this file can speak about. Past it, `covers()` is False and every
# caller must fall silent — a festival feature that starts guessing dates is
# worse than one that admits it's out of date.
LAST_COVERED_DATE = max(f.day for f in FESTIVALS)
FIRST_COVERED_DATE = min(f.day for f in FESTIVALS)


def coverage(region: str) -> tuple[date, date] | None:
    """The span this file can speak about FOR ONE REGION. Regions are
    transcribed independently and don't cover the same years, so a global
    min/max would tell a yen user they're covered on the strength of the Indian
    rows and then show them nothing."""
    days = [f.day for f in FESTIVALS if f.region == region]
    return (min(days), max(days)) if days else None


def covers(day: date, *, region: str = REGION_INDIA) -> bool:
    """Whether the calendar can still speak about this region.

    Only an upper bound, deliberately. The question this answers is "has the
    data run out?", not "does it start before today?" — a region whose rows
    happen to begin later than today is not broken, it just has nothing in the
    recent past, and `upcoming()` handles that correctly on its own."""
    span = coverage(region)
    return bool(span and day <= span[1])


def window(festival: Festival) -> tuple[date, date]:
    """The days over which this festival's money moves."""
    return (
        festival.day - timedelta(days=festival.lead_days),
        festival.day + timedelta(days=festival.trail_days),
    )


def upcoming(today: date, *, region: str = REGION_INDIA, horizon_days: int = 150) -> list[Festival]:
    """Festivals still ahead, soonest first."""
    limit = today + timedelta(days=horizon_days)
    return sorted(
        (f for f in FESTIVALS if f.region == region and today <= f.day <= limit),
        key=lambda f: f.day,
    )


def past(today: date, *, region: str = REGION_INDIA, within_days: int = 400) -> list[Festival]:
    """Festivals already gone, most recent first — the ones we may have spending
    history for."""
    floor = today - timedelta(days=within_days)
    return sorted(
        (f for f in FESTIVALS if f.region == region and floor <= f.day < today),
        key=lambda f: f.day,
        reverse=True,
    )


def all_festival_days(*, region: str = REGION_INDIA) -> set[date]:
    """Every day that falls inside SOME festival's money window.

    Needed to work out what an "ordinary" day costs. October is Navratri, then
    Dussehra, then Diwali — measure Diwali against the weeks before it and the
    baseline is itself full of festival spending, so Diwali comes out looking
    cheap. A day next to a festival is not an ordinary day."""
    days: set[date] = set()
    for festival in FESTIVALS:
        if festival.region != region:
            continue
        start, end = window(festival)
        for offset in range((end - start).days + 1):
            days.add(start + timedelta(days=offset))
    return days


def previous_occurrence(name: str, before: date, *, region: str = REGION_INDIA) -> Festival | None:
    """The last time this same festival came round — what "last Diwali" means."""
    matches = [f for f in FESTIVALS if f.region == region and f.name == name and f.day < before]
    return max(matches, key=lambda f: f.day) if matches else None
