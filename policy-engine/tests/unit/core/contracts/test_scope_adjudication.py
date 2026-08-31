from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

import polisyos.core.contracts as core_contracts
from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.contracts.scope_adjudication import (
    SCOPE_ADJUDICATION_PROHIBITED_USES,
    ScopeAdjudicationCandidate,
    ScopeAdjudicationPlane,
    ScopeAdjudicationPredicate,
    ScopeAdjudicationRuling,
    ScopePredicateObservation,
    build_scope_adjudication_candidate,
    verify_scope_adjudication_candidate,
)

_VALID_AT = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
_KNOWN_AT = datetime(2026, 8, 31, 12, 5, tzinfo=UTC)


def _ref(payload: bytes, *, kind: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID(f"sha256:{hashlib.sha256(payload).hexdigest()}"),
        kind=kind,
        media_type="application/json",
    )


def _observation(
    predicate: ScopeAdjudicationPredicate,
    value: bool | None,
    *,
    plane: ScopeAdjudicationPlane = ScopeAdjudicationPlane.PUBLIC_PROJECTION,
    predicate_class: str = "recomputed",
) -> ScopePredicateObservation:
    if value is None:
        return ScopePredicateObservation(
            plane=plane,
            predicate=predicate,
            value=None,
            predicate_class="not_established",
            evidence_ref=None,
            evidence_content_digest=None,
            limitation_code="scope_predicate_value_not_established",
        )
    evidence_ref = _ref(
        f"{predicate.value}:{value}".encode(), kind="scope-predicate-observation"
    )
    return ScopePredicateObservation(
        plane=plane,
        predicate=predicate,
        value=value,
        predicate_class=predicate_class,
        evidence_ref=evidence_ref,
        evidence_content_digest=str(evidence_ref.artifact_id),
        limitation_code=(
            None
            if predicate_class in {"recomputed", "independently_reconciled"}
            else "scope_predicate_authority_not_established"
        ),
    )


def _candidate(
    values: tuple[bool | None, bool | None, bool | None],
    *,
    observations: tuple[ScopePredicateObservation, ...] | None = None,
) -> ScopeAdjudicationCandidate:
    subject_ref = _ref(b"candidate function", kind="scope-subject")
    rule_ref = _ref(b"ratified four-way rule", kind="scope-rule")
    predicates = tuple(ScopeAdjudicationPredicate)
    resolved = observations or tuple(
        _observation(predicate, value)
        for predicate, value in zip(predicates, values, strict=True)
    )
    return build_scope_adjudication_candidate(
        candidate_function_id="public-signature-custody",
        candidate_description="Custody boundary for a public signature function",
        plane=ScopeAdjudicationPlane.PUBLIC_PROJECTION,
        subject_ref=subject_ref,
        subject_content_digest=str(subject_ref.artifact_id),
        rule_ref=rule_ref,
        rule_content_digest=str(rule_ref.artifact_id),
        rule_version="policyos-identity-and-custody-boundary@2026-07-20",
        rule_effective_at=datetime(2026, 7, 20, tzinfo=UTC),
        valid_at=_VALID_AT,
        known_at=_KNOWN_AT,
        observations=resolved,
    )


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((True, True, True), ScopeAdjudicationRuling.OWN),
        ((False, True, True), ScopeAdjudicationRuling.INTEGRATE),
        ((False, False, True), ScopeAdjudicationRuling.OBSERVE),
        ((False, False, False), ScopeAdjudicationRuling.OUT_OF_SCOPE),
    ],
)
def test_candidate_derives_ordered_four_way_proposals_without_authority(
    values: tuple[bool, bool, bool],
    expected: ScopeAdjudicationRuling,
) -> None:
    candidate = _candidate(values)

    assert candidate.proposed_ruling is expected
    assert candidate.status == "candidate_only"
    assert candidate.authority_effect == "none"
    assert candidate.closure_effect == "none"
    assert candidate.authoritative_for == ()
    assert candidate.may_not_use_for == SCOPE_ADJUDICATION_PROHIBITED_USES
    assert "scope_predicate_resolver_unappointed" in candidate.limitations
    assert "scope_adjudication_claim_lifecycle_consumer_unappointed" in (
        candidate.limitations
    )
    assert verify_scope_adjudication_candidate(candidate) == candidate


def test_candidate_rejects_mixed_planes_and_content_substitution() -> None:
    predicates = tuple(ScopeAdjudicationPredicate)
    mixed = tuple(
        _observation(
            predicate,
            False,
            plane=(
                ScopeAdjudicationPlane.EVIDENCE_ADMISSION
                if index == 1
                else ScopeAdjudicationPlane.PUBLIC_PROJECTION
            ),
        )
        for index, predicate in enumerate(predicates)
    )
    with pytest.raises(ValueError, match="scope_candidate_mixed_plane"):
        _candidate((False, False, False), observations=mixed)

    evidence_ref = _ref(b"evidence", kind="scope-predicate-observation")
    with pytest.raises(ValidationError, match="scope_evidence_content_digest_mismatch"):
        ScopePredicateObservation(
            plane=ScopeAdjudicationPlane.PUBLIC_PROJECTION,
            predicate=predicates[0],
            value=True,
            predicate_class="recomputed",
            evidence_ref=evidence_ref,
            evidence_content_digest="sha256:" + "0" * 64,
            limitation_code=None,
        )


def test_unestablished_predicate_is_preserved_as_a_typed_limitation() -> None:
    candidate = _candidate((False, None, True))

    assert candidate.proposed_ruling is None
    assert (
        "scope_predicate_not_established:output_changes_policyos_claim_validity"
        in candidate.limitations
    )
    unresolved = candidate.observations[1]
    assert unresolved.value is None
    assert unresolved.predicate_class == "not_established"
    assert unresolved.limitation_code == "scope_predicate_value_not_established"


def test_candidate_verifier_rejects_digest_and_semantic_substitution() -> None:
    candidate = _candidate((False, False, False))

    with pytest.raises(ValueError, match="scope_candidate_payload_digest_mismatch"):
        verify_scope_adjudication_candidate(
            candidate.model_copy(update={"payload_digest": "sha256:" + "f" * 64})
        )
    with pytest.raises(ValueError, match="scope_candidate_payload_digest_mismatch"):
        verify_scope_adjudication_candidate(
            candidate.model_copy(
                update={"candidate_description": "substituted authority claim"}
            )
        )


def test_scope_candidate_is_exported_from_the_contract_facade() -> None:
    assert core_contracts.ScopeAdjudicationCandidate is ScopeAdjudicationCandidate
