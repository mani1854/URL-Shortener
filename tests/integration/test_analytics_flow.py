"""
tests/integration/test_analytics_flow.py

Integration tests for URL analytics endpoint:
  - Analytics response data structure
  - Verification of metrics and breakdown fields
  - 404 on missing code
"""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_get_url_analytics_endpoint(client):
    """Test retrieving analytics metrics for a created short code."""
    create_res = await client.post(
        "/api/v1/urls",
        json={"url": "https://fastapi.tiangolo.com", "custom_alias": "analytics-link"},
    )
    assert create_res.status_code == 201

    analytics_res = await client.get("/api/v1/analytics/analytics-link")
    assert analytics_res.status_code == 200

    data = analytics_res.json()["data"]
    assert data["short_code"] == "analytics-link"
    assert data["total_clicks"] == 0
    assert isinstance(data["daily_clicks"], list)
    assert isinstance(data["country_distribution"], list)
    assert isinstance(data["browser_distribution"], list)
    assert isinstance(data["device_distribution"], list)


@pytest.mark.anyio
async def test_get_analytics_nonexistent_returns_404(client):
    """Test retrieving analytics for a missing code returns 404."""
    res = await client.get("/api/v1/analytics/missing-alias-xyz")
    assert res.status_code == 404
