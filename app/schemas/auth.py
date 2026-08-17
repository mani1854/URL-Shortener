"""
schemas/auth.py

Pydantic v2 schemas for authentication flows with OpenAPI examples.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Request schemas ────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    """Payload for registering a new user account."""

    email: EmailStr = Field(
        ...,
        description="A valid e-mail address.",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Minimum 8 characters with at least one letter and one number.",
        examples=["SecurePass123!"],
    )

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        has_letter = any(c.isalpha() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError("Password must contain at least one letter and one digit.")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "developer@example.com",
                "password": "StrongPassword2026!",
            }
        }
    }


class LoginRequest(BaseModel):
    """Payload for authenticating an existing user."""

    email: EmailStr = Field(..., description="Registered account e-mail address.", examples=["user@example.com"])
    password: str = Field(..., min_length=1, description="Account password.", examples=["SecurePass123!"])

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "developer@example.com",
                "password": "StrongPassword2026!",
            }
        }
    }


class RefreshRequest(BaseModel):
    """Payload for rotating and refreshing an expired access token."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Active refresh token string issued during login/signup.",
        examples=["dGhpcy1pcy1hLXZhbGlkLXJlZnJlc2gtdG9rZW4tc3RyaW5nLTQ4LWJ5dGVz"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "refresh_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4",
            }
        }
    }


# ── Response schemas ───────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Access and refresh token pair returned on authentication."""

    access_token: str = Field(description="Signed JWT bearer access token.")
    refresh_token: str = Field(description="Cryptographically secure refresh token for session renewal.")
    token_type: str = Field("bearer", description="Token authentication scheme.")
    expires_in: int = Field(description="Access token lifetime in seconds (e.g. 900s for 15 mins).")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4",
                "token_type": "bearer",
                "expires_in": 900,
            }
        }
    }


class AccessTokenResponse(BaseModel):
    """Refreshed access token response."""

    access_token: str = Field(description="Newly issued JWT bearer access token.")
    token_type: str = Field("bearer", description="Token authentication scheme.")
    expires_in: int = Field(description="Access token lifetime in seconds.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 900,
            }
        }
    }


class UserResponse(BaseModel):
    """Public user profile representation."""

    id: uuid.UUID = Field(description="Unique user UUID.")
    email: str = Field(description="User e-mail address.")
    is_active: bool = Field(description="Account active status.")
    is_superuser: bool = Field(description="Admin privileges flag.")
    created_at: datetime = Field(description="UTC timestamp of account creation.")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "e7b0a8c2-4b72-4b7b-83bb-1e4e3f43a512",
                "email": "developer@example.com",
                "is_active": True,
                "is_superuser": False,
                "created_at": "2026-08-17T12:00:00Z",
            }
        },
    }
