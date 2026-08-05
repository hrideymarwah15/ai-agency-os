"""Normalize tests — canonical deterministic transforms (RESEARCH Pattern 3, verbatim).

Pure functions, no DB: domain/phone/email/name canonicalization plus the
HN job-post heuristics (first-line split, URL extraction, location/industry
guessing) that Task 06 owns after moving them out of sources/hn.py.
"""

from backend.services.discovery.normalize import (
    normalize_domain,
    normalize_email,
    normalize_hn_job_post,
    normalize_name,
    normalize_phone,
)


def test_normalize_domain_strips_scheme_www_and_path() -> None:
    assert normalize_domain("https://www.Acme.com/") == "acme.com"
    assert normalize_domain("http://Acme.COM/about") == "acme.com"


def test_normalize_domain_scheme_less_input() -> None:
    assert normalize_domain("acme.com") == "acme.com"
    assert normalize_domain("www.acme.com") == "acme.com"


def test_normalize_domain_trailing_dots_stripped() -> None:
    assert normalize_domain("acme.com.") == "acme.com"


def test_normalize_domain_none_safe() -> None:
    assert normalize_domain(None) is None
    assert normalize_domain("") is None
    assert normalize_domain("not a url") is None
    assert normalize_domain("mailto:x@y.com") is None


def test_normalize_phone_digits_only_variants() -> None:
    assert normalize_phone("+91 98765 43210") == "919876543210"
    assert normalize_phone("+1 (415) 555-0132") == "14155550132"
    assert normalize_phone("415-555-0132") == "4155550132"
    assert normalize_phone("415.555.0132") == "4155550132"


def test_normalize_phone_none_safe() -> None:
    assert normalize_phone(None) is None
    assert normalize_phone("") is None


def test_normalize_email_lower_and_strip() -> None:
    assert normalize_email("  Alice@Example.COM ") == "alice@example.com"


def test_normalize_email_none_safe() -> None:
    assert normalize_email(None) is None
    assert normalize_email("   ") is None


def test_normalize_name_collapse_and_strip_suffixes() -> None:
    assert normalize_name("Acme Tech Pvt. Ltd.") == "acme tech"
    assert normalize_name("  Acme   Tech  ") == "acme tech"


def test_normalize_name_punctuation_to_space() -> None:
    assert normalize_name("Blue-Whale, Inc.") == "blue whale"
    assert normalize_name("Acme&Tech LLC") == "acme tech"


def test_normalize_name_none_safe() -> None:
    assert normalize_name(None) is None
    assert normalize_name("") is None
    assert normalize_name("Pvt. Ltd.") is None  # only suffixes left


def test_normalize_hn_job_post_four_part_line() -> None:
    """'Company | Role | Location | URL' — the canonical HN hiring-post shape."""
    normalized = normalize_hn_job_post(
        "Acme Corp | Senior Backend Engineer | Remote (US) | https://acme.example.com/careers",
        {},
    )
    assert normalized["name"] == "Acme Corp"
    assert normalized["website"] == "https://acme.example.com/careers"
    assert normalized["location"] == "Remote (US)"


def test_normalize_hn_job_post_three_part_line() -> None:
    """'Company | Location | URL' — the shape used by the T05 fixture corpus."""
    normalized = normalize_hn_job_post("Globex | Berlin | https://globex.example.com", {})
    assert normalized["name"] == "Globex"
    assert normalized["website"] == "https://globex.example.com"
    assert normalized["location"] == "Berlin"


def test_normalize_hn_job_post_url_in_name_part() -> None:
    """URL embedded in the first part is extracted and removed from the name."""
    normalized = normalize_hn_job_post("Acme (https://acme.example.com) | Remote | full-time", {})
    assert normalized["name"] == "Acme"
    assert normalized["website"] == "https://acme.example.com"
    assert normalized["location"] == "Remote"
