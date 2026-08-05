"""Ingestion sanitization (CMP-06): scraped HTML becomes inert, data-only text.

Constraint #5 adversarial fixtures (tests/fixtures/injections.json) must
sanitize to inert output: no prompt directives, no LLM boundary tokens, no
markup — and hostile/malformed input never raises. Scraped content is only
ever persisted/consumed through these two functions (D-27).
"""

import json
from pathlib import Path

from backend.services.discovery.sanitize import (
    _TOKENS,
    strip_control_tokens,
    strip_html_to_text,
)

FIXTURES = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "injections.json").read_text()
)

MAX_BYTES = 512_000
MAX_TEXT = 20_000


def test_script_style_noscript_dropped():
    """script/style/noscript blocks are removed entirely; charrefs converted."""
    html = (
        "<script>alert(1)</script>"
        "<style>.x { color: red }</style>"
        "<noscript>leak payload</noscript>"
        "<p>Hello &amp; welcome</p>"
    )
    assert strip_html_to_text(html) == "Hello & welcome"


def test_control_characters_stripped():
    """C0 controls and DEL are removed; whitespace collapses to single spaces."""
    assert strip_html_to_text("a\x00b\x1fc\x7fd") == "abcd"
    assert strip_html_to_text("a \t b \n\n c") == "a b c"


def test_raw_bytes_and_text_capped():
    """Raw input over 512_000 bytes and extracted text over 20_000 chars cap."""
    big = "x" * (MAX_BYTES + 10_000)
    assert len(strip_html_to_text(big)) == MAX_TEXT

    long_html = "<p>" + "y" * 300_000 + "</p>"  # under the byte cap, over text cap
    assert len(strip_html_to_text(long_html)) == MAX_TEXT


def test_hostile_input_never_raises():
    """Malformed/truncated/binary-ish input always returns a string."""
    hostile = [
        "<div><span>unclosed &bogus; &#xZZZ; <a href='x'>broken</div>",
        "<script>alert(document.cookie)",
        "\x00\x01\x02\x03",
        "&",
        "<",
        "</",
        "\x7f" * 100,
    ]
    for raw in hostile:
        assert isinstance(strip_html_to_text(raw), str)


def test_control_tokens_removed():
    """All four LLM boundary tokens are stripped from scraped text."""
    text = "<|endoftext|>A<|im_start|>B<|im_end|>C|>|endoftext|<|D"
    assert strip_control_tokens(text) == "ABCD"
    for token in _TOKENS:
        assert token not in strip_control_tokens(text)


def test_injections_fixture_inert():
    """Every adversarial fixture sanitizes to inert data: no directives, no
    boundary tokens, no markup, text capped."""
    for name, raw in FIXTURES.items():
        sanitized = strip_control_tokens(strip_html_to_text(raw))
        for token in _TOKENS:
            assert token not in sanitized, f"{name}: boundary token survived"
        assert "ignore previous instructions" not in sanitized, name
        assert "alert(1)" not in sanitized, name
        assert "{{7*7}}" not in sanitized, name
        assert "leak" not in sanitized, name
        assert "<" not in sanitized and ">" not in sanitized, name
        assert len(sanitized) <= MAX_TEXT, name
