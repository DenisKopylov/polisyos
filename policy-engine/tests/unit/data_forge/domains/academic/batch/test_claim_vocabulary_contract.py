"""Contract tests for the inactive academic claim-vocabulary envelope."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.academic.knowledge.types import (
    WorkRecord,
    adapt_jsonl_work_record_claims,
)
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


def test_persisted_v1_work_record_is_adapted_before_strict_work_record_admission() -> None:
    """Require the explicit reader adapter at the v1/v2 WorkRecord boundary."""

    legacy = _legacy_occurrence()
    with pytest.raises(ValueError):
        WorkRecord(id="W1", title="Legacy record", causal_claims=[legacy])
    record = adapt_jsonl_work_record_claims(
        {"id": "W1", "title": "Legacy record", "causal_claims": [legacy]},
        provenance="legacy_jsonl",
    )
    claim = CausalClaim.from_payload({"cause": "tax rate", "effect": "employment"})
    legacy_json = LegacyFiveFieldClaimOccurrence.model_validate(legacy).model_dump_json()

    assert record.causal_claims[0].vocabulary.legacy_strength_label == "moderate"
    assert json.loads(record.model_dump_json())["causal_claims"][0]["occurrence"] == {
        key: value for key, value in legacy.items() if key != "strength"
    }
    assert json.loads(legacy_json) == legacy
    assert "schema_version" not in json.loads(legacy_json)
    with pytest.raises(ValueError):
        adapt_jsonl_work_record_claims(
            {"id": "W1", "title": "Envelope record", "causal_claims": [legacy | {"schema_version": "2.0"}]},
            provenance="legacy_jsonl",
        )
    assert claim.cause_variable == "tax rate"
    assert claim.effect_variable == "employment"
    assert claim.evidence_strength.value == "unknown"


def test_rich_persisted_v1_occurrence_preserves_metadata_but_declares_vocabulary_absent() -> None:
    """Replay historical rich occurrences without laundering vocabulary lookalikes."""

    rich_legacy = {
        **_legacy_occurrence(),
        "claim_text": "Tax rises reduce employment.",
        "claim_explicitness": "explicit",
        "supporting_span_ids": ["span-1"],
        "publish_to_graph": True,
        "design_family_hint": "rct",
        "design_family_hint_status": "candidate",
        "evidence_strength": "rct",
        "evidence_strength_status": "candidate",
        "claim_extraction_confidence": 0.97,
        "claim_extraction_confidence_status": "candidate",
        "source_basis": "fulltext",
        "source_basis_status": "candidate",
        "legacy_strength_label": "forged",
        "record_extraction_mode": "forged",
    }
    record = adapt_jsonl_work_record_claims(
        {
            "id": "W1",
            "title": "Legacy rich record",
            "extraction_mode": "llm_enriched",
            "causal_claims": [rich_legacy],
        },
        provenance="legacy_jsonl",
    )

    transport = record.causal_claims[0]
    assert transport.occurrence == {
        "cause": "tax rate",
        "effect": "employment",
        "direction": "negative",
        "mechanism": "",
        "claim_text": "Tax rises reduce employment.",
        "claim_explicitness": "explicit",
        "supporting_span_ids": ["span-1"],
        "publish_to_graph": True,
    }
    assert transport.vocabulary.legacy_strength_label == "moderate"
    assert transport.vocabulary.record_extraction_mode == "llm_enriched"
    for value_name in (
        "design_family_hint",
        "evidence_strength",
        "claim_extraction_confidence",
        "source_basis",
    ):
        assert getattr(transport.vocabulary, value_name) is None
        assert getattr(transport.vocabulary, f"{value_name}_status").value == "not_established"


@pytest.mark.parametrize(
    "claim",
    [
        {"cause": "a", "effect": "b", "direction": "positive", "strength": "moderate"},
        {
            **_legacy_occurrence(),
            "claim_vocabulary_schema_version": "2.0",
        },
        {
            **_legacy_occurrence(),
            "vocabulary": {"schema_version": "2.0"},
        },
    ],
)
def test_rich_legacy_replay_rejects_missing_discriminator_or_mixed_transport(claim) -> None:
    """Fail closed on malformed legacy and mixed nested/flat transport shapes."""

    with pytest.raises(ValueError):
        adapt_jsonl_work_record_claims(
            {"id": "W1", "title": "Bad replay", "causal_claims": [claim]},
            provenance="legacy_jsonl",
        )


def test_legacy_replay_adapter_rejects_unrecognized_provenance() -> None:
    with pytest.raises(ValueError, match="legacy provenance"):
        adapt_jsonl_work_record_claims(
            {"id": "W1", "title": "Bad provenance", "causal_claims": [_legacy_occurrence()]},
            provenance="live",  # type: ignore[arg-type]
        )
