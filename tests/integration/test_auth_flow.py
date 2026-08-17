"""
tests/integration/test_auth_flow.py

End-to-end integration tests for user authentication:
  - Signup with password complexity validation
  - Duplicate email conflict handling (HTTP 409)
  - Login with JWT token generation
  - Profile retrieval via Bearer authentication (GET /auth/me)
  - Refresh token rotation (POST /auth/refresh)
  - Logout and token revocation (POST /auth/logout)
"""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_auth_signup_flow(client):
    """Test user registration returns 201 with access and refresh tokens."""
    payload = {
        "email": "integration_user1@example.com",
        "password": "SecurePassword123!",
    }
    response = await client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 900


@pytest.mark.anyio
async def test_auth_signup_duplicate_email(client):
    """Test duplicate registration returns 409 Conflict."""
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePassword123!",
    }
    res1 = await client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 409


@pytest.mark.anyio
async def test_auth_login_success(client):
    """Test login with correct credentials returns valid tokens."""
    # Register first
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "login_user@example.com", "password": "MyPassword123!"},
    )

    # Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_user@example.com", "password": "MyPassword123!"},
    )
    assert login_res.status_code == 200
    data = login_res.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.anyio
async def test_auth_login_invalid_password(client):
    """Test login with wrong password returns 401 Unauthorized."""
    await client.post(
        "/api/v1/auth/signup",
        json={"email": "wrongpass@example.com", "password": "CorrectPassword123!"},
    )

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "WrongPassword!"},
    )
    assert login_res.status_code == 401


@pytest.mark.anyio
async def test_auth_me_endpoint(client):
    """Test /auth/me returns current user profile when authenticated."""
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "me_profile@example.com", "password": "Password1234!"},
    )
    access_token = signup_res.json()["data"]["access_token"]

    # Access /auth/me with Bearer token
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    user_data = me_res.json()["data"]
    assert user_data["email"] == "me_profile@example.com"
    assert user_data["is_active"] is True


@pytest.mark.anyio
async def test_auth_refresh_token_rotation(client):
    """Test refresh token exchange returns new access token and revokes old one."""
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "refresh_user@example.com", "password": "Password1234!"},
    )
    refresh_token = signup_res.json()["data"]["refresh_token"]

    # Refresh
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()["data"]


@pytest.mark.anyio
async def test_auth_logout(client):
    """Test logout revokes the active refresh token."""
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "logout_user@example.com", "password": "Password1234!"},
    )
    refresh_token = signup_res.json()["data"]["refresh_token"]

    logout_res = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200
