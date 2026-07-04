"""Report generation: job artifacts to Markdown, HTML and (optionally) PDF."""

from reports.context import ReportContext, build_report_context
from reports.pdf import PdfUnavailableError, render_pdf
from reports.render import render_html, render_markdown

__all__ = [
    "PdfUnavailableError",
    "ReportContext",
    "build_report_context",
    "render_html",
    "render_markdown",
    "render_pdf",
]
