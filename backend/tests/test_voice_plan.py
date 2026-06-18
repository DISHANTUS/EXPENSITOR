"""Sprint 5b — voice personality (pure/deterministic).

Covers profile selection, emotional intensity, user-energy salutations, the
celebration lead, relationship-aware spoken phrasing, auto-play gating, and the
deterministic↔narrated fallback. No DB, no network.
"""

from __future__ import annotations

import re

from app.intelligence.mood import greeting as G, voice as V
from app.services import mood_service as M

_EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF]")


def _plan(ctx: V.VoiceContext, **kw):
    kw.setdefault("salutation", "Good morning.")
    kw.setdefault("fact_segments", ["Your salary should arrive today."])
    kw.setdefault("signature", "greet:2026-06-17:morning")
    return V.build_voice_plan(ctx, **kw)


# ---- profile selection ----------------------------------------------------

def test_celebration_profile_for_special_day_with_lead_and_autoplay():
    p = _plan(V.VoiceContext(special_day="goal_completed"))
    assert p.profile == V.CELEBRATION and p.intensity == V.HIGH
    assert p.lead == "Congratulations!" and p.auto_play is True


def test_milestone_celebration_uses_good_news_lead():
    p = _plan(V.VoiceContext(importance="milestone"))
    assert p.profile == V.CELEBRATION and p.lead == "Good news!" and p.auto_play is True


def test_concerned_profile_intensity_scales_with_stacked_concerns():
    assert _plan(V.VoiceContext(concern_count=1)).intensity == V.MEDIUM
    high = _plan(V.VoiceContext(concern_count=2))
    assert high.profile == V.CONCERNED and high.intensity == V.HIGH and high.auto_play is False


def test_warm_profile_for_relationship_event():
    p = _plan(V.VoiceContext(event=True, relationship=True))
    assert p.profile == V.WARM


def test_late_night_softens_routine_to_gentle():
    assert _plan(V.VoiceContext(user_energy="late_night")).profile == V.GENTLE


def test_routine_morning_is_neutral_low_and_not_autoplayed():
    p = _plan(V.VoiceContext(user_energy="morning"))
    assert p.profile == V.NEUTRAL and p.intensity == V.LOW and p.auto_play is False


# ---- segments / pacing ----------------------------------------------------

def test_segments_lead_with_salutation_and_drop_closer_when_concerned():
    warm = _plan(V.VoiceContext(event=True, relationship=True), encouragement="Have a good one.")
    assert warm.deterministic_segments[0] == "Good morning."
    assert "Have a good one." in warm.deterministic_segments       # closer kept when not concerned
    concerned = _plan(V.VoiceContext(concern_count=1), encouragement="Have a good one.")
    assert "Have a good one." not in concerned.deterministic_segments  # don't undercut concern


def test_narrated_falls_back_to_deterministic_then_uses_override():
    base = _plan(V.VoiceContext())
    assert base.narrated_segments == base.deterministic_segments    # offline: identical
    nar = _plan(V.VoiceContext(), narrated_facts=["Your pay lands today."])
    assert "Your pay lands today." in nar.narrated_segments
    assert "Your salary should arrive today." in nar.deterministic_segments


def test_signature_passthrough():
    assert _plan(V.VoiceContext()).signature == "greet:2026-06-17:morning"


# ---- relationship-aware spoken phrasing (greeting engine) -----------------

def _greet(named):
    ctx = G.GreetingContext(time_of_day="evening", tone="supportive", style="balanced",
                            presence_band="familiar", named_facts=named)
    return G.build_greeting(ctx, seed=1)


def test_overdue_speech_softens_and_flags_concern():
    g = _greet([G.NamedFact(kind="repay_overdue", person="Ravi", amount="₹3,000")])
    seg = " ".join(g.voice_segments)
    assert "Ravi still hasn’t returned the ₹3,000" in seg and "check in" in seg
    assert not _EMOJI.search(seg)                                  # spoken text is emoji-free
    assert g.voice_flags["overdue_count"] == 1 and g.voice_flags["relationship"] is True


def test_income_from_person_uses_gentle_maybe_phrasing():
    g = _greet([G.NamedFact(kind="income_today", person="your father", amount="₹5,000", when_label="today")])
    assert "Looks like your father may be sending ₹5,000 today." in g.voice_segments


# ---- user energy (mood_service helpers) -----------------------------------

def test_user_energy_maps_night_to_late_night():
    assert M._user_energy("night") == "late_night"
    assert M._user_energy("evening") == "evening"


def test_evening_salutation_is_past_tense():
    assert M._ENERGY_SALUTATION["evening"] == "Hope your day went well."
    assert M._ENERGY_SALUTATION["late_night"].startswith("It’s getting late")


def test_split_sentences():
    assert M._split_sentences("One thing. Two things! Three?") == ["One thing.", "Two things!", "Three?"]


def test_voice_for_builds_plan_from_payload():
    from datetime import date
    payload = {"time_of_day": "evening", "voice_segments": ["A.", "B.", "C."], "voice_flags": {"overdue_count": 0},
               "encouragement": "", "special_day": None, "presence_band": "familiar"}
    plan = M._voice_for(payload, "short", date(2026, 6, 17), mood_id="neutral")
    # short -> 1 fact segment + the evening salutation; signature is time-stable.
    assert plan["deterministic_segments"][0] == "Hope your day went well."
    assert plan["deterministic_segments"][1:] == ["A."]
    assert plan["signature"] == "greet:2026-06-17:evening"
