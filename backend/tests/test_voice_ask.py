"""Sprint 5c-A — Voice Conversation orchestration.

Pure tests for the concise summarizer + rounding, and integration tests for
command-vs-query routing, the VoicePlan wrapper, and session round-trip.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.intelligence.voice import voice_reply as vr
from app.schemas.advisor_chat import ChatTurn
from app.schemas.analytics import (
    DrilldownResult,
    GraphSeries,
    ReportSession,
    ReportStory,
    ReportSummary,
)
from app.schemas.forecast import Forecast, ScenarioPath

pytestmark = pytest.mark.asyncio


# ---- pure: rounding + concise summaries -----------------------------------

def test_spoken_amount_rounds_to_friendly_magnitude():
    assert vr.spoken_amount(Decimal("5320"), "INR") == "about 5,000 rupees"
    assert vr.spoken_amount(Decimal("320"), "INR") == "about 300 rupees"
    assert vr.spoken_amount(Decimal("63500"), "USD") == "about 64,000 dollars"
    assert vr.spoken_amount(None, "INR") == ""


def _report(spent="5320", saved="1200", red=2):
    s = ReportSummary(currency="INR", total_spent=Decimal(spent), total_income=Decimal("10000"),
                      saved=Decimal(saved), red_days=red, crown_days=1)
    return ReportSession(kind="week", period_from="2026-06-08", period_to="2026-06-14",
                         period_label="this week", currency="INR",
                         series=GraphSeries(granularity="day", points=[]), summary=s,
                         story=ReportStory(beginning="b", middle="m", end="e"),
                         timeline_events=[], confidence="high")


def test_report_summary_is_one_concise_line_with_nav():
    speech, nav = vr.summarize(ChatTurn(type="report", report=_report()))
    assert speech == ("You spent about 5,000 rupees this week, and saved about 1,000 rupees. "
                      "2 days went over budget. Want the details?")
    assert nav == "report"
    assert "beginning" not in speech and len(speech) < 200      # never the full report


def test_drilldown_red_days_speech():
    dd = DrilldownResult(kind="red_days", title="Red days", currency="INR", items=[], explanation="x")
    assert vr.summarize(ChatTurn(type="drilldown", drilldown=dd)) == ("You had 0 red days.", "report")


def test_forecast_uses_headline_and_offers_paths():
    fc = Forecast(kind="goal", headline="March 2028", currency="INR", confidence="high", reasoning="because",
                  scenarios=[ScenarioPath(mode="current", label="Current Path", monthly_rate=Decimal("1000"),
                                          narrative="n")])
    speech, nav = vr.summarize(ChatTurn(type="forecast", forecast=fc))
    assert speech == "March 2028 Want to hear the paths?" and nav is None


def test_clarify_is_spoken_verbatim():
    assert vr.summarize(ChatTurn(type="clarify", message="Which report would you like?"))[0] \
        == "Which report would you like?"


# ---- integration: routing + voice plan + session --------------------------

async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR"}, headers=h)
    return h


async def test_command_routes_to_act_and_previews(client: AsyncClient):
    h = await _auth(client, "va_cmd@example.com")
    # amount + category present -> straight to a confirmable preview (no clarify needed)
    out = (await client.post("/api/v1/voice/ask",
                             json={"text": "I spent 2000 on food today"}, headers=h)).json()
    assert out["type"] == "preview" and out["action"] == "add_expense"
    assert out["requires_confirmation"] and out["voice"]["deterministic_segments"]


async def test_query_routes_to_chat_with_voice_plan(client: AsyncClient):
    h = await _auth(client, "va_query@example.com")
    out = (await client.post("/api/v1/voice/ask", json={"text": "what can you do?"}, headers=h)).json()
    assert out["type"] == "answer"
    assert out["speech"] and out["voice"]["deterministic_segments"]
    assert out["turn"] is not None                            # full turn available for the sheet


def test_parser_classifies_income_and_lent():
    from datetime import date as _date

    from app.intelligence.nlp import parser as nlp
    t = _date(2026, 6, 17)
    inc = nlp.parse("My father gave me 10000", today=t, valid_category_names=set())
    assert inc.intent == nlp.ADD_INCOME and inc.fields["amount"] == 10000 and inc.fields["source_type"] == "gift"
    lent = nlp.parse("I lent Ravi 5000", today=t, valid_category_names=set())
    assert lent.intent == nlp.ADD_RECEIVABLE and lent.fields["amount"] == 5000 and lent.fields["source_name"] == "Ravi"


async def _ask(client, h, **body):
    return (await client.post("/api/v1/voice/ask", json=body, headers=h)).json()


async def test_voice_write_expense_clarify_confirm_execute(client: AsyncClient):
    h = await _auth(client, "vw_exp@example.com")
    # 1) amount present, category missing -> ask category
    r1 = await _ask(client, h, text="I spent 2000 today")
    assert r1["type"] == "clarification" and r1["awaiting"] == "category"
    # 2) answer category -> preview (confirm required)
    r2 = await _ask(client, h, text="food", command_text="I spent 2000 today", answers={"category": "food"})
    assert r2["type"] == "preview" and r2["requires_confirmation"] and r2["action"] == "add_expense"
    assert "Food & Dining" in r2["speech"]
    # 3) confirm -> executes; the expense now exists
    r3 = await _ask(client, h, text="yes", command_text="I spent 2000 today",
                    answers={"category": "food"}, confirm=True, request_id=r2["request_id"])
    assert r3["type"] == "result" and r3["action"] == "add_expense"
    page = (await client.get("/api/v1/expenses", headers=h)).json()
    assert page["total"] == 1 and page["items"][0]["original_amount"] in ("2000", "2000.0000", "2000.00")


async def test_voice_write_income_previews_then_records(client: AsyncClient):
    h = await _auth(client, "vw_inc@example.com")
    r1 = await _ask(client, h, text="My father gave me 10000")
    assert r1["type"] == "preview" and r1["action"] == "add_income"
    rid = r1["request_id"]
    r2 = await _ask(client, h, text="yes", command_text="My father gave me 10000", confirm=True, request_id=rid)
    assert r2["type"] == "result" and r2["action"] == "add_income"
    page = (await client.get("/api/v1/incomes", headers=h)).json()
    assert page["total"] == 1 and page["items"][0]["source_type"] == "gift"


async def test_mood_query_sets_explain_ref_for_followups(client: AsyncClient):
    h = await _auth(client, "va_mood@example.com")
    out = (await client.post("/api/v1/voice/ask", json={"text": "why are you worried?"}, headers=h)).json()
    assert out["session"]["last_explain_ref"] == "mood:current"
    # follow-up "why" round-trips the session
    out2 = (await client.post("/api/v1/voice/ask",
                              json={"text": "why", "session": out["session"]}, headers=h)).json()
    assert out2["speech"]
