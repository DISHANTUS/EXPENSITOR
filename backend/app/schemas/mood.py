"""Mood schemas (Sprint 4c-A)."""

from __future__ import annotations

from pydantic import BaseModel


class MoodFace(BaseModel):
    id: str
    emoji: str
    label: str
    kind: str
    priority: int


class MoodReason(BaseModel):
    label: str
    value: str


class GreetingReason(BaseModel):
    label: str
    detail: str = ""


class VoicePlan(BaseModel):
    """How the companion SPEAKS (Sprint 5b) — delivery, not facts."""
    profile: str = "neutral"             # neutral | concerned | warm | celebration | gentle
    intensity: str = "low"               # low | medium | high (same profile, different pacing)
    lead: str | None = None              # spoken first w/ a pause (celebration: "Congratulations!")
    deterministic_segments: list[str] = []   # always present — paced, emoji-free
    narrated_segments: list[str] = []        # optional Ollama rewording; == deterministic offline
    signature: str = ""                  # time-stable dedup key (voice memory)
    auto_play: bool = False              # high-priority only; else tap-to-hear


class Greeting(BaseModel):
    salutation: str
    lines: list[str] = []
    category: str
    summary: str                 # short form (greeting memory)
    reasons: list[GreetingReason] = []   # "why did I say this?" (greeting explainability)
    special_day: str | None = None
    tone: str
    display_text: str = ""       # what to show (narrated when ollama, else salutation+lines)
    spoken_text: str = ""        # plain, emoji-free, fact-complete — for Sprint 5 TTS
    narration_source: str = "deterministic"   # deterministic | ollama (4c-B2)
    pending_narration: bool = False           # a richer narrated version is being generated
    voice: VoicePlan | None = None            # paced, mood-aware delivery (5b)


class PendingReaction(BaseModel):
    kind: str
    emoji: str
    headline: str
    detail: str = ""
    importance: str = "normal"   # normal | milestone | achievement
    tap_route: str | None = None
    timeline_label: str | None = None
    signature: str


class MoodState(BaseModel):
    primary: MoodFace            # the dominant resting face (override or base)
    base: MoodFace               # the financial resting mood
    rotation: list[MoodFace]     # client cycles these (~2s each), always returns to base
    reasons: list[MoodReason] = []
    mood_word: str               # human label for the current mood
    presence_score: int          # internal context-depth (0..100)
    presence_band: str           # new | learning | familiar | deeply_personalized
    greeting: Greeting | None = None
    pending_reactions: list[PendingReaction] = []   # intelligence-driven reactions to surface (5a.5)
    companion_name: str | None = None               # the companion's name (6c), if set
