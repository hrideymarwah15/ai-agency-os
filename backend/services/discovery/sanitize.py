"""Ingestion sanitization (CMP-06) — scraped content becomes inert, data-only text.

stdlib only (html.parser, re) — zero new dependencies (D-30). The two public
functions are the ONLY sanctioned path for scraped content: adapters sanitize
before persisting, and future LLM-facing phases MUST route scraped content
through strip_control_tokens() (D-27) so prompt-boundary tokens from hostile
sources can never reach instruction context.
"""

import re
from html.parser import HTMLParser

from loguru import logger

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOKENS = ("<|endoftext|>", "<|im_start|>", "<|im_end|>", "|>|endoftext|<|")

# Whitespace-tolerant: HTMLParser mangles tokens like "<|endoftext|>" into
# "< |endoftext|>" while extracting text, so an exact match would let the
# boundary survive into instruction context. Each token matches with any
# whitespace between its characters (D-27 prompt-boundary guard).
_TOKEN_RE = re.compile("|".join(r"\s*".join(map(re.escape, token)) for token in _TOKENS))


class _TextExtractor(HTMLParser):
    """Collect text; drop script/style/noscript blocks entirely."""

    _SKIP = frozenset({"script", "style", "noscript"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def strip_html_to_text(raw: str, *, max_bytes: int = 512_000, max_text: int = 20_000) -> str:
    """Reduce scraped HTML to capped, control-free plain text.

    Hard caps at read (raw bytes) and at output (text chars); script/style/
    noscript content is dropped; character references are resolved. Hostile
    or malformed input NEVER raises (CMP-06) — parser edge cases are swallowed.
    """
    if len(raw.encode()) > max_bytes:
        raw = raw[:max_bytes]  # hard cap at read
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception as exc:  # noqa: BLE001 — CMP-06: hostile input must NEVER
        # raise; modern HTMLParser tolerates malformed markup, this guard covers
        # any parser edge case (HTMLParseError, UnicodeDecodeError).
        logger.debug("sanitize: swallowed parser edge case: {}", exc)
    # Strip controls from the joined text, then collapse whitespace via split.
    text = " ".join(_CTRL_RE.sub("", " ".join(parser.parts)).split())
    return text[:max_text]


def strip_control_tokens(text: str) -> str:
    """Prompt-boundary guard: remove all four LLM boundary tokens.

    D-27: any phase that routes scraped content into instruction context MUST
    pass it through this helper first — boundary tokens from hostile sources
    can otherwise break out of user-role delimiters.
    """
    return _TOKEN_RE.sub("", text)
