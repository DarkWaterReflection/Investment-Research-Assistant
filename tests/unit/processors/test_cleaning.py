from collectors.base import Evidence
from core.types import DataCategory
from processors.cleaning import clean_evidence, clean_text, normalize_whitespace, strip_html


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="Acme raises Series B",
        content="Acme Robotics announced a $40M Series B.",
        source_url="https://news.example/acme-series-b",
        collector="serpapi",
        reliability=0.65,
    )
    return Evidence(**{**defaults, **overrides})


def test_strip_html_removes_tags_and_unescapes_entities():
    assert strip_html("<p>Acme&nbsp;Robotics &amp; Co</p>").strip() == "Acme\xa0Robotics & Co"


def test_normalize_whitespace_collapses_runs_and_strips_controls():
    assert normalize_whitespace("  a\t\tb\n\nc\x00d  ") == "a b cd"


def test_clean_text_full_pass():
    assert clean_text("<div>Hello   &amp;   <b>World</b></div>") == "Hello & World"


def test_clean_evidence_strips_html_from_title_and_content():
    ev = make_evidence(
        title="<h1>About Acme</h1>",
        content="<p>Acme&nbsp;Robotics builds <b>robots</b></p>",
    )
    cleaned = clean_evidence(ev)
    assert cleaned.title == "About Acme"
    assert cleaned.content == "Acme Robotics builds robots"


def test_clean_evidence_does_not_mutate_input():
    ev = make_evidence(title="<h1>About Acme</h1>", content="<p>dirty</p>")
    original_title, original_content = ev.title, ev.content
    clean_evidence(ev)
    assert ev.title == original_title
    assert ev.content == original_content


def test_clean_evidence_preserves_other_fields():
    ev = make_evidence(content="<p>x</p>", reliability=0.42)
    cleaned = clean_evidence(ev)
    assert cleaned.id == ev.id
    assert cleaned.reliability == 0.42
    assert cleaned.source_url == ev.source_url
    assert cleaned.category is DataCategory.NEWS


def test_clean_evidence_on_already_clean_text_is_stable():
    ev = make_evidence(title="Clean title", content="Already clean content.")
    cleaned = clean_evidence(ev)
    assert cleaned.title == "Clean title"
    assert cleaned.content == "Already clean content."
