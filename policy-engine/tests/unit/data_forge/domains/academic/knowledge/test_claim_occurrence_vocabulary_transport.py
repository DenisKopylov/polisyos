"""Behavioral contracts for the inactive claim-vocabulary composite."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.academic.knowledge.types import (
    CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN,
    CLAIM_VOCABULARY_DISCRIMINATOR_VALUE,
    CLAIM_VOCABULARY_STORE_COLUMNS,
    ClaimOccurrenceVocabularyTransport,
    admit_candidate_claim_vocabulary,
    candidate_claim_vocabulary_store_values,
)
from polisyos.ir.analytics.literature import (
    ClaimVocabularyAxisStatus,
    DesignFamily,
    EvidenceStrength,
    SourceBasis,
    VersionedClaimVocabularyEnvelope,
    adapt_legacy_claim_occurrence_as_v2_absence,
)


def _sidecar() -> VersionedClaimVocabularyEnvelope:
    """Return a deliberately disagreeing, valid candidate sidecar."""

    return VersionedClaimVocabularyEnvelope(
        cause="tax rate",
        effect="employment",
        direction="negative",
        mechanism="labour cost",
        design_family_hint=DesignFamily.OLS,
        design_family_hint_status=ClaimVocabularyAxisStatus.CANDIDATE,
        evidence_strength=EvidenceStrength.RCT,
        evidence_strength_status=ClaimVocabularyAxisStatus.CANDIDATE,
        claim_extraction_confidence=0.23,
        claim_extraction_confidence_status=ClaimVocabularyAxisStatus.CANDIDATE,
        source_basis=SourceBasis.ABSTRACT_ONLY,
        source_basis_status=ClaimVocabularyAxisStatus.CANDIDATE,
    )


def _rich_occurrence() -> dict[str, object]:
    """Return non-vocabulary occurrence content that must survive unchanged."""

    return {
        "cause": "tax rate",
        "effect": "employment",
        "direction": "negative",
        "mechanism": "labour cost",
        "claim_type": "causal_claim",
        "effect_size": -0.12,
        "supporting_span_ids": ["r-1"],
        "extraction_warnings": ["candidate_only"],
        "publish_blockers": ["needs_review"],
        "future_additive_json": {"nested": ["retained", 7]},
    }


def test_composite_retains_non_vocabulary_occurrence_content_without_aliasing() -> None:
    """Catch a transport that drops rich metadata or changes independent axes."""

    occurrence = _rich_occurrence()
    transport = ClaimOccurrenceVocabularyTransport(occurrence=occurrence, vocabulary=_sidecar())

    assert transport.occurrence == occurrence
    assert transport.vocabulary.design_family_hint is DesignFamily.OLS
    assert transport.vocabulary.evidence_strength is EvidenceStrength.RCT
    assert transport.vocabulary.claim_extraction_confidence == pytest.approx(0.23)
    assert admit_candidate_claim_vocabulary(transport) == transport


@pytest.mark.parametrize(
    "forbidden_key",
    [
        "strength",
        "design_family_hint",
        "evidence_strength",
        "claim_extraction_confidence",
        "source_basis",
        "design_family_hint_status",
        "evidence_strength_status",
        "claim_extraction_confidence_status",
        "source_basis_status",
        "legacy_strength_label",
        "record_extraction_mode",
    ],
)
def test_composite_rejects_generic_and_duplicated_vocabulary_keys(forbidden_key: str) -> None:
    """Catch a v2 occurrence that retains a second vocabulary owner."""

    occurrence = _rich_occurrence()
    occurrence[forbidden_key] = "moderate"

    with pytest.raises(ValidationError, match=forbidden_key):
        ClaimOccurrenceVocabularyTransport(occurrence=occurrence, vocabulary=_sidecar())


def test_composite_rejects_missing_or_mismatched_identity_fields() -> None:
    """Catch a sidecar that is not bound to the occurrence it accompanies."""

    missing_cause = _rich_occurrence()
    del missing_cause["cause"]
    mismatched_effect = _rich_occurrence()
    mismatched_effect["effect"] = "informality"

    with pytest.raises(ValidationError, match="cause"):
        ClaimOccurrenceVocabularyTransport(occurrence=missing_cause, vocabulary=_sidecar())
    with pytest.raises(ValidationError, match="effect"):
        ClaimOccurrenceVocabularyTransport(occurrence=mismatched_effect, vocabulary=_sidecar())


def test_legacy_adapter_sidecar_pairs_with_a_legacy_occurrence_only_after_strength_is_removed() -> None:
    """Keep the historical literal audit-only when constructing the v2 composite."""

    legacy = {
        "cause": "tax rate",
        "effect": "employment",
        "direction": "negative",
        "strength": "moderate",
        "mechanism": "labour cost",
    }
    occurrence = {key: value for key, value in legacy.items() if key != "strength"}
    transport = ClaimOccurrenceVocabularyTransport(
        occurrence=occurrence,
        vocabulary=adapt_legacy_claim_occurrence_as_v2_absence(legacy),
    )

    assert "strength" not in transport.occurrence
    assert transport.vocabulary.legacy_strength_label == "moderate"


def test_inactive_store_values_revalidate_and_preserve_each_candidate_axis() -> None:
    """Catch Task-3 storage prep that invents generic strength or merges axes."""

    transport = ClaimOccurrenceVocabularyTransport(
        occurrence=_rich_occurrence(),
        vocabulary=_sidecar().model_copy(update={"legacy_strength_label": "moderate"}),
    )

    assert CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN == "claim_vocabulary_schema_version"
    assert CLAIM_VOCABULARY_DISCRIMINATOR_VALUE == "2.0"
    assert CLAIM_VOCABULARY_STORE_COLUMNS == (
        "design_family_hint",
        "design_family_hint_status",
        "evidence_strength",
        "evidence_strength_status",
        "claim_extraction_confidence",
        "claim_extraction_confidence_status",
        "source_basis",
        "source_basis_status",
        "legacy_strength_label",
        "record_extraction_mode",
    )
    assert candidate_claim_vocabulary_store_values(transport) == {
        "claim_vocabulary_schema_version": "2.0",
        "design_family_hint": "ols",
        "design_family_hint_status": "candidate",
        "evidence_strength": "rct",
        "evidence_strength_status": "candidate",
        "claim_extraction_confidence": 0.23,
        "claim_extraction_confidence_status": "candidate",
        "source_basis": "abstract_only",
        "source_basis_status": "candidate",
        "legacy_strength_label": "moderate",
        "record_extraction_mode": None,
    }
