"""Learning-loop schemas (Sprint 4b-5a): follow-up questions, answers, recall."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FollowUpOption(BaseModel):
    label: str          # "Partially"
    value: str          # yes | partial | no


class FollowUpQuestion(BaseModel):
    id: str
    kind: str
    importance: str
    subject_label: str | None = None
    claim: str
    question: str
    options: list[FollowUpOption] = []


class FollowUpAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="yes | partial | no")
    detail: str | None = Field(default=None, max_length=2000)


class FollowUpAck(BaseModel):
    acknowledged: str
    outcome_id: str | None = None
    circumstance: str | None = None
    advice_id: str
    lesson_suggestion: str | None = None


class MemoryRecallItem(BaseModel):
    id: str
    kind: str
    subject_label: str | None = None
    claim: str
    status: str
    answer: str | None = None
    answer_detail: str | None = None
    circumstance: str | None = None
    when: str | None = None


class MemoryRecall(BaseModel):
    about: str | None = None
    items: list[MemoryRecallItem] = []


# --- 4b-5b: lessons, reflection, accuracy, recap ----------------------------
class LifeLessonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    category: str | None = None


class LifeLessonRead(BaseModel):
    id: str
    lesson: str
    category: str
    source: str
    occurrences: int
    confidence: str
    status: str
    importance: str
    times_surfaced: int
    times_helpful: int
    first_observed: str
    last_observed: str


class ReflectionOption(BaseModel):
    label: str
    value: str


class ReflectionPrompt(BaseModel):
    trigger: str
    importance: str
    question: str
    options: list[ReflectionOption] = []


class ReflectionAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str
    answer: str


class AccuracyByType(BaseModel):
    accurate: int = 0
    partial: int = 0
    inaccurate: int = 0
    pending: int = 0


class PredictionAccuracy(BaseModel):
    tracked: int
    accurate: int
    partial: int
    inaccurate: int
    pending: int
    by_type: dict[str, AccuracyByType] = {}
    note: str


class FinancialIdentity(BaseModel):
    focus_areas: list[str] = []
    strongest_habit: str | None = None
    current_challenge: str | None = None
    currency: str


class RecapGoal(BaseModel):
    name: str
    target: str
    currency: str


class RecapRelationship(BaseModel):
    name: str
    loans: int
    repaid: int


class RecapAchievement(BaseModel):
    type: str
    importance: str
    label: str
    when: str | None = None


class CompanionRecap(BaseModel):
    financial_identity: FinancialIdentity
    goals: list[RecapGoal] = []
    habits: list[str] = []
    relationships: list[RecapRelationship] = []
    lessons: list[LifeLessonRead] = []
    achievements: list[RecapAchievement] = []
    preferences: dict[str, str] = {}
