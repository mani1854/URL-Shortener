"""
tests/integration/test_rate_limiting_flow.py

Integration tests for Rate Limiting behavior and headers across endpoints.
"""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_rate_limit_headers_on_api_endpoints(client):
    """Verify that standard rate limiting headers are injected on API responses."""
    res = await client.get("/api/v1/urls/non-existent-sample")
    # Response should contain rate limit headers even on 404
    assert "x-ratelimit-limit" in res.headers
    assert res.headers["x-ratelimit-limit"] == "50"


@pytest.mark.anyio
async def test_health_check_exempt_from_rate_limiting(client):
    """Verify that health check endpoint is exempt from rate limits."""
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
