"""Audit scoring rubrics (AUDT-01, D-36) — deterministic max(0, 100 − deductions).

Mirrors RESEARCH §Pattern 3: only measured signals deduct; absent signals are
never guessed. Each pass takes a flat signal dict (from the static analyzer or
the rendered probe) and returns an int 0-100. build_cwv_report() assembles the
CWV storage shape with D-34 methodology labels.
"""

from typing import Any


def _score(deductions: int) -> int:
    return max(0, 100 - deductions)


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def score_performance(signals: dict[str, Any]) -> int:
    """Performance rubric over measured signals only."""
    d = 0
    ttfb = signals.get("ttfb_ms")
    if ttfb is not None:
        if ttfb >= 2000:
            d += 40
        elif ttfb >= 1000:
            d += 25
        elif ttfb >= 300:
            d += 10

    html_bytes = signals.get("html_bytes")
    if html_bytes is not None:
        if html_bytes >= 1_500_000:
            d += 40
        elif html_bytes >= 1_000_000:
            d += 20
        elif html_bytes >= 500_000:
            d += 10

    asset_bytes = signals.get("asset_bytes")
    if asset_bytes is not None:
        if asset_bytes >= 5_000_000:
            d += 40
        elif asset_bytes >= 3_000_000:
            d += 30
        elif asset_bytes >= 1_000_000:
            d += 15

    asset_count = signals.get("asset_count")
    if asset_count is not None:
        if asset_count >= 120:
            d += 40
        elif asset_count >= 80:
            d += 20
        elif asset_count >= 40:
            d += 10

    rbk = signals.get("render_blocking_head_scripts")
    if rbk:
        d += 20 if rbk >= 5 else 10

    if signals.get("content_encoded") is False:
        d += 5

    lcp = signals.get("lcp_ms")
    if lcp is not None and lcp >= 2500:
        d += 20
    cls = signals.get("cls")
    if cls is not None and cls >= 0.1:
        d += 15
    inp = signals.get("inp_ms")
    if inp is not None and inp >= 200:
        d += 15

    return _score(d)


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------


def score_accessibility(signals: dict[str, Any]) -> int:
    """Accessibility rubric over measured signals only."""
    d = 0
    if signals.get("html_lang") is False:
        d += 15

    img_total = signals.get("img_total") or 0
    img_missing = signals.get("img_missing_alt") or 0
    if img_total and img_missing:
        d += 30 if img_missing >= 6 else 15

    inputs = signals.get("input_missing_label") or 0
    if inputs:
        d += 10 * min(inputs, 3)

    if signals.get("h1_count") == 0:
        d += 15
    if signals.get("heading_order_violation"):
        d += 5

    buttons = signals.get("button_empty_name") or 0
    if buttons:
        d += min(10 * buttons, 30)

    return _score(d)


# ---------------------------------------------------------------------------
# SEO
# ---------------------------------------------------------------------------


def score_seo(signals: dict[str, Any]) -> int:
    """SEO rubric over measured signals only."""
    d = 0
    if signals.get("has_title") is False:
        d += 20
    elif signals.get("title_length", 0) > 60:
        d += 5

    if signals.get("has_meta_description") is False:
        d += 15
    if signals.get("has_og_title") is False and signals.get("has_og_image") is False:
        d += 10
    elif signals.get("has_og_title") is False or signals.get("has_og_image") is False:
        d += 5
    if signals.get("has_twitter_card") is False:
        d += 5
    if signals.get("has_canonical") is False:
        d += 10

    h1 = signals.get("h1_count")
    if h1 == 0:
        d += 10
    elif h1 is not None and h1 > 1:
        d += 5
    if signals.get("has_json_ld") is False:
        d += 10
    if signals.get("scheme") == "http":
        d += 20
    if signals.get("robots_present") is False:
        d += 5
    if signals.get("sitemap_present") is False:
        d += 5

    return _score(d)


# ---------------------------------------------------------------------------
# Mobile
# ---------------------------------------------------------------------------


def score_mobile(signals: dict[str, Any]) -> int:
    """Mobile rubric over measured signals only."""
    d = 0
    if signals.get("viewport_meta") is False:
        d += 40

    tables = signals.get("tables") or 0
    fixed = signals.get("fixed_width_elements") or 0
    if tables or fixed:
        d += min((min(tables, 2) + min(fixed, 2)) * 10, 20)

    if signals.get("horizontal_overflow"):
        d += 30
    font = signals.get("body_font_size_px")
    if font is not None and font < 16:
        d += 10
    if signals.get("small_tap_targets"):
        d += 10

    img_total = signals.get("img_total") or 0
    with_srcset = signals.get("images_with_srcset") or 0
    if img_total > 2 and with_srcset < img_total:
        d += 5

    return _score(d)


# ---------------------------------------------------------------------------
# CWV report assembly (D-34 methodology labels)
# ---------------------------------------------------------------------------


def build_cwv_report(ttfb_ms: int, rendered: dict[str, Any] | None = None) -> dict[str, Any]:
    """Assemble the CWV storage shape; rendered probe data optional.

    Static-only runs keep lcp/cls/inp null and label inp as not_assessed;
    Playwright runs tag the INP estimation method (D-34, Pitfall 4).
    """
    rendered = rendered or {}
    inp_source = rendered.get("inp_source")
    if rendered:
        measured_with = "playwright"
        if inp_source == "event":
            inp_estimation = "scripted_event_timing"
        elif inp_source == "longtask":
            inp_estimation = "longtask_proxy"
        else:
            inp_estimation = "not_assessed"
        notes = []
    else:
        measured_with = "static"
        inp_estimation = "not_assessed"
        notes = ["browser unavailable — LCP/CLS/INP not measured"]

    return {
        "ttfb_ms": ttfb_ms,
        "lcp_ms": rendered.get("lcp_ms"),
        "cls": rendered.get("cls"),
        "inp_ms": rendered.get("inp_ms"),
        "methodology": {
            "measured_with": measured_with,
            "inp_estimation": inp_estimation,
            "notes": notes,
        },
    }
