"""Canonical normalization (RESEARCH Pattern 3) — deterministic, no LLM (Anti-Pattern: no LLM in collection loop).

Canonical keys feed dedup (dedup_key_domain/email/phone/name) and the master
record. Best-effort transforms only: None-safe everywhere.
"""

import re
from typing import Any
from urllib.parse import urlparse

_LEGAL_SUFFIXES = ("llc", "inc", "ltd", "pvt", "private limited", "limited", "co", "corp", "gmbh")

_URL_RE = re.compile(r"https?://[^\s|<>]+")
_LOCATION_HINT = re.compile(
    r"\b(remote|onsite|on-site|hybrid|worldwide|anywhere|relocation|visa)\b", re.IGNORECASE
)


def normalize_domain(website: str | None) -> str | None:
    """Canonical domain: scheme-less, lowercase, www. and trailing dots stripped.

    NOTE: no public-suffix handling in MVP (RESEARCH Pitfall 2). Inputs with
    userinfo (e.g. mailto:user@host) or whitespace in the host are rejected.
    """
    if not website:
        return None
    parsed = urlparse(website if "://" in website else f"https://{website}")
    if parsed.username is not None or parsed.password is not None:
        return None
    host = parsed.hostname
    if not host:
        return None
    host = host.lower().removeprefix("www.").strip(".")
    if not host or any(char.isspace() for char in host):
        return None
    return host


def normalize_phone(phone: str | None) -> str | None:
    """Canonical phone: digits only (country-prefix normalization is a later refinement)."""
    digits = re.sub(r"\D", "", phone or "")
    return digits or None


def normalize_email(email: str | None) -> str | None:
    """Canonical email: stripped and lowercased."""
    return (email or "").strip().lower() or None


def normalize_name(name: str | None) -> str | None:
    """Canonical name: whitespace collapsed, punctuation to space, legal suffixes dropped."""
    if not name:
        return None
    s = " ".join(name.lower().split())
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    words = [word for word in s.split() if word not in _LEGAL_SUFFIXES]
    return " ".join(words) or None


def normalize_hn_job_post(text: str, item: dict[str, Any]) -> dict[str, Any]:
    """Deterministic name/website/industry/location heuristics for a hiring post.

    Handles both "Company | Role | Location | URL" and "Company | Location | URL"
    shapes: the website is the URL-bearing part (or an inline URL), the location
    is the part that looks like one (Remote/Onsite/Hybrid/city), falling back to
    the last non-URL part. No LLM involved.
    """
    first_line = (text.splitlines() or [text])[0]
    parts = [part.strip() for part in first_line.split("|") if part.strip()]
    website = next((part for part in parts if part.startswith(("http://", "https://"))), None)
    if website is None:
        match = _URL_RE.search(first_line)
        if match:
            website = match.group(0).rstrip(").,;")
    name = parts[0] if parts else ""
    if website:
        name = name.replace(website, "").strip(" ()-")
    location = next(
        (
            part
            for part in parts[1:]
            if not part.startswith("http") and part != name and _LOCATION_HINT.search(part)
        ),
        None,
    )
    if location is None:
        location = next(
            (part for part in reversed(parts[1:]) if not part.startswith("http") and part != name),
            None,
        )
    return {"name": name or None, "website": website, "location": location, "industry": None}
