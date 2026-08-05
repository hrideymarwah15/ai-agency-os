"""Enrichment — SSRF-safe homepage scan filling only missing contact fields.

URL validation happens BEFORE any fetch (Pitfall 6): scheme {http, https},
public IP only (ipaddress rejects loopback/private/link-local/ULA), ports
80/443 only, no userinfo; every redirect hop is re-validated and capped at
_MAX_REDIRECTS. Content is sanitized via strip_html_to_text (CMP-06) — raw
HTML is never persisted and script-embedded addresses stay inert.
"""

import ipaddress
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from backend.database import Business
from backend.services.discovery.sanitize import strip_html_to_text
from backend.tools.http_client import CompliantHTTPClient, RobotsDeniedError

_MAX_REDIRECTS = 3

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{5,}\d")
_FORM_ACTION_RE = re.compile(r'<form\b[^>]*\baction=["\']([^"\']+)["\']', re.IGNORECASE)
_MAILTO_RE = re.compile(r'mailto:([^"\'<>\s]+)', re.IGNORECASE)


def validate_enrichment_url(url: str | None) -> str | None:
    """Return url iff fetch-safe (public http(s), port 80/443, no userinfo); else None."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    hostname = parsed.hostname
    if not hostname or parsed.username is not None or parsed.password is not None:
        return None
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return None
    try:
        if parsed.port not in (None, 80, 443):
            return None
    except ValueError:
        return None  # malformed port
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return url  # hostname, not an IP literal
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return None
    return url


def extract_email(raw_html: str, text: str) -> str | None:
    """First email: prefer a mailto: href target (raw), else any address in sanitized text."""
    mailto = _MAILTO_RE.search(raw_html)
    if mailto:
        candidate = mailto.group(1).split("?")[0]
        if "@" in candidate:
            return candidate
    match = _EMAIL_RE.search(text)
    return match.group(0) if match else None


def extract_phone(text: str) -> str | None:
    """First phone-like string (>= 7 digits) in sanitized text."""
    for match in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) >= 7:
            return match.group(0).strip()
    return None


def extract_form_url(html: str, base_url: str) -> str | None:
    """First <form action> resolved against base_url; None when absent or inert."""
    match = _FORM_ACTION_RE.search(html)
    if not match:
        return None
    action: str = match.group(1)  # regex group is Any; pin to str for urljoin typing
    if action.startswith(("#", "javascript:")):
        return None
    return urljoin(base_url, action)


async def _fetch_homepage(client: CompliantHTTPClient, url: str) -> httpx.Response | None:
    """Fetch url following at most _MAX_REDIRECTS hops; every hop is re-validated."""
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        target = validate_enrichment_url(current)
        if target is None:
            return None
        try:
            response = await client.fetch(target)
        except httpx.HTTPStatusError as exc:
            # The compliant door raises on 3xx; peel the response off for redirect hops.
            if not (exc.response.is_redirect and exc.response.headers.get("location")):
                return None
            response = exc.response
        except (httpx.HTTPError, RobotsDeniedError):
            return None
        location = response.headers.get("location")
        if response.is_redirect and location:
            current = str(response.url.join(location))
            continue
        return response
    return None


async def enrich_homepage(
    business: Business,
    *,
    client: CompliantHTTPClient,
    website: str | None = None,
) -> dict[str, Any]:
    """Fetch the homepage and fill ONLY missing contact fields (FR-062/D-26).

    Returns {"success": True, "fields": {"email", "phone", "form_url"}} with the
    Business mutated in place, or {"success": False, "reason": ..., "fields": {}}.
    """
    if not business.website_url and website:
        business.website_url = website
    target = validate_enrichment_url(business.website_url)
    if target is None:
        return {"success": False, "reason": "invalid_url", "fields": {}}
    response = await _fetch_homepage(client, target)
    if response is None:
        return {"success": False, "reason": "fetch_failed", "fields": {}}
    raw_html = response.text
    text = strip_html_to_text(raw_html)  # CMP-06: extraction reads inert text
    fields: dict[str, Any] = {}
    if not business.email:
        email = extract_email(raw_html, text)
        if email:
            business.email = email
            fields["email"] = email
    if not business.phone:
        phone = extract_phone(text)
        if phone:
            business.phone = phone
            fields["phone"] = phone
    form_url = extract_form_url(raw_html, target)
    if form_url:
        fields["form_url"] = form_url
    return {"success": True, "fields": fields}
