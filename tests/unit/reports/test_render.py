"""Rendering: Markdown structure, HTML escaping, citation footnotes."""

from datetime import UTC, datetime

from reports.context import build_report_context
from reports.render import render_html, render_markdown


def test_markdown_renders_all_report_blocks(context):
    md = render_markdown(context)

    assert "# Investment Memo — Acme Robotics" in md
    assert "## Executive Summary" in md
    assert "Acme is a fast-growing robotics company." in md
    assert "### Key Strengths" in md
    assert "European expansion underway[1]" in md
    assert "Round size is disputed[2][1]" in md
    assert "*inferred, high confidence*" in md
    assert "### Open Questions" in md
    assert "## Funding & Financials" in md
    assert "1 unresolved conflict(s)" in md
    assert "| 2026-05-12 | Acme opens Berlin office | news |" in md
    assert "## Sources" in md
    assert "[Acme opens Berlin office](https://news.example/acme-berlin)" in md
    assert "## Diagnostics" in md
    assert "serpapi: no news results" in md


def test_markdown_has_no_unrendered_template_syntax(context):
    md = render_markdown(context)

    assert "{{" not in md
    assert "{%" not in md


def test_html_renders_and_links_sources(context):
    html = render_html(context)

    assert "<title>Investment Memo — Acme Robotics</title>" in html
    assert '<a href="https://news.example/acme-berlin">' in html
    assert "Series B amount disagrees across sources." in html


def test_html_escapes_model_produced_text(corpus, analysis):
    analysis.synthesis.executive_summary = "<script>alert('x')</script> Acme is fine."

    context = build_report_context(
        company="Acme Robotics",
        corpus=corpus,
        analysis=analysis,
        stage="complete",
        total_cost_usd=0.0,
        generated_at=datetime(2026, 7, 4, tzinfo=UTC),
    )
    html = render_html(context)

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_markdown_leaves_text_unescaped(context):
    md = render_markdown(context)

    assert "Funding & Financials" in md  # no &amp; in markdown output
