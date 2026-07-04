"""Adversarial tests for schema validation + citation enforcement.

Every scenario runs against FakeLLM — no network, no keys. The contract under
test: schema failures get one repair then MalformedOutputError; sourced claims
without real evidence IDs get one repair then downgrade to inferred; unknown
IDs are always stripped; infrastructure errors always propagate.
"""

import pytest
from pydantic import BaseModel

from core.types import Basis, Confidence
from llm.base import LLMRateLimitedError, MalformedOutputError
from llm.fake import FakeLLM
from llm.schemas import Finding
from llm.validation import generate_validated, iter_findings

KNOWN_IDS = {"ev-real-1", "ev-real-2"}


class Section(BaseModel):
    summary: str
    findings: list[Finding]


class Memo(BaseModel):
    title: str
    sections: dict[str, Section]


def finding(claim="Acme raised $40M", basis="sourced", evidence_ids=(), confidence="high"):
    return {
        "claim": claim,
        "basis": basis,
        "evidence_ids": list(evidence_ids),
        "confidence": confidence,
    }


def section(*findings):
    return {"summary": "Funding overview.", "findings": list(findings)}


async def run(fake: FakeLLM, schema=Section, known=KNOWN_IDS):
    return await generate_validated(
        fake,
        system="You are an analyst.",
        prompt="Analyze the funding evidence.",
        schema=schema,
        known_evidence_ids=known,
    )


async def test_valid_first_try_needs_no_repair():
    fake = FakeLLM([section(finding(evidence_ids=["ev-real-1"]))])

    result = await run(fake)

    assert result.output.findings[0].basis is Basis.SOURCED
    assert result.output.findings[0].confidence is Confidence.HIGH
    assert not result.schema_repaired
    assert not result.citations_repaired
    assert result.warnings == []
    assert len(result.usage) == 1
    assert len(fake.calls) == 1


async def test_schema_failure_repaired_on_second_attempt():
    bad = {"summary": "ok"}  # findings missing
    fake = FakeLLM([bad, section(finding(evidence_ids=["ev-real-1"]))])

    result = await run(fake)

    assert result.schema_repaired
    assert len(result.usage) == 2
    repair_prompt = fake.calls[1].prompt
    assert "failed schema validation" in repair_prompt
    assert '"summary"' in repair_prompt  # echoes the previous payload
    assert "findings" in repair_prompt  # echoes the validation error


async def test_schema_failure_twice_raises_typed_error():
    fake = FakeLLM([{"nope": 1}, {"still": "nope"}])

    with pytest.raises(MalformedOutputError):
        await run(fake)


async def test_fabricated_ids_fixed_by_citation_repair():
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fixed = section(finding(evidence_ids=["ev-real-2"]))
    fake = FakeLLM([fabricated, fixed])

    result = await run(fake)

    assert result.citations_repaired
    assert result.output.findings[0].evidence_ids == ["ev-real-2"]
    assert result.output.findings[0].basis is Basis.SOURCED
    assert result.warnings == []
    assert "Never invent ids" in fake.calls[1].prompt
    assert "Acme raised $40M" in fake.calls[1].prompt


async def test_persistent_fabrication_downgrades_to_inferred():
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fake = FakeLLM([fabricated, section(finding(evidence_ids=["ev-still-fake"]))])

    result = await run(fake)

    out = result.output.findings[0]
    assert out.basis is Basis.INFERRED
    assert out.evidence_ids == []
    assert not result.citations_repaired
    assert any("Downgraded to inferred" in w for w in result.warnings)
    # the failed repair is discarded, so the stripped id is the original one
    assert any("ev-made-up" in w for w in result.warnings)


async def test_sourced_with_no_ids_repaired_to_inferred_is_accepted():
    uncited = section(finding(evidence_ids=[]))
    honest = section(finding(basis="inferred", evidence_ids=[]))
    fake = FakeLLM([uncited, honest])

    result = await run(fake)

    assert result.citations_repaired
    assert result.output.findings[0].basis is Basis.INFERRED
    assert result.warnings == []


async def test_mixed_real_and_fake_ids_stripped_without_repair_call():
    mixed = section(finding(evidence_ids=["ev-real-1", "ev-made-up"]))
    fake = FakeLLM([mixed])

    result = await run(fake)

    out = result.output.findings[0]
    assert out.basis is Basis.SOURCED  # one real citation keeps it sourced
    assert out.evidence_ids == ["ev-real-1"]
    assert len(fake.calls) == 1  # no repair spent on a partially valid claim
    assert any("ev-made-up" in w for w in result.warnings)


async def test_inferred_and_assumption_claims_are_untouched():
    payload = section(
        finding(claim="Likely expanding to EU", basis="inferred", evidence_ids=[]),
        finding(claim="Assume 20% churn", basis="assumption", evidence_ids=[]),
    )
    fake = FakeLLM([payload])

    result = await run(fake)

    assert [f.basis for f in result.output.findings] == [Basis.INFERRED, Basis.ASSUMPTION]
    assert result.warnings == []
    assert len(fake.calls) == 1


async def test_broken_citation_repair_falls_back_to_downgrade():
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fake = FakeLLM([fabricated, {"schema": "invalid"}])

    result = await run(fake)

    assert result.output.findings[0].basis is Basis.INFERRED
    assert not result.citations_repaired
    assert len(result.usage) == 2  # the failed repair is still paid for


async def test_malformed_citation_repair_falls_back_to_downgrade():
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fake = FakeLLM([fabricated, MalformedOutputError("fake", "no tool call")])

    result = await run(fake)

    assert result.output.findings[0].basis is Basis.INFERRED
    assert not result.citations_repaired


async def test_infrastructure_errors_propagate_from_repair():
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fake = FakeLLM([fabricated, LLMRateLimitedError("fake", "throttled")])

    with pytest.raises(LLMRateLimitedError):
        await run(fake)


async def test_schema_and_citation_repairs_can_both_run():
    bad = {"summary": "ok"}
    fabricated = section(finding(evidence_ids=["ev-made-up"]))
    fixed = section(finding(evidence_ids=["ev-real-1"]))
    fake = FakeLLM([bad, fabricated, fixed])

    result = await run(fake)

    assert result.schema_repaired
    assert result.citations_repaired
    assert len(result.usage) == 3


async def test_findings_are_enforced_in_nested_structures():
    memo = {
        "title": "Acme memo",
        "sections": {
            "funding": section(finding(evidence_ids=["ev-made-up"])),
            "team": section(finding(claim="CEO ex-Google", evidence_ids=["ev-real-1"])),
        },
    }
    honest = {
        "title": "Acme memo",
        "sections": {
            "funding": section(finding(basis="inferred")),
            "team": section(finding(claim="CEO ex-Google", evidence_ids=["ev-real-1"])),
        },
    }
    fake = FakeLLM([memo, honest])

    result = await run(fake, schema=Memo)

    assert result.citations_repaired
    findings = list(iter_findings(result.output))
    assert len(findings) == 2


def test_iter_findings_walks_models_lists_and_dicts():
    memo = Memo(
        title="t",
        sections={
            "a": Section(summary="s", findings=[Finding.model_validate(finding())]),
            "b": Section(
                summary="s",
                findings=[
                    Finding.model_validate(finding(claim="second")),
                    Finding.model_validate(finding(claim="third")),
                ],
            ),
        },
    )

    claims = [f.claim for f in iter_findings(memo)]

    assert sorted(claims) == ["Acme raised $40M", "second", "third"]
