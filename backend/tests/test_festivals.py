"""Festivals: real dates from the checked-in calendar, real money from the
user's own ledger, and nothing invented in between.

The dates are pinned deliberately. They're transcribed by hand from a panchang,
they cannot be derived, and a typo would be invisible in every other test — the
feature would just quietly tell someone the wrong day to save up for.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.intelligence.companion import festival_calendar as fc
from app.services import festival_service as svc

FESTIVALS = "/api/v1/festivals"
TODAY = date(2026, 7, 17)


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "Marin"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


# --- the dates themselves ---------------------------------------------------


@pytest.mark.parametrize(
    "name,year,expected",
    [
        # drikpanchang Indian calendar 2026 / 2027, cross-checked with calendarr.
        ("Diwali", 2026, date(2026, 11, 8)),     # Lakshmi Puja. NOT 9 Nov (that's the public holiday).
        ("Diwali", 2027, date(2027, 10, 29)),
        ("Holi", 2026, date(2026, 3, 3)),        # NOT 14 March — that is 2025's Holi.
        ("Holi", 2027, date(2027, 3, 22)),
        ("Dussehra", 2026, date(2026, 10, 20)),
        ("Dussehra", 2027, date(2027, 10, 9)),
        ("Raksha Bandhan", 2026, date(2026, 8, 28)),
        ("Ganesh Chaturthi", 2026, date(2026, 9, 14)),
        ("Makar Sankranti", 2027, date(2027, 1, 15)),
        ("Christmas", 2026, date(2026, 12, 25)),
    ],
)
def test_the_dates_match_the_sources(name, year, expected):
    match = [f for f in fc.FESTIVALS if f.name == name and f.day.year == year]
    assert len(match) == 1, f"{name} {year} should appear exactly once"
    assert match[0].day == expected


def test_lunar_festivals_actually_move_between_years():
    # If these ever come out equal, someone has "simplified" the calendar into a
    # fixed date, which is the exact failure this file exists to prevent.
    diwali = sorted(f.day for f in fc.FESTIVALS if f.name == "Diwali")
    assert diwali[0].month != diwali[1].month or diwali[0].day != diwali[1].day
    holi = sorted(f.day for f in fc.FESTIVALS if f.name == "Holi")
    assert holi[0] != holi[1].replace(year=holi[0].year)


def test_moon_sighting_festivals_are_flagged_as_approximate():
    # Eid is announced on a sighting and shifts by region. Presenting it as a
    # settled date would be a promise we can't keep.
    for f in fc.FESTIVALS:
        if f.name.startswith("Eid"):
            assert f.approximate is True
    assert all(not f.approximate for f in fc.FESTIVALS if f.name in ("Diwali", "Holi", "Christmas"))


def test_every_festival_has_a_sane_money_window():
    for f in fc.FESTIVALS:
        start, end = fc.window(f)
        assert start <= f.day <= end
        assert 0 <= f.lead_days <= 30
        assert 0 <= f.trail_days <= 15


# --- lookups ----------------------------------------------------------------


def test_upcoming_is_soonest_first_and_only_the_future():
    up = fc.upcoming(TODAY, horizon_days=150)
    assert up[0].name == "Raksha Bandhan"     # 28 Aug 2026, the next one along
    assert all(f.day >= TODAY for f in up)
    assert up == sorted(up, key=lambda f: f.day)


def test_upcoming_respects_the_horizon():
    assert fc.upcoming(TODAY, horizon_days=30) == []          # nothing until late August
    assert any(f.name == "Diwali" for f in fc.upcoming(TODAY, horizon_days=200))


def test_previous_occurrence_finds_last_year_not_this_one():
    prev = fc.previous_occurrence("Diwali", date(2027, 10, 29))
    assert prev is not None and prev.day == date(2026, 11, 8)


def test_previous_occurrence_is_none_before_the_calendar_starts():
    assert fc.previous_occurrence("Diwali", date(2026, 1, 1)) is None


# --- the calendar expiring ---------------------------------------------------


def test_the_calendar_knows_when_it_runs_out():
    last_in = fc.coverage(fc.REGION_INDIA)[1]
    assert fc.covers(TODAY, region=fc.REGION_INDIA) is True
    assert fc.covers(last_in, region=fc.REGION_INDIA) is True
    assert fc.covers(last_in + timedelta(days=1), region=fc.REGION_INDIA) is False


def test_coverage_is_per_region_not_one_global_span():
    """Regions are transcribed independently and cover different years. A global
    min/max would tell a yen user they're covered on the strength of the Indian
    rows, then show them an empty list."""
    india = fc.coverage(fc.REGION_INDIA)
    japan = fc.coverage(fc.REGION_JAPAN)
    assert india and japan
    assert india[1] != japan[1]                      # they run out on different days
    assert fc.covers(india[1], region=fc.REGION_INDIA) is True
    assert fc.covers(india[1] + timedelta(days=1), region=fc.REGION_INDIA) is False
    assert fc.coverage("BR") is None                 # a region with no rows at all
    assert fc.covers(TODAY, region="BR") is False


async def test_an_expired_calendar_says_so_instead_of_guessing(client: AsyncClient, db_session):
    """The honest end state of a baked dataset. Guessing a lunar date beyond the
    data would be the most convincing kind of wrong."""
    headers = await _auth(client, "fest-expired@example.com")
    user_id = (await client.get("/api/v1/users/me", headers=headers)).json()["id"]

    import uuid as _uuid
    beyond = fc.coverage(fc.REGION_INDIA)[1] + timedelta(days=1)
    result = await svc.insights(db_session, _uuid.UUID(user_id), today=beyond)
    assert result["ready"] is False
    assert result["reason"] == "festival_calendar_out_of_date"
    assert result["upcoming"] == []


# --- over HTTP ---------------------------------------------------------------


async def test_the_endpoint_returns_the_next_festivals(client: AsyncClient):
    headers = await _auth(client, "fest1@example.com")
    resp = await client.get(FESTIVALS, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ready"] is True
    assert body["calendar_until"] == fc.coverage(fc.REGION_INDIA)[1].isoformat()
    assert len(body["upcoming"]) >= 1
    # Regression: `region` was set by the service and silently dropped by the
    # response model, because the schema didn't declare it and no test asserted
    # it. That is the third time this exact bug class has bitten this project.
    assert body["region"] == fc.REGION_INDIA

    first = body["upcoming"][0]
    for field in ("name", "date", "days_away", "approximate", "line"):
        assert field in first, f"{field} was dropped by the response model"


async def test_with_no_history_it_gives_the_date_and_not_one_invented_rupee(client: AsyncClient):
    # THE guard. A brand-new user has no Diwali history. A national average or a
    # "typical Diwali costs ₹X" would be a fabrication attached to a real date,
    # which is the most believable kind of lie this feature could tell.
    headers = await _auth(client, "fest-new@example.com")
    body = (await client.get(FESTIVALS, headers=headers)).json()

    for item in body["upcoming"]:
        assert item["last_time"] is None
        assert "more than" not in item["line"]
        # The line should be the bare fact and nothing else.
        assert item["line"].startswith(item["name"])


async def test_requires_auth(client: AsyncClient):
    assert (await client.get(FESTIVALS)).status_code == 401


async def test_limit_is_bounded(client: AsyncClient):
    headers = await _auth(client, "fest-limit@example.com")
    assert (await client.get(FESTIVALS, headers=headers, params={"limit": 0})).status_code == 422
    assert (await client.get(FESTIVALS, headers=headers, params={"limit": 99})).status_code == 422


# --- wording -----------------------------------------------------------------


def test_the_busy_day_set_covers_every_festival_window():
    for region in (fc.REGION_INDIA, fc.REGION_JAPAN):
        busy = fc.all_festival_days(region=region)
        for f in (x for x in fc.FESTIVALS if x.region == region):
            start, end = fc.window(f)
            assert start in busy and f.day in busy and end in busy


def test_one_festival_is_never_another_festivals_baseline():
    """Regression, caught by running it: Holi's spike leaked into Eid's
    baseline and made Eid look CHEAPER than an ordinary week. October is
    Navratri then Dussehra then Diwali — without this, Diwali is measured
    against weeks already full of festival spending and comes out looking
    cheap, which is the opposite of what the feature exists to say."""
    busy = fc.all_festival_days()
    diwali = next(f for f in fc.FESTIVALS if f.name == "Diwali" and f.day.year == 2026)
    dussehra = next(f for f in fc.FESTIVALS if f.name == "Dussehra" and f.day.year == 2026)

    # Dussehra sits inside the 28 days before Diwali's window...
    d_start, _ = fc.window(diwali)
    assert d_start - timedelta(days=svc.BASELINE_DAYS) <= dussehra.day < d_start
    # ...so its days must be excluded from anything counted as "ordinary".
    assert dussehra.day in busy


def test_the_line_hedges_a_moon_sighting_date():
    eid = next(f for f in fc.FESTIVALS if f.name == "Eid al-Fitr" and f.day.year == 2027)
    line = svc._line(eid, 30, None, "INR")
    assert "moon sighting" in line


def test_the_line_states_a_measured_spike_with_the_users_own_number():
    diwali = next(f for f in fc.FESTIVALS if f.name == "Diwali" and f.day.year == 2026)
    measured = {"notable": True, "extra": "4200", "window_days": 15}
    line = svc._line(diwali, 20, measured, "INR")
    assert "INR 4,200 more" in line
    assert "usual 15 days" in line


def test_the_line_says_so_when_a_festival_was_not_expensive():
    # "Should I worry about this one?" — "no" is a useful answer, not silence.
    diwali = next(f for f in fc.FESTIVALS if f.name == "Diwali" and f.day.year == 2026)
    line = svc._line(diwali, 20, {"notable": False, "extra": "10", "window_days": 15}, "INR")
    assert "didn't cost you much more" in line


def test_today_and_tomorrow_read_naturally():
    holi = next(f for f in fc.FESTIVALS if f.name == "Holi" and f.day.year == 2027)
    assert "is today." in svc._line(holi, 0, None, "INR")
    assert "is tomorrow." in svc._line(holi, 1, None, "INR")
    assert "in 5 days." in svc._line(holi, 5, None, "INR")


# --- Japan / multi-region ----------------------------------------------------


@pytest.mark.parametrize(
    "name,year,expected",
    [
        # nippon.com national holidays 2027; japan-guide for the cluster spans.
        ("Golden Week", 2027, date(2027, 4, 29)),   # Showa Day — the START of the run
        ("Golden Week", 2028, date(2028, 4, 29)),
        ("Shogatsu", 2027, date(2027, 1, 1)),
        ("Obon", 2027, date(2027, 8, 13)),
    ],
)
def test_the_japanese_dates_match_the_sources(name, year, expected):
    match = [f for f in fc.FESTIVALS if f.name == name and f.day.year == year]
    assert len(match) == 1
    assert match[0].day == expected
    assert match[0].region == fc.REGION_JAPAN


def test_golden_week_window_opens_when_the_trains_go_on_sale():
    """JR opens Shinkansen reserved seats EXACTLY one month before travel, so
    the fare is paid ~30 days out. A window covering only the holiday itself
    would miss the single biggest transaction of the event."""
    gw = next(f for f in fc.FESTIVALS if f.name == "Golden Week" and f.day.year == 2027)
    start, end = fc.window(gw)
    assert start == date(2027, 3, 30)          # a month before Showa Day
    assert end >= date(2027, 5, 5)             # ...through Children's Day at the far end


def test_a_japanese_cluster_is_anchored_at_its_start_not_its_end():
    # "Golden Week is in 24 days" must count to when it begins.
    gw = next(f for f in fc.FESTIVALS if f.name == "Golden Week" and f.day.year == 2027)
    assert gw.day == date(2027, 4, 29)
    assert gw.day < date(2027, 5, 5)


def test_region_is_derived_from_the_currency_the_user_thinks_in():
    assert fc.region_for_currency("INR") == fc.REGION_INDIA
    assert fc.region_for_currency("JPY") == fc.REGION_JAPAN
    assert fc.region_for_currency("jpy") == fc.REGION_JAPAN
    # No calendar on file -> no region -> no festivals. Showing a Brazilian user
    # Diwali would be worse than showing them nothing.
    assert fc.region_for_currency("BRL") is None
    assert fc.region_for_currency(None) is None


def test_a_japanese_user_never_sees_indian_festivals():
    jp = fc.upcoming(date(2027, 4, 1), region=fc.REGION_JAPAN, horizon_days=400)
    assert jp and all(f.region == fc.REGION_JAPAN for f in jp)
    assert not any(f.name in ("Diwali", "Holi") for f in jp)


def test_an_indian_user_never_sees_golden_week():
    india = fc.upcoming(TODAY, region=fc.REGION_INDIA, horizon_days=400)
    assert india and all(f.region == fc.REGION_INDIA for f in india)
    assert not any(f.name in ("Golden Week", "Obon", "Shogatsu") for f in india)


def test_one_regions_festivals_are_not_the_other_regions_busy_days():
    # Diwali must not be excluded from a Japanese user's baseline, and vice
    # versa — otherwise a yen user's "ordinary days" get holes punched in them
    # by a calendar that has nothing to do with them.
    jp_busy = fc.all_festival_days(region=fc.REGION_JAPAN)
    diwali = next(f for f in fc.FESTIVALS if f.name == "Diwali" and f.day.year == 2027)
    assert diwali.day not in jp_busy


async def test_a_currency_with_no_calendar_says_so_rather_than_guessing(client, db_session):
    # USD is a supported currency with no festival calendar on file — the real
    # shape of this case. (BRL isn't a supported currency at all, so patching to
    # it 422s and the user silently stays on INR.)
    import uuid as _uuid
    headers = await _auth(client, "fest-usd@example.com")
    user_id = (await client.get("/api/v1/users/me", headers=headers)).json()["id"]
    resp = await client.patch("/api/v1/users/me/settings", headers=headers, json={"base_currency": "USD"})
    assert resp.status_code == 200, resp.text

    result = await svc.insights(db_session, _uuid.UUID(user_id), today=TODAY)
    assert result["ready"] is False
    assert result["reason"] == "no_festival_calendar_for_region"
    assert result["upcoming"] == []


async def test_a_yen_user_gets_japanese_festivals_over_http(client: AsyncClient):
    headers = await _auth(client, "fest-jp@example.com")
    await client.patch("/api/v1/users/me/settings", headers=headers, json={"base_currency": "JPY"})

    body = (await client.get(FESTIVALS, headers=headers)).json()
    assert body["ready"] is True
    assert body["region"] == fc.REGION_JAPAN
    names = [f["name"] for f in body["upcoming"]]
    assert names, "a yen user in 2026 should see the Japanese calendar"
    assert not any(n in ("Diwali", "Holi") for n in names)
