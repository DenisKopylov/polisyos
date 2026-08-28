"""Behavioral tests for the read-only epoch/staleness projection compiler."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.decision_validity import (
    EpochValidityGateNonReceipt,
    EpochValidityN9Projection,
)
from polisyos.core.contracts.runtime import EpochDerivedRecomputeView, TemporalScope
from polisyos.runtime.quality.epoch_staleness_projection import (
    compile_epoch_staleness_projection,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    AdvisoryPerturbationEvent,
    DerivationRecipeBinding,
    EpochDependencyDenominatorReceipt,
    EpochDependencyEdge,
    EpochDependencyGraph,
    EpochTransitionSigningNonReceipt,
    _semantic_hash,
    bind_certificate_to_epoch,
    build_epoch_validity_transition,
    resolve_owner_target_dispositions,
)
from polisyos.runtime.quality.semantic_epoch import SemanticEpochManifest
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    IncidentPerturbation,
    persist_governance_monitor_event,
)


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


def _ref(label: str, *, kind: str = "test.artifact") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_digest(label),
        kind=kind,
        media_type="application/json",
    )


def _compile_absence(*, observed_at: datetime, valid_at: datetime | None = None):
    query_ref = _digest("absence-query")
    return compile_epoch_staleness_projection(
        run_id="run-ds18-absence",
        decision_packet_ref=_ref("absence-packet", kind="scientist.decision_packet"),
        temporal_scope=TemporalScope(valid_at=valid_at),
        requested_query_context_ref=query_ref,
        owner_as_of=None,
        observed_at=observed_at,
        epoch_gate=EpochValidityGateNonReceipt(
            status="not_established",
            code="policy_admission_missing",
            subject_ref=_ref("absence-subject", kind="chronology.epoch_validity_subject"),
            requested_query_context_ref=query_ref,
        ),
        transition=EpochTransitionSigningNonReceipt(
            status="not_established",
            code="epoch_transition_signer_not_established",
            predicate_class="not_established",
        ),
    )


def test_real_signer_nonreceipts_render_two_distinct_first_class_absences() -> None:
    projection = _compile_absence(
        observed_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
    )

    assert projection.status == "not_established"
    assert projection.owner_as_of is None
    assert projection.owner_time_reason == "owner_time_not_established"
    assert {row.refusal_code for row in projection.institutional_absences} == {
        "policy_admission_missing",
        "epoch_transition_signer_not_established",
    }
    assert {row.title for row in projection.institutional_absences} == {
        "Authority not appointed"
    }
    assert all(
        row.appointment_is_closure_precondition is False
        for row in projection.institutional_absences
    )

    assert len(projection.engineering_absences) == 1
    engineering = projection.engineering_absences[0]
    assert engineering.title == "Engineering capability not wired"
    assert engineering.missing_labels == ("producer_missing", "bridge_missing")
    assert engineering.candidate_owner_module == (
        "polisyos.runtime.quality.derived_observations"
    )
    assert engineering.institutional_dependency is False
    assert projection.open_world_risk.promotion_frozen is True


def test_server_observation_time_is_not_owner_time_or_semantic_identity() -> None:
    first = _compile_absence(observed_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC))
    reread = _compile_absence(observed_at=datetime(2026, 8, 27, 12, 5, tzinfo=UTC))
    changed_scope = _compile_absence(
        observed_at=datetime(2026, 8, 27, 12, 5, tzinfo=UTC),
        valid_at=datetime(2026, 8, 26, 0, 0, tzinfo=UTC),
    )

    assert first.observed_at != reread.observed_at
    assert first.owner_as_of is None and reread.owner_as_of is None
    assert first.projection_semantic_hash == reread.projection_semantic_hash
    assert reread.projection_semantic_hash != changed_scope.projection_semantic_hash


def test_fake_completed_recompute_receipt_fails_closed() -> None:
    with pytest.raises(ValidationError, match="content-bound owner evidence"):
        EpochDerivedRecomputeView(
            status="completed",
            predicate_provenance="consumer_asserted",
        )
    with pytest.raises(ValidationError, match="positive owner evidence"):
        EpochDerivedRecomputeView(
            status="not_established",
            predicate_provenance="not_established",
            evidence_ref=_ref("fake-recompute", kind="derived.recompute_receipt"),
            evidence_content_hash=_digest("fake-recompute-bytes"),
        )


def test_epoch_change_propagates_to_certificate_dependency_class_and_boundary(tmp_path) -> None:
    query_ref = _digest("positive-query")
    old_epoch = SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-old"))
    current_epoch = SemanticEpochManifest.model_construct(epoch_ref=_digest("epoch-current"))
    recipe = DerivationRecipeBinding(
        recipe_ref=_ref("recipe", kind="epoch.derivation_recipe"),
        recipe_content_hash=_digest("recipe-content"),
        recipe_schema_profile_ref=_digest("recipe-schema"),
        input_roles=("revised_input",),
    )
    certificate = bind_certificate_to_epoch(
        certificate_ref=_ref("certificate", kind="decision.certificate"),
        certificate_content_hash=_digest("certificate-content"),
        epoch=old_epoch,
        input_certificate_refs=(_ref("input-certificate", kind="decision.certificate"),),
        recipe=recipe,
        canonical_producer_ref="producer://decision-validity",
        authority_purpose="decision_validity",
        native_coordinate_refs=(_digest("valid-coordinate"),),
        rule_schema_profile_refs=(_digest("rule-schema"),),
    )
    revised_input = _ref("revised-input", kind="decision.input")
    edges = (
        EpochDependencyEdge(
            source_ref=revised_input,
            target_ref=certificate.certificate_ref,
            relation="invalidates",
            authority_purpose="decision_validity",
        ),
    )
    graph = EpochDependencyGraph(
        edges=edges,
        denominator_ref=_semantic_hash("polisyos.epoch.dependency-graph.v1", {"edges": edges}),
    )
    store = FileSystemCAS(tmp_path / "cas")
    monitor = persist_governance_monitor_event(
        store,
        GovernanceMonitorEvent(
            event_id="incident-revision",
            decision_packet_ref=_ref("positive-packet", kind="scientist.decision_packet"),
            event_type="incident",
            severity="warning",
            affected_claim_ids=["claim-positive"],
            reason="An exact incident revised one certificate input.",
            perturbation=IncidentPerturbation(
                incident_report_ref=_ref("incident", kind="scientist.incident_report")
            ),
            advisory_posture="review_required",
        ),
    )
    advisory = AdvisoryPerturbationEvent(
        event_ref=monitor.event_ref,
        target_ref=revised_input,
        source_class="incident",
        scope="dependency_descendants",
        event_kind="invalidate",
        authority_purpose="decision_validity",
        observed_epoch_ref=old_epoch.epoch_ref,
    )
    vector = resolve_owner_target_dispositions(
        advisory_events=(advisory,),
        owner_dispositions=(),
        dependency_graph=graph,
    )
    denominator_payload = {
        "certificate_bindings": (certificate,),
        "dependency_graph": graph,
        "target_refs": (certificate.certificate_ref,),
    }
    denominator = EpochDependencyDenominatorReceipt(
        denominator_ref=_semantic_hash(
            "polisyos.epoch.dependency-denominator.v1",
            denominator_payload,
        ),
        **denominator_payload,
        predicate_class="independently_reconciled",
    )
    transition = build_epoch_validity_transition(
        previous_epoch=old_epoch,
        current_epoch=current_epoch,
        certificates=(certificate,),
        dependency_graph=graph,
        target_vector=vector,
        dependency_denominator_ref=denominator.denominator_ref,
        adjudication_denominator_ref=_digest("adjudication-denominator"),
        requested_query_context_ref=query_ref,
        authority_purpose="decision_validity",
    )

    # The fixture intentionally uses construct for the already-verified N9 owner result;
    # the compiler marks the whole positive surface fixture_only.
    gate = EpochValidityN9Projection.model_construct(
        requested_query_context_ref=query_ref,
        status="batch_completed",
        predicate_class="independently_reconciled",
    )
    projection = compile_epoch_staleness_projection(
        run_id="run-ds18-positive",
        decision_packet_ref=monitor.event.decision_packet_ref,
        temporal_scope=TemporalScope(valid_at=datetime(2026, 8, 27, tzinfo=UTC)),
        requested_query_context_ref=query_ref,
        owner_as_of=datetime(2026, 8, 27, tzinfo=UTC),
        observed_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
        epoch_gate=gate,
        transition=transition,
        dependency_denominator=denominator,
        monitor_events=(monitor,),
        fixture_only=True,
    )

    assert projection.status == "revalidation_required"
    assert projection.certificates[0].status == "revalidation_required"
    assert projection.dependencies[0].source_classes == ("incident",)
    assert projection.dependencies[0].recompute.status == "not_established"
    assert projection.perturbations[0].source_class == "incident"
    assert projection.lineage[0].previous_epoch_ref == old_epoch.epoch_ref
    assert projection.lineage[0].current_epoch_ref == current_epoch.epoch_ref

    forged = monitor.model_copy(
        update={
            "event": monitor.event.model_copy(
                update={
                    "perturbation": monitor.event.perturbation.model_copy(
                        update={"source_class": "appeal"}
                    )
                }
            )
        }
    )
    with pytest.raises(ValueError, match="source class differs"):
        compile_epoch_staleness_projection(
            run_id="run-ds18-positive",
            decision_packet_ref=monitor.event.decision_packet_ref,
            temporal_scope=TemporalScope(),
            requested_query_context_ref=query_ref,
            owner_as_of=datetime(2026, 8, 27, tzinfo=UTC),
            observed_at=datetime(2026, 8, 27, 12, 0, tzinfo=UTC),
            epoch_gate=gate,
            transition=transition,
            dependency_denominator=denominator,
            monitor_events=(forged,),
            fixture_only=True,
        )
