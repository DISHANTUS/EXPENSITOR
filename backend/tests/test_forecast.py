"""4b-4 tests: forecasting (ETA + evidence + levers + opportunity cost + confidence +
life-event + receivable-default + Future Me) and the honesty rule (never fabricate a
date when savings are non-positive or data is insufficient)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"
FORECAST = "/api/v1/advisor/forecast"


def _today():
    return datetime.now(timezone.utc).date()


async def _auth(client: AsyncClient, email: str, *, starting: str = "0") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings",
                       json={"timezone": "UTC", "base_currency": "INR", "starting_balance": starting}, headers=h)
    return h


async def _food_id(client: AsyncClient, h: dict[str, str]) -> str:
    cats = (await client.get("/api/v1/categories", headers=h)).json()
    return next(c["id"] for c in cats if c["name"] == "Food & Dining")


async def _spend_days(client, h, *, days: int, amount: str, category_id: str | None = None) -> None:
    """Post one expense on each of the last `days` distinct days (feeds the mu window)."""
    base = _today()
    for i in range(days):
        body = {"original_amount": amount, "original_currency": "INR",
                "expense_date": (base - timedelta(days=i)).isoformat()}
        if category_id:
            body["category_id"] = category_id
        await client.post("/api/v1/expenses", json=body, headers=h)


async def _income(client, h, amount: str) -> None:
    await client.post("/api/v1/incomes", json={"source_type": "salary", "original_amount": amount,
                                               "original_currency": "INR", "received_date": _today().isoformat()}, headers=h)


async def _goal(client, h, *, name="Japan Fund", amount="300000", months_out=24) -> str:
    target = (_today() + timedelta(days=30 * months_out)).isoformat()
    g = (await client.post("/api/v1/savings-goals",
                           json={"name": name, "kind": "custom_goal", "original_amount": amount,
                                 "original_currency": "INR", "target_date": target}, headers=h)).json()
    return g["id"]


# --------------------------------------------------------------------------- #
async def test_goal_eta_has_layered_evidence_and_paths(client: AsyncClient) -> None:
    h = await _auth(client, "fc1@example.com", starting="120000")
    await _income(client, h, "45000")
    await _spend_days(client, h, days=6, amount="50")
    await _goal(client, h)

    fc = (await client.post(FORECAST, json={}, headers=h)).json()
    assert fc["kind"] in ("goal", "what_if")
    # Level-1 headline is a real month, Level-2 reasoning, Level-3 evidence with actual values (no magic numbers).
    assert re.match(r"[A-Z][a-z]+ \d{4}", fc["headline"])
    assert "savings rate" in fc["reasoning"].lower()
    labels = {e["label"] for e in fc["evidence"]}
    assert {"Current savings rate", "Goal amount", "Current progress"} <= labels
    # Three scenario paths + Future Me + a timeline candidate.
    assert len(fc["scenarios"]) == 3
    assert fc["future_me"]["optimistic_path"] and fc["future_me"]["conservative_path"]
    assert any("completion" in tc["label"].lower() for tc in fc["timeline_candidates"])


async def test_future_me_paths_are_ordered_with_narratives(client: AsyncClient) -> None:
    h = await _auth(client, "fc2@example.com", starting="120000")
    await _income(client, h, "60000")
    await _spend_days(client, h, days=8, amount="80")
    await _goal(client, h)

    fm = (await client.post(FORECAST, json={}, headers=h)).json()["future_me"]
    cur = float(fm["current_path"]["monthly_rate"])
    opt = float(fm["optimistic_path"]["monthly_rate"])
    con = float(fm["conservative_path"]["monthly_rate"])
    assert opt >= cur >= con
    assert all(fm[p]["narrative"] for p in ("current_path", "optimistic_path", "conservative_path"))


async def test_lever_creates_opportunity_cost(client: AsyncClient) -> None:
    h = await _auth(client, "fc3@example.com", starting="120000")
    await _income(client, h, "50000")
    await _spend_days(client, h, days=6, amount="50")
    await _goal(client, h)

    base = (await client.post(FORECAST, json={}, headers=h)).json()
    levered = (await client.post(FORECAST, json={"levers": ["save:+5000"]}, headers=h)).json()
    assert levered["applied_levers"], "the save lever should be applied"
    opp = levered["opportunity_costs"]
    assert any(o.get("annual_savings") == "60000.00" for o in opp)  # 5000 * 12
    # Saving more never pushes the goal later.
    if base["headline"].startswith(tuple("JFMASOND")) and levered["headline"][0:3] != "Not":
        assert any((o.get("days_earlier") or 0) >= 0 for o in opp)


async def test_low_confidence_when_history_is_thin(client: AsyncClient) -> None:
    h = await _auth(client, "fc4@example.com", starting="120000")
    await _income(client, h, "50000")
    await _spend_days(client, h, days=6, amount="100")   # 6 distinct days -> observed ~6 -> low
    await _goal(client, h)

    fc = (await client.post(FORECAST, json={}, headers=h)).json()
    assert fc["confidence"] == "low"
    assert "history" in (fc["confidence_note"] or "").lower()


async def test_negative_savings_never_fabricates_a_date(client: AsyncClient) -> None:
    h = await _auth(client, "fc5@example.com")                 # no starting balance, no income
    await _spend_days(client, h, days=6, amount="2000")        # heavy spend, net negative
    await _goal(client, h)

    fc = (await client.post(FORECAST, json={}, headers=h)).json()
    assert fc["kind"] == "negative"
    assert "decreasing" in fc["headline"].lower()
    assert not fc["scenarios"]                                  # honesty: no fabricated path/date
    labels = [o["label"] for o in fc["follow_ups"]]
    assert "Recovery plan" in labels


async def test_receivable_default_pushes_goal_later(client: AsyncClient) -> None:
    h = await _auth(client, "fc6@example.com", starting="120000")
    await _income(client, h, "50000")
    await _spend_days(client, h, days=6, amount="50")
    past = (_today() - timedelta(days=5)).isoformat()
    await client.post("/api/v1/receivables",
                      json={"title": "Loan", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "5000", "original_currency": "INR", "expected_date": past}, headers=h)
    await _goal(client, h)

    fc = (await client.post(FORECAST, json={"levers": ["recv:Ravi:default"]}, headers=h)).json()
    assert any(lv["kind"] == "receivable" for lv in fc["applied_levers"])
    assert any("ravi" in o["summary"].lower() for o in fc["opportunity_costs"])


async def test_life_event_affordability(client: AsyncClient) -> None:
    h = await _auth(client, "fc7@example.com", starting="200000")
    await _income(client, h, "60000")
    await _spend_days(client, h, days=6, amount="100")
    target = (_today() + timedelta(days=120)).isoformat()

    fc = (await client.post(FORECAST,
                            json={"expected_cost": "60000", "target_date": target, "event_type": "purchase"},
                            headers=h)).json()
    assert fc["kind"] == "life_event"
    labels = {e["label"] for e in fc["evidence"]}
    assert "Verdict" in labels and "Expected cost" in labels


async def test_no_goal_still_gives_opportunity_cost(client: AsyncClient) -> None:
    h = await _auth(client, "fc8@example.com", starting="50000")
    await _income(client, h, "40000")
    await _spend_days(client, h, days=6, amount="100")
    # An active subscription so there's a recurring cost to annualize.
    await client.post("/api/v1/recurring-rules",
                      json={"rule_type": "subscription", "label": "Netflix", "original_amount": "500",
                            "original_currency": "INR", "recurrence_day": 5,
                            "start_date": _today().replace(day=1).isoformat()}, headers=h)

    fc = (await client.post(FORECAST, json={}, headers=h)).json()
    assert fc["kind"] == "insufficient"                         # no goal yet
    assert any("year" in o["summary"].lower() for o in fc["opportunity_costs"])


# --- chat routing -------------------------------------------------------------
async def test_chat_when_will_i_reach_routes_to_forecast(client: AsyncClient) -> None:
    h = await _auth(client, "fc9@example.com", starting="120000")
    await _income(client, h, "50000")
    await _spend_days(client, h, days=6, amount="50")
    await _goal(client, h)
    r = (await client.post(CHAT, json={"message": "when will I reach my goal?"}, headers=h)).json()
    assert r["type"] == "forecast"
    assert r["forecast"]["headline"]


async def test_chat_what_if_lever_routes_to_forecast(client: AsyncClient) -> None:
    h = await _auth(client, "fc10@example.com", starting="120000")
    await _income(client, h, "50000")
    food = await _food_id(client, h)
    await _spend_days(client, h, days=6, amount="400", category_id=food)
    await _goal(client, h)
    r = (await client.post(CHAT, json={"message": "what if I reduce Food & Dining by 50%?"}, headers=h)).json()
    assert r["type"] == "forecast"
    assert any(lv["kind"] == "category" for lv in r["forecast"]["applied_levers"])


async def test_chat_compare_goals(client: AsyncClient) -> None:
    h = await _auth(client, "fc11@example.com", starting="120000")
    await _income(client, h, "50000")
    await _spend_days(client, h, days=6, amount="50")
    await _goal(client, h, name="Japan Fund", amount="300000")
    await _goal(client, h, name="Laptop", amount="60000", months_out=8)
    r = (await client.post(CHAT, json={"message": "compare goals"}, headers=h)).json()
    assert r["type"] == "forecast"
    assert r["forecast"]["kind"] == "compare_goals"
    assert len(r["forecast"]["goals"]) == 2


async def test_chat_can_i_afford_life_event(client: AsyncClient) -> None:
    h = await _auth(client, "fc12@example.com", starting="200000")
    await _income(client, h, "60000")
    await _spend_days(client, h, days=6, amount="100")
    r = (await client.post(CHAT, json={"message": "can I afford a 60000 laptop in October?"}, headers=h)).json()
    assert r["type"] == "forecast"
    assert r["forecast"]["kind"] == "life_event"
