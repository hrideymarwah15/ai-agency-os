"""Playwright-gated rendered analysis (D-33): probe, CWV observer, INP, overflow.

browser_available() is the CI skip gate — it lazily imports Playwright and
never raises. render_audit() runs one headless chromium page load and returns
the rendered-DOM signal envelope: lab CWV (LCP/CLS real; INP as event-timing
estimate with long-task proxy fallback per D-34), horizontal overflow at the
375px mobile viewport, body font size, and sampled tap-target sizes. Hostile
or unreachable URLs degrade to the envelope with an error note — never raise
(RESEARCH Pitfall: "the renderer degrades to static mode at runtime").
"""

import logging
from typing import Any

from backend.config import settings
from backend.services.discovery.sanitize import strip_control_tokens

logger = logging.getLogger(__name__)

# Injected before any page script runs so CWV observers capture the whole load.
# Must be an expression with side effects (Playwright evaluates the string);
# an arrow-function wrapper is silently dropped.
_CWV_OBSERVER_JS = """
window.__vitals = {lcp: 0, cls: 0, ttfb: 0, inp: 0, longtask: 0};
new PerformanceObserver((list) => {
  const entries = list.getEntries();
  window.__vitals.lcp = entries[entries.length - 1].startTime || 0;
}).observe({type: 'largest-contentful-paint', buffered: true});
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (!e.hadRecentInput) window.__vitals.cls += e.value;
  }
}).observe({type: 'layout-shift', buffered: true});
new PerformanceObserver((list) => {
  const nav = list.getEntries()[0];
  window.__vitals.ttfb = nav ? (nav.responseStart || 0) : 0;
}).observe({type: 'navigation', buffered: true});
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (e.duration > window.__vitals.inp) window.__vitals.inp = e.duration;
  }
}).observe({type: 'event', durationThreshold: 16, buffered: true});
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) {
    if (e.duration > window.__vitals.longtask) window.__vitals.longtask = e.duration;
  }
}).observe({type: 'longtask', buffered: true});
"""

_TAP_TARGETS_JS = """
() => {
  const els = [...document.querySelectorAll('a, button')].filter(
    (e) => e.offsetParent !== null
  ).slice(0, 5);
  if (!els.length) return null;
  const small = els.filter((e) => {
    const r = e.getBoundingClientRect();
    return r.width < 44 || r.height < 44;
  });
  return small.length > 0;
}
"""

_OVERFLOW_JS = """
() => document.documentElement.scrollWidth > document.documentElement.clientWidth
"""

_BODY_EMPTY_JS = """
() => (document.body.innerText || '').trim().length === 0
"""

_FONT_JS = """
() => {
  const s = getComputedStyle(document.body);
  const px = parseFloat(s.fontSize);
  return Number.isFinite(px) ? px : null;
}
"""


def browser_available() -> bool:
    """True when the Playwright chromium executable is launchable (CI skip gate)."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=settings.playwright_headless)
            browser.close()
        return True
    except Exception:  # noqa: BLE001 — probe must never raise (D-33)
        return False


async def render_audit(url: str, *, viewport_width: int = 375) -> dict[str, Any]:
    """Render url headlessly and return the rendered-DOM signal envelope.

    Always returns a dict (never raises): on browser failure or an unreachable
    target the envelope carries an "error" note and nulled metrics so the
    runner can degrade to static-only mode (D-34 honesty).
    """
    envelope: dict[str, Any] = {
        "lcp_ms": None,
        "cls": None,
        "inp_ms": None,
        "inp_source": None,
        "horizontal_overflow": None,
        "body_font_size_px": None,
        "small_tap_targets": None,
        "rendered_body_empty": None,
        "rendered_html": "",
        "error": "",
    }
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.playwright_headless)
            try:
                context = await browser.new_context(
                    viewport={"width": viewport_width, "height": 812}
                )
                page = await context.new_page()
                await page.add_init_script(_CWV_OBSERVER_JS)
                await page.goto(
                    url,
                    wait_until="load",
                    timeout=settings.audit_max_render_seconds * 1000,
                )
                await page.wait_for_timeout(2500)  # let LCP/CLS settle
                vitals = await page.evaluate("() => window.__vitals")
                envelope["lcp_ms"] = float(vitals["lcp"]) if vitals.get("lcp") else None
                envelope["cls"] = float(vitals["cls"])
                envelope["inp_ms"] = float(vitals["inp"]) if vitals.get("inp") else None
                if vitals.get("inp"):
                    envelope["inp_source"] = "event"
                elif vitals.get("longtask"):
                    envelope["inp_ms"] = float(vitals["longtask"])
                    envelope["inp_source"] = "longtask"
                envelope["horizontal_overflow"] = bool(await page.evaluate(_OVERFLOW_JS))
                envelope["body_font_size_px"] = await page.evaluate(_FONT_JS)
                envelope["small_tap_targets"] = await page.evaluate(_TAP_TARGETS_JS)
                envelope["rendered_body_empty"] = bool(await page.evaluate(_BODY_EMPTY_JS))
                html = await page.content()
                envelope["rendered_html"] = strip_control_tokens(html)[
                    : settings.audit_html_max_bytes
                ]
                return envelope
            finally:
                await browser.close()
    except Exception as exc:  # noqa: BLE001 — degrade, never raise (D-34)
        logger.warning("render_audit degraded for %s: %s", url, exc)
        envelope["error"] = f"{type(exc).__name__}: {exc}"
        return envelope
