from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.chronology import PredicateClass
from polisyos.core.contracts.scope_adjudication import (
    SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
    SCOPE_ADJUDICATION_RECORD_KIND,
    PersistedScopeAdjudicationRecord,
    PersistedScopePredicateEvidence,
    ScopeAdjudicationNonReceipt,
    ScopeAdjudicationPlane,
    ScopeAdjudicationPredicate,
    ScopeAdjudicationProducer,
    ScopeAdjudicationRequest,
    ScopeAdjudicationRuling,
    ScopePredicateEvidence,
    consume_scope_adjudication_record,
    persist_scope_predicate_evidence,
)

_VALID_AT = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _put_bytes(store: FileSystemCAS, payload: bytes, *, kind: str) -> ArtifactRef:
    return store.put_bytes(
        payload,
        PutOptions(kind=kind, media_type="application/octet-stream"),
    )


@dataclass(slots=True)
class _FixturePredicateResolver:
    store: FileSystemCAS
    verifier_provenance_ref: ArtifactRef
    rule_version_ref: ArtifactRef
    outcomes: dict[str, tuple[bool, bool, bool]]
    predicate_class: PredicateClass = "independently_reconciled"
    plane_overrides: dict[ScopeAdjudicationPredicate, ScopeAdjudicationPlane] = field(
        default_factory=dict
    )

    def resolve_scope_predicate_evidence(
        self,
        *,
        request: ScopeAdjudicationRequest,
    ) -> tuple[PersistedScopePredicateEvidence, ...]:
        predicate_order = (
            ScopeAdjudicationPredicate.ABSENCE_MAKES_OUR_PUBLISHED_CLAIM_FALSE,
            ScopeAdjudicationPredicate.OUTPUT_CHANGES_OUR_CLAIM_VALIDITY,
            ScopeAdjudicationPredicate.CHANGES_ONLY_WHO_ANSWERS_FOR_OUR_CLAIMS,
        )
        values = self.outcomes[request.candidate_function_id]
        receipts: list[PersistedScopePredicateEvidence] = []
        for predicate, outcome in zip(predicate_order, values, strict=True):
            evidence_ref = _put_bytes(
                self.store,
                (
                    f"{request.candidate_function_id}:{predicate.value}:"
                    f"{str(outcome).lower()}"
                ).encode(),
                kind="policyos.scope_predicate_evidence",
            )
            receipts.append(
                persist_scope_predicate_evidence(
                    self.store,
                    ScopePredicateEvidence(
                        candidate_function_id=request.candidate_function_id,
                        target_ref=request.target_ref,
                        target_content_hash=request.target_content_hash,
                        plane=self.plane_overrides.get(predicate, request.plane),
                        predicate=predicate,
                        outcome=outcome,
                        predicate_class=self.predicate_class,
                        evidence_ref=evidence_ref,
                        evidence_content_hash=str(evidence_ref.artifact_id),
                        verifier_provenance_ref=self.verifier_provenance_ref,
                        verifier_provenance_content_hash=str(
                            self.verifier_provenance_ref.artifact_id
                        ),
                        rule_version_ref=self.rule_version_ref,
                        rule_version_content_hash=str(self.rule_version_ref.artifact_id),
                        authority_purpose=SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
                        observed_at=_VALID_AT,
                    ),
                )
            )
        return tuple(receipts)


def _request(
    *,
    candidate_function_id: str,
    target_ref: ArtifactRef,
    rule_version_ref: ArtifactRef,
    external_owner: str | None,
    integration_contract_ref: ArtifactRef | None,
) -> ScopeAdjudicationRequest:
    return ScopeAdjudicationRequest(
        candidate_function_id=candidate_function_id,
        candidate_description=f"Boundary candidate {candidate_function_id}",
        target_ref=target_ref,
        target_content_hash=str(target_ref.artifact_id),
        plane=ScopeAdjudicationPlane.PUBLIC_PROJECTION,
        authority_purpose=SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
        rule_version_ref=rule_version_ref,
        rule_version_content_hash=str(rule_version_ref.artifact_id),
        rule_source_path=(
            "docs/system-design-decisions/"
            "policyos-identity-and-custody-boundary.md"
        ),
        rule_coordinate="§5",
        rule_version="2026-08-30",
        rule_effective_at=datetime(2026, 7, 20, tzinfo=UTC),
        valid_at=_VALID_AT,
        reconsider_on=datetime(2027, 8, 30, tzinfo=UTC),
        audiences=("internal_governance", "audit"),
        external_owner=external_owner,
        integration_contract_ref=integration_contract_ref,
        integration_contract_content_hash=(
            str(integration_contract_ref.artifact_id)
            if integration_contract_ref is not None
            else None
        ),
    )


def _producer(
    *,
    store: FileSystemCAS,
    resolver: _FixturePredicateResolver,
    verifier_provenance_ref: ArtifactRef,
    producer_provenance_ref: ArtifactRef,
) -> ScopeAdjudicationProducer:
    return ScopeAdjudicationProducer(
        store=store,
        evidence_resolver=resolver,
        appointed_verifier_provenance_ref=verifier_provenance_ref,
        producer_provenance_ref=producer_provenance_ref,
    )


def test_four_way_ruling_is_produced_consumed_and_plane_specific(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_version_ref = _put_bytes(
        store,
        b"policyos identity and custody boundary ratified 2026-08-30",
        kind="policyos.scope_adjudication_rule",
    )
    verifier_provenance_ref = _put_bytes(
        store,
        b"appointed scope predicate verifier",
        kind="policyos.scope_predicate_verifier",
    )
    producer_provenance_ref = _put_bytes(
        store,
        b"scope adjudication producer build",
        kind="policyos.scope_adjudication_producer",
    )
    integration_contract_ref = _put_bytes(
        store,
        b"typed fail-closed external evidence contract",
        kind="policyos.scope_integration_contract",
    )
    outcomes = {
        "candidate-own": (True, True, True),
        "candidate-integrate": (False, True, False),
        "candidate-observe": (False, False, True),
        "candidate-out-of-scope": (False, False, False),
    }
    resolver = _FixturePredicateResolver(
        store=store,
        verifier_provenance_ref=verifier_provenance_ref,
        rule_version_ref=rule_version_ref,
        outcomes=outcomes,
    )
    producer = _producer(
        store=store,
        resolver=resolver,
        verifier_provenance_ref=verifier_provenance_ref,
        producer_provenance_ref=producer_provenance_ref,
    )
    expected = {
        "candidate-own": ScopeAdjudicationRuling.OWN,
        "candidate-integrate": ScopeAdjudicationRuling.INTEGRATE,
        "candidate-observe": ScopeAdjudicationRuling.OBSERVE,
        "candidate-out-of-scope": ScopeAdjudicationRuling.OUT_OF_SCOPE,
    }

    for candidate_function_id, expected_ruling in expected.items():
        external = expected_ruling is not ScopeAdjudicationRuling.OWN
        target_ref = _put_bytes(
            store,
            f"scope target {candidate_function_id}".encode(),
            kind="policyos.scope_adjudication_target",
        )
        request = _request(
            candidate_function_id=candidate_function_id,
            target_ref=target_ref,
            rule_version_ref=rule_version_ref,
            external_owner="appointed external institution" if external else None,
            integration_contract_ref=integration_contract_ref if external else None,
        )

        persisted = producer.produce(request=request)
        assert isinstance(persisted, PersistedScopeAdjudicationRecord)
        consumed = consume_scope_adjudication_record(
            store,
            persisted,
            expected_candidate_function_id=candidate_function_id,
            expected_target_ref=target_ref,
            expected_target_content_hash=str(target_ref.artifact_id),
            expected_plane=request.plane,
            expected_rule_version_ref=rule_version_ref,
            expected_authority_purpose=SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
            appointed_verifier_provenance_ref=verifier_provenance_ref,
            valid_at_time=_VALID_AT,
            as_known_at=persisted.record.recorded_at,
        )

        assert persisted.record_content_hash == str(persisted.record_ref.artifact_id)
        assert consumed.ruling is expected_ruling
        assert consumed.candidate_function_id == candidate_function_id
        assert consumed.plane is ScopeAdjudicationPlane.PUBLIC_PROJECTION
        assert len(consumed.predicate_evidence_refs) == 3
        assert consumed.authority_boundary.authoritative_for == ("scope_adjudication",)
        assert "institutional_execution" in consumed.authority_boundary.may_not_use_for

        with pytest.raises(
            ValueError,
            match="scope_adjudication_consumer_binding_mismatch",
        ):
            consume_scope_adjudication_record(
                store,
                persisted,
                expected_candidate_function_id=candidate_function_id,
                expected_target_ref=target_ref,
                expected_target_content_hash=str(target_ref.artifact_id),
                expected_plane=request.plane,
                expected_rule_version_ref=rule_version_ref,
                expected_authority_purpose=SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
                appointed_verifier_provenance_ref=verifier_provenance_ref,
                valid_at_time=_VALID_AT,
                as_known_at=_VALID_AT,
            )


def test_scope_adjudication_rejects_mixed_planes_before_record_persistence(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _put_bytes(store, b"rule", kind="policyos.scope_adjudication_rule")
    verifier_ref = _put_bytes(store, b"verifier", kind="policyos.scope_predicate_verifier")
    producer_ref = _put_bytes(store, b"producer", kind="policyos.scope_adjudication_producer")
    resolver = _FixturePredicateResolver(
        store=store,
        verifier_provenance_ref=verifier_ref,
        rule_version_ref=rule_ref,
        outcomes={"mixed-plane": (False, False, False)},
        plane_overrides={
            ScopeAdjudicationPredicate.OUTPUT_CHANGES_OUR_CLAIM_VALIDITY: (
                ScopeAdjudicationPlane.EVIDENCE_ADMISSION
            )
        },
    )

    result = _producer(
        store=store,
        resolver=resolver,
        verifier_provenance_ref=verifier_ref,
        producer_provenance_ref=producer_ref,
    ).produce(
        request=_request(
            candidate_function_id="mixed-plane",
            target_ref=_put_bytes(
                store,
                b"mixed plane target",
                kind="policyos.scope_adjudication_target",
            ),
            rule_version_ref=rule_ref,
            external_owner="external owner",
            integration_contract_ref=_put_bytes(
                store,
                b"contract",
                kind="policyos.scope_integration_contract",
            ),
        )
    )

    assert isinstance(result, ScopeAdjudicationNonReceipt)
    assert result.code == "scope_predicate_plane_mismatch"

    assert all(
        store.get_manifest(artifact_id).kind != SCOPE_ADJUDICATION_RECORD_KIND
        for artifact_id in store.iter_artifact_ids()
    )


def test_scope_adjudication_rejects_consumer_asserted_predicates(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _put_bytes(store, b"rule", kind="policyos.scope_adjudication_rule")
    verifier_ref = _put_bytes(store, b"verifier", kind="policyos.scope_predicate_verifier")
    producer_ref = _put_bytes(store, b"producer", kind="policyos.scope_adjudication_producer")
    resolver = _FixturePredicateResolver(
        store=store,
        verifier_provenance_ref=verifier_ref,
        rule_version_ref=rule_ref,
        outcomes={"declared-premise": (True, False, False)},
        predicate_class="consumer_asserted",
    )

    result = _producer(
        store=store,
        resolver=resolver,
        verifier_provenance_ref=verifier_ref,
        producer_provenance_ref=producer_ref,
    ).produce(
        request=_request(
            candidate_function_id="declared-premise",
            target_ref=_put_bytes(
                store,
                b"declared premise target",
                kind="policyos.scope_adjudication_target",
            ),
            rule_version_ref=rule_ref,
            external_owner=None,
            integration_contract_ref=None,
        )
    )

    assert isinstance(result, ScopeAdjudicationNonReceipt)
    assert result.code == "scope_predicate_not_established"


def test_scope_adjudication_consumer_rejects_shaped_record_ref(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _put_bytes(store, b"rule", kind="policyos.scope_adjudication_rule")
    verifier_ref = _put_bytes(store, b"verifier", kind="policyos.scope_predicate_verifier")
    producer_ref = _put_bytes(store, b"producer", kind="policyos.scope_adjudication_producer")
    resolver = _FixturePredicateResolver(
        store=store,
        verifier_provenance_ref=verifier_ref,
        rule_version_ref=rule_ref,
        outcomes={"shaped-record": (True, False, False)},
    )
    target_ref = _put_bytes(
        store,
        b"shaped record target",
        kind="policyos.scope_adjudication_target",
    )
    request = _request(
        candidate_function_id="shaped-record",
        target_ref=target_ref,
        rule_version_ref=rule_ref,
        external_owner=None,
        integration_contract_ref=None,
    )
    persisted = _producer(
        store=store,
        resolver=resolver,
        verifier_provenance_ref=verifier_ref,
        producer_provenance_ref=producer_ref,
    ).produce(request=request)
    assert isinstance(persisted, PersistedScopeAdjudicationRecord)
    shaped = persisted.model_copy(
        update={
            "record_ref": persisted.record_ref.model_copy(
                update={"kind": "policyos.looks_like_scope_adjudication"}
            )
        }
    )

    with pytest.raises(ValueError, match="scope_adjudication_record_profile_mismatch"):
        consume_scope_adjudication_record(
            store,
            shaped,
            expected_candidate_function_id=request.candidate_function_id,
            expected_target_ref=target_ref,
            expected_target_content_hash=str(target_ref.artifact_id),
            expected_plane=request.plane,
            expected_rule_version_ref=rule_ref,
            expected_authority_purpose=SCOPE_ADJUDICATION_AUTHORITY_PURPOSE,
            appointed_verifier_provenance_ref=verifier_ref,
            valid_at_time=_VALID_AT,
            as_known_at=persisted.record.recorded_at,
        )
