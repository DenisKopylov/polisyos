"""Behavioral tests for the owner-bound OpenWorldRisk negative path."""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Literal

import pytest

from polisyos.core import artifacts
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.contracts.c4_persisted_profiles import (
    C4_PERSISTED_PROFILE_SPECS,
    c4_canonical_mapping,
    c4_profile,
)
from polisyos.pdc import PromotionObligationClass
from polisyos.runtime.quality import epoch_validity_cascade as epoch_cascade_module
from polisyos.runtime.quality import open_world_risk as open_world_module
from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.epoch_validity_cascade import (
    BoundPromotionCandidateContextStatement,
    PromotionCandidateDenominatorStatement,
    PromotionCandidateOccurrenceStatement,
    PromotionOwnerQueryContextNonReceipt,
    _persist_model,
    _seal_completed_generation_candidate_batch,
    _semantic_hash,
    promotion_candidate_summary_content_hash,
)
from polisyos.runtime.quality.generation_cycle import CandidateSummary
from polisyos.runtime.quality.open_world_risk import (
    BoundProblemDeclaredScopeManifestProvider,
    CompetentDeploymentScopeEvidence,
    DeclaredScopeComponent,
    DeclaredScopeManifest,
    DeploymentScopeQuery,
    DeploymentScopeRoleResolution,
    NoPositiveDeploymentScopeEvidenceVerifier,
    OpenWorldRiskPromotionAuthority,
    OpenWorldRiskPromotionGate,
    OpenWorldRiskResolutionNonReceipt,
    OpenWorldRiskVector,
    OpenWorldRiskVectorArtifactRepository,
    OpenWorldRiskVectorProducer,
    PromotionRuntime,
    PromotionRuntimeBatch,
    VerifiedDeploymentScopeEvidence,
    VerifiedOpenWorldRiskVector,
    resolve_open_world_risk,
)


def _digest(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


_INDEPENDENT_C4_PROFILE_ROWS = {
    "generation_owner_snapshot": (
        "runtime.promotion.generation_owner_snapshot",
        "polisyos.promotion.generation-owner-snapshot.v1",
        b"polisyos.promotion.generation-owner-snapshot.v1\0",
        (
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "declared_candidate_count",
            "ordered_candidate_ids",
            "ordered_candidate_content_hashes",
            "ordered_candidate_summary_content_hashes",
            "ordered_cycle_indices",
            "predicate_class",
        ),
        (),
        (),
    ),
    "candidate_occurrence": (
        "runtime.promotion.candidate_occurrence",
        "polisyos.promotion.candidate-occurrence.v1",
        b"polisyos.promotion.candidate-occurrence.v1\0",
        (
            "ordinal",
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "candidate_id",
            "candidate_content_hash",
            "candidate_summary",
            "candidate_summary_content_hash",
            "cycle_index",
        ),
        (),
        (
            ("candidate_summary", "proxy_score"),
            ("candidate_summary", "voi_estimate"),
            ("candidate_summary", "grounding_score"),
        ),
    ),
    "candidate_denominator": (
        "runtime.promotion.candidate_denominator",
        "polisyos.promotion.candidate-denominator.v1",
        b"polisyos.promotion.candidate-denominator.v1\0",
        (
            "owner_snapshot_ref",
            "owner_snapshot_content_hash",
            "design_problem_binding_ref",
            "declared_candidate_count",
            "ordered_occurrence_refs",
            "ordered_occurrence_content_hashes",
            "predicate_class",
        ),
        (),
        (),
    ),
    "epoch_query_evidence": (
        "runtime.promotion.semantic_epoch_query",
        "polisyos.promotion.semantic-epoch-query.v1",
        b"polisyos.promotion-query.semantic-epoch.v1\0",
        (
            "schema_version",
            "design_problem_binding_ref",
            "candidate",
            "qualification_result",
        ),
        (),
        (),
    ),
    "deployment_query_evidence": (
        "runtime.promotion.deployment_scope_query",
        "polisyos.promotion.deployment-scope-query.v1",
        b"polisyos.promotion-query.deployment-scope.v1\0",
        (
            "schema_version",
            "design_problem_binding_ref",
            "candidate",
            "authority_purpose",
        ),
        (),
        (),
    ),
    "member_context": (
        "runtime.promotion.candidate_context_member",
        "polisyos.promotion.candidate-context-member.v1",
        b"polisyos.promotion-candidate-context-member.v1\0",
        (
            "candidate_occurrence_ref",
            "candidate_occurrence_content_hash",
            "epoch_query_evidence_ref",
            "epoch_query_evidence_content_hash",
            "epoch_native_query_context_ref",
            "deployment_query_evidence_ref",
            "deployment_query_evidence_content_hash",
            "deployment_native_query_context_ref",
            "authority_purpose",
        ),
        (),
        (),
    ),
    "aggregate_context": (
        "runtime.promotion.owner_query_context",
        "polisyos.promotion.owner-query-context.v2",
        b"polisyos.promotion-owner-query-context.v2\0",
        (
            "design_problem_binding_ref",
            "design_problem_binding_content_hash",
            "authority_purpose",
            "candidate_denominator_ref",
            "candidate_denominator_content_hash",
            "ordered_candidate_contexts",
            "requested_query_context_ref",
            "owner_resolution_provenance_ref",
            "predicate_class",
        ),
        (),
        (),
    ),
    "bound_member": (
        "runtime.promotion.bound_candidate_context",
        "polisyos.promotion.bound-candidate-context.v1",
        b"polisyos.promotion-bound-candidate-context.v1\0",
        (
            "aggregate_context_ref",
            "aggregate_context_content_hash",
            "member_context_ref",
            "member_context_content_hash",
            "candidate_occurrence_ref",
            "ordinal",
        ),
        (),
        (),
    ),
    "open_world_risk_vector": (
        "runtime.promotion.open_world_risk_vector",
        "polisyos.promotion.open-world-risk-vector.v1",
        b"polisyos.open-world-risk.vector.v1\0",
        (
            "schema_version",
            "aggregate_context_ref",
            "aggregate_context_content_hash",
            "bound_member_ref",
            "bound_member_content_hash",
            "candidate_occurrence_ref",
            "candidate_occurrence_content_hash",
            "requested_query_context_ref",
            "declared_component_denominator_ref",
            "lifecycle_role_denominator_ref",
            "components",
            "status",
            "limitation_code",
            "vector_content_hash",
        ),
        ("vector_content_hash",),
        (),
    ),
}

_INDEPENDENT_C4_PROFILE_ROWS.update(
    {
        "pre_n9_epoch_subject": (
            "runtime.promotion.pre_n9_epoch_validity_subject",
            "polisyos.promotion.pre-n9-epoch-validity-subject.v1",
            b"polisyos.promotion.pre-n9-epoch-validity-subject.v1\0",
            (
                "owner_query_context_ref",
                "owner_query_context_content_hash",
                "bound_member_ref",
                "bound_member_content_hash",
                "candidate_occurrence_ref",
                "candidate_occurrence_content_hash",
                "decision_packet_lineage_key_ref",
                "current_decision_packet_ref",
                "packet_epoch_refs",
            ),
            (),
            (),
        ),
        "epoch_validity_gate_receipt": (
            "runtime.promotion.epoch_validity_gate_receipt",
            "polisyos.promotion.epoch-validity-gate-receipt.v1",
            b"polisyos.promotion.epoch-validity-gate-receipt.v1\0",
            (
                "status",
                "subject_ref",
                "subject_content_hash",
                "current_decision_packet_ref",
                "packet_epoch_refs",
                "current_epoch_head_refs",
                "dependency_denominator_ref",
                "adjudication_denominator_ref",
                "prior_completed_binding_ref",
                "completed_batch_receipt_ref",
                "requested_query_context_ref",
                "failure_codes",
            ),
            (),
            (),
        ),
        "pre_n9_admitted_candidate_batch": (
            "runtime.promotion.pre_n9_admitted_candidate_batch",
            "polisyos.promotion.pre-n9-admitted-candidate-batch.v1",
            b"polisyos.promotion-pre-n9-admitted-candidate-batch.v1\0",
            (
                "aggregate_context_ref",
                "aggregate_context_content_hash",
                "candidate_denominator_ref",
                "candidate_denominator_content_hash",
                "ordered_admissions",
                "batch_content_hash",
            ),
            ("batch_content_hash",),
            (),
        ),
        "claim_ledger_preparation": (
            "scientist.claims.ledger_preparation",
            "polisyos.claim-ledger.preparation.v1",
            b"polisyos.claim-ledger-preparation.v1\0",
            (
                "schema_version",
                "owner_key",
                "base_claims_ref",
                "base_claims_content_hash",
                "source_artifact_refs",
                "source_artifact_content_hashes",
                "initialization_policy_ref",
                "initialization_policy_content_hash",
                "initialization_policy_verifier_provenance_ref",
                "initial_ledger_ref",
                "initial_ledger_content_hash",
            ),
            (),
            (),
        ),
        "claim_ledger_root_basis": (
            "scientist.claims.ledger_root_basis",
            "polisyos.claim-ledger.root-basis.v1",
            b"polisyos.claim-ledger-root-basis.v1\0",
            (
                "owner_key",
                "preparation_ref",
                "preparation_content_hash",
                "decision_packet_ref",
                "decision_packet_content_hash",
                "initial_ledger_ref",
                "initial_ledger_content_hash",
                "denominator_receipt_ref",
                "denominator_receipt_content_hash",
            ),
            (),
            (),
        ),
        "claim_ledger_root": (
            "scientist.claims.ledger_root",
            "polisyos.claim-ledger.root.v1",
            b"polisyos.claim-ledger-root-root.v1\0",
            (
                "schema_version",
                "root_identity",
                "basis_ref",
                "basis_content_hash",
                "issuance_evidence_ref",
                "issuance_evidence_content_hash",
                "issuance_verifier_provenance_ref",
            ),
            (),
            (),
        ),
        "claim_ledger_root_verification": (
            "scientist.claims.ledger_root_verification",
            "polisyos.claim-ledger.root-verification.v1",
            b"polisyos.claim-ledger-root-verification.v1\0",
            (
                "root_ref",
                "root_content_hash",
                "verifier_provenance_ref",
                "disposition",
            ),
            (),
            (),
        ),
        "claim_ledger_head": (
            "scientist.claims.ledger_head",
            "polisyos.claim-ledger.head.v1",
            b"polisyos.claim-ledger-head-statement.v1\0",
            (
                "schema_version",
                "root_identity",
                "root_receipt_ref",
                "root_receipt_content_hash",
                "owner_key",
                "ledger_artifact_ref",
                "ledger_raw_cas_hash",
                "generation",
                "predecessor_head_ref",
                "bridge_result_refs",
                "issuance_verifier_receipt_ref",
                "issuance_verifier_receipt_content_hash",
            ),
            (),
            (),
        ),
        "claim_ledger_head_readback": (
            "scientist.claims.ledger_head_readback",
            "polisyos.claim-ledger.head-readback.v1",
            b"polisyos.claim-ledger-head-readback.v1\0",
            (
                "schema_version",
                "owner_key",
                "root_identity",
                "expected_prior_head_ref",
                "observed_head_ref",
                "observed_head_content_hash",
                "observed_generation",
                "durable_pointer_content_hash",
                "disposition",
            ),
            (),
            (),
        ),
        "decision_packet_root_snapshot": (
            "scientist.claims.decision_packet_root_snapshot",
            "polisyos.claim-ledger.decision-packet-root-snapshot.v1",
            b"polisyos.claim-ledger-decision-packet-root-snapshot.v1\0",
            ("schema_version", "row_count", "ordered_rows", "verifier_provenance_ref"),
            (),
            (),
        ),
        "claim_ledger_root_denominator": (
            "scientist.claims.ledger_root_denominator",
            "polisyos.claim-ledger.root-denominator.v1",
            b"polisyos.claim-ledger-root-denominator.v1\0",
            (
                "owner_snapshot_ref",
                "owner_snapshot_content_hash",
                "independent_walk_content_hash",
                "owner_snapshot_row_count",
                "independent_walk_row_count",
                "declared_root_count",
                "assessments",
                "denominator_hash",
                "predicate_class",
            ),
            ("denominator_hash",),
            (),
        ),
        "claim_dependency_denominator": (
            "scientist.claims.dependency_denominator",
            "polisyos.claim-ledger.dependency-denominator.v1",
            b"polisyos.claim-ledger-dependency-denominator.v1\0",
            (
                "schema_version",
                "registry_ref",
                "registry_content_hash",
                "claim_schema_content_hash",
                "ledger_artifact_ref",
                "ledger_raw_cas_hash",
                "batch_dependency_denominator_ref",
                "requested_dependency_keys",
                "declared_path_count",
                "observed_path_count",
                "ordered_dependency_rows",
                "ordered_affected_claim_ids",
                "denominator_hash",
                "predicate_class",
            ),
            ("denominator_hash",),
            (),
        ),
        "claim_bridge_pending": (
            "scientist.claims.bridge_pending",
            "polisyos.claim-ledger.bridge-pending.v1",
            b"polisyos.claim-ledger-bridge-pending.v1\0",
            (
                "schema_version",
                "batch_receipt_ref",
                "batch_receipt_content_hash",
                "decision_packet_ref",
                "decision_packet_content_hash",
                "requested_query_context_ref",
                "target_mapping_ref",
                "target_mapping_content_hash",
                "ordered_affected_claim_ids",
                "expected_head_ref",
                "mapping_status",
                "limitation_code",
            ),
            (),
            (),
        ),
        "claim_bridge_result": (
            "scientist.claims.bridge_result",
            "polisyos.claim-ledger.bridge-result.v1",
            b"polisyos.claim-ledger-bridge-result.v1\0",
            (
                "schema_version",
                "owner_key",
                "batch_receipt_ref",
                "batch_receipt_content_hash",
                "decision_packet_ref",
                "decision_packet_content_hash",
                "requested_query_context_ref",
                "pending_ref",
                "pending_content_hash",
                "dependency_denominator_ref",
                "dependency_denominator_content_hash",
                "lifecycle_result_ref",
                "lifecycle_result_content_hash",
                "prior_ledger_ref",
                "prior_ledger_content_hash",
                "next_ledger_ref",
                "next_ledger_content_hash",
                "ordered_affected_claim_ids",
                "predicate_class",
            ),
            (),
            (),
        ),
    }
)


def _problem(problem_id: str = "open_world_problem") -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement="Test a policy candidate under explicit unknown deployment scope.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Test a policy candidate.",
            source_surface="test_open_world_risk",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-08-25",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="survival",
                description="Improve survival",
                metric_id="survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Remain shadow without owner evidence.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Remain shadow.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="survival",
            metric_id="survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="scope",
                    question="Who owns deployment scope?",
                    required_for="promotion",
                )
            ]
        ),
    )


def _summary(candidate_id: str = "candidate_a") -> CandidateSummary:
    return CandidateSummary(
        candidate_id=candidate_id,
        content_hash=_digest(candidate_id),
        cycle_index=0,
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.95,
        current_valid=True,
        value_status="value_ready",
        value_decision_grade="high",
        value_ref=_digest(candidate_id + ":value"),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )


def _prepared(tmp_path, *, summaries: tuple[CandidateSummary, ...] | None = None):
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    result = runtime._prepare_completed_generation(
        problem=_problem(), summaries=summaries or (_summary(),)
    )
    assert not isinstance(result, PromotionOwnerQueryContextNonReceipt)
    return runtime, result


def test_no_owner_still_persists_one_not_established_row_per_declared_component(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    verified = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )

    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    assert verified.vector.status == "not_established"
    assert [row.component_id for row in verified.vector.components] == [
        "calibration",
        "model",
        "obligation",
    ]
    assert {row.status for row in verified.vector.components} == {"not_established"}


def test_self_asserted_positive_owner_is_not_admitted_without_competent_verification(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path)
    evidence_ref = runtime.store.put_bytes(
        b"self-asserted deployment role",
        artifacts.ArtifactWriteOptions(
            kind="deployment.scope.self_asserted",
            media_type="application/octet-stream",
        ),
    )

    class SelfAssertedLifecycleOwner:
        def resolve_component(
            self, *, query: DeploymentScopeQuery
        ) -> DeploymentScopeRoleResolution:
            return DeploymentScopeRoleResolution(
                query=query,
                status="within_scope",
                role="authorized_intended",
                limitation_code="caller_claims_within_scope",
                evidence_ref=evidence_ref,
                evidence_content_hash=_digest("self-asserted-evidence"),
                predicate_class="independently_reconciled",
            )

    repository = OpenWorldRiskVectorArtifactRepository(store=runtime.store)
    producer = OpenWorldRiskVectorProducer(
        owner_contexts=runtime.context_repository,
        manifests=BoundProblemDeclaredScopeManifestProvider(
            store=runtime.store,
            contexts=runtime.context_repository,
        ),
        lifecycle_owner=SelfAssertedLifecycleOwner(),
        evidence_verifier=NoPositiveDeploymentScopeEvidenceVerifier(),
        artifacts=repository,
        verifier_provenance_ref=runtime.verifier_provenance_ref,
    )
    authority = OpenWorldRiskPromotionAuthority(
        producer=producer,
        resolver=OpenWorldRiskVectorArtifactRepository(store=runtime.store),
    )

    verified = authority.prepare_verified_projection(
        bound_member_ref=batch.contexts.ordered_bound_members[0].bound_member_ref
    )

    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    assert verified.vector.status == "not_established"
    assert {row.predicate_class for row in verified.vector.components} == {"not_established"}


def test_manifest_binds_the_complete_canonical_promotion_obligation_denominator(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path)
    member = batch.contexts.ordered_bound_members[0]
    manifest = BoundProblemDeclaredScopeManifestProvider(
        store=runtime.store,
        contexts=runtime.context_repository,
    ).resolve_complete_manifest(member=member)
    assert isinstance(manifest, DeclaredScopeManifest)
    problem = _problem()
    denominator = tuple(item.value for item in PromotionObligationClass)
    obligation = next(
        component for component in manifest.components if component.component_id == "obligation"
    )
    full_ref = _semantic_hash(
        "polisyos.deployment.scope-component.obligation.v1",
        {
            "constraints": tuple(row.model_dump(mode="json") for row in problem.constraints),
            "promotion_obligation_classes": denominator,
        },
    )
    dropped_ref = _semantic_hash(
        "polisyos.deployment.scope-component.obligation.v1",
        {
            "constraints": tuple(row.model_dump(mode="json") for row in problem.constraints),
            "promotion_obligation_classes": denominator[:-1],
        },
    )

    assert obligation.source_status == "present"
    assert obligation.component_ref == full_ref
    assert obligation.component_ref != dropped_ref


def test_open_world_composition_covers_established_and_limited_branches(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    member = batch.contexts.ordered_bound_members[0]
    manifest = BoundProblemDeclaredScopeManifestProvider(
        store=runtime.store,
        contexts=runtime.context_repository,
    ).resolve_complete_manifest(member=member)
    assert isinstance(manifest, DeclaredScopeManifest)
    present_components = tuple(
        component.model_copy(update={"source_status": "present"})
        for component in manifest.components
    )
    manifest = manifest.model_copy(
        update={
            "components": present_components,
            "declared_component_denominator_ref": _semantic_hash(
                "polisyos.deployment.declared-scope-denominator.v1",
                {"components": present_components},
            ),
        }
    )

    def resolutions(*, outside_component: str | None = None):
        return tuple(
            DeploymentScopeRoleResolution(
                query=DeploymentScopeQuery(
                    authority_purpose=manifest.authority_purpose,
                    requested_query_context_ref=_semantic_hash(
                        "polisyos.deployment.scope-query.v1",
                        {
                            "bound_member_ref": manifest.bound_member_ref,
                            "component_ref": component.component_ref,
                        },
                    ),
                    aggregate_context_ref=manifest.aggregate_context_ref,
                    bound_member_ref=manifest.bound_member_ref,
                    candidate_occurrence_ref=manifest.candidate_occurrence_ref,
                    component_ref=component.component_ref,
                    component_kind=component.component_kind,
                ),
                status=(
                    "outside_scope"
                    if component.component_id == outside_component
                    else "within_scope"
                ),
                role="authorized_intended",
                limitation_code=(
                    "deployment_scope_outside_scope"
                    if component.component_id == outside_component
                    else "deployment_scope_within_scope"
                ),
                evidence_ref=runtime.verifier_provenance_ref,
                evidence_content_hash=str(runtime.verifier_provenance_ref.artifact_id),
                predicate_class="independently_reconciled",
            )
            for component in manifest.components
        )

    assert (
        resolve_open_world_risk(
            manifest=manifest,
            resolutions=resolutions(),
        ).status
        == "established"
    )
    limited = resolve_open_world_risk(
        manifest=manifest,
        resolutions=resolutions(outside_component="model"),
    )
    assert limited.status == "limited"
    assert {row.component_id for row in limited.components if row.status == "outside_scope"} == {
        "model"
    }

    mixed_rows = list(resolutions(outside_component="model"))
    unknown_index = next(
        index
        for index, component in enumerate(manifest.components)
        if component.component_id != "model"
    )
    mixed_rows[unknown_index] = DeploymentScopeRoleResolution(
        query=mixed_rows[unknown_index].query,
        status="not_established",
        limitation_code="deployment_scope_component_not_established",
        predicate_class="not_established",
    )
    mixed = resolve_open_world_risk(
        manifest=manifest,
        resolutions=tuple(mixed_rows),
    )
    assert mixed.status == "limited"
    assert mixed.limitation_code == "deployment_scope_limited"

    absent_components = tuple(
        component.model_copy(update={"source_status": "declared_absent"})
        if component.component_id == "model"
        else component
        for component in manifest.components
    )
    absent_manifest = manifest.model_copy(
        update={
            "components": absent_components,
            "declared_component_denominator_ref": _semantic_hash(
                "polisyos.deployment.declared-scope-denominator.v1",
                {"components": absent_components},
            ),
        }
    )
    absent = resolve_open_world_risk(
        manifest=absent_manifest,
        resolutions=resolutions(),
    )
    absent_model = next(row for row in absent.components if row.component_id == "model")
    assert absent.status == "not_established"
    assert absent_model.status == "not_established"
    assert absent_model.limitation_code == "deployment_scope_component_source_absent"


def test_lifecycle_role_change_recomputes_actual_scope_and_freezes_risk(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    member = batch.contexts.ordered_bound_members[0]
    candidate_manifest = BoundProblemDeclaredScopeManifestProvider(
        store=runtime.store,
        contexts=runtime.context_repository,
    ).resolve_complete_manifest(member=member)
    assert isinstance(candidate_manifest, DeclaredScopeManifest)
    present_components = tuple(
        component.model_copy(update={"source_status": "present"})
        for component in candidate_manifest.components
    )
    manifest = candidate_manifest.model_copy(
        update={
            "components": present_components,
            "declared_component_denominator_ref": _semantic_hash(
                "polisyos.deployment.declared-scope-denominator.v1",
                {"components": present_components},
            ),
        }
    )
    evidence_ref = runtime.store.put_bytes(
        b"lifecycle-role-transition-evidence\n",
        artifacts.ArtifactWriteOptions(
            kind="deployment.scope.owner_evidence",
            media_type="application/octet-stream",
        ),
    )

    def resolutions(
        *,
        role: Literal["authorized_intended", "actual"],
        outside_component: str | None = None,
    ) -> tuple[DeploymentScopeRoleResolution, ...]:
        return tuple(
            DeploymentScopeRoleResolution(
                query=DeploymentScopeQuery(
                    authority_purpose=manifest.authority_purpose,
                    requested_query_context_ref=_semantic_hash(
                        "polisyos.deployment.scope-query.v1",
                        {
                            "bound_member_ref": manifest.bound_member_ref,
                            "component_ref": component.component_ref,
                        },
                    ),
                    aggregate_context_ref=manifest.aggregate_context_ref,
                    bound_member_ref=manifest.bound_member_ref,
                    candidate_occurrence_ref=manifest.candidate_occurrence_ref,
                    component_ref=component.component_ref,
                    component_kind=component.component_kind,
                ),
                status=(
                    "outside_scope"
                    if component.component_id == outside_component
                    else "within_scope"
                ),
                role=role,
                limitation_code=(
                    "deployment_scope_outside_scope"
                    if component.component_id == outside_component
                    else "deployment_scope_within_scope"
                ),
                evidence_ref=evidence_ref,
                evidence_content_hash=str(evidence_ref.artifact_id),
                predicate_class="independently_reconciled",
            )
            for component in manifest.components
        )

    intended = resolve_open_world_risk(
        manifest=manifest,
        resolutions=resolutions(role="authorized_intended"),
    )
    actual = resolve_open_world_risk(
        manifest=manifest,
        resolutions=resolutions(role="actual", outside_component="obligation"),
    )
    missing_actual = resolve_open_world_risk(
        manifest=manifest,
        resolutions=tuple(
            DeploymentScopeRoleResolution(
                query=row.query,
                status="not_established",
                limitation_code="deployment_lifecycle_owner_not_established",
                predicate_class="not_established",
            )
            for row in resolutions(role="actual")
        ),
    )

    assert intended.status == "established"
    assert actual.status == "limited"
    assert actual.limitation_code == "deployment_scope_limited"
    assert missing_actual.status == "not_established"
    assert (
        len(
            {
                intended.lifecycle_role_denominator_ref,
                actual.lifecycle_role_denominator_ref,
                missing_actual.lifecycle_role_denominator_ref,
            }
        )
        == 3
    )


def test_positive_vector_round_trip_recomputes_with_independent_owner_and_verifier(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path)
    member = batch.contexts.ordered_bound_members[0]
    evidence_ref = runtime.store.put_bytes(
        b"appointed test-only deployment evidence\n",
        artifacts.ArtifactWriteOptions(
            kind="deployment.scope.owner_evidence",
            media_type="application/octet-stream",
        ),
    )

    class AppointedTestOwner:
        def __init__(self, *, outside: frozenset[str]) -> None:
            self._outside = outside

        def resolve_component(
            self, *, query: DeploymentScopeQuery
        ) -> DeploymentScopeRoleResolution:
            status = "outside_scope" if query.component_ref in self._outside else "within_scope"
            return DeploymentScopeRoleResolution(
                query=query,
                status=status,
                role="actual",
                limitation_code=(
                    "deployment_scope_outside_scope"
                    if status == "outside_scope"
                    else "deployment_scope_within_scope"
                ),
                evidence_ref=evidence_ref,
                evidence_content_hash=str(evidence_ref.artifact_id),
                predicate_class="independently_reconciled",
            )

    class ExactTestEvidenceVerifier:
        def verify(
            self, *, evidence: CompetentDeploymentScopeEvidence
        ) -> VerifiedDeploymentScopeEvidence | DeploymentScopeRoleResolution:
            if (
                evidence.evidence_ref != evidence_ref
                or runtime.store.get_bytes(evidence_ref.artifact_id)
                != b"appointed test-only deployment evidence\n"
                or evidence.evidence_content_hash != str(evidence_ref.artifact_id)
                or evidence.verifier_provenance_ref != runtime.verifier_provenance_ref
            ):
                return DeploymentScopeRoleResolution(
                    query=evidence.query,
                    status="not_established",
                    limitation_code="competent_deployment_scope_evidence_not_established",
                    predicate_class="not_established",
                )
            return VerifiedDeploymentScopeEvidence(
                **evidence.model_dump(mode="python"),
                predicate_class="independently_reconciled",
            )

    manifest = BoundProblemDeclaredScopeManifestProvider(
        store=runtime.store,
        contexts=runtime.context_repository,
    ).resolve_complete_manifest(member=member)
    assert isinstance(manifest, DeclaredScopeManifest)
    obligation_ref = next(
        row.component_ref for row in manifest.components if row.component_id == "obligation"
    )
    writer_repository = OpenWorldRiskVectorArtifactRepository(
        store=runtime.store,
        lifecycle_owner=AppointedTestOwner(outside=frozenset({obligation_ref})),
        evidence_verifier=ExactTestEvidenceVerifier(),
    )
    producer = OpenWorldRiskVectorProducer(
        owner_contexts=runtime.context_repository,
        manifests=BoundProblemDeclaredScopeManifestProvider(
            store=runtime.store,
            contexts=runtime.context_repository,
        ),
        lifecycle_owner=AppointedTestOwner(outside=frozenset({obligation_ref})),
        evidence_verifier=ExactTestEvidenceVerifier(),
        artifacts=writer_repository,
        verifier_provenance_ref=runtime.verifier_provenance_ref,
    )
    authority = OpenWorldRiskPromotionAuthority(
        producer=producer,
        resolver=OpenWorldRiskVectorArtifactRepository(
            store=runtime.store,
            lifecycle_owner=AppointedTestOwner(outside=frozenset({obligation_ref})),
            evidence_verifier=ExactTestEvidenceVerifier(),
        ),
    )

    verified = authority.prepare_verified_projection(bound_member_ref=member.bound_member_ref)

    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    assert verified.vector.status == "limited"
    assert {
        row.component_id for row in verified.vector.components if row.status == "outside_scope"
    } == {"obligation"}


def test_epoch_qualification_is_invoked_and_returns_policy_admission_missing(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path)
    epoch_query = batch.contexts.aggregate_context.statement.ordered_candidate_contexts[
        0
    ].epoch_query

    assert epoch_query.qualification_status == "not_established"
    assert epoch_query.qualification_failure_codes == ("policy_admission_missing",)
    assert epoch_query.predicate_class == "independently_reconciled"
    reloaded = runtime.resolve_verified_epoch_query(
        bound_member_ref=batch.contexts.ordered_bound_members[0].bound_member_ref
    )
    assert reloaded == epoch_query
    raw = runtime.store.get_bytes(epoch_query.query_artifact_ref.artifact_id)
    payload = from_canonical_bytes(raw)
    qualification = core_contracts.chronology.NativeChronologyPolicyResolutionFailed.model_validate(
        payload["qualification_result"]
    )
    assert epoch_query.native_requested_query_context_ref == (
        qualification.query.requested_query_context_ref
    )
    payload_proxy = _semantic_hash(
        "polisyos.promotion-query.semantic-epoch.context.v1",
        payload,
    )
    assert payload_proxy != epoch_query.native_requested_query_context_ref
    with pytest.raises(
        ValueError,
        match="promotion_query_context_binding_mismatch",
    ):
        runtime.context_repository._verify_query_evidence(
            design_problem_binding_ref=(
                batch.contexts.aggregate_context.statement.design_problem_binding_ref
            ),
            candidate=epoch_query.candidate,
            evidence=epoch_query.model_copy(
                update={"native_requested_query_context_ref": payload_proxy}
            ),
            authority_purpose="n9_promotion",
            expected_verifier_provenance_ref=runtime.verifier_provenance_ref,
        )


def test_owner_context_varies_while_problem_and_candidate_bytes_stay_fixed(
    tmp_path,
) -> None:
    runtime, first = _prepared(tmp_path)
    denominator_ref = first.contexts.aggregate_context.statement.candidate_denominator_ref
    alternate_provenance = runtime.store.put_bytes(
        b"polisyos.open-world-risk.verifier.alternate-test-owner.v1\n",
        artifacts.ArtifactWriteOptions(
            kind="chronology.open_world_risk_verifier",
            media_type="text/plain",
        ),
    )
    alternate_authority = epoch_cascade_module.PromotionOwnerQueryContextAuthority(
        candidates=runtime.candidates,
        epoch_queries=open_world_module._PersistedNegativeEpochQueryOwner(
            store=runtime.store,
            provenance_ref=alternate_provenance,
        ),
        deployment_queries=open_world_module._PersistedDeploymentQueryOwner(
            store=runtime.store,
            provenance_ref=alternate_provenance,
        ),
        artifacts=runtime.store,
        verifier_provenance_ref=alternate_provenance,
    )

    second = alternate_authority.persist_for_promotion(denominator_ref=denominator_ref)

    assert isinstance(second, epoch_cascade_module.PersistedPromotionContextBatch)
    first_statement = first.contexts.aggregate_context.statement
    second_statement = second.aggregate_context.statement
    assert first_statement.design_problem_binding_ref == (
        second_statement.design_problem_binding_ref
    )
    assert first_statement.candidate_denominator_ref == (second_statement.candidate_denominator_ref)
    assert first_statement.ordered_candidate_contexts[0].candidate == (
        second_statement.ordered_candidate_contexts[0].candidate
    )
    assert first_statement.owner_resolution_provenance_ref != (
        second_statement.owner_resolution_provenance_ref
    )
    assert first.contexts.aggregate_context.context_ref != second.aggregate_context.context_ref


def test_not_established_scope_cannot_carry_an_owner_role(tmp_path) -> None:
    _, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    query = DeploymentScopeQuery(
        authority_purpose="n9_promotion",
        requested_query_context_ref=_digest("query"),
        aggregate_context_ref=gate.aggregate_context_ref,
        bound_member_ref=gate.bound_member_ref,
        candidate_occurrence_ref=gate.candidate_occurrence_ref,
        component_ref=_digest("component"),
        component_kind="model",
    )

    with pytest.raises(
        ValueError,
        match="deployment_scope_negative_authority_fields_present",
    ):
        DeploymentScopeRoleResolution(
            query=query,
            status="not_established",
            role="actual",
            limitation_code="deployment_lifecycle_owner_not_established",
            predicate_class="not_established",
        )

    with pytest.raises(ValueError, match="authorized_intended"):
        DeploymentScopeRoleResolution.model_validate(
            {
                "query": query.model_dump(mode="json"),
                "status": "within_scope",
                "role": "executor",
                "limitation_code": "deployment_scope_within_scope",
                "evidence_ref": gate.verifier_provenance_ref.model_dump(mode="json"),
                "evidence_content_hash": str(gate.verifier_provenance_ref.artifact_id),
                "predicate_class": "independently_reconciled",
            }
        )


def test_open_world_vector_persists_and_round_trips(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]

    verified = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )

    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    assert (
        OpenWorldRiskPromotionGate.from_verified(
            verified,
            aggregate_context_content_hash=gate.aggregate_context_content_hash,
            bound_member_content_hash=gate.bound_member_content_hash,
            candidate_occurrence_content_hash=gate.candidate_occurrence_content_hash,
        )
        == gate
    )


def test_promotion_artifacts_use_the_frozen_profiles_and_independent_preimages(
    tmp_path,
) -> None:
    assert set(_INDEPENDENT_C4_PROFILE_ROWS) == set(C4_PERSISTED_PROFILE_SPECS)
    runtime, batch = _prepared(tmp_path)
    aggregate = batch.contexts.aggregate_context
    bound = batch.contexts.ordered_bound_members[0]
    candidate_context = aggregate.statement.ordered_candidate_contexts[0]
    gate = batch.gates_by_candidate_id["candidate_a"]
    denominator_ref = aggregate.statement.candidate_denominator_ref
    occurrence_ref = candidate_context.candidate.occurrence_ref
    rows = (
        (
            "candidate_occurrence",
            occurrence_ref,
            candidate_context.candidate.occurrence_content_hash,
        ),
        (
            "candidate_denominator",
            denominator_ref,
            aggregate.statement.candidate_denominator_content_hash,
        ),
        (
            "epoch_query_evidence",
            candidate_context.epoch_query.query_artifact_ref,
            candidate_context.epoch_query.query_artifact_content_hash,
        ),
        (
            "deployment_query_evidence",
            candidate_context.deployment_query.query_artifact_ref,
            candidate_context.deployment_query.query_artifact_content_hash,
        ),
        (
            "member_context",
            bound.statement.member_context_ref,
            bound.statement.member_context_content_hash,
        ),
        ("aggregate_context", aggregate.context_ref, aggregate.semantic_hash),
        ("bound_member", bound.bound_member_ref, bound.bound_member_content_hash),
        ("open_world_risk_vector", gate.vector_artifact_ref, gate.semantic_hash),
    )
    deployment_payload = {
        "schema_version": "polisyos.promotion.deployment-scope-query.v1",
        "design_problem_binding_ref": aggregate.statement.design_problem_binding_ref.model_dump(
            mode="json"
        ),
        "candidate": candidate_context.candidate.model_dump(mode="json"),
        "authority_purpose": "n9_promotion",
    }
    assert c4_canonical_mapping("deployment_query_evidence", deployment_payload) == (
        deployment_payload
    )
    with pytest.raises(
        ValueError,
        match="c4_persisted_profile_field_mismatch:deployment_query_evidence",
    ):
        c4_canonical_mapping(
            "deployment_query_evidence",
            {key: value for key, value in deployment_payload.items() if key != "authority_purpose"},
        )
    independent_canon = CanonSpec(
        name="polisyos.canon.json",
        version="0.2.0",
        forbid_floats=True,
        forbid_nan_inf=True,
        exclude_none=False,
        max_depth=128,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    for record, ref, expected_semantic_hash in rows:
        profile = c4_profile(record)
        (
            expected_kind,
            expected_schema_name,
            expected_prefix,
            expected_fields,
            expected_exclusions,
            expected_binary64_paths,
        ) = _INDEPENDENT_C4_PROFILE_ROWS[record]
        assert profile.kind == expected_kind
        assert profile.schema_name == expected_schema_name
        assert profile.semantic_prefix == expected_prefix
        assert profile.raw_mapping_fields == expected_fields
        assert profile.self_field_exclusions == expected_exclusions
        assert profile.binary64_decimal_paths == expected_binary64_paths
        manifest = runtime.store.get_manifest(ref.artifact_id)
        raw = runtime.store.get_bytes(ref.artifact_id)
        mapping = from_canonical_bytes(raw)
        assert isinstance(mapping, dict)
        assert set(mapping) == set(expected_fields)
        assert ref.kind == expected_kind
        assert ref.media_type == profile.media_type
        assert manifest.artifact_schema == artifacts.SchemaInfo(
            name=expected_schema_name,
            version=profile.schema_version,
        )
        assert manifest.canon == artifacts.CanonInfo.from_spec(independent_canon)
        assert raw == to_canonical_bytes(mapping, independent_canon)
        if record == "candidate_occurrence":
            summary_mapping = mapping["candidate_summary"]
            assert isinstance(summary_mapping, dict)
            assert all(
                isinstance(summary_mapping[field], Decimal)
                for field in ("proxy_score", "voi_estimate", "grounding_score")
            )
        else:
            assert expected_binary64_paths == ()
        semantic_mapping = {
            field: mapping[field] for field in expected_fields if field not in expected_exclusions
        }
        canonical = to_canonical_bytes(semantic_mapping, independent_canon)
        independently_recomputed = (
            "sha256:"
            + hashlib.sha256(
                expected_prefix + len(canonical).to_bytes(8, "big") + canonical
            ).hexdigest()
        )
        assert independently_recomputed == expected_semantic_hash

    requested_mapping = {
        "design_problem_binding_ref": aggregate.statement.design_problem_binding_ref,
        "design_problem_binding_content_hash": (
            aggregate.statement.design_problem_binding_content_hash
        ),
        "authority_purpose": aggregate.statement.authority_purpose,
        "candidate_denominator_ref": aggregate.statement.candidate_denominator_ref,
        "candidate_denominator_content_hash": (
            aggregate.statement.candidate_denominator_content_hash
        ),
        "ordered_candidate_contexts": tuple(
            {
                "candidate": row.candidate,
                "member_query_context_ref": row.member_query_context_ref,
            }
            for row in aggregate.statement.ordered_candidate_contexts
        ),
    }
    requested_bytes = to_canonical_bytes(requested_mapping, independent_canon)
    independently_requested = (
        "sha256:"
        + hashlib.sha256(
            b"polisyos.promotion-owner-query-context.v2\0"
            + len(requested_bytes).to_bytes(8, "big")
            + requested_bytes
        ).hexdigest()
    )
    assert independently_requested == aggregate.statement.requested_query_context_ref
    assert gate.requested_query_context_ref == aggregate.statement.requested_query_context_ref


def test_novel_or_missing_scope_component_is_not_established(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    verified = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )
    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    original = verified.vector
    novel = DeclaredScopeComponent(
        component_id="novel",
        component_kind="novel",
        component_ref=_digest("novel"),
        source_status="present",
    )
    components = tuple(sorted((*original.components, novel), key=lambda row: row.component_id))
    declared = tuple(
        DeclaredScopeComponent(
            component_id=row.component_id,
            component_kind=row.component_kind,
            component_ref=row.component_ref,
            source_status="present",
        )
        for row in components
    )
    manifest = DeclaredScopeManifest(
        aggregate_context_ref=original.aggregate_context_ref,
        aggregate_context_content_hash=original.aggregate_context_content_hash,
        bound_member_ref=original.bound_member_ref,
        bound_member_content_hash=original.bound_member_content_hash,
        candidate_occurrence_ref=original.candidate_occurrence_ref,
        candidate_occurrence_content_hash=original.candidate_occurrence_content_hash,
        requested_query_context_ref=original.requested_query_context_ref,
        authority_purpose="n9_promotion",
        components=declared,
        declared_component_denominator_ref=_semantic_hash(
            "polisyos.deployment.declared-scope-denominator.v1",
            {"components": declared},
        ),
    )

    vector = resolve_open_world_risk(manifest=manifest, resolutions=())

    assert vector.status == "not_established"
    assert next(row for row in vector.components if row.component_id == "novel").status == (
        "not_established"
    )


def test_supplied_low_false_cannot_override_vector(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    verified = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )
    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    vector = verified.vector
    declared = tuple(
        DeclaredScopeComponent(
            component_id=row.component_id,
            component_kind=row.component_kind,
            component_ref=row.component_ref,
            source_status="present",
        )
        for row in vector.components
    )
    manifest = DeclaredScopeManifest(
        aggregate_context_ref=vector.aggregate_context_ref,
        aggregate_context_content_hash=vector.aggregate_context_content_hash,
        bound_member_ref=vector.bound_member_ref,
        bound_member_content_hash=vector.bound_member_content_hash,
        candidate_occurrence_ref=vector.candidate_occurrence_ref,
        candidate_occurrence_content_hash=vector.candidate_occurrence_content_hash,
        requested_query_context_ref=vector.requested_query_context_ref,
        authority_purpose="n9_promotion",
        components=declared,
        declared_component_denominator_ref=_semantic_hash(
            "polisyos.deployment.declared-scope-denominator.v1",
            {"components": declared},
        ),
    )
    resolutions = tuple(
        DeploymentScopeRoleResolution(
            query=DeploymentScopeQuery(
                authority_purpose="n9_promotion",
                requested_query_context_ref=_digest(row.component_id + ":query"),
                aggregate_context_ref=vector.aggregate_context_ref,
                bound_member_ref=vector.bound_member_ref,
                candidate_occurrence_ref=vector.candidate_occurrence_ref,
                component_ref=row.component_ref,
                component_kind=row.component_kind,
            ),
            status="not_established",
            limitation_code="deployment_lifecycle_owner_not_established",
            predicate_class="not_established",
        )
        for row in vector.components
    )

    assert (
        resolve_open_world_risk(
            manifest=manifest, resolutions=resolutions, supplied_low=False
        ).status
        == "not_established"
    )


def test_open_world_limitation_code_is_derived_from_status(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    verified = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )
    assert isinstance(verified, VerifiedOpenWorldRiskVector)
    payload = verified.vector.model_dump(mode="json", exclude={"vector_content_hash"})
    payload["limitation_code"] = "deployment_scope_established"
    payload["vector_content_hash"] = _semantic_hash("polisyos.open-world-risk.vector.v1", payload)

    with pytest.raises(ValueError, match="open_world_limitation_code_not_derived"):
        OpenWorldRiskVector.model_validate(payload)


def test_arbitrary_vector_bytes_or_first_writer_lineage_cannot_enter_n9(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    gate = batch.gates_by_candidate_id["candidate_a"]
    wrong_kind = gate.vector_artifact_ref.model_copy(update={"kind": "arbitrary.bytes"})

    result = runtime.resolver.resolve_verified(
        vector_artifact_ref=wrong_kind,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )

    assert isinstance(result, OpenWorldRiskResolutionNonReceipt)

    poisoned_store = FileSystemCAS(tmp_path / "poisoned-cas")
    vector_bytes = runtime.store.get_bytes(gate.vector_artifact_ref.artifact_id)
    poisoned_store.put_bytes(
        vector_bytes,
        artifacts.ArtifactWriteOptions(
            kind="arbitrary.first_writer",
            media_type="application/octet-stream",
        ),
    )
    provenance_bytes = runtime.store.get_bytes(gate.verifier_provenance_ref.artifact_id)
    poisoned_store.put_bytes(
        provenance_bytes,
        artifacts.ArtifactWriteOptions(
            kind=gate.verifier_provenance_ref.kind,
            media_type=gate.verifier_provenance_ref.media_type,
        ),
    )
    poisoned = OpenWorldRiskVectorArtifactRepository(store=poisoned_store).resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )

    assert isinstance(poisoned, OpenWorldRiskResolutionNonReceipt)
    assert poisoned.code == "open_world_vector_unresolved"

    profile = c4_profile("open_world_risk_vector")
    lineage_store = FileSystemCAS(tmp_path / "lineage-cas")
    lineage_input = lineage_store.put_bytes(
        b"unrelated-lineage",
        artifacts.ArtifactWriteOptions(
            kind="test.unrelated",
            media_type="application/octet-stream",
        ),
    )
    lineage_store.put_bytes(
        vector_bytes,
        artifacts.ArtifactWriteOptions(
            kind=profile.kind,
            media_type=profile.media_type,
            schema=artifacts.SchemaInfo(
                name=profile.schema_name,
                version=profile.schema_version,
            ),
            canon=artifacts.CanonInfo.from_spec(profile.canon_spec),
            inputs=[
                artifacts.InputRef(
                    artifact_id=lineage_input.artifact_id,
                    role="forged_lineage",
                )
            ],
        ),
    )
    lineage_store.put_bytes(
        provenance_bytes,
        artifacts.ArtifactWriteOptions(
            kind=gate.verifier_provenance_ref.kind,
            media_type=gate.verifier_provenance_ref.media_type,
        ),
    )
    lineage_poisoned = OpenWorldRiskVectorArtifactRepository(store=lineage_store).resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )
    assert isinstance(lineage_poisoned, OpenWorldRiskResolutionNonReceipt)
    assert lineage_poisoned.code == "open_world_vector_unresolved"

    wrong_provenance_ref = gate.verifier_provenance_ref.model_copy(
        update={"kind": "arbitrary.verifier"}
    )
    wrong_provenance = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=wrong_provenance_ref,
    )
    assert isinstance(wrong_provenance, OpenWorldRiskResolutionNonReceipt)
    assert wrong_provenance.code == "open_world_verifier_untrusted"

    provenance_lineage_store = FileSystemCAS(tmp_path / "provenance-lineage-cas")
    provenance_input = provenance_lineage_store.put_bytes(
        b"unrelated-provenance-lineage",
        artifacts.ArtifactWriteOptions(
            kind="test.unrelated",
            media_type="application/octet-stream",
        ),
    )
    provenance_lineage_store.put_bytes(
        provenance_bytes,
        artifacts.ArtifactWriteOptions(
            kind=gate.verifier_provenance_ref.kind,
            media_type=gate.verifier_provenance_ref.media_type,
            inputs=[
                artifacts.InputRef(
                    artifact_id=provenance_input.artifact_id,
                    role="forged_lineage",
                )
            ],
        ),
    )
    provenance_lineage = OpenWorldRiskVectorArtifactRepository(
        store=provenance_lineage_store
    ).resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=gate.aggregate_context_ref,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )
    assert isinstance(provenance_lineage, OpenWorldRiskResolutionNonReceipt)
    assert provenance_lineage.code == "open_world_verifier_untrusted"


def test_wrong_kind_or_mutated_promotion_owner_context_rejects(tmp_path) -> None:
    runtime, batch = _prepared(tmp_path)
    ref = batch.contexts.aggregate_context.context_ref
    wrong = ref.model_copy(update={"kind": "arbitrary.context"})

    result = runtime.context_repository.resolve_verified(context_ref=wrong)

    assert isinstance(result, PromotionOwnerQueryContextNonReceipt)

    blob_file, _ = runtime.store._paths(ref.artifact_id)
    original = blob_file.read_bytes()
    blob_file.write_bytes(original.replace(b"n9_promotion", b"n9_forged___", 1))
    mutated = runtime.context_repository.resolve_verified(context_ref=ref)

    assert isinstance(mutated, PromotionOwnerQueryContextNonReceipt)


def test_owner_context_is_derived_from_canonical_candidate_denominator(tmp_path) -> None:
    _, batch = _prepared(tmp_path, summaries=(_summary("a"), _summary("b")))
    statement = batch.contexts.aggregate_context.statement

    assert [row.candidate.ordinal for row in statement.ordered_candidate_contexts] == [0, 1]
    assert [row.candidate.candidate_id for row in statement.ordered_candidate_contexts] == [
        "a",
        "b",
    ]
    assert len(batch.contexts.ordered_bound_members) == 2


def test_owner_context_rejects_dropped_duplicate_reordered_or_cross_promotion_member(
    tmp_path,
) -> None:
    runtime, batch = _prepared(tmp_path, summaries=(_summary("a"), _summary("b")))
    first, second = batch.contexts.ordered_bound_members

    aggregate = batch.contexts.aggregate_context
    reordered_statement = aggregate.statement.model_copy(
        update={
            "ordered_candidate_contexts": tuple(
                reversed(aggregate.statement.ordered_candidate_contexts)
            )
        }
    )
    reordered_ref, _, _ = _persist_model(
        store=runtime.store,
        value=reordered_statement,
        profile_record="aggregate_context",
    )
    assert isinstance(
        runtime.context_repository.resolve_verified(context_ref=reordered_ref),
        PromotionOwnerQueryContextNonReceipt,
    )

    cross_aggregate = BoundPromotionCandidateContextStatement(
        aggregate_context_ref=aggregate.context_ref,
        aggregate_context_content_hash=aggregate.semantic_hash,
        member_context_ref=second.statement.member_context_ref,
        member_context_content_hash=second.statement.member_context_content_hash,
        candidate_occurrence_ref=first.statement.candidate_occurrence_ref,
        ordinal=first.statement.ordinal,
    )
    cross_ref, _, _ = _persist_model(
        store=runtime.store,
        value=cross_aggregate,
        profile_record="bound_member",
    )
    with pytest.raises(ValueError, match="bound_member_context_mismatch"):
        runtime.context_repository.resolve_bound_member(bound_member_ref=cross_ref)

    duplicated_statement = aggregate.statement.model_copy(
        update={
            "ordered_candidate_contexts": (
                aggregate.statement.ordered_candidate_contexts[0],
                aggregate.statement.ordered_candidate_contexts[0],
            )
        }
    )
    duplicated_ref, _, _ = _persist_model(
        store=runtime.store,
        value=duplicated_statement,
        profile_record="aggregate_context",
    )
    assert isinstance(
        runtime.context_repository.resolve_verified(context_ref=duplicated_ref),
        PromotionOwnerQueryContextNonReceipt,
    )

    dropped_statement = aggregate.statement.model_copy(
        update={"ordered_candidate_contexts": aggregate.statement.ordered_candidate_contexts[:1]}
    )
    dropped_ref, _, _ = _persist_model(
        store=runtime.store,
        value=dropped_statement,
        profile_record="aggregate_context",
    )
    assert isinstance(
        runtime.context_repository.resolve_verified(context_ref=dropped_ref),
        PromotionOwnerQueryContextNonReceipt,
    )

    with pytest.raises((TypeError, ValueError)):
        runtime.context_repository.resolve_bound_member(
            bound_member_ref=first.bound_member_ref.model_copy(
                update={"kind": second.bound_member_ref.kind + ".wrong"}
            )
        )


def test_authentic_member_context_under_another_aggregate_freezes_n9(tmp_path) -> None:
    runtime, first = _prepared(tmp_path)
    second_result = runtime._prepare_completed_generation(
        problem=_problem("other_problem"), summaries=(_summary(),)
    )
    assert not isinstance(second_result, PromotionOwnerQueryContextNonReceipt)
    gate = first.gates_by_candidate_id["candidate_a"]
    other = second_result.contexts.aggregate_context.context_ref

    result = runtime.resolver.resolve_verified(
        vector_artifact_ref=gate.vector_artifact_ref,
        expected_raw_cas_hash=gate.raw_cas_hash,
        expected_semantic_hash=gate.semantic_hash,
        requested_query_context_ref=gate.requested_query_context_ref,
        expected_aggregate_context_ref=other,
        expected_bound_member_ref=gate.bound_member_ref,
        expected_candidate_occurrence_ref=gate.candidate_occurrence_ref,
        expected_verifier_provenance_ref=gate.verifier_provenance_ref,
    )

    assert isinstance(result, OpenWorldRiskResolutionNonReceipt)
    assert result.code == "open_world_vector_query_mismatch"

    forged_gate = gate.model_copy(update={"aggregate_context_ref": other})
    forged_batch = PromotionRuntimeBatch(
        contexts=first.contexts,
        gates_by_candidate_id={"candidate_a": forged_gate},
    )
    prepared = runtime.prepare_verified_gate(
        batch=forged_batch,
        ordinal=0,
        summary=_summary(),
    )
    assert isinstance(prepared, PromotionOwnerQueryContextNonReceipt)
    assert prepared.code == "promotion_query_context_binding_mismatch"


def test_coherent_prior_denominator_forces_fail_closed_unequal_cross_process_refreeze(
    tmp_path,
) -> None:
    store_root = tmp_path / "cas"
    first_runtime = PromotionRuntime(store=FileSystemCAS(store_root))
    original = first_runtime._prepare_completed_generation(
        problem=_problem(), summaries=(_summary(),)
    )
    assert isinstance(original, PromotionRuntimeBatch)

    changed = _summary().model_copy(update={"content_hash": _digest("changed")})
    second_runtime = PromotionRuntime(store=FileSystemCAS(store_root))
    rejected = second_runtime._prepare_completed_generation(
        problem=_problem(), summaries=(changed,)
    )
    assert isinstance(rejected, PromotionOwnerQueryContextNonReceipt)
    assert rejected.code == "promotion_candidate_denominator_mismatch"

    # The rejected attempt leaves an orphan snapshot behind. Only the coherent
    # prior denominator participates in the fail-closed cross-process conflict
    # scan; the store has no persistent owner-admission carrier that could make
    # a positive provenance claim about it.
    third_runtime = PromotionRuntime(store=FileSystemCAS(store_root))
    repeated = third_runtime._prepare_completed_generation(
        problem=_problem(), summaries=(_summary(),)
    )
    assert isinstance(repeated, PromotionRuntimeBatch)
    assert (
        repeated.contexts.aggregate_context.statement.candidate_denominator_ref
        == original.contexts.aggregate_context.statement.candidate_denominator_ref
    )
    assert (
        repeated.contexts.aggregate_context.statement.candidate_denominator_content_hash
        == original.contexts.aggregate_context.statement.candidate_denominator_content_hash
    )
    counts = {"snapshot": 0, "denominator": 0}
    for artifact_id in third_runtime.store.iter_artifact_ids():
        kind = third_runtime.store.get_manifest(artifact_id).kind
        if kind == c4_profile("generation_owner_snapshot").kind:
            counts["snapshot"] += 1
        if kind == c4_profile("candidate_denominator").kind:
            counts["denominator"] += 1
    assert counts == {"snapshot": 2, "denominator": 1}


def test_shaped_denominator_cannot_poison_the_admitted_owner_snapshot(tmp_path) -> None:
    store_root = tmp_path / "cas"
    runtime, original = _prepared(tmp_path)
    aggregate = original.contexts.aggregate_context.statement
    admitted = runtime.context_repository.resolve_denominator(
        denominator_ref=aggregate.candidate_denominator_ref
    )
    changed = _summary().model_copy(update={"content_hash": _digest("changed")})
    orphan = epoch_cascade_module._seal_completed_generation_candidate_batch(
        artifacts=runtime.store,
        design_problem_ref=aggregate.design_problem_binding_ref,
        design_problem_content_hash=aggregate.design_problem_binding_content_hash,
        summaries=(changed,),
    )
    shaped = PromotionCandidateDenominatorStatement(
        owner_snapshot_ref=orphan.owner_snapshot_ref,
        owner_snapshot_content_hash=orphan.owner_snapshot_content_hash,
        design_problem_binding_ref=aggregate.design_problem_binding_ref,
        declared_candidate_count=1,
        ordered_occurrence_refs=admitted.ordered_occurrence_refs,
        ordered_occurrence_content_hashes=admitted.ordered_occurrence_content_hashes,
        predicate_class="recomputed",
    )
    _persist_model(
        store=runtime.store,
        value=shaped,
        profile_record="candidate_denominator",
    )

    fresh_runtime = PromotionRuntime(store=FileSystemCAS(store_root))
    repeated = fresh_runtime._prepare_completed_generation(
        problem=_problem(), summaries=(_summary(),)
    )
    assert isinstance(repeated, PromotionRuntimeBatch)
    assert (
        repeated.contexts.aggregate_context.statement.candidate_denominator_ref
        == aggregate.candidate_denominator_ref
    )


def test_coherent_unadmitted_denominator_cannot_enter_owner_context(tmp_path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    runtime = PromotionRuntime(store=store)
    first = runtime._prepare_completed_generation(
        problem=_problem(),
        summaries=(_summary(),),
    )
    assert isinstance(first, PromotionRuntimeBatch)
    aggregate = first.contexts.aggregate_context.statement
    changed = _summary().model_copy(update={"content_hash": _digest("coherent-forged")})
    sealed = _seal_completed_generation_candidate_batch(
        artifacts=store,
        design_problem_ref=aggregate.design_problem_binding_ref,
        design_problem_content_hash=aggregate.design_problem_binding_content_hash,
        summaries=(changed,),
    )
    occurrence = PromotionCandidateOccurrenceStatement(
        ordinal=0,
        design_problem_binding_ref=sealed.design_problem_ref,
        design_problem_binding_content_hash=sealed.design_problem_content_hash,
        candidate_id=changed.candidate_id,
        candidate_content_hash=changed.content_hash,
        candidate_summary=changed,
        candidate_summary_content_hash=promotion_candidate_summary_content_hash(changed),
        cycle_index=changed.cycle_index,
    )
    occurrence_ref, occurrence_hash, _ = _persist_model(
        store=store,
        value=occurrence,
        profile_record="candidate_occurrence",
    )
    denominator = PromotionCandidateDenominatorStatement(
        owner_snapshot_ref=sealed.owner_snapshot_ref,
        owner_snapshot_content_hash=sealed.owner_snapshot_content_hash,
        design_problem_binding_ref=sealed.design_problem_ref,
        declared_candidate_count=1,
        ordered_occurrence_refs=(occurrence_ref,),
        ordered_occurrence_content_hashes=(occurrence_hash,),
        predicate_class="recomputed",
    )
    denominator_ref, _, _ = _persist_model(
        store=store,
        value=denominator,
        profile_record="candidate_denominator",
    )

    rejected = runtime.context_authority.persist_for_promotion(denominator_ref=denominator_ref)

    assert isinstance(rejected, PromotionOwnerQueryContextNonReceipt)
    assert rejected.code == "promotion_candidate_denominator_mismatch"


def test_partial_candidate_sequence_has_no_public_owner_freeze_surface() -> None:
    assert not hasattr(epoch_cascade_module, "seal_completed_generation_candidate_batch")
    assert not hasattr(PromotionRuntime, "prepare_completed_generation")


def test_owner_context_cannot_relabel_native_n9_evidence_under_another_purpose(
    tmp_path,
) -> None:
    runtime, first = _prepared(tmp_path)
    statement = first.contexts.aggregate_context.statement
    with pytest.raises(TypeError, match="authority_purpose"):
        runtime.context_authority.persist_for_promotion(
            denominator_ref=statement.candidate_denominator_ref,
            authority_purpose="public_export",  # type: ignore[call-arg]
        )
    assert statement.authority_purpose == "n9_promotion"
