"""Sprint 7 — memory system: chapters, search, filters, relationship pages.

The query engine is deterministic and shared, so we test the pure core directly
and the surfaces (timeline/search/relationships/chat) over real data.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.intelligence.timeline import builder as B, chapters, query

pytestmark = pytest.mark.asyncio
_TODAY = date(2026, 6, 17)


# ---- pure: chapters + query ------------------------------------------------

def test_chapters_open_named_anchors():
    es = [
        B.Entry(date(2026, 1, 5), "Recorded your first income", kind="income"),
        B.Entry(date(2026, 6, 1), "Started saving for Japan Fund", kind="goal"),
        B.Entry(date(2028, 4, 1), "Move to Japan", kind="life_event"),
    ]
    chs = chapters.assign(es)
    titles = [c[0] for c in chs]
    assert titles[0] == "Starting Out"
    assert "Japan Preparation" in titles      # the Japan entry opened a named chapter


def test_query_parses_person_period_kind_and_keyword():
    people = {"Ravi", "Naruse"}
    assert query.parse_query("show everything involving Ravi", today=_TODAY, known_people=people).person == "Ravi"
    s = query.parse_query("what happened in June 2026", today=_TODAY, known_people=people)
    assert (s.month, s.year) == (6, 2026)
    assert query.parse_query("show my achievements", today=_TODAY, known_people=people).kinds == frozenset({"achievement"})
    jp = query.parse_query("when did i start preparing for japan", today=_TODAY, known_people=people)
    assert jp.earliest and jp.keyword == "japan"


def test_filter_entries_by_person_and_keyword():
    es = [
        B.Entry(date(2026, 6, 1), "Started saving for Japan Fund", kind="goal"),
        B.Entry(date(2026, 6, 2), "Lent ₹3,000 to Ravi", kind="loan", person="Ravi"),
    ]
    only_ravi = query.filter_entries(es, query.QuerySpec(person="Ravi"))
    assert len(only_ravi) == 1 and only_ravi[0].person == "Ravi"
    japan = query.filter_entries(es, query.QuerySpec(keyword="japan", earliest=True))
    assert len(japan) == 1 and "Japan" in japan[0].title


# ---- surfaces over real data ----------------------------------------------

async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def _seed(client: AsyncClient, h: dict[str, str]) -> None:
    await client.post("/api/v1/incomes", json={
        "source_type": "salary", "original_amount": "50000", "original_currency": "INR",
        "received_date": "2026-01-05"}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000", "original_currency": "INR",
        "target_date": (date.today() + timedelta(days=400)).isoformat()}, headers=h)
    r = (await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "3000", "original_currency": "INR", "expected_date": "2026-06-10"}, headers=h)).json()
    await client.patch(f"/api/v1/receivables/{r['id']}", json={"status": "received"}, headers=h)
    await client.post("/api/v1/planned-expenses", json={
        "title": "Dinner with Naruse", "planned_date": "2026-06-12", "occasion_type": "outing",
        "original_amount": "1500", "original_currency": "INR"}, headers=h)
    await client.post("/api/v1/life-events", json={
        "title": "Move to Japan", "event_date": "2028-04-01", "kind": "move", "icon": "✈️"}, headers=h)


async def test_timeline_has_named_chapters(client: AsyncClient):
    h = await _auth(client, "mem_ch@example.com")
    await _seed(client, h)
    tl = (await client.get("/api/v1/timeline", headers=h)).json()
    labels = [c["label"] for c in tl["chapters"]]
    assert "Starting Out" in labels
    assert any("Japan" in lbl for lbl in labels)
    assert all("subtitle" in c for c in tl["chapters"])


async def test_search_involving_person_and_achievements_and_period(client: AsyncClient):
    h = await _auth(client, "mem_s@example.com")
    await _seed(client, h)

    ravi = (await client.get("/api/v1/timeline/search", params={"q": "show everything involving Ravi"}, headers=h)).json()
    assert "Ravi" in ravi["summary"] and ravi["entries"]
    assert all(("Ravi" in (e["person"] or "")) or ("Ravi" in e["title"]) for e in ravi["entries"])

    ach = (await client.get("/api/v1/timeline/search", params={"q": "show my achievements"}, headers=h)).json()
    assert ach["entries"] and all(e["kind"] == "achievement" for e in ach["entries"])

    jun = (await client.get("/api/v1/timeline/search", params={"q": "what happened in January 2026"}, headers=h)).json()
    assert "January 2026" in jun["summary"]

    jp = (await client.get("/api/v1/timeline/search", params={"q": "when did i start preparing for Japan"}, headers=h)).json()
    assert "Japan" in (jp["entries"][0]["title"] if jp["entries"] else jp["summary"])


async def test_relationship_list_and_detail(client: AsyncClient):
    h = await _auth(client, "mem_rel@example.com")
    await _seed(client, h)

    people = (await client.get("/api/v1/relationships", headers=h)).json()["people"]
    names = {p["name"] for p in people}
    assert "Ravi" in names and "Naruse" in names

    ravi = (await client.get("/api/v1/relationships/Ravi", headers=h)).json()
    assert ravi["trust"] and ravi["trust"]["repaid"] == 1 and ravi["trust"]["total"] == 1
    assert ravi["trust"]["label"] == "Reliable"
    assert "memor" in ravi["companion_note"] and "together" in ravi["companion_note"]

    naruse = (await client.get("/api/v1/relationships/Naruse", headers=h)).json()
    assert any("Naruse" in e["title"] for e in naruse["timeline"]) and naruse["memories"]


async def test_chat_memory_search(client: AsyncClient):
    h = await _auth(client, "mem_chat@example.com")
    await _seed(client, h)
    turn = (await client.post("/api/v1/advisor/chat",
                              json={"message": "show everything involving Ravi"}, headers=h)).json()
    assert "Ravi" in turn["message"]
