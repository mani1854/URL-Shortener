"""
api/v1/endpoints/auth.py

Authentication REST endpoints.
Handles registration, login, token rotation, logout, and profile queries.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_active_user
from app.dependencies.db import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.common import APIResponse, ErrorResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── POST /auth/signup ─────────────────────────────────────────────────────────

@router.post(
    "/signup",
    response_model=APIResponse[TokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
    description="Register a new user account with email and password. Returns an initial JWT access token and refresh token.",
    responses={
        201: {"description": "Account created successfully."},
        400: {"model": ErrorResponse, "description": "Password does not meet complexity requirements."},
        409: {"model": ErrorResponse, "description": "An account with this email address already exists."},
        422: {"model": ErrorResponse, "description": "Validation error in request body."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def signup(
    payload: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TokenResponse]:
    tokens = await auth_service.signup(
        db, email=payload.email, password=payload.password
    )
    return APIResponse(data=tokens, message="Account created successfully.")


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=APIResponse[TokenResponse],
    summary="Log in to account",
    description="Authenticate with email and password to receive a JWT access token and secure refresh token.",
    responses={
        200: {"description": "Login successful."},
        401: {"model": ErrorResponse, "description": "Invalid email or password."},
        422: {"model": ErrorResponse, "description": "Validation error."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TokenResponse]:
    user_agent = request.headers.get("user-agent")
    tokens = await auth_service.login(
        db,
        email=payload.email,
        password=payload.password,
        user_agent=user_agent,
    )
    return APIResponse(data=tokens, message="Login successful.")


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=APIResponse[AccessTokenResponse],
    summary="Refresh access token",
    description="Exchange a valid, non-expired refresh token for a newly issued access token.",
    responses={
        200: {"description": "Access token refreshed successfully."},
        401: {"model": ErrorResponse, "description": "Refresh token is expired, revoked, or invalid."},
        422: {"model": ErrorResponse, "description": "Validation error."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[AccessTokenResponse]:
    token_data = await auth_service.refresh_access_token(
        db, raw_refresh_token=payload.refresh_token
    )
    return APIResponse(data=token_data, message="Access token refreshed.")


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=APIResponse[None],
    summary="Log out of session",
    description="Revoke the provided refresh token, invalidating future session renewals.",
    responses={
        200: {"description": "Logged out successfully."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def logout(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[None]:
    await auth_service.logout(db, raw_refresh_token=payload.refresh_token)
    return APIResponse(message="Logged out successfully.")


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=APIResponse[UserResponse],
    summary="Get current user profile",
    description="Return the authenticated user profile using Bearer JWT authentication.",
    responses={
        200: {"description": "User profile returned."},
        401: {"model": ErrorResponse, "description": "Missing or invalid Bearer access token."},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded."},
    },
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> APIResponse[UserResponse]:
    return APIResponse(data=UserResponse.model_validate(current_user))
