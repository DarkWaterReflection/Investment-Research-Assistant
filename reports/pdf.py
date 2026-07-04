"""PDF export via WeasyPrint — an optional heavyweight dependency.

WeasyPrint needs native libraries (Pango/GTK) that many environments lack, so
it is imported lazily and its absence is a typed, catchable error: Markdown
and HTML export keep working, and the API layer can return 501 for PDF.
Install with: pip install -e ".[pdf]"
"""

from __future__ import annotations

from typing import cast

from reports.context import ReportContext
from reports.render import render_html


class PdfUnavailableError(RuntimeError):
    """WeasyPrint (or its native libraries) is not installed."""


def render_pdf(context: ReportContext) -> bytes:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:  # OSError: missing Pango/GTK natives
        raise PdfUnavailableError(
            "PDF export requires WeasyPrint and its native libraries; "
            'install with pip install -e ".[pdf]". '
            f"Underlying error: {exc}"
        ) from exc
    # weasyprint is untyped; write_pdf() returns bytes when no target is given
    return cast(bytes, HTML(string=render_html(context)).write_pdf())
