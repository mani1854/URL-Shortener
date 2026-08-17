"""
utils/client_info.py

Client request metadata extraction and User-Agent parsing utilities.
Extracts client IP, User-Agent, Referer, and parses device, browser, and OS.
"""

from __future__ import annotations

from typing import NamedTuple

from starlette.requests import Request

try:
    import user_agents
    HAS_USER_AGENTS = True
except ImportError:
    HAS_USER_AGENTS = False


class ParsedClientInfo(NamedTuple):
    ip_address: str | None
    user_agent: str | None
    referer: str | None
    device_type: str | None
    browser: str | None
    os: str | None


def extract_client_ip(request: Request) -> str | None:
    """
    Extract the client's public IP address, respecting reverse proxy headers.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take first IP in chain (client IP)
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return None


def parse_user_agent_details(user_agent_str: str | None) -> tuple[str | None, str | None, str | None]:
    """
    Parse (device_type, browser, os) from a User-Agent header string.
    """
    if not user_agent_str:
        return (None, None, None)

    if HAS_USER_AGENTS:
        try:
            ua = user_agents.parse(user_agent_str)
            if ua.is_bot:
                device_type = "bot"
            elif ua.is_mobile:
                device_type = "mobile"
            elif ua.is_tablet:
                device_type = "tablet"
            elif ua.is_pc:
                device_type = "desktop"
            else:
                device_type = "unknown"

            browser = f"{ua.browser.family} {ua.browser.version_string}".strip() or ua.browser.family
            os_name = f"{ua.os.family} {ua.os.version_string}".strip() or ua.os.family
            return (device_type, browser[:50] if browser else None, os_name[:50] if os_name else None)
        except Exception:
            pass

    # Fallback coarse parser if user-agents library is unavailable
    lower_ua = user_agent_str.lower()
    if any(b in lower_ua for b in ("bot", "crawler", "spider", "scraper")):
        device_type = "bot"
    elif "mobile" in lower_ua or "android" in lower_ua or "iphone" in lower_ua:
        device_type = "mobile"
    elif "ipad" in lower_ua or "tablet" in lower_ua:
        device_type = "tablet"
    else:
        device_type = "desktop"

    # Coarse browser detection
    if "edg" in lower_ua:
        browser = "Edge"
    elif "chrome" in lower_ua and "chromium" not in lower_ua:
        browser = "Chrome"
    elif "safari" in lower_ua and "chrome" not in lower_ua:
        browser = "Safari"
    elif "firefox" in lower_ua:
        browser = "Firefox"
    else:
        browser = "Other"

    # Coarse OS detection
    if "windows" in lower_ua:
        os_name = "Windows"
    elif "mac os" in lower_ua or "macintosh" in lower_ua:
        os_name = "macOS"
    elif "android" in lower_ua:
        os_name = "Android"
    elif "iphone" in lower_ua or "ios" in lower_ua:
        os_name = "iOS"
    elif "linux" in lower_ua:
        os_name = "Linux"
    else:
        os_name = "Other"

    return (device_type, browser, os_name)


def extract_client_info(request: Request) -> ParsedClientInfo:
    """
    Extract comprehensive client details from the incoming request.
    """
    ip_address = extract_client_ip(request)
    user_agent = request.headers.get("user-agent")
    referer = request.headers.get("referer")
    device_type, browser, os_name = parse_user_agent_details(user_agent)

    return ParsedClientInfo(
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer,
        device_type=device_type,
        browser=browser,
        os=os_name,
    )
