"""
utils/shortcode.py

Base62 short code generation and alias validation utilities.

Base62 uses [0-9a-zA-Z] (62 alphanumeric characters), providing:
  - 62^7 = ~3.52 trillion unique combinations for 7-character codes.
  - Safe, URL-friendly strings without requiring URL escaping.
"""

from __future__ import annotations

import re
import secrets

from app.core.config import settings

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE62_BASE = len(BASE62_ALPHABET)
_CUSTOM_ALIAS_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def encode_base62(num: int) -> str:
    """
    Encode an integer into a Base62 string.

    Args:
        num: Non-negative integer.

    Returns:
        Base62 encoded string.
    """
    if num < 0:
        raise ValueError("Number must be non-negative for Base62 encoding.")
    if num == 0:
        return BASE62_ALPHABET[0]

    digits: list[str] = []
    while num > 0:
        num, remainder = divmod(num, BASE62_BASE)
        digits.append(BASE62_ALPHABET[remainder])

    return "".join(reversed(digits))


def decode_base62(code: str) -> int:
    """
    Decode a Base62 string back into an integer.

    Args:
        code: Base62 encoded string.

    Returns:
        Decoded integer value.
    """
    num = 0
    for char in code:
        idx = BASE62_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid character '{char}' in Base62 code.")
        num = num * BASE62_BASE + idx
    return num


def generate_base62_code(length: int | None = None) -> str:
    """
    Generate a cryptographically random Base62 short code of specified length.

    Args:
        length: Code character length. Defaults to settings.SHORT_CODE_LENGTH (7).

    Returns:
        A random Base62 string.
    """
    code_length = length or settings.SHORT_CODE_LENGTH
    return "".join(secrets.choice(BASE62_ALPHABET) for _ in range(code_length))


def generate_short_code(length: int | None = None) -> str:
    """
    Convenience alias for generate_base62_code.
    """
    return generate_base62_code(length)


def is_valid_custom_alias(alias: str) -> bool:
    """
    Validate if a custom alias satisfies length and character constraints.

    Rules:
      - Length between 4 and settings.MAX_CUSTOM_ALIAS_LENGTH (default 50).
      - Contains only alphanumeric characters, hyphens, and underscores.
      - Disallows reserved endpoint keywords (e.g., 'health', 'docs', 'auth', 'analytics').
    """
    if not (4 <= len(alias) <= settings.MAX_CUSTOM_ALIAS_LENGTH):
        return False

    if not _CUSTOM_ALIAS_REGEX.match(alias):
        return False

    reserved_keywords = {
        "health",
        "docs",
        "redoc",
        "openapi",
        "auth",
        "api",
        "analytics",
        "shorten",
        "my-urls",
        "dashboard",
        "metrics",
        "admin",
    }
    return alias.lower() not in reserved_keywords
