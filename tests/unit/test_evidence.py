from datetime import UTC

import pytest
from pydantic import ValidationError

from collectors.base import Evidence
from core.types import DataCategory


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


def test_evidence_gets_id_and_timestamp():
    ev = make_evidence()
    assert len(ev.id) == 32
    assert ev.collected_at.tzinfo == UTC


def test_two_evidence_records_have_distinct_ids():
    assert make_evidence().id != make_evidence().id


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_reliability_must_be_within_unit_interval(bad):
    with pytest.raises(ValidationError):
        make_evidence(reliability=bad)


@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_confidence_must_be_within_unit_interval(bad):
    with pytest.raises(ValidationError):
        make_evidence(confidence=bad)


def test_raw_payload_is_preserved_verbatim():
    raw = {"nested": {"key": [1, 2, 3]}}
    assert make_evidence(raw=raw).raw == raw
