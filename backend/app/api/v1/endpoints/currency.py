"""Currency reference + conversion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.currency import (
    ConvertRequest,
    ConvertResponse,
    CurrencyRead,
    RatesRefreshResult,
    RatesStatus,
)
from app.services import calendar_service, currency_service, rates_service
from app.services.exceptions import CurrencyNotFoundError, RateNotAvailableError

router = APIRouter(tags=["currency"])


@router.get("/currencies", response_model=list[CurrencyRead], summary="List supported currencies")
async def list_currencies(current_user: CurrentUser, db: DbSession) -> list[CurrencyRead]:
    rows = await currency_service.list_currencies(db)
    return [CurrencyRead.model_validate(row) for row in rows]


@router.get("/currencies/{code}", response_model=CurrencyRead, summary="Get a currency")
async def get_currency(code: str, current_user: CurrentUser, db: DbSession) -> CurrencyRead:
    try:
        row = await currency_service.get_currency(db, code)
    except CurrencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CurrencyRead.model_validate(row)


@router.post("/currency/convert", response_model=ConvertResponse, summary="Convert an amount")
async def convert(data: ConvertRequest, current_user: CurrentUser, db: DbSession) -> ConvertResponse:
    try:
        result = await currency_service.convert(db, data.amount, data.from_currency, data.to_currency)
    except CurrencyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported currency: {exc.code}",
        ) from exc
    except RateNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ConvertResponse.model_validate(result)


@router.get("/currency/rates-status", response_model=RatesStatus,
            summary="When exchange rates were last updated + their source")
async def rates_status(current_user: CurrentUser, db: DbSession) -> RatesStatus:
    today = await calendar_service.user_today(db, current_user.id)
    return RatesStatus.model_validate(await rates_service.status(db, today=today))


@router.post("/currency/refresh", response_model=RatesRefreshResult,
             summary="Refresh exchange rates from the live source (only if stale, unless force)")
async def refresh_rates(current_user: CurrentUser, db: DbSession,
                        force: bool = Query(default=False)) -> RatesRefreshResult:
    today = await calendar_service.user_today(db, current_user.id)
    return RatesRefreshResult.model_validate(await rates_service.refresh(db, today=today, force=force))
