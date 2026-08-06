"""Scoring rubric tests (D-36, AUDT-01) — deterministic max(0, 100 − deductions).

Pure math over signal dicts (RESEARCH §Pattern 3): only measured signals
deduct; absent signals are never guessed. CWV storage shape carries
methodology labels per D-34.
"""

from backend.services.audits.scoring import (
    build_cwv_report,
    score_accessibility,
    score_mobile,
    score_performance,
    score_seo,
)


def test_performance_clean_signals_score_100():
    assert (
        score_performance(
            {
                "ttfb_ms": 210,
                "html_bytes": 60_000,
                "asset_bytes": 300_000,
                "asset_count": 10,
                "render_blocking_head_scripts": 0,
                "content_encoded": True,
            }
        )
        == 100
    )


def test_performance_ttfb_deductions():
    assert score_performance({"ttfb_ms": 900}) == 90
    assert score_performance({"ttfb_ms": 1600}) == 75


def test_performance_html_byte_deductions():
    assert score_performance({"html_bytes": 600_000}) == 90
    assert score_performance({"html_bytes": 1_100_000}) == 80


def test_performance_asset_deductions():
    assert score_performance({"asset_bytes": 1_600_000}) == 85
    assert score_performance({"asset_bytes": 3_100_000}) == 70
    assert score_performance({"asset_count": 41}) == 90
    assert score_performance({"asset_count": 81}) == 80


def test_performance_render_blocking_and_encoding():
    assert score_performance({"render_blocking_head_scripts": 4}) == 90
    assert score_performance({"content_encoded": False}) == 95


def test_performance_rendered_cwv_deductions():
    assert score_performance({"lcp_ms": 2600}) == 80
    assert score_performance({"cls": 0.11}) == 85
    assert score_performance({"inp_ms": 250}) == 85


def test_performance_never_below_zero():
    assert (
        score_performance(
            {
                "ttfb_ms": 2500,
                "html_bytes": 2_000_000,
                "asset_bytes": 5_000_000,
                "asset_count": 100,
                "render_blocking_head_scripts": 5,
                "content_encoded": False,
                "lcp_ms": 3000,
                "cls": 0.3,
                "inp_ms": 400,
            }
        )
        == 0
    )


def test_accessibility_lang_and_img_alt():
    assert score_accessibility({"html_lang": False}) == 85
    assert score_accessibility({"img_total": 10, "img_missing_alt": 5}) == 85
    assert score_accessibility({"img_total": 10, "img_missing_alt": 10}) == 70


def test_accessibility_labels_headings_buttons():
    assert score_accessibility({"input_missing_label": 1}) == 90
    assert score_accessibility({"input_missing_label": 5}) == 70  # capped at 3 inputs
    assert score_accessibility({"h1_count": 0}) == 85
    assert score_accessibility({"heading_order_violation": True}) == 95
    assert score_accessibility({"button_empty_name": 2}) == 80


def test_accessibility_never_below_zero():
    assert (
        score_accessibility(
            {
                "html_lang": False,
                "img_total": 10,
                "img_missing_alt": 10,
                "input_missing_label": 5,
                "h1_count": 0,
                "heading_order_violation": True,
                "button_empty_name": 2,
            }
        )
        == 0
    )


def test_seo_perfect_signals_score_100():
    assert (
        score_seo(
            {
                "has_title": True,
                "title_length": 50,
                "has_meta_description": True,
                "has_og_title": True,
                "has_og_image": True,
                "has_twitter_card": True,
                "has_canonical": True,
                "h1_count": 1,
                "has_json_ld": True,
                "robots_present": True,
                "sitemap_present": True,
                "scheme": "https",
            }
        )
        == 100
    )


def test_seo_title_description_deductions():
    assert score_seo({"has_title": False}) == 80
    assert score_seo({"has_title": True, "title_length": 70}) == 95
    assert score_seo({"has_meta_description": False}) == 85


def test_seo_open_graph_and_canonical_deductions():
    assert score_seo({"has_og_title": False, "has_og_image": False}) == 90
    assert score_seo({"has_twitter_card": False}) == 95
    assert score_seo({"has_canonical": False}) == 90


def test_seo_headings_structure_and_scheme():
    assert score_seo({"h1_count": 0}) == 90
    assert score_seo({"h1_count": 2}) == 95
    assert score_seo({"has_json_ld": False}) == 90
    assert score_seo({"scheme": "http"}) == 80
    assert score_seo({"robots_present": False}) == 95
    assert score_seo({"sitemap_present": False}) == 95


def test_mobile_viewport_and_fixed_layout():
    assert score_mobile({"viewport_meta": False}) == 60
    assert score_mobile({"tables": 1, "fixed_width_elements": 1}) == 80
    assert score_mobile({"tables": 2, "fixed_width_elements": 4}) == 80  # capped at 2


def test_mobile_rendered_signals():
    assert score_mobile({"horizontal_overflow": True}) == 70
    assert score_mobile({"body_font_size_px": 15}) == 90
    assert score_mobile({"small_tap_targets": True}) == 90


def test_mobile_srcset_deduction():
    assert score_mobile({"img_total": 3, "images_with_srcset": 0}) == 95
    assert score_mobile({"img_total": 3, "images_with_srcset": 3}) == 100


def test_cwv_static_mode_labels():
    """Static-only runs: TTFB measured, everything else null + not assessed (D-34)."""
    report = build_cwv_report(ttfb_ms=210)
    assert report["ttfb_ms"] == 210
    assert report["lcp_ms"] is None
    assert report["cls"] is None
    assert report["inp_ms"] is None
    assert report["methodology"]["measured_with"] == "static"
    assert report["methodology"]["inp_estimation"] == "not_assessed"
    assert any("browser unavailable" in note for note in report["methodology"]["notes"])


def test_cwv_playwright_measured():
    report = build_cwv_report(
        ttfb_ms=210,
        rendered={"lcp_ms": 1870, "cls": 0.02, "inp_ms": 145, "inp_source": "event"},
    )
    assert report["lcp_ms"] == 1870
    assert report["cls"] == 0.02
    assert report["inp_ms"] == 145
    assert report["methodology"]["measured_with"] == "playwright"
    assert report["methodology"]["inp_estimation"] == "scripted_event_timing"


def test_cwv_longtask_proxy_labeled():
    """INP from the long-task fallback is labeled as a proxy (Pitfall 4)."""
    report = build_cwv_report(
        ttfb_ms=100,
        rendered={"lcp_ms": None, "cls": None, "inp_ms": 220, "inp_source": "longtask"},
    )
    assert report["methodology"]["inp_estimation"] == "longtask_proxy"
