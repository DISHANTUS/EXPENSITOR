"""End-of-day report: the numbers, and the honesty rules around them.

The riskiest thing this feature can do is tell someone they saved money when
they didn't — either because the day isn't over yet, or because "under budget"
got quietly reworded into "saved". Most of this file guards that.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient

from app.services import daily_report_service as svc

REPORT = "/api/v1/daily-report"
TODAY = date(2026, 7, 16)


# --- the streak rule (pure, no DB) ----------------------------------------


def _days(*pairs: tuple[date, str]) -> dict[date, Decimal]:
    return {d: Decimal(v) for d, v in pairs}


_LONG_AGO = TODAY - timedelta(days=365)


def test_today_only_counts_toward_a_streak_once_the_day_is_over():
    # At 2pm you are not "3 days under budget" — you are 2 days under budget
    # and having a good morning. Counting today early turns a promise into a
    # claim, and dinner can still break it.
    spend = _days(
        (TODAY, "10"),
        (TODAY - timedelta(days=1), "10"),
        (TODAY - timedelta(days=2), "10"),
    )
    allowance = Decimal("100")
    joined = TODAY - timedelta(days=2)
    assert svc._streak(spend, allowance, TODAY, day_done=False, history_start=joined) == 2
    assert svc._streak(spend, allowance, TODAY, day_done=True, history_start=joined) == 3


def test_a_streak_stops_at_the_first_day_over_budget():
    spend = _days(
        (TODAY, "10"),
        (TODAY - timedelta(days=1), "500"),
        (TODAY - timedelta(days=2), "10"),
    )
    assert svc._streak(spend, Decimal("100"), TODAY, day_done=True, history_start=_LONG_AGO) == 1


def test_a_streak_cannot_reach_back_past_the_account_itself():
    # A user who joined yesterday has not been under budget for 400 days.
    spend = _days((TODAY, "10"))
    joined_yesterday = TODAY - timedelta(days=1)
    assert svc._streak(spend, Decimal("100"), TODAY, day_done=True, history_start=joined_yesterday) == 2
    assert svc._streak(spend, Decimal("100"), TODAY, day_done=True, history_start=TODAY) == 1


def test_a_day_with_no_spending_still_counts_as_under_budget():
    # Within the account's life, no expenses means no spend — which is exactly
    # the thing being measured. Only days before the account are excluded.
    spend = _days((TODAY, "10"))
    assert svc._streak(spend, Decimal("100"), TODAY, day_done=True, history_start=TODAY - timedelta(days=3)) == 4


def test_no_allowance_means_no_streak():
    assert svc._streak(_days((TODAY, "0")), Decimal("0"), TODAY, day_done=True, history_start=_LONG_AGO) == 0


# --- wording ---------------------------------------------------------------


def _lines(**kw):
    base = dict(
        currency="INR",
        allowance=Decimal("100"),
        spent_today=Decimal("40"),
        saved_today=Decimal("60"),
        day_done=True,
        streak=0,
        window_net=Decimal("0"),
        window_days=7,
        goal=None,
    )
    base.update(kw)
    return svc._lines(**base)


def test_a_day_in_progress_never_claims_the_day_is_done():
    text = " ".join(_lines(day_done=False)).lower()
    assert "so far" in text
    # It must not state a finished-day fact.
    assert "you came in" not in text


def test_a_finished_day_is_stated_plainly():
    text = " ".join(_lines(day_done=True)).lower()
    assert "so far" not in text
    assert "under your" in text


def test_being_over_budget_is_said_out_loud():
    text = " ".join(_lines(saved_today=Decimal("-250"), spent_today=Decimal("350"))).lower()
    assert "over your" in text
    assert "250" in text


def test_a_streak_is_only_mentioned_once_it_is_one():
    assert not any("in a row" in l for l in _lines(streak=1))
    assert any("2 days in a row" in l for l in _lines(streak=2))


def test_a_one_day_window_is_not_reported_as_a_multi_day_total():
    # Caught by reading the live output: a brand-new account produced
    # "Across the last 1 days you're INR 847.74 under budget overall" — broken
    # grammar, and the same number the line above had already given.
    lines = _lines(window_days=1, window_net=Decimal("847.74"))
    assert not any("Across the last" in l for l in lines)
    assert not any(" 1 days" in l for l in lines)


def test_a_real_multi_day_total_is_still_reported():
    assert any(
        "Across the last 4 days you're INR 800.97 under budget overall." == l
        for l in _lines(window_days=4, window_net=Decimal("800.97"))
    )
    assert any(
        "Across the last 4 days you're INR 46.77 over budget overall." == l
        for l in _lines(window_days=4, window_net=Decimal("-46.77"))
    )


def test_the_goal_line_says_what_is_left_and_when():
    lines = _lines(goal={"name": "Headphones", "remaining": "2500", "days_left": 30})
    assert any("Still INR 2,500 to go for Headphones, 30 days out." == l for l in lines)


def test_a_finished_goal_is_not_nagged_about():
    lines = _lines(goal={"name": "Headphones", "remaining": "0", "days_left": 30})
    assert any("already got what you need" in l for l in lines)
    assert not any("to go for" in l for l in lines)


def test_a_passed_deadline_is_acknowledged_not_hidden():
    lines = _lines(goal={"name": "Headphones", "remaining": "2500", "days_left": -3})
    assert any("date you picked has passed" in l for l in lines)


def test_with_no_budget_yet_it_reports_spend_and_says_why_that_is_all():
    lines = _lines(allowance=Decimal("0"), saved_today=Decimal("0"), spent_today=Decimal("40"))
    text = " ".join(lines).lower()
    assert "spent inr 40" in text
    assert "income and commitments" in text
    # It must not invent an allowance comparison it has no basis for.
    assert "under your" not in text


def test_a_goal_is_still_reported_when_there_is_no_allowance_yet():
    # Regression: the no-allowance branch returned early and swallowed the goal
    # line, so anyone who hadn't entered their income never saw their goal —
    # i.e. exactly the person most likely to have just set one.
    lines = _lines(
        allowance=Decimal("0"),
        saved_today=Decimal("0"),
        spent_today=Decimal("40"),
        goal={"name": "Headphones", "remaining": "3000", "days_left": 30},
    )
    assert any("to go for Headphones" in l for l in lines)


# --- over HTTP -------------------------------------------------------------


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "Hori"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_report_returns_every_field_over_http(client: AsyncClient):
    # At the HTTP layer on purpose: response_model silently drops undeclared
    # fields, and a service-level test would never notice.
    headers = await _auth(client, "report@example.com")
    resp = await client.get(REPORT, headers=headers, params={"hour": 21})
    assert resp.status_code == 200
    body = resp.json()
    for field in (
        "date", "currency", "day_done", "daily_allowance", "spent_today",
        "saved_today", "status", "streak_days", "window_days", "window_net", "lines",
    ):
        assert field in body, f"{field} was dropped by the response model"
    assert body["day_done"] is True
    assert isinstance(body["lines"], list) and body["lines"]


async def test_a_brand_new_user_gets_a_sane_report_not_a_crash(client: AsyncClient):
    headers = await _auth(client, "report-new@example.com")
    body = (await client.get(REPORT, headers=headers)).json()
    assert body["spent_today"] == "0.00"
    assert body["streak_days"] == 0
    assert body["goal"] is None
    assert body["day_done"] is False  # no hour sent -> never assume the day is done


async def test_a_new_account_is_not_credited_with_days_it_was_not_here_for(client: AsyncClient):
    """Regression: the window totalled a fixed 7 days against the allowance,
    counting every pre-signup day as a full day's saving. A user who joined
    today was congratulated for a week of thrift that never happened — and it
    contradicted the streak, which already refused to count empty days."""
    headers = await _auth(client, "report-window@example.com")
    body = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()

    # Registered moments ago: the window can only be today.
    assert body["window_days"] == 1
    assert body["streak_days"] <= 1
    # And with no income there's no allowance, so nothing can be "saved" at all.
    assert Decimal(body["window_net"]) == Decimal("0")


async def test_the_window_never_exceeds_the_account_age(client: AsyncClient):
    headers = await _auth(client, "report-age@example.com")
    body = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()
    assert 1 <= body["window_days"] <= svc.WINDOW_DAYS
    # The wording must quote the days actually counted, never a stock "7 days".
    assert not any("last 7 days" in l for l in body["lines"])


async def test_the_hour_decides_whether_the_day_is_called(client: AsyncClient):
    headers = await _auth(client, "report-hour@example.com")
    early = (await client.get(REPORT, headers=headers, params={"hour": 9})).json()
    late = (await client.get(REPORT, headers=headers, params={"hour": 22})).json()
    assert early["day_done"] is False
    assert late["day_done"] is True
    assert any("so far" in l.lower() for l in early["lines"])


async def test_an_impossible_hour_is_rejected(client: AsyncClient):
    headers = await _auth(client, "report-badhour@example.com")
    assert (await client.get(REPORT, headers=headers, params={"hour": 24})).status_code == 422
    assert (await client.get(REPORT, headers=headers, params={"hour": -1})).status_code == 422


async def test_report_requires_auth(client: AsyncClient):
    assert (await client.get(REPORT)).status_code == 401


async def test_the_nearest_goal_is_reported_with_what_is_left(client: AsyncClient):
    """The headline the whole feature exists for: "still ₹Y to go for X"."""
    headers = await _auth(client, "report-goal@example.com")
    today = date.fromisoformat((await client.get(REPORT, headers=headers)).json()["date"])

    far = await client.post("/api/v1/savings-goals", headers=headers, json={
        "name": "Japan trip", "kind": "custom_goal", "original_amount": "200000",
        "original_currency": "INR", "target_date": (today + timedelta(days=300)).isoformat(),
    })
    assert far.status_code == 201, far.text
    near = await client.post("/api/v1/savings-goals", headers=headers, json={
        "name": "Headphones", "kind": "custom_goal", "original_amount": "3000",
        "original_currency": "INR", "target_date": (today + timedelta(days=30)).isoformat(),
    })
    assert near.status_code == 201, near.text

    body = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()
    goal = body["goal"]
    assert goal is not None
    # The SOONEST deadline is the one that matters today, not the biggest.
    assert goal["name"] == "Headphones"
    assert Decimal(goal["target_amount"]) == Decimal("3000")
    assert goal["days_left"] == 30
    # Nothing saved yet, so the whole target is still to go.
    assert Decimal(goal["remaining"]) == Decimal("3000")
    assert any("to go for Headphones" in l for l in body["lines"])


async def test_the_report_and_the_plan_screen_never_disagree(client: AsyncClient):
    # The report reads its goal numbers from the savings engine rather than
    # recomputing them. Two surfaces quoting different figures for the same
    # goal would be worse than showing no goal at all.
    headers = await _auth(client, "report-agree@example.com")
    today = date.fromisoformat((await client.get(REPORT, headers=headers)).json()["date"])
    created = await client.post("/api/v1/savings-goals", headers=headers, json={
        "name": "Bike", "kind": "custom_goal", "original_amount": "50000",
        "original_currency": "INR", "target_date": (today + timedelta(days=90)).isoformat(),
    })
    goal_id = created.json()["id"]

    report_goal = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()["goal"]
    plan_state = (await client.get(f"/api/v1/savings-goals/{goal_id}/state", headers=headers)).json()["state"]

    assert Decimal(report_goal["target_amount"]) == Decimal(plan_state["target_amount"])
    assert report_goal["status"] == plan_state["status"]


async def test_a_monthly_target_goal_is_not_reported_as_a_countdown(client: AsyncClient):
    # monthly_target is "put X aside every month" — it has no finish line, so
    # "still ₹Y to go" would be a category error.
    headers = await _auth(client, "report-monthly@example.com")
    created = await client.post("/api/v1/savings-goals", headers=headers, json={
        "name": "Monthly saving", "kind": "monthly_target",
        "original_amount": "5000", "original_currency": "INR",
    })
    assert created.status_code == 201, created.text

    body = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()
    assert body["goal"] is None
    assert not any("to go for" in l for l in body["lines"])


async def test_spending_shows_up_in_the_report(client: AsyncClient):
    headers = await _auth(client, "report-spend@example.com")
    # Ask the report which day it considers "today" (the user's calendar day,
    # not the server's) and spend on that day.
    today = (await client.get(REPORT, headers=headers)).json()["date"]

    created = await client.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "original_amount": "250",
            "original_currency": "INR",
            "expense_date": today,
            "description": "Lunch",
        },
    )
    # Assert the setup worked. Without this the test passes when the POST 422s
    # and the report is simply empty — which is how this test first "passed".
    assert created.status_code == 201, created.text

    body = (await client.get(REPORT, headers=headers, params={"hour": 21})).json()
    assert Decimal(body["spent_today"]) == Decimal("250")
    assert any("250" in l for l in body["lines"])
