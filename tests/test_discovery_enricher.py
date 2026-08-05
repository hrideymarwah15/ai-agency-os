"""Enricher tests — homepage contact extraction with SSRF-safe URL validation.

Rules (Pitfall 6): validate BEFORE any fetch (public http(s), port 80/443, no
userinfo); every redirect hop is re-validated; redirect cap ≤ 3; fill-if-missing
only (FR-062/D-26); never persist raw HTML (CMP-06 — extraction reads the
sanitized text, so script-embedded addresses are inert).
"""

import httpx
import pytest

from backend.database import Business
from backend.services.discovery.enricher import (
    enrich_homepage,
    extract_email,
    extract_form_url,
    extract_phone,
    validate_enrichment_url,
)
from backend.tools.http_client import build_compliant_client

HOMEPAGE_HTML = """<!doctype html>
<html>
<head><title>Acme Web Studio</title></head>
<body>
  <h1>Acme Web Studio</h1>
  <p>Reach us at <a href="mailto:hello@acme.example.com?subject=hi">hello@acme.example.com</a>
     or call +1 (415) 555-0132.</p>
  <form action="/contact" method="post"><input type="email" name="e"></form>
  <script>var leaked = "spam@script.example.com";</script>
</body>
</html>
"""


def _client(mock_transport, handler) -> None:
    return build_compliant_client(
        mock_transport(handler), api_hosts=frozenset({"acme.example.com"})
    )


def _page_handler(html: str, calls: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, text=html)

    return handler


def test_validate_enrichment_url_rejects_ssrf_targets() -> None:
    """Every listed internal/abuse target is rejected outright (Pitfall 6)."""
    for url in [
        "http://localhost",
        "http://localhost:5432",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5",
        "http://172.16.0.1",
        "http://192.168.1.10",
        "http://0.0.0.0",
        "http://[::1]/",
        "http://[fe80::1]/",
        "ftp://example.com",
        "file:///etc/passwd",
        "https://user:pass@example.com",
        "http://example.com:8080",
        "http://example.com:9999",
        None,
        "",
    ]:
        assert validate_enrichment_url(url) is None, url


def test_validate_enrichment_url_accepts_public_http() -> None:
    assert validate_enrichment_url("https://example.com") == "https://example.com"
    assert validate_enrichment_url("http://example.com") == "http://example.com"
    assert (
        validate_enrichment_url("https://example.com:443/contact")
        == "https://example.com:443/contact"
    )
    assert (
        validate_enrichment_url("http://sub.example.co.uk/page")
        == "http://sub.example.co.uk/page"
    )


def test_extract_email_prefers_mailto_and_ignores_script() -> None:
    text = "Reach us at hello@acme.example.com or call us."
    assert extract_email(HOMEPAGE_HTML, text) == "hello@acme.example.com"
    # Without a mailto, script-embedded addresses are NOT picked up from sanitized text.
    no_mailto = '<script>var x = "spam@script.example.com";</script><p>team@acme.example.com</p>'
    assert extract_email(no_mailto, "team@acme.example.com") == "team@acme.example.com"
    assert extract_email("<p>no address here</p>", "no address here") is None


def test_extract_phone_finds_formatted_number() -> None:
    assert extract_phone("call +1 (415) 555-0132 today") == "+1 (415) 555-0132"
    assert extract_phone("no phone") is None


def test_extract_form_url_resolves_relative_action() -> None:
    assert extract_form_url(HOMEPAGE_HTML, "https://acme.example.com") == (
        "https://acme.example.com/contact"
    )
    assert extract_form_url("<p>no form</p>", "https://acme.example.com") is None


async def test_enricher_extracts_contacts_and_fills_missing_fields(mock_transport) -> None:
    """email/phone/form_url extracted; only missing Business fields are filled."""
    calls: list[str] = []
    business = Business(name="Acme Web Studio", website_url="https://acme.example.com")
    result = await enrich_homepage(
        business,
        client=_client(mock_transport, _page_handler(HOMEPAGE_HTML, calls)),
        website=None,
    )

    assert result["success"] is True
    assert result["fields"]["email"] == "hello@acme.example.com"
    assert result["fields"]["phone"] == "+1 (415) 555-0132"
    assert result["fields"]["form_url"] == "https://acme.example.com/contact"
    assert business.email == "hello@acme.example.com"
    assert business.phone == "+1 (415) 555-0132"
    assert business.website_url == "https://acme.example.com"  # untouched
    assert calls == ["/"]


async def test_enricher_fill_if_missing_leaves_existing_values(mock_transport) -> None:
    """Existing email survives; the missing phone is filled (FR-062/D-26)."""
    calls: list[str] = []
    business = Business(
        name="Acme Web Studio",
        website_url="https://acme.example.com",
        email="owner@known.example.com",
    )
    result = await enrich_homepage(
        business,
        client=_client(mock_transport, _page_handler(HOMEPAGE_HTML, calls)),
        website=None,
    )

    assert result["success"] is True
    assert business.email == "owner@known.example.com"  # untouched
    assert business.phone == "+1 (415) 555-0132"  # filled
    assert "email" not in result["fields"]
    assert result["fields"]["phone"] == "+1 (415) 555-0132"


async def test_enricher_zero_requests_for_invalid_url(mock_transport) -> None:
    """SSRF guard: an invalid website URL is never fetched (handler asserts)."""
    calls: list[str] = []
    business = Business(name="Acme", website_url="http://169.254.169.254/latest/meta-data")
    result = await enrich_homepage(
        business,
        client=_client(mock_transport, _page_handler(HOMEPAGE_HTML, calls)),
        website=None,
    )

    assert result["success"] is False
    assert result["reason"] == "invalid_url"
    assert calls == []


async def test_enricher_redirect_cap_three(mock_transport) -> None:
    """At most 3 redirects are followed; a 4th hop is never requested."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "/hop1"})
        if request.url.path in ("/hop1", "/hop2", "/hop3"):
            return httpx.Response(
                301, headers={"location": "/hop" + str(int(request.url.path[-1]) + 1)}
            )
        return httpx.Response(200, text="final")

    business = Business(name="Acme", website_url="https://acme.example.com")
    result = await enrich_homepage(
        business, client=_client(mock_transport, handler), website=None
    )

    assert calls == ["/", "/hop1", "/hop2", "/hop3"]  # hop4 never fetched
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"


async def test_enricher_redirect_to_internal_host_rejected(mock_transport) -> None:
    """A redirect hop onto an internal host is re-validated and refused."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(301, headers={"location": "http://localhost:5432/evil"})

    business = Business(name="Acme", website_url="https://acme.example.com")
    result = await enrich_homepage(
        business, client=_client(mock_transport, handler), website=None
    )

    assert calls == ["/"]  # internal hop never fetched
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"
