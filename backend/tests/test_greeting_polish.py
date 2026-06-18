"""4c-B polish tests: multi-event ranked greetings, relationship-aware phrasing,
event-specific advice, explainability reasons, rotation memory, voice settings."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.core.config import settings as app_config
from app.intelligence.mood import greeting as G
from app.intelligence.mood.advice_library import advice_for
from app.services import mood_service

pytestmark = pytest.mark.asyncio

MOOD = "/api/v1/companion/mood"


def _today():
    return datetime.now(timezone.utc).date()


def _ctx(**kw) -> G.GreetingContext:
    base = dict(time_of_day="afternoon", tone="encouraging", style="balanced", presence_band="deeply_personalized",
                special_day=None, named_facts=[], goal_name=None, streak_days=0, follow_up=None)
    base.update(kw)
    return G.GreetingContext(**base)


# --- pure: ranking, phrasing, advice, reasons, rotation ----------------------
def test_multiple_events_shown_and_ranked() -> None:
    facts = [
        G.NamedFact(kind="income_today", tier=G.HIGH, person="your father", amount="₹5,000", when_label="today"),
        G.NamedFact(kind="event", tier=G.HIGH, occasion="date", person="Naruse", when_label="this evening"),
    ]
    g = G.build_greeting(_ctx(named_facts=facts, streak_days=12, goal_name="Japan Fund"), seed=1)
    body = " ".join(g.lines)
    assert "your father" in body.lower() and "Naruse" in body          # multiple events, not just one
    assert "12-day budget streak" in body                              # streak rides along (deeply = 3 items)


def test_critical_special_day_leads_over_high_events() -> None:
    g = G.build_greeting(_ctx(special_day="goal_completed",
                              named_facts=[G.NamedFact(kind="income_today", tier=G.HIGH, label="Salary",
                                                       amount="₹5,000", when_label="today")]), seed=1)
    assert g.category == "special_day"
    assert "goal" in g.lines[0].lower()                                # CRITICAL celebration leads


def test_presence_band_caps_item_count() -> None:
    facts = [G.NamedFact(kind="income_today", tier=G.HIGH, label="Salary", amount="₹5,000"),
             G.NamedFact(kind="repay_due", tier=G.HIGH, person="Ravi", amount="₹3,000")]
    new = G.build_greeting(_ctx(named_facts=facts, streak_days=9, presence_band="new"), seed=1)
    deep = G.build_greeting(_ctx(named_facts=facts, streak_days=9, presence_band="deeply_personalized"), seed=1)
    # 'new' shows just one item (+salutation); 'deeply' shows more.
    assert len([ln for ln in new.lines]) < len([ln for ln in deep.lines])


def test_relationship_natural_phrasing() -> None:
    assert mood_service._natural_person("father") == "your father"     # noqa: SLF001
    assert mood_service._natural_person("Ravi") == "Ravi"              # noqa: SLF001
    assert mood_service._natural_person("Mom") == "your mom"           # noqa: SLF001


def test_event_specific_advice() -> None:
    assert "present" in advice_for("date", person="Naruse").lower()
    assert "with Naruse" in advice_for("date", person="Naruse")
    assert "early" in advice_for("interview").lower()
    assert advice_for("income_today", goal=None) is None              # no goal -> no allocation advice
    assert "Japan" in advice_for("income_today", goal="Japan")


def test_reasons_explain_each_shown_item() -> None:
    facts = [G.NamedFact(kind="repay_due", tier=G.HIGH, person="Ravi", amount="₹3,000", when_label="today")]
    g = G.build_greeting(_ctx(named_facts=facts, streak_days=12), seed=1)
    labels = {r["label"] for r in g.reasons}
    assert "Repayment due today" in labels and "Budget streak" in labels


def test_encouragement_rotates_away_from_recent() -> None:
    g1 = G.build_greeting(_ctx(named_facts=[G.NamedFact(kind="repay_due", person="Ravi", amount="₹1")], style="balanced"),
                          seed=1)
    g2 = G.build_greeting(_ctx(named_facts=[G.NamedFact(kind="repay_due", person="Ravi", amount="₹1")], style="balanced"),
                          seed=1, recent_encouragements=[g1.encouragement])
    assert g2.encouragement != g1.encouragement                       # avoids repeating the same closer


# --- API: named facts end-to-end + voice settings ----------------------------
async def _auth(client: AsyncClient, email: str, **settings) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "base_currency": "INR", **settings}, headers=h)
    return h


async def test_greeting_names_a_repayment_due_today(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(app_config, "OLLAMA_ENABLED", False)          # deterministic, no background narration
    h = await _auth(client, "gp1@example.com")
    await client.post("/api/v1/receivables",
                      json={"title": "Loan", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "3000", "original_currency": "INR",
                            "expected_date": _today().isoformat()}, headers=h)
    g = (await client.get(MOOD, headers=h)).json()["greeting"]
    body = " ".join([g["salutation"], *g["lines"]])
    assert "Ravi" in body and "3,000" in body
    assert any(r["label"] == "Repayment due today" for r in g["reasons"])
    assert g["narration_source"] == "deterministic"


async def test_voice_settings_persist(client: AsyncClient) -> None:
    h = await _auth(client, "gp2@example.com")
    await client.patch("/api/v1/users/me/settings",
                       json={"notification_preferences": {"threshold_alerts": True, "weekly_summary": True,
                             "planned_expense_reminders": True, "monthly_report": True,
                             "speak_greeting_on_open": True, "speak_reminders": False,
                             "speak_celebrations": True, "voice_when_tapped_only": False}}, headers=h)
    s = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert s["notification_preferences"]["speak_greeting_on_open"] is True
