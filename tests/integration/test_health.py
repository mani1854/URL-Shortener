"""
tests/integration/test_health.py

Integration tests for the /health endpoint.
These tests use the async test client from conftest.py.
"""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_health_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert "version" in body
    assert "environment" in body
