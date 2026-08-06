"""Deterministic static HTML analysis — bucket extraction (AUDT-01..03, D-36).

analyze_html() parses the page (sanitized, size-capped upstream) with a stdlib
HTMLParser subclass and returns an AuditStats namespace consumed by the four
scoring passes and the link walker. find_conversion_gaps() derives the
conversion-gap kinds shown in the audit view. Zero network, zero rendering —
pure local determinism. Mirrors the CMP-06 never-raises posture of
backend/tools/sanitize.py.
"""

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from backend.services.discovery.sanitize import strip_control_tokens

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_HTML_LANG_RE = re.compile(r"<html\b[^>]*\blang\s*=", re.IGNORECASE)
_JSONLD_RE = re.compile(r'<script\b[^>]*type\s*=\s*["\']application/ld\+json["\']', re.IGNORECASE)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d|\b\d{3}[-.)\s]\d{3}[-.\s]\d{4}\b")
_WIDTH_STYLE_RE = re.compile(r"(?:min-|max-)?width\s*:\s*\d+(?:\.\d+)?(px|rem|em)")

_CTA_WORDS = (
    "contact",
    "book",
    "quote",
    "estimate",
    "get started",
    "request",
    "schedule",
    "demo",
    "call",
    "email us",
)


def _parse_attr(tag: str) -> dict[str, str]:
    """Parse a single tag's attributes into a lowercase-key dict."""
    attrs: dict[str, str] = {}
    for m in re.finditer(
        r'([a-zA-Z_:][a-zA-Z0-9_:.-]*)\s*=\s*("([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag
    ):
        key = m.group(1).lower()
        value = m.group(3) or m.group(4) or m.group(5) or ""
        attrs.setdefault(key, value)
    return attrs


def _has_accessible_name(attrs: dict[str, str]) -> bool:
    return bool(
        attrs.get("aria-label")
        or attrs.get("aria-labelledby")
        or attrs.get("title")
        or attrs.get("label")
    )


@dataclass
class AuditStats:
    """Flat bucket of static signals derived from one page (AUDT-01..03)."""

    html_lang: bool
    title: str | None
    meta_description: bool
    og_title: bool
    og_image: bool
    twitter_card: bool
    canonical: bool
    json_ld: bool
    viewport_meta: bool
    h1_count: int
    heading_order_violation: bool
    img_total: int
    img_missing_alt: int
    images_with_srcset: int
    fixed_width_elements: int
    render_blocking_head_scripts: int
    input_missing_label: int
    button_empty_name: int
    iframe_missing_title: int
    tables: int
    has_mailto: bool
    has_tel: bool
    has_cta: bool
    forms: list[dict[str, Any]]
    scripts: list[dict[str, Any]]
    links: list[dict[str, str]]
    body_text_length: int


class _StatsCollector(HTMLParser):
    """One-pass bucket collector over a page fragment (CMP-06: never raises)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.h1_count = 0
        self.saw_h1 = False
        self.heading_order_violation = False
        self.img_total = 0
        self.img_missing_alt = 0
        self.images_with_srcset = 0
        self.fixed_width_elements = 0
        self.render_blocking_head_scripts = 0
        self.input_missing_label = 0
        self.button_empty_name = 0
        self.iframe_missing_title = 0
        self.tables = 0
        self.forms: list[dict[str, Any]] = []
        self.scripts: list[dict[str, Any]] = []
        self.links: list[dict[str, str]] = []
        self.has_mailto = False
        self.has_tel = False
        self.has_cta = False
        self._head_depth = 0
        self._frames: list[str] = []  # text accumulators
        self._kinds: list[str] = []  # "a-http" | "button" | "generic" | "head"
        self._button_names: list[bool] = []  # accessible-name flags for open buttons

    # -- helpers ----------------------------------------------------------

    def handle_data(self, data: str) -> None:
        if self._frames:
            self._frames[-1] += data

    def _open(self, kind: str) -> None:
        self._frames.append("")
        self._kinds.append(kind)

    def _close(self) -> tuple[str, str]:
        text = self._frames.pop() if self._frames else ""
        kind = self._kinds.pop() if self._kinds else "generic"
        return kind, text

    # -- parser callbacks -------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a: dict[str, str] = {k.lower(): (v or "") for k, v in attrs}
        if tag == "head":
            self._head_depth = 1
            self._open("head")
            return
        if tag == "body":
            self._head_depth = 0
            self._open("generic")
            return
        if tag == "img":
            self.img_total += 1
            if a.get("srcset"):
                self.images_with_srcset += 1
            if not a.get("alt") and not a.get("aria-label"):
                self.img_missing_alt += 1
            return
        if tag == "input":
            if a.get("type") in ("hidden", "submit", "button", "reset", "image"):
                return
            if not _has_accessible_name(a):
                self.input_missing_label += 1
            return
        if tag == "select" or tag == "textarea":
            if not _has_accessible_name(a):
                self.input_missing_label += 1
            self._open("generic")
            return
        if tag == "script":
            if a.get("src"):
                self.scripts.append(
                    {"src": a.get("src", ""), "async": "async" in a, "defer": "defer" in a}
                )
                if self._head_depth and "async" not in a and "defer" not in a:
                    self.render_blocking_head_scripts += 1
            self._open("generic")
            return
        if tag == "form":
            action = a.get("action", "")
            self.forms.append(
                {"action": action, "method": a.get("method", ""), "has_action": bool(action)}
            )
            self._open("generic")
            return
        if tag == "a":
            href = a.get("href", "")
            lowered = href.strip().lower()
            if lowered.startswith("mailto:"):
                self.has_mailto = True
            elif lowered.startswith("tel:"):
                self.has_tel = True
            elif lowered.startswith(("http://", "https://")):
                self.links.append({"href": href, "text": ""})
                self._open("a-http")
                return
            self._open("generic")
            return
        if tag == "button":
            self._open("button")
            self._button_names.append(_has_accessible_name(a))
            return
        if tag == "iframe":
            if not a.get("title"):
                self.iframe_missing_title += 1
            self._open("generic")
            return
        if tag == "table":
            self.tables += 1
        if tag in ("table", "td", "th") and a.get("width"):
            self.fixed_width_elements += 1
        if _WIDTH_STYLE_RE.search(a.get("style", "")):
            self.fixed_width_elements += 1
        self._open("generic")

    def handle_endtag(self, tag: str) -> None:
        kind, text = self._close()
        if tag == "h1":
            self.h1_count += 1
            self.saw_h1 = True
        elif tag == "h2":
            if not self.saw_h1:
                self.heading_order_violation = True
        elif kind == "button":
            has_name = self._button_names.pop() if self._button_names else False
            if not text.strip() and not has_name:
                self.button_empty_name += 1
        elif kind == "a-http":
            if self.links:
                self.links[-1]["text"] = text.strip()[:200]
                lowered = text.strip().lower()
                if any(word in lowered for word in _CTA_WORDS):
                    self.has_cta = True
        elif tag == "head":
            self._head_depth = 0


def _clean(html: str) -> str:
    return strip_control_tokens(html)


def analyze_html(html: str, max_bytes: int | None = None) -> AuditStats:
    """Analyze a page's static signals — deterministic, never raises (CMP-06)."""
    if max_bytes is not None and max_bytes >= 0:
        html = html[:max_bytes] if max_bytes > 0 else ""
    html = _clean(html)
    parser = _StatsCollector()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: S110, BLE001 — CMP-06: hostile input must never raise
        pass

    meta_description = False
    og_title = False
    og_image = False
    twitter_card = False
    for tag in _META_RE.findall(html):
        attrs = _parse_attr(tag)
        name = (attrs.get("name") or attrs.get("property") or "").lower()
        if name == "description":
            meta_description = True
        elif name == "og:title":
            og_title = True
        elif name == "og:image":
            og_image = True
        elif name == "twitter:card":
            twitter_card = True

    canonical = False
    for tag in _LINK_RE.findall(html):
        if _parse_attr(tag).get("rel", "").lower() == "canonical":
            canonical = True
            break

    title = None
    m = _TITLE_RE.search(html)
    if m:
        title = _WS_RE.sub(" ", _clean(m.group(1))).strip()[:300] or None

    body_text = _WS_RE.sub(" ", _TAG_STRIP_RE.sub(" ", _clean(html))).strip()
    has_phone_text = bool(_PHONE_RE.search(body_text))

    return AuditStats(
        html_lang=bool(_HTML_LANG_RE.search(html)),
        title=title,
        meta_description=meta_description,
        og_title=og_title,
        og_image=og_image,
        twitter_card=twitter_card,
        canonical=canonical,
        json_ld=bool(_JSONLD_RE.search(html)),
        viewport_meta="viewport" in html.lower(),
        h1_count=parser.h1_count,
        heading_order_violation=parser.heading_order_violation,
        img_total=parser.img_total,
        img_missing_alt=parser.img_missing_alt,
        images_with_srcset=parser.images_with_srcset,
        fixed_width_elements=parser.fixed_width_elements,
        render_blocking_head_scripts=parser.render_blocking_head_scripts,
        input_missing_label=parser.input_missing_label,
        button_empty_name=parser.button_empty_name,
        iframe_missing_title=parser.iframe_missing_title,
        tables=parser.tables,
        has_mailto=parser.has_mailto,
        has_tel=parser.has_tel or has_phone_text,
        has_cta=parser.has_cta,
        forms=parser.forms,
        scripts=parser.scripts,
        links=parser.links,
        body_text_length=len(body_text),
    )


# ---------------------------------------------------------------------------
# Conversion gaps (AUDT-03)
# ---------------------------------------------------------------------------


def find_conversion_gaps(stats: AuditStats) -> list[dict[str, str]]:
    """Return the classic conversion-gap findings for the audit view.

    Kinds: missing_contact_form, missing_cta, no_direct_contact,
    no_phone_listed, form_no_action.
    """
    gaps: list[dict[str, str]] = []
    if not stats.forms:
        gaps.append({"kind": "missing_contact_form"})
    if not stats.has_cta:
        gaps.append({"kind": "missing_cta"})
    if not stats.has_mailto and not stats.has_tel and not stats.forms:
        gaps.append({"kind": "no_direct_contact"})
    if not stats.has_tel:
        gaps.append({"kind": "no_phone_listed"})
    if stats.forms and not any(f.get("action") for f in stats.forms):
        gaps.append({"kind": "form_no_action"})
    return gaps
