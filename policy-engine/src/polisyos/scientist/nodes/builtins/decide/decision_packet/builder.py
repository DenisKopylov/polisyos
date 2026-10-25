"""Public decide build decision packet module API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel

import polisyos.scientist.nodes.builtins.errors as node_errors
from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.common.logger import get_logger
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import Metrics
from polisyos.core.contracts.scientist import (
    DecisionPacketRef,
    SourceVerificationReportRef,
    ValidationReportRef,
    VerifiedPolicyReportRef,
)
from polisyos.ir.analytics.metric_validation_report import (
    load_metric_validation_report,
)
from polisyos.ir.registry import MetricValidationReportRef as IRMetricValidationReportRef
from polisyos.scientist.evidence.claims.head_index import ClaimLedgerHeadAdvanced
from polisyos.scientist.evidence.claims.validators import (
    is_fail_on_naked_claims_enabled,
    validate_naked_decision_claims,
)
from polisyos.scientist.governance.report import (
    GovernanceReport,
)
from polisyos.scientist.methods.research_dag.projections import (
    is_research_dag_required_for_publication,
)
from polisyos.scientist.methods.research_dag.replay import legacy_research_dag_status
from polisyos.scientist.nodes.builtins.decide._decision_packet_contracts import (
    _ClaimLedgerAttachment,
    _DecisionPacketBuildRequest,
)
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _prepare_policy_candidate_state_for_direct_consumer,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.enrichment import (
    _attach_claim_ledger_to_packet,
    _attach_human_review_projection,
    _build_abm_alignment_section,
    _build_abstraction_section,
    _build_aux_artifact_section,
    _build_backtest_section,
    _build_calibration_validation_section,
    _build_causal_section,
    _build_continuous_governance_section,
    _build_data_basis,
    _build_diagnostics_summary,
    _build_distributional_section,
    _build_econometrics_section,
    _build_feedback_loop,
    _build_hte_section,
    _build_knowledge_basis,
    _build_metric_significance_projection,
    _build_metric_significance_summary,
    _build_metric_validation_comparison_rows,
    _build_normative_basis,
    _build_phase3_section,
    _build_policy_summary,
    _build_runtime_contracts_section,
    _build_sensitivity_section,
    _build_strategic_section,
    _build_targeting_section,
    _build_tradeoff_certificate_section,
    _build_transportability_basis,
    _build_uncertainty_bounds,
    _build_uncertainty_section,
    _build_voi_section,
    _build_watched_triggers,
    _build_web_evidence_section,
    _build_welfare_section,
    _load_normative_frame_payload,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.serialization import (
    _build_artifacts_section,
    _build_document_outline,
    _build_inputs_section,
    _build_manifest_inputs,
    _sensitivity_analysis_bundle_ref_from_packet,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet.validation import (
    _DECISION_PACKET_LOAD_ERRORS,
    __prepare_decision_validity__,
    _build_analysis_limits,
    _decision_packet_degraded,
    _missing_serious_decision_contracts,
    _phase5_validation_summary,
    _record_decision_packet_degraded,
    _should_run_phase5_publication_preflight,
)
from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
    _build_replay_section,
    _compute_replay_readiness,
    _determine_strategy_hint,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    _CURRENT_POLICY_PROJECTION_WRITE_PATHS,
    _CURRENT_POLICY_PROMOTION_PARAM_KEYS,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CLAIM_LEDGER_V2_REF,
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF,
    ARTIFACT_DECISION_PACKET_REF,
    ARTIFACT_HTE_RESULT_REF,
    ARTIFACT_JUDGE_VERDICT_REF,
    ARTIFACT_METRIC_VALIDATION_REPORT_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_NORM_IMPACT_REPORT_REF,
    ARTIFACT_POLICY_OUTPUT_BUNDLE_REF,
    ARTIFACT_REISSUE_PACKET_REF,
    ARTIFACT_RESEARCH_DAG_REF,
    ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF,
    ARTIFACT_SOURCE_VERIFICATION_REPORT_REF,
    ARTIFACT_STRESS_TEST_REPORT_REF,
    ARTIFACT_VALIDATION_REPORT_REF,
    ARTIFACT_VERIFIED_POLICY_REPORT_REF,
    ARTIFACT_VOI_RUN_REPORT_REF,
    ARTIFACT_WITHDRAWAL_RECORD_REF,
    REPORT_GOVERNANCE_REPORT_REF,
)
from polisyos.scientist.orchestration.engine.context import (
    ClaimCapableExecutionContext,
    ExecutionContext,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from polisyos.scientist.validation.epoch_certificate_issuance import (
    EpochCertificateIssuanceNonReceipt,
    EpochCertificateIssuanceOwner,
    PersistedEpochCertificateIssuancePreparation,
    _capture_decision_packet_invocation,
    _completed_decision_packet_execution,
)
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    Phase5ValidationBlocked,
    enforce_phase5_publication,
    run_phase5_artifact_preflight,
)
from polisyos.scientist.validation.policy_verified import (
    load_source_verification_report,
    load_verified_policy_report,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class _GovernanceReportIntakeRefusal:
    """Preserve failure to admit a supplied governance report through node intake."""

    artifact_ref: str
    reason_code: str


def _parse_completed_hte_source_request(
    params: Mapping[str, object],
) -> tuple[str | None, Literal["absent", "requested", "invalid"]]:
    """Preserve absent, requested, and malformed HTE selector states."""
    key = "completed_hte_source_run_id"
    if key not in params:
        return None, "absent"
    value = params[key]
    if type(value) is str and value.strip() and len(value) <= 256:
        return value, "requested"
    return None, "invalid"


def _selected_ref_identity(value: object) -> tuple[str, str, str, str | None] | None:
    if not isinstance(value, BaseModel):
        return None
    field_names = type(value).model_fields
    if not {"artifact_id", "kind", "media_type"}.issubset(field_names):
        return None
    payload = value.model_dump(mode="python")
    try:
        ref = ArtifactRef.model_validate(
            {
                "artifact_id": payload["artifact_id"],
                "kind": payload["kind"],
                "media_type": payload["media_type"],
                "manifest_profile_sha256": payload.get("manifest_profile_sha256"),
            }
        )
    except (TypeError, ValueError):
        return None
    return artifact_ref_identity_key(ref)


def _model_artifact_refs(value: object) -> tuple[ArtifactRef, ...]:
    """Collect selected ArtifactRefs recursively from strict Runtime DTO models."""
    if isinstance(value, ArtifactRef):
        return (value,)
    if isinstance(value, BaseModel):
        field_names = getattr(type(value), "model_fields", {})
        if {"artifact_id", "kind", "media_type"}.issubset(field_names):
            identity = _selected_ref_identity(value)
            if identity is None:
                raise ValueError("completed_hte_selected_artifact_ref_invalid")
            return (
                ArtifactRef.model_validate(
                    {
                        "artifact_id": identity[0],
                        "kind": identity[1],
                        "media_type": identity[2],
                        "manifest_profile_sha256": identity[3],
                    }
                ),
            )
        refs: list[ArtifactRef] = []
        for field_name in field_names:
            refs.extend(_model_artifact_refs(getattr(value, field_name)))
        return tuple(refs)
    if isinstance(value, (tuple, list)):
        return tuple(ref for item in value for ref in _model_artifact_refs(item))
    if isinstance(value, dict):
        return tuple(ref for item in value.values() for ref in _model_artifact_refs(item))
    return ()


def _completed_hte_source_not_established(
    *,
    request_status: Literal["requested", "invalid"],
    source_run_id: str | None,
    reason_code: str,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "selection_status": "verification_missing",
        "request_status": request_status,
        "requested_source_run_id": source_run_id,
        "limitation_code": reason_code,
        "authority_purpose": "candidate_method_evidence",
        "publication_authorization": "not_established",
        "currentness_status": "not_established",
        "limitations": ["completed_hte_source_not_established"],
    }


def _build_completed_hte_source_section(
    ctx: ExecutionContext,
    *,
    source_run_id: str | None,
    request_status: Literal["requested", "invalid"],
) -> dict[str, object]:
    """Project one Runtime-owned completed HTE selection into a new packet."""
    if request_status == "invalid":
        return _completed_hte_source_not_established(
            request_status="invalid",
            source_run_id=None,
            reason_code="completed_hte_source_selector_invalid",
        )
    if not isinstance(source_run_id, str) or not source_run_id:
        return _completed_hte_source_not_established(
            request_status="requested",
            source_run_id=None,
            reason_code="completed_hte_source_selector_not_established",
        )
    tenant_id = ctx.run.tenant_id
    cell_id = ctx.run.cell_id
    owner = ctx.completed_method_hte_selection_owner
    if not tenant_id or owner is None:
        return _completed_hte_source_not_established(
            request_status="requested",
            source_run_id=source_run_id,
            reason_code="completed_hte_selection_owner_not_established",
        )
    try:
        source = owner.resolve_completed_method_hte_selection(
            source_run_id=source_run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        source = None
    if source is None:
        return _completed_hte_source_not_established(
            request_status="requested",
            source_run_id=source_run_id,
            reason_code="completed_hte_source_not_established",
        )

    try:
        from polisyos.core.contracts.owned_attempt_anchor import (
            OwnedAttemptAnchorProjectionAssociation,
        )
        from polisyos.core.contracts.runtime import (
            CompletedMethodHTESource,
            DirectMethodExecutionHTESummary,
        )

        if type(source) is not CompletedMethodHTESource:
            raise ValueError("completed_hte_runtime_source_type_invalid")
        summary = source.summary
        association = source.association
        if (
            type(summary) is not DirectMethodExecutionHTESummary
            or type(association) is not OwnedAttemptAnchorProjectionAssociation
        ):
            raise ValueError("completed_hte_runtime_projection_type_invalid")
        event = association.job_completed_event
        if (
            source.source_run_id != source_run_id
            or type(source.source_attempt) is not int
            or source.source_attempt < 1
            or type(source.completed_event_id) is not int
            or source.completed_event_id < 1
            or association.run_id != source_run_id
            or association.job_id != source.source_job_id
            or association.attempt != source.source_attempt
            or association.tenant_id != tenant_id
            or association.cell_id != cell_id
            or association.outcome_kind != summary.kind
            or event.job_id != source.source_job_id
            or event.event_id != source.completed_event_id
            or event.payload_sha256 != source.completed_event_payload_sha256
            or event.event_type != "job_completed"
        ):
            raise ValueError("completed_hte_owner_association_mismatch")
        matching_fields = (
            (summary.owned_attempt_anchor_ref, association.anchor_ref),
            (summary.hte_outcome_ref, association.outcome_ref),
            (summary.source_data_ref, association.source_data_ref),
            (summary.method_result_ref, association.method_result_ref),
            (summary.method_evidence_ref, association.method_evidence_ref),
            (summary.point_result_ref, association.point_result_ref),
            (summary.hte_result_ref, association.hte_result_ref),
            (summary.inference_basis_ref, association.inference_basis_ref),
            (summary.refusal_diagnostic_ref, association.refusal_diagnostic_ref),
            (
                summary.materialization_binding_ref,
                association.materialization_binding_ref,
            ),
            (
                summary.search_uncertainty_task_binding_ref,
                association.search_uncertainty_task_binding_ref,
            ),
        )
        if any(
            _selected_ref_identity(summary_ref) != _selected_ref_identity(association_ref)
            for summary_ref, association_ref in matching_fields
        ):
            raise ValueError("completed_hte_summary_association_ref_mismatch")

        refs = _model_artifact_refs(summary) + _model_artifact_refs(association)
        unique_refs: dict[tuple[str, str, str, str | None], ArtifactRef] = {}
        for ref in refs:
            identity = artifact_ref_identity_key(ref)
            if ref.manifest_profile_sha256 is None:
                raise ValueError("completed_hte_manifest_profile_missing")
            unique_refs[identity] = ref
        if not unique_refs:
            raise ValueError("completed_hte_selected_refs_missing")
        # Resolve each exact selected manifest view without reading method or HTE arrays.
        for ref in unique_refs.values():
            ctx.store.get_manifest(ref)
    except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return _completed_hte_source_not_established(
            request_status="requested",
            source_run_id=source_run_id,
            reason_code="completed_hte_source_verification_missing",
        )

    limitations = list(summary.limitations)
    limitations.append("hte_summary_does_not_establish_publication_authority")
    return {
        "schema_version": "1.0",
        "selection_status": "selected",
        "request_status": "requested",
        "requested_source_run_id": source_run_id,
        "source_run_id": source.source_run_id,
        "source_job_id": source.source_job_id,
        "source_attempt": source.source_attempt,
        "completed_event_id": source.completed_event_id,
        "completed_event_payload_sha256": source.completed_event_payload_sha256,
        "outcome_kind": summary.kind,
        "method_profile_id": summary.method_profile_id,
        "authority_purpose": "candidate_method_evidence",
        "publication_authorization": "not_established",
        "currentness_status": "reconciled_at_completed_event",
        "manifest_resolution_status": "selected_profiles_resolved",
        "owner_source": {
            "summary": summary.model_dump(mode="json"),
            "association": association.model_dump(mode="json", exclude_none=True),
        },
        "limitations": sorted(set(limitations)),
    }


_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_decision_packet@1.5.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Decision Packet",
    description="Create the DecisionPacket artifact from available reports and metrics.",
    tags=["builtin", "decide"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "run_id",
        "params.random_seed",
        "params.determinism_tier",
        "params.workflow_id",
        "params.policy_mode",
        "params.completed_hte_source_run_id",
        *(f"params.{key}" for key in _CURRENT_POLICY_PROMOTION_PARAM_KEYS),
        "params.reported_policy_promotion_history",
        "execution_profile",
        "capability_manifest_ref",
        "inputs",
        "reports_index",
        "artifacts_index",
        "artifacts_index.normative_arbitration_result_ref",
        "artifacts_index.policy_output_bundle_ref",
        "artifacts_index.claims_ref",
        "artifacts_index.claim_ledger_v2_ref",
        "artifacts_index.research_dag_ref",
        "artifacts_index.voi_run_report_ref",
        "artifacts_index.continuous_governance_report_ref",
        "artifacts_index.reissue_packet_ref",
        "artifacts_index.withdrawal_record_ref",
        "artifacts_index.human_review_packet_ref",
        "artifacts_index.human_review_decision_ref",
        "artifacts_index.web_evidence_bundle_ref",
        "artifacts_index.source_verification_report_ref",
        "artifacts_index.verified_policy_report_ref",
        "artifacts_index.bounds_bundle_ref",
        "artifacts_index.decision_readiness_contract_ref",
    ],
    state_writes=list(
        dict.fromkeys(
            [
                f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}",
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                f"artifacts_index.{ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF}",
                *_CURRENT_POLICY_PROJECTION_WRITE_PATHS,
            ]
        )
    ),
    produces=[
        ARTIFACT_DECISION_PACKET_REF,
        ARTIFACT_CLAIMS_REF,
        ARTIFACT_CLAIM_LEDGER_V2_REF,
        ARTIFACT_VALIDATION_REPORT_REF,
        ARTIFACT_JUDGE_VERDICT_REF,
    ],
)


@dataclass(frozen=True)
class BuildDecisionPacketNode:
    """Build a DecisionPacket from the engine state."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        state = _prepare_policy_candidate_state_for_direct_consumer(
            ctx,
            state,
            preserve_source_bound_candidate_bundle=True,
        )
        invocation_input_refs = tuple(
            (*state.inputs.values(), *state.artifacts_index.values(), *state.reports_index.values())
        )
        invocation = _capture_decision_packet_invocation(
            store=ctx.store,
            state=state,
            run_manifest=ctx.run.run_manifest,
            node_spec=self.spec,
            implementation_file=__file__,
            implementation_code=BuildDecisionPacketNode.execute.__code__,
            input_refs=invocation_input_refs,
        )
        request = _build_decision_packet_request(ctx, state)
        packet_payload, governance_report = __build_packet_payload__(ctx, state, request)
        if isinstance(governance_report, _GovernanceReportIntakeRefusal):
            return NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        code="governance_report_not_established",
                        message="Supplied GovernanceReport could not be admitted by its owner profile.",
                        attrs={
                            "reason_code": governance_report.reason_code,
                            "artifact_ref": governance_report.artifact_ref,
                        },
                    )
                ],
                error=NodeError(
                    code="governance_report_not_established",
                    message="GovernanceReport admission is not established",
                    details={
                        "governance_report_status": "not_established",
                        "governance_report_refusal_code": governance_report.reason_code,
                        "artifact_ref": governance_report.artifact_ref,
                    },
                ),
            )
        (
            validity_envelope,
            validity_baseline,
            issuance_owner,
            issuance_preparation,
            monitoring_contract_ref,
        ) = __prepare_decision_validity__(
            ctx=ctx,
            state=state,
            packet_payload=packet_payload,
            invocation=invocation,
            invocation_input_refs=invocation_input_refs,
            build_normative_basis=_build_normative_basis,
            build_data_basis=_build_data_basis,
            build_knowledge_basis=_build_knowledge_basis,
            build_transportability_basis=_build_transportability_basis,
            build_watched_triggers=_build_watched_triggers,
            load_normative_frame_payload=_load_normative_frame_payload,
            build_feedback_loop=_build_feedback_loop,
        )
        gate_outcome, claim_attachment, validation_ref, judge_verdict_ref = (
            __run_publication_gates__(
                ctx, state, request, packet_payload, governance_report, monitoring_contract_ref
            )
        )
        if gate_outcome is not None:
            return gate_outcome
        assert claim_attachment is not None
        claims_ref = claim_attachment.claims_ref
        claim_ledger_v2_ref = claim_attachment.claim_ledger_v2_ref

        inputs = _build_manifest_inputs(
            packet_payload,
            source_state=state,
            source_artifact_refs=(
                *claim_attachment.artifacts,
                *(ref for ref in (validation_ref, judge_verdict_ref) if ref is not None),
            ),
        )

        packet_ref_payload = ctx.store.put_json(
            packet_payload,
            PutOptions(
                kind="scientist.decision_packet",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.DecisionPacket",
                    version="3.4",
                ),
                inputs=inputs or None,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        packet_ref = DecisionPacketRef.model_validate(packet_ref_payload.model_dump(mode="json"))
        if claim_attachment.authority_status == "prepared":
            if (
                not isinstance(ctx, ClaimCapableExecutionContext)
                or claim_attachment.preparation is None
            ):
                raise ValueError("claim_root_preparation_owner_missing")
            root_result = ctx.claim_ledger_owner.finalize_initial_root(
                preparation_ref=claim_attachment.preparation.preparation_ref,
                decision_packet_ref=packet_ref_payload,
            )
            if not isinstance(root_result, ClaimLedgerHeadAdvanced):
                failure_code = getattr(
                    root_result,
                    "code",
                    "claim_root_issuance_not_established",
                )
                return NodeOutcome(
                    status="fail",
                    state=state,
                    artifacts=claim_attachment.artifacts,
                    events=[
                        NodeEvent(
                            level="error",
                            message=(
                                "Claim Ledger root issuance did not establish a current head."
                            ),
                        )
                    ],
                    error=NodeError(
                        code=str(failure_code),
                        message="Claim Ledger root issuance is not established",
                        details={
                            "claim_ledger_status": "not_established",
                            "packet_candidate_ref": str(packet_ref_payload.artifact_id),
                        },
                    ),
                )
            claim_attachment = claim_attachment.mark_current()
        sensitivity_bundle_ref = _sensitivity_analysis_bundle_ref_from_packet(packet_payload)
        if isinstance(issuance_preparation, PersistedEpochCertificateIssuancePreparation):
            assert issuance_owner is not None
            issuance_owner.finalize(
                execution=_completed_decision_packet_execution(
                    preparation=issuance_preparation,
                    decision_packet_ref=packet_ref_payload,
                )
            )
        DecisionValidityService(ctx.store).register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=validity_envelope,
            baseline=validity_baseline,
            monitoring_contract_ref=monitoring_contract_ref,
        )

        new_state = branch_state(
            state,
            write_paths=(
                f"artifacts_index.{ARTIFACT_DECISION_PACKET_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
                f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}",
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}",
                f"artifacts_index.{ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF}",
            ),
        ).state
        new_state.artifacts_index[ARTIFACT_DECISION_PACKET_REF] = packet_ref
        claim_attachment.apply_to_state(new_state)
        if validation_ref is not None:
            new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
        if judge_verdict_ref is not None:
            new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = judge_verdict_ref
        if sensitivity_bundle_ref is not None:
            new_state.artifacts_index[ARTIFACT_SENSITIVITY_ANALYSIS_BUNDLE_REF] = (
                ArtifactRef.model_validate(sensitivity_bundle_ref.model_dump(mode="json"))
            )

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[
                artifact
                for artifact in (
                    packet_ref,
                    claims_ref,
                    claim_ledger_v2_ref,
                    validation_ref,
                    judge_verdict_ref,
                )
                if artifact is not None
            ],
        )


def _build_packet_payload(
    ctx: ExecutionContext,
    state: ExperimentState,
    request: _DecisionPacketBuildRequest,
) -> tuple[dict[str, object], GovernanceReport | _GovernanceReportIntakeRefusal | None]:
    from polisyos.core.artifacts import load_core_json_artifact

    replay_section = _build_replay_section(
        inputs_section=request.inputs_section,
        artifacts_section=request.artifacts_section,
        readiness=request.readiness,
        strategy_hint=request.strategy_hint,
        seed=request.seed,
        determinism_tier=state.params.get("determinism_tier"),
    )

    packet_payload: dict[str, object] = {
        "schema_version": "3.4",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": state.run_id,
        "seed": request.seed,
        "policy_summary": request.policy_summary,
        "intervention_count": request.intervention_count,
        "run_record": {
            "schema_version": "3.2",
            "run_id": state.run_id,
            "seed": request.seed,
            "engine": "scientist.engine",
        },
        "simulation_results": None,
        "metric_validation_report_ref": None,
        "metric_significance": None,
        "metric_significance_summary": None,
        "metric_validation_family_adjustment": None,
        "metric_validation_comparisons": [],
        "governance": None,
        "legal_verification": None,
        "source_coverage": None,
        "policy_answer": None,
        "verified_findings": [],
        "hypotheses": [],
        "intervention_legal_basis_map": {},
        "uncertainty": None,
        "uncertainty_bounds": None,
        "causal": None,
        "abm_alignment": None,
        "abstraction_certificate": None,
        "strategic": None,
        "hte": None,
        "targeting": None,
        "backtest": None,
        "calibration_validation": None,
        "distributional": None,
        "welfare": None,
        "phase3": None,
        "econometrics": None,
        "norm_impact": None,
        "sensitivity": None,
        "causal_validity": None,
        "stress_test": None,
        "tradeoff_certificate": None,
        "runtime_contracts": _build_runtime_contracts_section(state),
        "inputs": request.inputs_section,
        "artifacts": request.artifacts_section,
        "replay": replay_section,
        "research_dag_ref": request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF),
        "research_dag_status": legacy_research_dag_status(
            request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF)
        ),
        "voi_report_ref": request.artifacts_section.get(ARTIFACT_VOI_RUN_REPORT_REF),
        "voi_report_status": (
            "available"
            if request.artifacts_section.get(ARTIFACT_VOI_RUN_REPORT_REF) is not None
            else "legacy_missing"
        ),
        "voi": None,
        "continuous_governance_report_ref": request.artifacts_section.get(
            ARTIFACT_CONTINUOUS_GOVERNANCE_REPORT_REF
        ),
        "reissue_packet_ref": request.artifacts_section.get(ARTIFACT_REISSUE_PACKET_REF),
        "withdrawal_record_ref": request.artifacts_section.get(ARTIFACT_WITHDRAWAL_RECORD_REF),
        "continuous_governance": None,
        "human_review": None,
        "human_review_validation": None,
        "web_evidence": None,
        "degraded_paths": [],
        "document_outline": [],
        "notes": [],
    }

    packet_payload["web_evidence"] = _build_web_evidence_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["voi"] = _build_voi_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["continuous_governance"] = _build_continuous_governance_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["uncertainty"] = _build_uncertainty_section(
        ctx,
        state.inputs,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["causal"] = _build_causal_section(
        ctx,
        state,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["abm_alignment"] = _build_abm_alignment_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["abstraction_certificate"] = _build_abstraction_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["strategic"] = _build_strategic_section(
        ctx,
        state,
        packet_payload=packet_payload,
    )

    completed_hte_source_run_id, completed_hte_source_request_status = (
        _parse_completed_hte_source_request(state.params)
    )
    if completed_hte_source_request_status == "absent":
        packet_payload["hte"] = _build_hte_section(
            ctx,
            state.artifacts_index,
            packet_payload=packet_payload,
        )
    else:
        completed_hte_source = _build_completed_hte_source_section(
            ctx,
            source_run_id=completed_hte_source_run_id,
            request_status=completed_hte_source_request_status,
        )
        owner_source = completed_hte_source.get("owner_source")
        owner_summary = owner_source.get("summary") if isinstance(owner_source, dict) else None
        packet_payload["hte"] = owner_summary if isinstance(owner_summary, dict) else None
        # Consumed by the existing validity-basis builder. The persisted HTE
        # slot keeps the public scalar-summary shape; status and ownership are
        # emitted into its typed basis and manifest dependencies.
        packet_payload["_completed_hte_source"] = completed_hte_source
        artifacts_payload = packet_payload.get("artifacts")
        if isinstance(artifacts_payload, dict):
            artifacts_payload.pop(ARTIFACT_HTE_RESULT_REF, None)

    packet_payload["targeting"] = _build_targeting_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["backtest"] = _build_backtest_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["calibration_validation"] = _build_calibration_validation_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["distributional"] = _build_distributional_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["welfare"] = _build_welfare_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["phase3"] = _build_phase3_section(
        ctx,
        state,
        packet_payload=packet_payload,
    )

    packet_payload["econometrics"] = _build_econometrics_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["norm_impact"] = _build_aux_artifact_section(
        ctx,
        state.artifacts_index,
        ARTIFACT_NORM_IMPACT_REPORT_REF,
        packet_payload=packet_payload,
    )

    packet_payload["sensitivity"] = _build_sensitivity_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    packet_payload["causal_validity"] = _build_aux_artifact_section(
        ctx,
        state.artifacts_index,
        ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
        packet_payload=packet_payload,
    )

    packet_payload["stress_test"] = _build_aux_artifact_section(
        ctx,
        state.artifacts_index,
        ARTIFACT_STRESS_TEST_REPORT_REF,
        packet_payload=packet_payload,
    )

    packet_payload["tradeoff_certificate"] = _build_tradeoff_certificate_section(
        ctx,
        state.artifacts_index,
        packet_payload=packet_payload,
    )

    if isinstance(packet_payload["backtest"], dict):
        backtest_section = packet_payload["backtest"]
        if bool(backtest_section.get("trust_eligible", True)):
            packet_payload["trust_profile"] = {
                "backtest_trust_score": backtest_section.get("trust_score"),
                "backtest_trust_grade": backtest_section.get("trust_grade"),
            }
        else:
            packet_payload["trust_profile"] = {
                "backtest_trust_score": None,
                "backtest_trust_grade": None,
            }

    metrics_ref = state.artifacts_index.get(ARTIFACT_METRICS_REF)

    if metrics_ref is not None:
        try:
            payload = load_core_json_artifact(ctx.store, metrics_ref)
            metrics = Metrics.model_validate(payload)
            packet_payload["simulation_results"] = dict(metrics.values)
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            packet_payload["simulation_results"] = None
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_metrics_artifact",
                    reason="metrics_load_failed",
                    exc=exc,
                    ref=metrics_ref,
                    artifact_key=ARTIFACT_METRICS_REF,
                ),
            )

    metric_validation_ref = state.artifacts_index.get(ARTIFACT_METRIC_VALIDATION_REPORT_REF)

    if metric_validation_ref is not None:
        try:
            report = load_metric_validation_report(
                _ensure_ir_artifact_store(ctx.store),
                IRMetricValidationReportRef.model_validate(
                    metric_validation_ref.model_dump(mode="json")
                ),
            )
            packet_payload["metric_validation_report_ref"] = str(metric_validation_ref.artifact_id)
            packet_payload["metric_significance"] = _build_metric_significance_projection(report)
            packet_payload["metric_significance_summary"] = _build_metric_significance_summary(
                report
            )
            packet_payload["metric_validation_family_adjustment"] = (
                report.family_adjustment.model_dump(mode="json")
            )
            packet_payload["metric_validation_comparisons"] = (
                _build_metric_validation_comparison_rows(report)
            )
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_metric_validation_report",
                    reason="metric_validation_report_load_failed",
                    exc=exc,
                    ref=metric_validation_ref,
                    artifact_key=ARTIFACT_METRIC_VALIDATION_REPORT_REF,
                ),
            )

    governance_report: GovernanceReport | _GovernanceReportIntakeRefusal | None = None

    governance_ref = state.reports_index.get(REPORT_GOVERNANCE_REPORT_REF)

    if governance_ref is not None:
        try:
            from polisyos.scientist.governance.report_currentness import (
                resolve_current_governance_report,
            )

            governance_admission = resolve_current_governance_report(ctx, state, governance_ref)
            if not governance_admission.is_current or governance_admission.report is None:
                governance_report = _GovernanceReportIntakeRefusal(
                    artifact_ref=str(governance_ref.artifact_id),
                    reason_code=governance_admission.reason_code,
                )
                packet_payload["governance"] = None
                return packet_payload, governance_report
            governance_report_value = governance_admission.report
            governance_report = governance_report_value
            packet_payload["governance"] = {
                "verdict": governance_report_value.verdict,
                "issues": governance_report_value.issues,
                "links": governance_report_value.links.model_dump(mode="json"),
                "notes": governance_report_value.notes,
                "currentness": "current",
            }
        except _DECISION_PACKET_LOAD_ERRORS as exc:
            _record_decision_packet_degraded(
                packet_payload,
                _decision_packet_degraded(
                    operation="load_governance_report",
                    reason="governance_report_load_failed",
                    exc=exc,
                    ref=governance_ref,
                    artifact_key=REPORT_GOVERNANCE_REPORT_REF,
                ),
            )
            refusal_code = (
                exc.code
                if isinstance(exc, CanonicalProfileRefusalError)
                else "governance_report_load_failed"
            )
            governance_report = _GovernanceReportIntakeRefusal(
                artifact_ref=str(governance_ref.artifact_id),
                reason_code=refusal_code,
            )
            packet_payload["governance"] = None
            return packet_payload, governance_report

    from polisyos.scientist.nodes.builtins.decide.decision_packet_support import (
        _populate_optional_report_projections,
    )

    _populate_optional_report_projections(ctx, state, packet_payload)

    uncertainty_bounds = _build_uncertainty_bounds(
        ctx,
        (packet_payload["uncertainty"] if isinstance(packet_payload["uncertainty"], dict) else {}),
        packet_payload=packet_payload,
    )

    packet_payload["uncertainty_bounds"] = uncertainty_bounds

    packet_payload["diagnostics_summary"] = _build_diagnostics_summary(
        ctx=ctx,
        packet_payload=packet_payload,
        state=state,
    )

    packet_payload["analysis_limits"] = _build_analysis_limits(packet_payload)

    packet_payload["document_outline"] = _build_document_outline(packet_payload)
    return packet_payload, governance_report


def _run_publication_gates(
    ctx: ExecutionContext,
    state: ExperimentState,
    request: _DecisionPacketBuildRequest,
    packet_payload: dict[str, object],
    governance_report: GovernanceReport | None,
    monitoring_contract_ref: str | None,
) -> tuple[
    NodeOutcome | None,
    _ClaimLedgerAttachment | None,
    ValidationReportRef | None,
    ArtifactRef | None,
]:
    missing_serious_contracts = _missing_serious_decision_contracts(
        state=state,
        monitoring_contract_ref=monitoring_contract_ref,
    )

    if missing_serious_contracts:
        return (
            NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message=(
                            "Serious execution profiles require a complete decision contract; "
                            f"missing: {', '.join(missing_serious_contracts)}."
                        ),
                    )
                ],
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="Incomplete serious decision contract",
                    details={
                        "execution_profile": state.execution_profile,
                        "missing_contracts": missing_serious_contracts,
                    },
                ),
            ),
            None,
            None,
            None,
        )

    claim_attachment = _attach_claim_ledger_to_packet(ctx, state, packet_payload)

    claims_ref = claim_attachment.claims_ref

    claim_ledger_v2_ref = claim_attachment.claim_ledger_v2_ref

    human_review_validation = _attach_human_review_projection(
        ctx,
        state,
        packet_payload,
        governance_report=governance_report,
    )

    claim_gate = validate_naked_decision_claims(
        packet_payload,
        claims_ref=claims_ref,
        workflow_id=str(state.params.get("workflow_id") or ""),
        fail_on_naked_claims=is_fail_on_naked_claims_enabled(state.params),
    )

    packet_payload["claim_ledger_validation"] = claim_gate.model_dump(mode="json")

    if not claim_gate.passed:
        new_state = branch_state(state, write_paths=claim_attachment.write_paths).state
        claim_attachment.apply_to_state(new_state)
        return (
            NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=claim_attachment.artifacts,
                events=[
                    NodeEvent(
                        level="error",
                        message="Claim spine validation blocked decision packet publication.",
                    )
                ],
                error=NodeError(
                    code="claim_spine_validation_failed",
                    message="Decision packet contains decision-bearing claims without claims_ref",
                    details=claim_gate.model_dump(mode="json"),
                ),
            ),
            claim_attachment,
            None,
            None,
        )

    if not human_review_validation.passed:
        new_state = branch_state(state, write_paths=claim_attachment.write_paths).state
        claim_attachment.apply_to_state(new_state)
        return (
            NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=claim_attachment.artifacts,
                events=[
                    NodeEvent(
                        level="error",
                        message="Human review validation blocked decision packet publication.",
                    )
                ],
                error=NodeError(
                    code="human_review_validation_failed",
                    message="Decision packet human-review readiness requires review refs",
                    details=human_review_validation.model_dump(mode="json"),
                ),
            ),
            claim_attachment,
            None,
            None,
        )

    if (
        is_research_dag_required_for_publication(state.params)
        and request.artifacts_section.get(ARTIFACT_RESEARCH_DAG_REF) is None
    ):
        return (
            NodeOutcome(
                status="fail",
                state=state,
                events=[
                    NodeEvent(
                        level="error",
                        message="Research DAG sidecar is required for publication.",
                    )
                ],
                error=NodeError(
                    code="research_dag_missing_for_publication",
                    message="Decision packet publication requires research_dag_ref",
                    details={"research_dag_status": "legacy_missing"},
                ),
            ),
            claim_attachment,
            None,
            None,
        )

    validation_ref: ValidationReportRef | None = None

    judge_verdict_ref: ArtifactRef | None = None

    if _should_run_phase5_publication_preflight(state):
        publication = run_phase5_artifact_preflight(
            ctx,
            state,
            Phase5ArtifactPreflightInput(
                artifact_payload=packet_payload,
                artifact_kind="scientist.decision_packet",
                generated_for="scientist.decision_packet",
                analyst_facing=True,
                base_readiness="ready",
            ),
        )
        validation_report = publication.validation_report
        validation_ref = ValidationReportRef.model_validate(dict(publication.validation_ref))
        judge_verdict_ref = publication.judge_verdict_ref
        try:
            enforce_phase5_publication(publication)
        except Phase5ValidationBlocked:
            write_paths = [
                f"artifacts_index.{ARTIFACT_VALIDATION_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_CLAIMS_REF}",
            ]
            if claim_ledger_v2_ref is not None:
                write_paths.append(f"artifacts_index.{ARTIFACT_CLAIM_LEDGER_V2_REF}")
            if judge_verdict_ref is not None:
                write_paths.append(f"artifacts_index.{ARTIFACT_JUDGE_VERDICT_REF}")
            new_state = branch_state(
                state,
                write_paths=tuple(write_paths),
            ).state
            new_state.artifacts_index[ARTIFACT_VALIDATION_REPORT_REF] = validation_ref
            claim_attachment.apply_to_state(new_state)
            if judge_verdict_ref is not None:
                new_state.artifacts_index[ARTIFACT_JUDGE_VERDICT_REF] = judge_verdict_ref
            return (
                NodeOutcome(
                    status="fail",
                    state=new_state,
                    events=[
                        NodeEvent(
                            level="error",
                            message="Phase 5 validation blocked decision packet publication.",
                        )
                    ],
                    artifacts=[
                        artifact
                        for artifact in (
                            validation_ref,
                            judge_verdict_ref,
                            *claim_attachment.artifacts,
                        )
                        if artifact is not None
                    ],
                    error=NodeError(
                        code="phase5_validation_failed",
                        message="Phase 5 validation blocked analyst-facing publication",
                        details={
                            "validation_report_ref": str(validation_ref.artifact_id),
                            "verdict": validation_report.verdict,
                            "readiness": validation_report.readiness,
                            "gate_failures": list(validation_report.gate_failures),
                        },
                    ),
                ),
                claim_attachment,
                validation_ref,
                judge_verdict_ref,
            )

        packet_payload["validation_report_ref"] = validation_ref.model_dump(mode="json")
        if judge_verdict_ref is not None:
            packet_payload["judge_verdict_ref"] = judge_verdict_ref.model_dump(mode="json")
        packet_payload["validation"] = _phase5_validation_summary(validation_report)
    return None, claim_attachment, validation_ref, judge_verdict_ref


def _build_decision_packet_request(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> _DecisionPacketBuildRequest:
    raw_seed = state.params.get("random_seed", 0)
    if not raw_seed:
        seed = 0
    elif isinstance(raw_seed, (int, float, str)):
        seed = int(raw_seed)
    else:
        raise TypeError("random_seed must be a JSON integer, number, string, or null")
    inputs_section = _build_inputs_section(state.inputs, state.artifacts_index)
    artifacts_section = _build_artifacts_section(
        state.artifacts_index,
        state.reports_index,
    )
    readiness = _compute_replay_readiness(inputs_section)
    strategy_hint = _determine_strategy_hint(inputs_section, artifacts_section)
    policy_summary, intervention_count = _build_policy_summary(ctx, state.inputs)
    return _DecisionPacketBuildRequest(
        seed=seed,
        inputs_section=inputs_section,
        artifacts_section=artifacts_section,
        readiness=readiness,
        strategy_hint=strategy_hint,
        policy_summary=policy_summary,
        intervention_count=intervention_count,
    )


__build_packet_payload__ = _build_packet_payload
__run_publication_gates__ = _run_publication_gates
del _build_packet_payload, _run_publication_gates
