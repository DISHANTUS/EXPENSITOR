"""Authentication endpoints: register, login, refresh, logout."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import DbSession
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.user import UserRead
from app.services import auth_service
from app.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(data: RegisterRequest, db: DbSession) -> UserRead:
    try:
        user = await auth_service.register_user(
            db, email=data.email, password=data.password, full_name=data.full_name
        )
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Log in and obtain tokens")
async def login(data: LoginRequest, db: DbSession) -> TokenResponse:
    try:
        user = await auth_service.authenticate_user(db, data.email, data.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    access, refresh, expires_in = await auth_service.issue_token_pair(db, user)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token")
async def refresh(data: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        access, refresh_token, expires_in = await auth_service.rotate_refresh_token(
            db, data.refresh_token
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc
    return TokenResponse(access_token=access, refresh_token=refresh_token, expires_in=expires_in)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a refresh token (logout)",
)
async def logout(data: LogoutRequest, db: DbSession) -> Response:
    await auth_service.revoke_refresh_token(db, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
