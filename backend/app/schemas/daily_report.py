"""End-of-day report schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ReportGoal(BaseModel):
    id: str
    name: str
    target_amount: str
    remaining: str
    days_left: int | None = None
    required_daily_saving: str | None = None
    status: str | None = None
    target_date: str | None = None


class DailyReportOut(BaseModel):
    date: str
    currency: str
    day_done: bool          # false -> the day is still in progress; wording stays provisional
    daily_allowance: str
    spent_today: str
    saved_today: str        # allowance - spent; negative means over
    status: str             # under | over | even
    streak_days: int
    window_days: int
    window_net: str         # under(+)/over(-) budget across the window
    goal: ReportGoal | None = None
    lines: list[str] = []   # the report in words, one sentence per line
