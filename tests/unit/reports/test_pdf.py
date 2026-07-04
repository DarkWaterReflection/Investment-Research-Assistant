"""PDF export: real render when WeasyPrint is present, typed error when not."""

import sys

import pytest

from reports.pdf import PdfUnavailableError, render_pdf


def test_missing_weasyprint_raises_typed_error(context, monkeypatch):
    # A None entry in sys.modules makes `from weasyprint import HTML` raise ImportError.
    monkeypatch.setitem(sys.modules, "weasyprint", None)

    with pytest.raises(PdfUnavailableError) as excinfo:
        render_pdf(context)

    assert "pip install" in str(excinfo.value)


def test_pdf_bytes_when_weasyprint_installed(context):
    pytest.importorskip("weasyprint")

    pdf = render_pdf(context)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
