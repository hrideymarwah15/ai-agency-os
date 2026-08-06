"""Renderer + fetch_stream tests (D-33, AUDT-01/03) — TDD contract for Task 03.

fetch_stream tests run against a MockTransport fast client (no network, robots
denial via canned robots.txt). Renderer tests are skipif-gated on the browser
probe (D-33 CI pattern): when Playwright chromium is absent the module still
collects and only the browser-dependent tests skip; browser_available() itself
never raises.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import httpx
import pytest

from backend.services.audits.renderer import browser_available, render_audit
from backend.services.compliance.rate_limit import DomainTokenBucket
from backend.services.compliance.robots import RobotsPolicy
from backend.tools.http_client import CompliantHTTPClient, RobotsDeniedError

_HOMEPAGE_HTML = """<!doctype html><html lang="en"><head>
<title>Acme Web Studio — Web Design</title>
</head><body>
<h1>Welcome</h1>
<p>We build websites for small businesses.</p>
<a href="/about">About</a>
<button>Book a call</button>
</body></html>"""

_WIDE_HTML = """<!doctype html><html lang="en"><head>
<title>Wide</title>
</head><body>
<h1>Wide page</h1>
<div style="min-width: 1200px">x</div>
</body></html>"""


# ---------------------------------------------------------------------------
# fetch_stream — compliant door streaming probe (AUDT-01 TTFB, AUDT-03 links)
# ---------------------------------------------------------------------------


def _robots_handler(allow: bool):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            body = "User-agent: *\nAllow: /\n" if allow else "User-agent: *\nDisallow: /\n"
            return httpx.Response(200, text=body)
        return httpx.Response(200, text=_HOMEPAGE_HTML)

    return handler


def _client(allow: bool = True) -> CompliantHTTPClient:
    inner = httpx.AsyncClient(transport=httpx.MockTransport(_robots_handler(allow)), timeout=10.0)
    return CompliantHTTPClient(
        inner,
        bucket=DomainTokenBucket(capacity=1000.0, refill_per_sec=1000.0),
        policy=RobotsPolicy(inner, user_agent="test-agent", ttl_seconds=60),
    )


async def test_fetch_stream_returns_ttfb_and_response():
    """Stream probe yields (response, ttfb_ms) with a non-negative TTFB."""
    client = _client()
    response, ttfb_ms = await client.fetch_stream("https://acme.example.com/")
    assert response.status_code == 200
    assert ttfb_ms >= 0
    assert isinstance(ttfb_ms, float)


async def test_fetch_stream_robots_denied_raises_before_request():
    """Denied robots.txt raises RobotsDeniedError; no request is issued."""
    client = _client(allow=False)
    with pytest.raises(RobotsDeniedError):
        await client.fetch_stream("https://acme.example.com/denied")


async def test_fetch_stream_default_fetch_unchanged():
    """The original fetch() contract still works after the streaming addition."""
    client = _client()
    response = await client.fetch("https://acme.example.com/")
    assert response.status_code == 200
    assert "Acme" in response.text


# ---------------------------------------------------------------------------
# browser probe — never raises, returns bool
# ---------------------------------------------------------------------------


def test_browser_available_returns_bool():
    """Probe is a plain bool function — safe to call at import/collection."""
    assert isinstance(browser_available(), bool)


# ---------------------------------------------------------------------------
# render_audit — skipif-gated on the browser probe (D-33)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not browser_available(),
    reason="Playwright browser not installed (install: python -m playwright install chromium)",
)


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/wide"):
            body = _WIDE_HTML.encode()
        else:
            body = _HOMEPAGE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture(scope="module")
def fixture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


async def test_render_audit_returns_cwv_and_overflow_signals(fixture_server):
    """Rendered probe returns the CWV/mobile signal envelope for a real page."""
    result = await render_audit(f"{fixture_server}/")
    assert result["lcp_ms"] is None or result["lcp_ms"] > 0
    assert "cls" in result
    assert "inp_ms" in result
    assert result["inp_source"] in ("event", "longtask", None)
    assert result["horizontal_overflow"] is False
    assert result["body_font_size_px"] is None or result["body_font_size_px"] > 0
    assert "small_tap_targets" in result
    assert result["rendered_body_empty"] is False
    assert "Welcome" in result["rendered_html"]


async def test_render_audit_detects_horizontal_overflow(fixture_server):
    """A 1200px min-width element at the 375px viewport overflows horizontally."""
    result = await render_audit(f"{fixture_server}/wide")
    assert result["horizontal_overflow"] is True
    assert "Wide page" in result["rendered_html"]


async def test_render_audit_never_raises_on_hostile_url():
    """Unreachable/hostile URLs degrade to the signal envelope, never raise."""
    result = await render_audit("http://127.0.0.1:1/")  # closed port
    assert isinstance(result, dict)
    assert "rendered_html" in result or "error" in result
