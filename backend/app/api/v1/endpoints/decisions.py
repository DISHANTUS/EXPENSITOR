"""Financial Decision Engine endpoint (C7a): POST /decisions/quote."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.intelligence.decision.modifiers.base import ModifierInputs
from app.intelligence.decision.request import UserConstraints
from app.schemas.decision import DecisionQuoteIn, ModifierInputsIn
from app.services import decision_service
from app.services.exceptions import CurrencyNotFoundError, RateNotAvailableError

router = APIRouter(prefix="/decisions", tags=["decisions"])


def _modifier_inputs(m: ModifierInputsIn | None) -> ModifierInputs:
    if m is None:
        return ModifierInputs()
    return ModifierInputs(
        involves=tuple(m.involves) if m.involves is not None else None,
        original_amount=m.original_amount, final_amount=m.final_amount, items_useful=m.items_useful,
        delivery_fee=m.delivery_fee, free_delivery_threshold=m.free_delivery_threshold, offer=m.offer,
        bundle_add_ons=tuple(m.bundle_add_ons) if m.bundle_add_ons is not None else None,
        hidden_items=tuple(m.hidden_items) if m.hidden_items is not None else None,
        subscription=m.subscription, emi=m.emi, cancel_cost=m.cancel_cost, change_trigger=m.change_trigger,
    )


@router.post("/quote")
async def quote_decision(data: DecisionQuoteIn, current_user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """"I want to do this financially" — structured strategies + advisor explanation."""
    constraints = UserConstraints(
        date_fixed=data.constraints.date_fixed,
        no_savings=data.constraints.no_savings,
        no_delay=data.constraints.no_delay,
        mandatory=data.constraints.mandatory,
        willing_to_delay=data.constraints.willing_to_delay,
        willing_to_use_savings=data.constraints.willing_to_use_savings,
        willing_to_reduce_spending=data.constraints.willing_to_reduce_spending,
        reducible_categories=tuple(data.constraints.reducible_categories),
    )
    try:
        return await decision_service.quote(
            db, current_user.id,
            item_label=data.item_label,
            original_amount=data.original_amount,
            original_currency=data.original_currency,
            decision_kind=data.decision_kind,
            outflow_shape=data.outflow_shape,
            recurrence_months=data.recurrence_months,
            tenure_months=data.tenure_months,
            target_date=data.target_date,
            flexibility=data.flexibility,
            emotional_importance=data.emotional_importance,
            constraints=constraints,
            excluded_strategies=tuple(data.excluded_strategies),
            modifier_inputs=_modifier_inputs(data.modifiers),
        )
    except (CurrencyNotFoundError, RateNotAvailableError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
