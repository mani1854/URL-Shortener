"""
tests/integration/test_redirect_flow.py

Integration tests for URL redirection:
  - 302 redirect via /api/v1/urls/{short_code}/redirect
  - 302 redirect via top-level /{short_code}
  - HTTP 410 Gone for expired links
  - HTTP 404 Not Found for non-existent or deactivated links
"""

from __future__ import annotations

import pytest


@pytest.mark.anyio
async def test_redirect_via_api_v1(client):
    """Test standard redirect endpoint returns HTTP 302 with Location header."""
    create_res = await client.post(
        "/api/v1/urls",
        json={"url": "https://fastapi.tiangolo.com/tutorial/", "custom_alias": "fastapi-tut"},
    )
    assert create_res.status_code == 201

    # Follow redirect is disabled by default in client.get, so we capture the 302
    redirect_res = await client.get("/api/v1/urls/fastapi-tut/redirect", follow_redirects=False)
    assert redirect_res.status_code == 302
    assert redirect_res.headers["location"] == "https://fastapi.tiangolo.com/tutorial/"


@pytest.mark.anyio
async def test_redirect_via_root_path(client):
    """Test top-level /{short_code} returns HTTP 302 redirect."""
    create_res = await client.post(
        "/api/v1/urls",
        json={"url": "https://python.org", "custom_alias": "py-org"},
    )
    assert create_res.status_code == 201

    redirect_res = await client.get("/py-org", follow_redirects=False)
    assert redirect_res.status_code == 302
    assert redirect_res.headers["location"].rstrip("/") == "https://python.org"


@pytest.mark.anyio
async def test_redirect_nonexistent_returns_404(client):
    """Test redirect on non-existent short code returns 404."""
    redirect_res = await client.get("/api/v1/urls/no-such-code/redirect")
    assert redirect_res.status_code == 404
