"""Calendar-correct date helpers (leap-aware). Pure functions."""

from __future__ import annotations

import calendar
from collections.abc import Iterator
from datetime import date


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def clamp_day(year: int, month: int, day: int) -> date:
    """Date for (year, month, day), clamping day to the month length.

    e.g. clamp_day(2027, 2, 31) -> 2027-02-28 (non-leap); (2028, 2, 29) -> leap day.
    """
    return date(year, month, min(day, days_in_month(year, month)))


def add_months(d: date, n: int) -> date:
    """Add n calendar months (NOT 90 days), clamping the day to the target month."""
    index = d.month - 1 + n
    year = d.year + index // 12
    month = index % 12 + 1
    return clamp_day(year, month, d.day)


def iter_year_months(start: date, end: date) -> Iterator[tuple[int, int]]:
    """Yield (year, month) from start's month through end's month, inclusive."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            month = 1
            year += 1
