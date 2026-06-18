"""4b-1 tests: conversational advisor — clarify, report, insufficient-data honesty."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC"}, headers=h)
    return h


def _today():
    return datetime.now(timezone.utc).date()


async def test_ambiguous_report_asks_to_clarify(client: AsyncClient) -> None:
    h = await _auth(client, "chat1@example.com")
    r = (await client.post(CHAT, json={"message": "show my spending"}, headers=h)).json()
    assert r["type"] == "clarify"
    labels = [o["label"] for o in r["options"]]
    assert "Weekly" in labels and "Monthly" in labels


async def test_weekly_without_ref_clarifies_period(client: AsyncClient) -> None:
    h = await _auth(client, "chat2@example.com")
    r = (await client.post(CHAT, json={"message": "weekly report"}, headers=h)).json()
    assert r["type"] == "clarify"
    assert any("Last week" in o["label"] for o in r["options"])


async def test_insufficient_data_is_honest(client: AsyncClient) -> None:
    h = await _auth(client, "chat3@example.com")
    r = (await client.post(CHAT, json={"message": "how did i do last week"}, headers=h)).json()
    # Fresh user with no expenses -> don't fake a report.
    assert r["type"] == "answer"
    assert "enough" in r["message"].lower()


async def test_report_returns_graph_summary_story(client: AsyncClient) -> None:
    h = await _auth(client, "chat4@example.com")
    today = _today()
    # Seed a couple of expenses this week so there's data.
    for amt in ("300", "450"):
        await client.post("/api/v1/expenses",
                          json={"original_amount": amt, "original_currency": "INR", "expense_date": today.isoformat()},
                          headers=h)
    r = (await client.post(CHAT, json={"message": "this week report"}, headers=h)).json()
    assert r["type"] == "report"
    report = r["report"]
    assert report["summary"]["total_spent"] == "750.0000"
    assert report["series"]["points"]  # graph data present
    assert report["story"]["beginning"] and report["story"]["middle"] and report["story"]["end"]
    assert report["confidence"] in ("low", "medium", "high")
    assert r["follow_ups"]  # guides the next step
    # Conversation memory echoed back.
    assert r["session"]["last_kind"] == "week" and r["session"]["last_ref"] == "this"


async def test_comparison_is_first_class_with_delta(client: AsyncClient) -> None:
    h = await _auth(client, "cmp@example.com")
    today = _today()
    await client.post("/api/v1/expenses",
                      json={"original_amount": "500", "original_currency": "INR", "expense_date": today.isoformat()},
                      headers=h)
    r = (await client.post(CHAT, json={"message": "compare this month to last month"}, headers=h)).json()
    assert r["type"] == "comparison"
    report = r["report"]
    assert report["comparison_from"] is not None and report["comparison_to"] is not None
    assert report["delta"] is not None
    assert "categories" in report["delta"]
    assert report["story"]["beginning"].lower().startswith("compared to")


async def test_drilldown_red_days_with_explanation(client: AsyncClient) -> None:
    h = await _auth(client, "drill@example.com")
    today = _today()
    # Budget 100, spend 400 -> a red day in this month.
    await client.put(f"/api/v1/daily-plans/{today.isoformat()}", json={"planned_budget": "100"}, headers=h)
    await client.post("/api/v1/expenses",
                      json={"original_amount": "400", "original_currency": "INR", "expense_date": today.isoformat()},
                      headers=h)
    r = (await client.post(CHAT, json={"message": "show red days"}, headers=h)).json()
    assert r["type"] == "drilldown"
    dd = r["drilldown"]
    assert dd["kind"] == "red_days"
    assert dd["explanation"]
    assert len(dd["items"]) >= 1
    assert r["follow_ups"]


async def test_drilldown_keyword_search(client: AsyncClient) -> None:
    h = await _auth(client, "drill2@example.com")
    today = _today()
    await client.post("/api/v1/expenses",
                      json={"original_amount": "900", "original_currency": "INR",
                            "expense_date": today.isoformat(), "description": "Japan trip train ticket"},
                      headers=h)
    r = (await client.post(CHAT, json={"message": "show japan spending"}, headers=h)).json()
    assert r["type"] == "drilldown"
    assert r["drilldown"]["kind"] == "keyword"
    assert any("japan" in i["label"].lower() for i in r["drilldown"]["items"])


async def test_marker_period_label_present(client: AsyncClient) -> None:
    h = await _auth(client, "chat5@example.com")
    today = _today()
    await client.post("/api/v1/expenses",
                      json={"original_amount": "100", "original_currency": "INR", "expense_date": today.isoformat()},
                      headers=h)
    r = (await client.post(CHAT, json={"message": "this month report"}, headers=h)).json()
    assert r["type"] == "report"
    assert r["report"]["period_label"]  # e.g. "June 2026"
    assert r["report"]["series"]["granularity"] == "week"
