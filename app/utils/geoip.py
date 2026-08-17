"""
utils/geoip.py

Asynchronous GeoIP lookup utility.
Resolves public IP addresses to country codes and city names with strict timeouts
and in-memory caching to minimize external HTTP overhead.
"""

from __future__ import annotations

import ipaddress
import logging

import httpx

logger = logging.getLogger(__name__)

# Local in-memory LRU-like cache for IP -> (country, city) lookups
_GEOIP_CACHE: dict[str, tuple[str | None, str | None]] = {}
_MAX_GEOIP_CACHE_ENTRIES = 10000


def is_private_or_reserved_ip(ip_str: str) -> bool:
    """Check if an IP is loopback, private, multicast, or reserved."""
    try:
        ip_obj = ipaddress.ip_address(ip_str.strip())
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_multicast
    except ValueError:
        return True


async def lookup_ip_geolocation(ip_address: str | None) -> tuple[str | None, str | None]:
    """
    Look up country code (ISO 3166-1 alpha-2) and city for a given IP address.

    Returns:
        Tuple of (country_code, city_name), e.g. ("US", "San Francisco") or (None, None).
    """
    if not ip_address:
        return (None, None)

    cleaned_ip = ip_address.strip()
    if is_private_or_reserved_ip(cleaned_ip):
        return (None, None)

    # Check local cache
    if cleaned_ip in _GEOIP_CACHE:
        return _GEOIP_CACHE[cleaned_ip]

    country: str | None = None
    city: str | None = None

    try:
        # Use ip-api.com free tier endpoint with strict 1.2s timeout
        async with httpx.AsyncClient(timeout=1.2) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{cleaned_ip}?fields=status,countryCode,city"
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    country = data.get("countryCode")
                    city = data.get("city")
    except Exception as exc:
        logger.debug("GeoIP lookup failed for IP %s: %s", cleaned_ip, exc)

    # Store in memory cache (evict old entries if too large)
    if len(_GEOIP_CACHE) >= _MAX_GEOIP_CACHE_ENTRIES:
        _GEOIP_CACHE.clear()
    _GEOIP_CACHE[cleaned_ip] = (country, city)

    return (country, city)
