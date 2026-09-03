"""Contract tests for the inactive academic claim-vocabulary envelope."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
from polisyos.ir.analytics.literature import (
    CausalClaim,
    ClaimVocabularyAxisStatus,
    LegacyFiveFieldClaimOccurrence,
    VersionedClaimVocabularyEnvelope,
    adapt_legacy_claim_occurrence_as_v2_absence,
)


def _legacy_occurrence() -> dict[str, str]:
    """Return one deterministic five-field legacy occurrence."""

    return {
        "cause": "tax rate",
        "effect": "employment",
        "direction": "negative",
        "strength": "moderate",
        "mechanism": "",
    }


def test_v2_envelope_rejects_generic_strength_and_legacy_adapter_is_explicit() -> None:
    """Prevent generic legacy labels from entering the strict v2 payload."""

    v2_payload = {
        "schema_version": "2.0",
        "cause": "tax rate",
        "effect": "employment",
        "strength": "moderate",
    }

    with pytest.raises(ValidationError, match="strength"):
        VersionedClaimVocabularyEnvelope.model_validate(v2_payload)

    adapted = adapt_legacy_claim_occurrence_as_v2_absence(_legacy_occurrence())

    assert adapted.legacy_strength_label == "moderate"
    assert VersionedClaimVocabularyEnvelope.model_validate_json(adapted.model_dump_json()) == adapted
    assert json.loads(adapted.model_dump_json())["schema_version"] == "2.0"


def test_legacy_moderate_is_audited_without_typed_axis_or_false_default() -> None:
    """Keep ambiguous legacy labels as observations instead of typed conclusions."""

    adapted = adapt_legacy_claim_occurrence_as_v2_absence(
        _legacy_occurrence(),
        record_extraction_mode="deterministic",
    )

    assert adapted.design_family_hint is None
    assert adapted.evidence_strength is None
    assert adapted.claim_extraction_confidence is None
    assert adapted.source_basis is None
    assert adapted.design_family_hint_status is ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    assert adapted.evidence_strength_status is ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    assert (
        adapted.claim_extraction_confidence_status
        is ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    )
    assert adapted.source_basis_status is ClaimVocabularyAxisStatus.NOT_ESTABLISHED
    assert adapted.legacy_strength_label == "moderate"
    assert adapted.record_extraction_mode == "deterministic"


def test_legacy_adapter_ignores_parent_design_and_record_confidence() -> None:
    """Ensure the adapter has no parent-paper or record-confidence inference input."""

    with pytest.raises(TypeError, match="study_design"):
        adapt_legacy_claim_occurrence_as_v2_absence(  # type: ignore[call-arg]
            _legacy_occurrence(),
            study_design="rct",
        )

    with pytest.raises(TypeError, match="extraction_confidence"):
        adapt_legacy_claim_occurrence_as_v2_absence(  # type: ignore[call-arg]
            _legacy_occurrence(),
            extraction_confidence=0.99,
        )


def test_legacy_adapter_rejects_missing_or_rich_occurrence_fields() -> None:
    """Reject malformed and richer inputs instead of silently truncating them."""

    missing_cause = _legacy_occurrence()
    del missing_cause["cause"]
    extra_occurrence = {**_legacy_occurrence(), "unexpected": "value"}
    rich_occurrence = {**_legacy_occurrence(), "claim_type": "causal_claim"}

    with pytest.raises(ValidationError, match="cause"):
        adapt_legacy_claim_occurrence_as_v2_absence(missing_cause)
    with pytest.raises(ValidationError, match="unexpected"):
        adapt_legacy_claim_occurrence_as_v2_absence(extra_occurrence)
    with pytest.raises(ValidationError, match="claim_type"):
        adapt_legacy_claim_occurrence_as_v2_absence(rich_occurrence)


def test_existing_v1_work_record_and_causal_claim_paths_are_not_activated() -> None:
    """Keep the legacy transport and v1 normalizer independent from the envelope."""

    legacy = _legacy_occurrence()
    record = WorkRecord(id="W1", title="Legacy record", causal_claims=[legacy])
    claim = CausalClaim.from_payload({"cause": "tax rate", "effect": "employment"})
    envelope = adapt_legacy_claim_occurrence_as_v2_absence(legacy)
    legacy_json = LegacyFiveFieldClaimOccurrence.model_validate(legacy).model_dump_json()

    assert record.causal_claims == [legacy]
    assert json.loads(record.model_dump_json())["causal_claims"] == [legacy]
    assert json.loads(legacy_json) == legacy
    assert "schema_version" not in json.loads(legacy_json)
    with pytest.raises(ValidationError):
        WorkRecord(id="W1", title="Envelope record", causal_claims=[envelope])
    assert claim.cause_variable == "tax rate"
    assert claim.effect_variable == "employment"
    assert claim.evidence_strength.value == "unknown"
