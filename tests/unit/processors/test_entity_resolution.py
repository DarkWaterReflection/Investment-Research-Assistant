from corpus import build_corpus, build_target

from collectors.base import CompanyTarget, Evidence
from core.types import DataCategory
from processors.entity_resolution import EntityResolutionResult, resolve_entities


def make_evidence(**overrides):
    defaults = dict(
        company="Acme Robotics",
        category=DataCategory.NEWS,
        title="A headline",
        content="Some body text.",
        source_url="https://news.example/story",
        collector="serpapi",
        reliability=0.6,
    )
    return Evidence(**{**defaults, **overrides})


def test_name_mention_in_content_matches():
    target = CompanyTarget(name="Acme Robotics", website=None)
    ev = make_evidence(content="Today Acme Robotics shipped a product.")
    result = resolve_entities([ev], target)
    assert result.matched == [ev]
    assert result.quarantined == []


def test_name_mention_is_case_insensitive():
    target = CompanyTarget(name="Acme Robotics", website=None)
    ev = make_evidence(title="ACME ROBOTICS wins award", content="body")
    result = resolve_entities([ev], target)
    assert result.matched == [ev]


def test_alias_mention_matches():
    target = CompanyTarget(name="Acme Robotics", website=None, aliases=["AcmeBot"])
    ev = make_evidence(content="AcmeBot is the flagship product line.")
    result = resolve_entities([ev], target)
    assert result.matched == [ev]


def test_domain_match_without_name_mention():
    target = CompanyTarget(name="Acme Robotics", website="https://acme-robotics.example")
    ev = make_evidence(
        title="Our mission",
        content="We build the future.",  # no name mention at all
        source_url="https://acme-robotics.example/about",
    )
    result = resolve_entities([ev], target)
    assert result.matched == [ev]


def test_subdomain_of_target_site_matches():
    target = CompanyTarget(name="Acme Robotics", website="https://acme-robotics.example")
    ev = make_evidence(content="No mention here.", source_url="https://blog.acme-robotics.example/x")
    result = resolve_entities([ev], target)
    assert result.matched == [ev]


def test_unrelated_namesake_is_quarantined():
    target = CompanyTarget(name="Acme Robotics", website="https://acme-robotics.example")
    ev = make_evidence(
        title="Acme Bakery opens downtown",
        content="Acme Bakery sells fresh bread.",
        source_url="https://localnews.example/bakery",
    )
    result = resolve_entities([ev], target)
    assert result.matched == []
    assert result.quarantined == [ev]


def test_empty_list():
    target = build_target()
    assert resolve_entities([], target) == EntityResolutionResult(matched=[], quarantined=[])


def test_does_not_mutate_input():
    target = build_target()
    evidence = build_corpus()
    ids_before = [e.id for e in evidence]
    resolve_entities(evidence, target)
    assert [e.id for e in evidence] == ids_before


def test_corpus_partition_quarantines_only_the_bakery():
    target = build_target()
    result = resolve_entities(build_corpus(), target)
    assert [e.id for e in result.quarantined] == ["ev07"]
    matched_ids = {e.id for e in result.matched}
    assert "ev07" not in matched_ids
    assert len(result.matched) + len(result.quarantined) == 15
