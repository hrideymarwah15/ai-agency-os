"""Proposal document renderer tests with optional dependency seams."""

import sys
import asyncio
from types import SimpleNamespace

import pytest

from backend.services.proposal.pdf import PDFRenderer


def test_render_html_includes_print_css() -> None:
    html = PDFRenderer().render_html("<html><head></head><body>Test</body></html>")
    assert "@page" in html
    assert "@media print" in html


def test_render_pdf_uses_weasyprint_when_available(monkeypatch) -> None:
    class FakeHTML:
        def __init__(self, **kwargs):
            assert "Proposal" in kwargs["string"]

        def write_pdf(self) -> bytes:
            return b"%PDF-1.7\n" + b"x" * 1200

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=FakeHTML))
    content = asyncio.run(PDFRenderer().render_pdf("<html><body>Proposal</body></html>"))
    assert content.startswith(b"%PDF")
    assert len(content) > 1000


def test_docx_reports_optional_dependency(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(RuntimeError, match="optional"):
        PDFRenderer().render_docx("<h1>Proposal</h1>")


def test_weasyprint_failure_uses_playwright_fallback(monkeypatch) -> None:
    class BrokenHTML:
        def __init__(self, **kwargs):
            pass

        def write_pdf(self):
            raise ValueError("broken renderer")

    renderer = PDFRenderer()
    async def fallback(html: str) -> bytes:
        return b"%PDF-fallback"

    monkeypatch.setitem(sys.modules, "weasyprint", SimpleNamespace(HTML=BrokenHTML))
    monkeypatch.setattr(renderer, "_render_playwright", fallback)
    assert asyncio.run(renderer.render_pdf("<p>Proposal</p>")) == b"%PDF-fallback"


def test_pdf_reports_clear_error_when_both_renderers_fail(monkeypatch) -> None:
    renderer = PDFRenderer()
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    async def broken(html: str) -> bytes:
        raise RuntimeError("missing")
    monkeypatch.setattr(renderer, "_render_playwright", broken)
    with pytest.raises(RuntimeError, match="WeasyPrint and Playwright failed"):
        asyncio.run(renderer.render_pdf("<p>Proposal</p>"))
