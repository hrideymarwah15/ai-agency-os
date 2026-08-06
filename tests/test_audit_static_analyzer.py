"""Static HTML analyzer tests (D-36, AUDT-01..03) — extraction + gap rules.

Deterministic, zero-network: fixture HTML strings parsed with the stdlib
HTMLParser subclass. Also asserts the CMP-06 hostile-input-never-raises posture
copied from sanitize.py.
"""

from backend.services.audits.static_analyzer import analyze_html, find_conversion_gaps

_FIXTURE = """<!doctype html>
<html lang="en"><head>
<title>Acme Web Studio — Web Design</title>
<meta name="description" content="We build websites for small businesses.">
<meta property="og:title" content="Acme Web Studio">
<meta property="og:image" content="https://acme.example.com/og.png">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://acme.example.com/">
<script type="application/ld+json">{"@type": "Organization"}</script>
<script src="https://cdn.example.com/app.js"></script>
</head><body>
<h1>Welcome</h1>
<h2>Services</h2>
<img src="/logo.png" alt="Acme logo">
<img src="/hero.png">
<form action="/contact"><input name="name" aria-label="Name"></form>
<a href="https://acme.example.com/about">About</a>
<a href="https://external.example.com/partner">Partner</a>
<a href="mailto:hello@acme.example.com">Email</a>
<a href="https://acme.example.com/contact">Contact us</a>
<table><tr><td>x</td></tr></table>
</body></html>"""


def test_analyze_html_extracts_meta_headings_links():
    """Well-formed page: all extraction buckets populated."""
    s = analyze_html(_FIXTURE)
    assert s.html_lang is True
    assert s.title is not None
    assert len(s.title) <= 60
    assert s.meta_description is True
    assert s.og_title is True
    assert s.og_image is True
    assert s.twitter_card is False
    assert s.canonical is True
    assert s.json_ld is True
    assert s.viewport_meta is True
    assert s.h1_count == 1
    assert s.heading_order_violation is False
    assert s.img_total == 2
    assert s.img_missing_alt == 1
    assert len(s.links) == 3  # http(s) anchors only — mailto excluded
    assert len(s.forms) == 1
    assert s.forms[0]["has_action"] is True
    assert len(s.scripts) == 1
    assert s.has_mailto is True
    assert s.has_cta is True
    assert s.tables == 1
    assert s.input_missing_label == 0  # aria-label present on the input


def test_analyze_html_missing_everything():
    """Bare page: all boolean flags false, counts zero."""
    s = analyze_html("<html><body><p>just text</p></body></html>")
    assert s.html_lang is False
    assert s.title is None
    assert s.meta_description is False
    assert s.viewport_meta is False
    assert s.h1_count == 0
    assert s.img_total == 0
    assert s.links == []
    assert s.forms == []
    assert s.body_text_length > 0


def test_heading_order_violation_detected():
    """h2 before h1 is a heading-order violation; counts still correct."""
    s = analyze_html("<html><body><h2>X</h2><h1>Y</h1></body></html>")
    assert s.heading_order_violation is True
    assert s.h1_count == 1


def test_render_blocking_head_scripts_counted():
    """Scripts in <head> without async/defer are render-blocking."""
    html = (
        "<html><head><script src='/a.js'></script>"
        "<script src='/b.js' async></script><script src='/c.js' defer></script>"
        "</head><body></body></html>"
    )
    s = analyze_html(html)
    assert s.render_blocking_head_scripts == 1
    assert len(s.scripts) == 3


def test_srcset_and_fixed_width_signals():
    """srcset images counted; tables and fixed widths flagged for mobile."""
    html = (
        '<img src="/a.jpg" srcset="/a-2x.jpg 2x">'
        '<table width="800"><tr><td>x</td></tr></table>'
        '<div style="min-width: 900px">x</div>'
    )
    s = analyze_html(html)
    assert s.images_with_srcset == 1
    assert s.img_total == 1
    assert s.tables == 1
    assert s.fixed_width_elements >= 2


def test_input_missing_label_counted():
    """Controls without label/aria-label/aria-labelledby/title are flagged."""
    html = (
        '<input name="a"><input name="b" aria-label="B">'
        '<select name="c"></select><textarea name="d" title="D"></textarea>'
    )
    s = analyze_html(html)
    assert s.input_missing_label == 2


def test_button_empty_name_counted():
    """A <button> with no text and no accessible-name attr is empty-named."""
    html = '<button aria-label="Good"></button><button><span></span></button><button>Save</button>'
    s = analyze_html(html)
    assert s.button_empty_name == 1


def test_iframe_missing_title_counted():
    """<iframe> without a title attr is flagged (a11y)."""
    s = analyze_html('<iframe src="/x"></iframe><iframe src="/y" title="Y"></iframe>')
    assert s.iframe_missing_title == 1


def test_bare_page_gaps_all_four():
    """No form, CTA, contact link or phone → the four classic gaps."""
    s = analyze_html("<html><body><p>just text</p></body></html>")
    gaps = find_conversion_gaps(s)
    assert {g["kind"] for g in gaps} == {
        "missing_contact_form",
        "missing_cta",
        "no_direct_contact",
        "no_phone_listed",
    }


def test_form_without_action_is_gap():
    """A form with no usable action → form_no_action (not missing_contact_form)."""
    html = (
        "<html><body><form><input name='q'></form>"
        "<a href='https://x.example.com/contact'>Contact us</a>"
        "<a href='tel:+14155550132'>Call</a></body></html>"
    )
    s = analyze_html(html)
    gaps = find_conversion_gaps(s)
    assert {"kind": "form_no_action"} in gaps
    assert {"kind": "missing_contact_form"} not in gaps


def test_cta_and_phone_present_but_no_form():
    """CTA + phone + contact link, no form → only the missing-form gap."""
    html = (
        "<html><body><a href='https://x.example.com/contact'>Request a demo</a>"
        "<p>Call us at 415-555-0132</p></body></html>"
    )
    s = analyze_html(html)
    gaps = find_conversion_gaps(s)
    assert {g["kind"] for g in gaps} == {"missing_contact_form"}


def test_hostile_input_never_raises():
    """Control-heavy malformed markup is swallowed (CMP-06 posture)."""
    s = analyze_html(("<" + "\x00\x01" * 500 + ">" + "</unclosed") * 20)
    assert s is not None


def test_html_cap_enforced_at_read():
    """max_bytes caps the input before parsing (CMP-06)."""
    s = analyze_html("<html><body><p>huge</p></body></html>", max_bytes=8)
    assert s is not None
