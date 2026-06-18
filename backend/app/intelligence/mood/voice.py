"""Voice personality (Sprint 5b, pure/deterministic).

Turns voice CONTEXT — mood, relationship, user energy (time-of-day), emotional
intensity — into a VoicePlan the client performs with flutter_tts: a delivery
profile, an intensity tier, an optional celebration lead, and sentence-level
segments for paced speech.

Facts stay deterministic. This layer decides HOW the companion speaks, never
WHAT is true. Wording may be optionally rephrased downstream by local Ollama
(`narrated_segments`), always with a deterministic fallback — so voice works
instantly offline and can never hallucinate.
"""

from __future__ import annotations

from dataclasses import dataclass

# Delivery profiles (client maps each to concrete rate/pitch/volume).
NEUTRAL, CONCERNED, WARM, CELEBRATION, GENTLE = "neutral", "concerned", "warm", "celebration", "gentle"
# Emotional intensity — same profile, different pacing (Sprint 5b addition).
LOW, MEDIUM, HIGH = "low", "medium", "high"

# Special days that warrant a celebration voice + auto-play (high-priority only).
_CELEBRATORY = {"first_salary", "goal_completed", "graduation", "job_offer", "debt_cleared",
                "birthday", "anniversary"}
_AUTO_PLAY_DAYS = _CELEBRATORY
_LEADS = {
    "first_salary": "Congratulations!", "goal_completed": "Congratulations!",
    "graduation": "Congratulations!", "job_offer": "Congratulations!",
    "debt_cleared": "Wonderful news!", "birthday": "Happy birthday!", "anniversary": "Happy anniversary!",
}


@dataclass(frozen=True)
class VoiceContext:
    """Everything that shapes delivery. Future-proofed for Sprint 6 (Timeline /
    Future Me will read `achievement`, `presence_band`, `user_energy`)."""
    mood: str = "neutral"
    user_energy: str = "morning"        # morning | afternoon | evening | late_night
    presence_band: str = "new"
    relationship: bool = False
    achievement: bool = False
    event: bool = False
    importance: str = "normal"          # normal | milestone | achievement
    special_day: str | None = None
    concern_count: int = 0              # stacked serious facts -> higher intensity


@dataclass(frozen=True)
class VoicePlan:
    profile: str
    intensity: str
    lead: str | None
    deterministic_segments: tuple[str, ...]
    narrated_segments: tuple[str, ...]   # == deterministic until Ollama upgrades it
    signature: str
    auto_play: bool


def _profile(ctx: VoiceContext) -> str:
    if ctx.special_day in _CELEBRATORY or ctx.importance in ("achievement", "milestone") or ctx.achievement:
        return CELEBRATION
    if ctx.concern_count > 0 or ctx.mood in ("concerned", "slightly_over"):
        return CONCERNED
    if ctx.event and ctx.relationship:
        return WARM
    if ctx.user_energy == "late_night":     # routine, but soften the delivery late at night
        return GENTLE
    return NEUTRAL


def _intensity(ctx: VoiceContext, profile: str) -> str:
    if profile == CELEBRATION:
        return HIGH if (ctx.importance == "achievement" or ctx.achievement or ctx.special_day) else MEDIUM
    if profile == CONCERNED:
        if ctx.concern_count >= 2:
            return HIGH                      # several things stacked -> sound more serious
        return MEDIUM if ctx.concern_count == 1 else LOW
    return LOW


def _lead(ctx: VoiceContext, profile: str) -> str | None:
    if profile != CELEBRATION:
        return None
    if ctx.special_day in _LEADS:
        return _LEADS[ctx.special_day]
    return "Congratulations!" if (ctx.importance == "achievement" or ctx.achievement) else "Good news!"


def build_voice_plan(ctx: VoiceContext, *, salutation: str, fact_segments: list[str], signature: str,
                     encouragement: str = "", narrated_facts: list[str] | None = None) -> VoicePlan:
    """Compose the plan. `salutation` is the energy-aware spoken opener (kept
    verbatim, never narrated). `narrated_facts` (if given) are the Ollama-reworded
    fact segments — used in place of the deterministic ones, else they match."""
    profile = _profile(ctx)
    intensity = _intensity(ctx, profile)
    lead = _lead(ctx, profile)
    # A closer feels natural except when we're being serious (don't undercut concern).
    closer = [encouragement] if (encouragement and profile != CONCERNED) else []

    def _segs(facts: list[str]) -> tuple[str, ...]:
        return tuple(s for s in [salutation, *facts, *closer] if s and s.strip())

    det = _segs(fact_segments)
    nar = _segs(narrated_facts) if narrated_facts else det
    auto = (ctx.special_day in _AUTO_PLAY_DAYS) or (ctx.importance in ("achievement", "milestone"))
    return VoicePlan(profile, intensity, lead, det, nar, signature, auto)


def as_dict(plan: VoicePlan) -> dict:
    return {
        "profile": plan.profile, "intensity": plan.intensity, "lead": plan.lead,
        "deterministic_segments": list(plan.deterministic_segments),
        "narrated_segments": list(plan.narrated_segments),
        "signature": plan.signature, "auto_play": plan.auto_play,
    }
