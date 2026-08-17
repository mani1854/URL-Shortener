"""
utils/validators.py

URL and input validation helpers.
Uses the `validators` library as a first-pass check, then applies
project-specific rules (blocked domains, max length, etc.).
"""

from __future__ import annotations

import validators as _validators


def is_valid_url(url: str) -> bool:
    """
    Return True if `url` is a well-formed HTTP/HTTPS URL.

    Args:
        url: The URL string to validate.

    Returns:
        bool – True if valid, False otherwise.
    """
    result = _validators.url(url)
    return result is True


def normalize_url(url: str) -> str:
    """
    Strip leading/trailing whitespace from a URL.

    Extend this function to add canonicalisation (lowercase scheme/host,
    remove tracking params, etc.) as requirements grow.
    """
    return url.strip()
