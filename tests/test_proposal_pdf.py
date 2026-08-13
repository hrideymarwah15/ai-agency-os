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
