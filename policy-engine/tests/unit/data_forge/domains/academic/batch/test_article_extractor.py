"""Behavioral regression tests for the shared academic evidence normalizer."""

import pytest

from polisyos.data_forge.domains.academic.batch import article_extractor
from polisyos.data_forge.domains.academic.batch._resolve_extract_transformers import (
    _normalize_extraction_payload,
)
from polisyos.data_forge.domains.academic.knowledge.skg_store import EVIDENCE_WEIGHTS
from polisyos.ir.analytics.literature import DesignFamily, EvidenceStrength


@pytest.mark.parametrize("design", list(DesignFamily), ids=lambda member: member.value)
def test_design_family_normalization_preserves_canonical_identity(design: DesignFamily) -> None:
    """A substring alias must never replace an exact canonical design identity."""
    assert article_extractor._normalize_design_family(design.value) == design.value
    assert article_extractor._normalize_design_family(
        design.value.upper().replace("_", " ")
    ) == design.value


@pytest.mark.parametrize("supplied", [None, "", "not-a-design"])
def test_unmatched_design_family_remains_unclear(supplied: str | None) -> None:
    """Input without an exact or substring alias retains the unclear fallback."""
    assert article_extractor._normalize_design_family(supplied) == "unclear"


def test_weighted_evidence_vocabulary_matches_canonical_enum() -> None:
    """A class added to either owner must join the normalization regression set."""
    assert set(EVIDENCE_WEIGHTS) == {member.value for member in EvidenceStrength}


@pytest.mark.parametrize("strength", EVIDENCE_WEIGHTS)
def test_evidence_strength_normalization_is_idempotent(strength: str) -> None:
    """Preserve every weighted canonical class, including repeated normalization."""
    assert article_extractor._normalize_evidence_strength(strength) == strength
    assert article_extractor._normalize_evidence_strength(
        strength.upper().replace("_", " ")
    ) == strength


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("event_study", "quasi_natural_event"),
        ("event-study", "quasi_natural_event"),
        ("structural_model", "structural"),
        ("time_series_cointegration", "structural"),
    ],
)
def test_evidence_alias_outputs_survive_normalization(supplied: str, expected: str) -> None:
    """An accepted alias must not degrade when its canonical output is normalized again."""
    normalized = article_extractor._normalize_evidence_strength(supplied)
    assert normalized == expected
    assert article_extractor._normalize_evidence_strength(normalized) == expected


@pytest.mark.parametrize("supplied", [None, "", "not-a-class", "rct_unrecognized"])
def test_unrecognized_evidence_strength_remains_unknown(supplied: str | None) -> None:
    """Outside canonical names and explicit aliases, retain the exact unknown fallback."""
    assert article_extractor._normalize_evidence_strength(supplied) == "unknown"


@pytest.mark.parametrize("strength", EVIDENCE_WEIGHTS)
def test_batch_claim_normalization_preserves_candidate_evidence(strength: str) -> None:
    """Exercise the batch import, claim normalizer and serialized candidate envelope."""
    normalized = _normalize_extraction_payload(
        work={"id": "synthetic:normalizer-regression"},
        parsed={
            "causal_claims": [
                {
                    "cause_variable": "tax rate",
                    "effect_variable": "employment",
                    "evidence_strength": strength,
                    "supporting_spans": [{"section": "results", "text": "Employment fell."}],
                }
            ]
        },
        model="stub-no-model-call",
        usage={},
        evidence_bundle={},
        source_kind="fulltext",
    )
    (claim,) = normalized["causal_claims"]
    assert claim.evidence_strength.value == strength
    transport = article_extractor.serialize_rich_claim_occurrence_vocabulary(
        claim, record_extraction_mode="resolve_extract"
    )
    restored = type(transport).model_validate_json(transport.model_dump_json())
    assert restored.vocabulary.evidence_strength.value == strength
    assert restored.vocabulary.evidence_strength_status.value == "candidate"
    assert EVIDENCE_WEIGHTS[restored.vocabulary.evidence_strength.value] == EVIDENCE_WEIGHTS[
        strength
    ]
