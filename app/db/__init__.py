"""
db/__init__.py

Imports Base and every ORM model so that Alembic's autogenerate can
detect all table definitions via Base.metadata.

ADD NEW MODEL IMPORTS HERE alongside the existing ones.
"""

from app.db.base import Base  # noqa: F401 – must come first

# Register all models with Base.metadata
from app.models.click_analytics import ClickAnalytics  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.url import URL  # noqa: F401
from app.models.user import User  # noqa: F401
