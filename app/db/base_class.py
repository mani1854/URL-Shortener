"""
db/base_class.py

Convenience re-export so that application code can always import from
`app.db.base_class` without worrying about internal restructuring.
"""

from app.db.base import Base  # noqa: F401 – re-export
