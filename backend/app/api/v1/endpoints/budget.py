"""Budget derivation endpoints (Budget Setup output)."""

from __future__ import annotations

from fastapi import APIRouter

from decimal import Decimal

from fastapi import Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.budget import BudgetSummary
from app.schemas.budget_reality import BudgetReality
from app.schemas.budget_recommendation import RecommendationSet
from app.schemas.country_baseline import CountryBaseline
from app.schemas.feasibility import Feasibility
from app.schemas.profile_mutation import MutationIn, ProfileChangeProposal, ProfileChangeResult
from app.services import (
    baseline_service,
    budget_service,
    feasibility_service,
    profile_mutation_service,
    reality_service,
    recommendation_budget_service,
)

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/reality", response_model=BudgetReality, summary="Income by source + the 4 expense buckets (survival before savings)")
async def budget_reality(current_user: CurrentUser, db: DbSession) -> BudgetReality:
    return await reality_service.build(db, current_user.id)


@router.get("/feasibility", response_model=Feasibility, summary="Survival-first waterfall + success probability + structural diagnosis")
async def budget_feasibility(current_user: CurrentUser, db: DbSession) -> Feasibility:
    return await feasibility_service.assess(db, current_user.id)


@router.get("/recommendations", response_model=RecommendationSet,
            summary="Conservative/Balanced/Aggressive ways to bridge a savings goal (full math, essentials protected)")
async def budget_recommendations(
    current_user: CurrentUser, db: DbSession,
    target: Decimal | None = Query(default=None, ge=0, description="Monthly savings target; defaults to your goals"),
    insist: bool = Query(default=False, description="Aggressive-goal users only: opt into trimming essentials"),
) -> RecommendationSet:
    return await recommendation_budget_service.recommend(db, current_user.id, target=target, insist=insist)


@router.post("/profile/parse", response_model=ProfileChangeProposal,
             summary="Parse a life change into a profile-update preview (no change applied)")
async def parse_life_change(data: MutationIn, current_user: CurrentUser, db: DbSession) -> ProfileChangeProposal:
    return await profile_mutation_service.propose(db, current_user.id, data.text)


@router.post("/profile/apply", response_model=ProfileChangeResult,
             summary="Apply a life change, recalculate, and report the impact")
async def apply_life_change(data: MutationIn, current_user: CurrentUser, db: DbSession) -> ProfileChangeResult:
    return await profile_mutation_service.apply(db, current_user.id, data.text)


@router.get("/baseline", response_model=CountryBaseline, summary="Profile-specific country baseline (reference only)")
async def budget_baseline(
    current_user: CurrentUser, db: DbSession,
    refresh: bool = Query(default=False, description="Best-effort one-time web refresh; falls back to bundled"),
) -> CountryBaseline:
    return await baseline_service.get_baseline(db, current_user.id, refresh=refresh)


@router.get("/summary", response_model=BudgetSummary, summary="Derived monthly/weekly/daily budget")
async def budget_summary(current_user: CurrentUser, db: DbSession) -> BudgetSummary:
    return await budget_service.summary(db, current_user.id)


@router.post("/apply", response_model=BudgetSummary, summary="Apply derived budget (sets monthly threshold)")
async def apply_budget(current_user: CurrentUser, db: DbSession) -> BudgetSummary:
    return await budget_service.apply(db, current_user.id)
