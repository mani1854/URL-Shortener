"""
tests/unit/test_shortcode.py

Unit tests for Base62 encoding, decoding, random code generation, and alias validation.
"""

from __future__ import annotations

import pytest

from app.utils.shortcode import (
    decode_base62,
    encode_base62,
    generate_base62_code,
    generate_short_code,
    is_valid_custom_alias,
)


class TestBase62Encoding:
    def test_encode_zero(self):
        assert encode_base62(0) == "0"

    def test_encode_decode_roundtrip(self):
        numbers = [0, 1, 61, 62, 125, 3844, 999999, 123456789012]
        for num in numbers:
            encoded = encode_base62(num)
            decoded = decode_base62(encoded)
            assert decoded == num

    def test_encode_negative_raises(self):
        with pytest.raises(ValueError):
            encode_base62(-5)

    def test_decode_invalid_chars_raises(self):
        with pytest.raises(ValueError):
            decode_base62("abc@123")


class TestGenerateShortCode:
    def test_default_length(self):
        code = generate_short_code()
        assert len(code) == 7

    def test_custom_length(self):
        for length in (4, 8, 12, 20):
            code = generate_base62_code(length=length)
            assert len(code) == length

    def test_url_safe_characters(self):
        """Generated codes must be alphanumeric (Base62)."""
        for _ in range(50):
            code = generate_short_code()
            assert code.isalnum(), f"Non-alphanumeric character in: {code}"

    def test_uniqueness(self):
        """Codes should be statistically unique."""
        codes = {generate_short_code() for _ in range(1000)}
        assert len(codes) == 1000


class TestIsValidCustomAlias:
    @pytest.mark.parametrize(
        "alias",
        [
            "hello",
            "my-link",
            "cool_url",
            "abc123",
            "A1b2-C3_d4",
            "custom-slug-2026",
        ],
    )
    def test_valid_aliases(self, alias: str):
        assert is_valid_custom_alias(alias) is True

    @pytest.mark.parametrize(
        "alias",
        [
            "ab",           # too short (< 4)
            "hi",           # too short
            "has space",    # invalid space
            "has@symbol",   # invalid char
            "has$money",    # invalid char
            "a" * 51,       # too long (> 50)
            "health",       # reserved keyword
            "docs",         # reserved keyword
            "auth",         # reserved keyword
            "analytics",    # reserved keyword
            "shorten",      # reserved keyword
        ],
    )
    def test_invalid_aliases(self, alias: str):
        assert is_valid_custom_alias(alias) is False
