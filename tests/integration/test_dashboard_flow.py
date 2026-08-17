"""
tests/integration/test_dashboard_flow.py

Integration tests for User Dashboard operations:
  - GET /my-urls paginated listing scoped to authenticated user
  - PATCH /my-urls/{short_code} expiry updates
  - DELETE /my-urls/{short_code} soft-deletion
  - 401 Unauthorized for unauthenticated requests
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.anyio
async def test_dashboard_unauthenticated_returns_401(client):
    """Accessing /my-urls without a valid Bearer token returns 401."""
    res = await client.get("/api/v1/my-urls")
    assert res.status_code == 401


@pytest.mark.anyio
async def test_dashboard_crud_flow(client):
    """Test user can list their URLs, update expiry, and delete their links."""
    # 1. Signup & obtain token
    signup_res = await client.post(
        "/api/v1/auth/signup",
        json={"email": "dash_user@example.com", "password": "SecurePassword123!"},
    )
    assert signup_res.status_code == 201
    token = signup_res.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create 2 short URLs while authenticated
    res1 = await client.post(
        "/api/v1/urls",
        json={"url": "https://fastapi.tiangolo.com", "custom_alias": "dash-fastapi"},
        headers=headers,
    )
    assert res1.status_code == 201

    res2 = await client.post(
        "/api/v1/urls",
        json={"url": "https://python.org", "custom_alias": "dash-python"},
        headers=headers,
    )
    assert res2.status_code == 201

    # 3. List URLs on dashboard
    list_res = await client.get("/api/v1/my-urls", headers=headers)
    assert list_res.status_code == 200
    page_data = list_res.json()["data"]
    assert page_data["total"] == 2
    assert len(page_data["items"]) == 2

    # 4. Update expiry on one link
    future_time = (datetime.now(UTC) + timedelta(days=60)).isoformat()
    patch_res = await client.patch(
        "/api/v1/my-urls/dash-fastapi",
        json={"expiry": future_time},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["expiry"] is not None

    # 5. Delete one link
    del_res = await client.delete("/api/v1/my-urls/dash-python", headers=headers)
    assert del_res.status_code == 204

    # 6. Verify dashboard now lists only 1 active link
    updated_list_res = await client.get("/api/v1/my-urls", headers=headers)
    assert updated_list_res.status_code == 200
    assert updated_list_res.json()["data"]["total"] == 1
    assert updated_list_res.json()["data"]["items"][0]["short_code"] == "dash-fastapi"
