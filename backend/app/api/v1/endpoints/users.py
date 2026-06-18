"""Current-user endpoints: profile and settings."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession, is_developer
from app.schemas.financial_profile import FinancialProfileRead, FinancialProfileUpdate
from app.schemas.settings import UserSettingsRead, UserSettingsUpdate
from app.schemas.user import UserRead
from app.services import profile_service, settings_service
from app.services.exceptions import FieldNotNullableError, UnsupportedCurrencyError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get the current user")
async def read_me(current_user: CurrentUser, db: DbSession) -> UserRead:
    # Reflect the EFFECTIVE developer status (flag OR email allow-list) and whether
    # the first-launch tour has been seen (drives the client onboarding gate).
    s = await settings_service.get_settings(db, current_user.id)
    return UserRead.model_validate(current_user).model_copy(update={
        "is_developer": is_developer(current_user),
        "has_seen_tour": s.tour_completed_at is not None,
    })


@router.get("/me/settings", response_model=UserSettingsRead, summary="Get current user settings")
async def read_my_settings(current_user: CurrentUser, db: DbSession) -> UserSettingsRead:
    row = await settings_service.get_settings(db, current_user.id)
    return UserSettingsRead.model_validate(row)


@router.patch(
    "/me/settings", response_model=UserSettingsRead, summary="Update current user settings"
)
async def update_my_settings(
    data: UserSettingsUpdate, current_user: CurrentUser, db: DbSession
) -> UserSettingsRead:
    try:
        row = await settings_service.update_settings(db, current_user.id, data)
    except UnsupportedCurrencyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported base currency: {exc.code}",
        ) from exc
    except FieldNotNullableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Field '{exc.field}' cannot be null",
        ) from exc
    return UserSettingsRead.model_validate(row)


@router.get("/me/profile", response_model=FinancialProfileRead, summary="Get the financial profile")
async def read_my_profile(current_user: CurrentUser, db: DbSession) -> FinancialProfileRead:
    row = await profile_service.get_profile(db, current_user.id)
    return FinancialProfileRead.model_validate(row)


@router.patch("/me/profile", response_model=FinancialProfileRead, summary="Update the financial profile")
async def update_my_profile(
    data: FinancialProfileUpdate, current_user: CurrentUser, db: DbSession
) -> FinancialProfileRead:
    row = await profile_service.update_profile(db, current_user.id, data)
    return FinancialProfileRead.model_validate(row)
