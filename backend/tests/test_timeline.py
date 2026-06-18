"""Sprint 6a — Life Timeline: pure builder + aggregation over real data."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.intelligence.timeline import builder as B

pytestmark = pytest.mark.asyncio
_TODAY = date(2026, 6, 17)


# ---- pure builder ---------------------------------------------------------

def test_build_orders_dedupes_and_splits_when():
    entries = [
        B.Entry(date(2027, 3, 1), "Reach Japan goal", kind="goal", importance="high", when=B.FUTURE),
        B.Entry(date(2025, 1, 1), "First income", kind="achievement", importance="life_milestone", when=B.PAST),
        B.Entry(None, "Saving in progress", when=B.PRESENT),
        B.Entry(date(2025, 1, 1), "First income", kind="achievement", importance="life_milestone", when=B.PAST),  # dup
    ]
    tl = B.build(entries, today=_TODAY)
    assert (tl.past_count, tl.present_count, tl.future_count) == (1, 1, 1)   # dup collapsed
    assert [c.label for c in tl.chapters] == ["2025", "2026", "2027"]        # chronological by year
    assert tl.chapters[0].entries[0].title == "First income"
    assert "story so far" in tl.headline


def test_build_empty_has_a_starter_headline():
    tl = B.build([], today=_TODAY)
    assert tl.chapters == [] and "story starts here" in tl.headline


# ---- aggregation over real data -------------------------------------------

async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


def _titles(tl: dict) -> list[str]:
    return [e["title"] for c in tl["chapters"] for e in c["entries"]]


async def test_timeline_weaves_income_goals_and_loans(client: AsyncClient):
    h = await _auth(client, "tl_main@example.com")
    await client.post("/api/v1/incomes", json={
        "source_type": "salary", "original_amount": "50000", "original_currency": "INR",
        "received_date": "2026-01-05"}, headers=h)
    # a completed goal (past win) ...
    g = (await client.post("/api/v1/savings-goals", json={
        "name": "Phone", "kind": "custom_goal", "original_amount": "30000", "original_currency": "INR",
        "target_date": "2026-05-01"}, headers=h)).json()
    await client.patch(f"/api/v1/savings-goals/{g['id']}", json={"status": "completed"}, headers=h)
    # ... and an active goal with a future target
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000", "original_currency": "INR",
        "target_date": "2027-07-01"}, headers=h)
    # a loan still owed
    await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "3000", "original_currency": "INR",
        "expected_date": (date.today() + timedelta(days=30)).isoformat()}, headers=h)

    tl = (await client.get("/api/v1/timeline", headers=h)).json()
    titles = _titles(tl)
    assert "Recorded your first income" in titles
    assert "Completed your Phone goal" in titles
    assert any("Japan Fund" in t for t in titles)
    assert any("Ravi" in t for t in titles)
    assert tl["future_count"] >= 1 and tl["headline"]
    # chapters are named (Sprint 7), starting with "Starting Out"
    labels = [c["label"] for c in tl["chapters"]]
    assert labels and labels[0] == "Starting Out"


async def test_timeline_empty_for_new_user(client: AsyncClient):
    h = await _auth(client, "tl_empty@example.com")
    tl = (await client.get("/api/v1/timeline", headers=h)).json()
    assert tl["chapters"] == [] and "story starts here" in tl["headline"]
