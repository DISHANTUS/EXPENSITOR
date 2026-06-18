"""Forecasting schemas (4b-4): Future Planning, not Goal Math.

Every forecast defends a *future* claim with the same layered envelope as the
4b-3 explainability work: scenarios + confidence + evidence + reasoning +
opportunity cost + a story + follow-ups. Honesty rule (hard): never emit a
fabricated completion date when monthly savings are non-positive or data is
insufficient — say so and offer recovery instead.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

_Date = date  # alias so a field literally named `date` doesn't shadow the type

from app.schemas.chat_primitives import ChatContext, ChatOption
from app.schemas.explain import EvidenceItem


class Lever(BaseModel):
    """A deterministic what-if transform. `ref` round-trips so a tapped chip can
    be re-sent verbatim to re-run the forecast."""
    ref: str            # category:Food:-10 | sub:Netflix:cancel | save:+2000 | recv:Ravi:default | spending:current
    label: str          # "Food −10%"
    kind: str           # category | subscription | savings | receivable | baseline
    monthly_delta: Decimal = Decimal("0")   # +ve improves monthly savings (₹/month)


class LeverChip(BaseModel):
    label: str
    ref: str


class OpportunityCost(BaseModel):
    lever_label: str
    annual_savings: Decimal | None = None   # works even with NO goal (req 5)
    days_earlier: int | None = None         # vs baseline ETA; None when no goal / no ETA
    summary: str


class ScenarioPath(BaseModel):
    mode: str                # current | optimistic | conservative
    label: str               # "Current Path"
    eta: date | None = None  # None => non-positive savings on this path (honest)
    monthly_rate: Decimal
    final_balance: Decimal | None = None
    narrative: str           # a tiny human story (req 7)


class ForecastStory(BaseModel):
    beginning: str
    middle: str
    end: str


class TimelineCandidate(BaseModel):
    """A future-dated event a forecast suggests recording (req 3 — feeds Life
    Timeline later). Not persisted here; the client/Timeline decides."""
    label: str               # "Forecasted Japan Completion"
    date: _Date | None = None
    kind: str = "forecast"


class GoalRef(BaseModel):
    id: str
    name: str
    eta: date | None = None
    progress_pct: float | None = None


class FutureMe(BaseModel):
    current_path: ScenarioPath | None = None
    optimistic_path: ScenarioPath | None = None
    conservative_path: ScenarioPath | None = None


class ForecastIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str | None = Field(default=None, max_length=2000)
    goal_id: str | None = None
    levers: list[str] = []                       # applied lever refs
    # --- life-event inputs (req 1): present even though v1 is simple ---
    target_date: date | None = None
    expected_cost: Decimal | None = None
    event_type: str | None = None                # trip | purchase | move | ...
    session: ChatContext | None = None


class Forecast(BaseModel):
    kind: str                # goal | what_if | life_event | negative | compare_goals | insufficient
    headline: str            # Level-1 explanation (e.g. "March 2028")
    currency: str
    confidence: str          # high | medium | low | insufficient (DATA sufficiency)
    confidence_word: str | None = None
    confidence_note: str | None = None   # "I only have 10 days of spending history."
    reasoning: str           # Level-2 explanation (because: rate / amount / progress)
    scenarios: list[ScenarioPath] = []
    evidence: list[EvidenceItem] = []    # Level-3 (Show Evidence)
    opportunity_costs: list[OpportunityCost] = []
    story: ForecastStory | None = None
    levers: list[LeverChip] = []         # tappable what-if chips
    applied_levers: list[Lever] = []
    timeline_candidates: list[TimelineCandidate] = []
    goals: list[GoalRef] = []            # multi-goal aware (req 2)
    future_me: FutureMe | None = None
    follow_ups: list[ChatOption] = []    # See obstacles / recovery / compare goals / opp costs / Future Me
    surfaced_lesson: str | None = None   # a confirmed lesson the user taught, relevant here (4b-5b)
    accuracy_note: str | None = None     # how reliable my past forecasts have been (4b-5b)
    explain_ref: str | None = None
    session: ChatContext = ChatContext()


# Resolve all forward refs in THIS module's namespace (where `date`/`Decimal`/the
# sub-models live) so `ChatTurn` can embed `Forecast` without a wrong-namespace eval.
for _m in (Lever, LeverChip, OpportunityCost, ScenarioPath, ForecastStory, TimelineCandidate,
           GoalRef, FutureMe, ForecastIn, Forecast):
    _m.model_rebuild()
