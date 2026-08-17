"""
tests/unit/test_openapi.py

Unit tests verifying OpenAPI specification generation, tags, models, and documentation metadata.
"""

from __future__ import annotations

from app.core.application import create_application


def test_openapi_schema_generation():
    """Verify that custom OpenAPI schema is generated properly with tags and paths."""
    app = create_application()
    schema = app.openapi()

    assert schema is not None
    assert "openapi" in schema
    assert schema["info"]["title"] == app.title
    assert "paths" in schema
    assert "components" in schema

    # Verify Tags
    tag_names = {t["name"] for t in schema.get("tags", [])}
    expected_tags = {"Health", "Authentication", "URLs", "Analytics", "Dashboard"}
    assert expected_tags.issubset(tag_names)

    # Verify key API paths
    paths = schema["paths"]
    assert "/api/v1/auth/signup" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/urls" in paths
    assert "/api/v1/analytics/{short_code}" in paths
    assert "/api/v1/my-urls" in paths
    assert "/api/v1/my-urls/{short_code}" in paths


def test_openapi_components_and_examples():
    """Verify schemas and examples are present in OpenAPI components."""
    app = create_application()
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    assert "ErrorResponse" in schemas
    assert "ErrorDetail" in schemas
    assert "SignupRequest" in schemas
    assert "URLCreateRequest" in schemas
    assert "AnalyticsResponse" in schemas
    assert "UserURLItem" in schemas
