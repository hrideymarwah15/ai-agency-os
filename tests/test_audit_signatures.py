"""Signature detection tests (D-38, AUDT-02) — marker → verdict + confidence.

Deterministic first-match-wins for CMS/hosting, set-union for stack/analytics;
multiple markers for one name vote confidence up. Zero network: fixture HTML,
header and cookie dicts only.
"""

from backend.services.audits.signatures import match_signatures

_WORDPRESS_HTML = """<html><head>
<meta name="generator" content="WordPress 6.4" />
<link rel="stylesheet" href="https://cdn.example.com/wp-content/themes/x/style.css" />
<script src="https://cdn.example.com/wp-includes/js/jquery.min.js"></script>
</head><body><h1>Hello</h1></body></html>"""


def test_wordpress_detected_from_generator_and_assets():
    """wp-content + generator meta → wordpress CMS with high-confidence."""
    result = match_signatures(_WORDPRESS_HTML, {}, {})
    assert result["cms"]["name"] == "wordpress"
    assert result["cms"]["confidence"] >= 0.9
    assert "jquery" in [item["name"] for item in result["tech_stack"]]


def test_shopify_detected_from_cdn_script():
    """cdn.shopify.com script src pins Shopify as the CMS."""
    html = '<script src="https://cdn.shopify.com/s/files/1/1234/t/5/main.js"></script>'
    result = match_signatures(html, {}, {})
    assert result["cms"]["name"] == "shopify"
    assert result["cms"]["confidence"] >= 0.85


def test_cloudflare_hosting_from_cf_ray_header():
    """cf-ray response header → Cloudflare hosting at HIGH confidence."""
    result = match_signatures("<html></html>", {"cf-ray": "abc123-CPH"}, {})
    assert result["hosting"]["name"] == "cloudflare"
    assert result["hosting"]["confidence"] >= 0.9


def test_react_detected_from_marker():
    """data-reactroot marker → react framework in the tech stack."""
    html = '<div id="root" data-reactroot=""><span>hi</span></div>'
    result = match_signatures(html, {}, {})
    assert "react" in [item["name"] for item in result["tech_stack"]]
    react = next(item for item in result["tech_stack"] if item["name"] == "react")
    assert react["category"] == "framework"


def test_ga4_analytics_detected_from_gtag_marker():
    """gtag('js' marker → GA4 in analytics."""
    html = "<script>gtag('js', new Date());</script>"
    result = match_signatures(html, {}, {})
    assert "ga4" in [item["name"] for item in result["analytics"]]


def test_django_backend_from_cookie():
    """django cookie → Django backend in the stack."""
    result = match_signatures("<html></html>", {}, {"django": "1.0"})
    assert "django" in [item["name"] for item in result["tech_stack"]]
    django = next(item for item in result["tech_stack"] if item["name"] == "django")
    assert django["category"] == "backend"


def test_no_signatures_yields_empty_detection():
    """Bare page → None cms/hosting, empty stack/analytics lists."""
    result = match_signatures("<html><body></body></html>", {}, {})
    assert result["cms"] is None
    assert result["hosting"] is None
    assert result["tech_stack"] == []
    assert result["analytics"] == []


def test_confidence_votes_up_on_multiple_matches():
    """More than one marker for a name raises its confidence above the base."""
    html = (
        '<script src="https://www.googletagmanager.com/gtag/js?id=G-ABC123"></script>'
        "<script>gtag('js', new Date());</script>"
    )
    result = match_signatures(html, {}, {})
    ga4 = next(item for item in result["analytics"] if item["name"] == "ga4")
    assert ga4["confidence"] > 0.9
    assert ga4["confidence"] <= 0.99


def test_first_match_wins_for_cms_category():
    """Two CMSs present → the earliest table row owns the CMS slot (RESEARCH 4)."""
    html = (
        '<script src="https://cdn.shopify.com/x.js"></script>'
        '<meta name="generator" content="WordPress 6.4" />'
    )
    result = match_signatures(html, {}, {})
    assert result["cms"]["name"] == "wordpress"  # wordpress row precedes shopify in the table


def test_hostile_input_never_raises():
    """Malformed/control-heavy HTML never raises (CMP-06 posture)."""
    result = match_signatures("\x00\x01\x02<unclosed" * 50, {}, {})
    assert result is not None
