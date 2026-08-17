"""
models/__init__.py

Re-exports all ORM models so that:
  1. Application code has a single import surface.
  2. Alembic's env.py sees every model's metadata for autogenerate migrations.

ADD NEW MODELS HERE.
"""

from app.models.click_analytics import ClickAnalytics  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.url import URL  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = ["User", "RefreshToken", "URL", "ClickAnalytics"]
