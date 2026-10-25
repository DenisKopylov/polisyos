"""Typed input resolution for policy blueprint runtime execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile
from polisyos.ir.analytics.decision_layer import load_optimization_ambiguity_certificate
from polisyos.ir.analytics.distributional import DistributionalReport
from polisyos.scientist.evidence.sources import (
    EvidenceSourcesConfig,
    normalize_evidence_sources_config,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _resolve_candidate,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ensure_policy_candidate_ref,
    load_ambiguity_certificate,
    load_causal_report,
    load_cross_graph_profile,
    load_distributional_report_for_state,
    load_governance_report,
    load_search_uncertainty,
    load_simulation_metrics,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState, JsonValue
from polisyos.scientist.policy_design.phase3 import (
    ensure_optimization_ambiguity_certificate,
    phase3_ambiguity_required,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema


def _parse_method_metric_source_request(
    params: Mapping[str, object],
) -> tuple[str | None, Literal["absent", "requested", "invalid"]]:
    """Preserve explicit selector presence and validate its bounded value."""
    key = "method_metric_source_run_id"
    if key not in params:
        return None, "absent"

    value = params[key]
    if type(value) is str and value.strip() and len(value) <= 256:
        return value, "requested"
    return None, "invalid"


@dataclass(frozen=True)
class PolicyRuntimeRequest:
    """Resolved runtime inputs needed by blueprint policy execution."""

    candidate: PolicyCandidateSchema
    candidate_ref: ArtifactRef
    uncertainty_envelope: UncertaintyEnvelope | None
    governance_report: GovernanceReport | None
    causal_report: CausalEffectReport | None
    distributional_report: DistributionalReport | None
    cross_graph_profile: CrossGraphEvidenceProfile | None
    evidence_sources: EvidenceSourcesConfig
    simulation_metrics: object | None
    ambiguity_certificate: object | None
    ambiguity_certificate_ref: ArtifactRef | None
    execution_plan_ref: ArtifactRef | None
    method_catalog_snapshot_ref: ArtifactRef | None
    execution_profile: str | None
    causal_method_fqn: str | None
    causal_method_params: dict[str, JsonValue]
    method_metric_source_run_id: str | None = None
    method_metric_source_request_status: Literal["absent", "requested", "invalid"] = "absent"


def resolve_policy_runtime_request(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> PolicyRuntimeRequest | None:
    """Resolve candidate and runtime context for policy blueprint execution."""

    candidate, candidate_ref = _resolve_candidate(ctx, state)
    if candidate is None:
        return None
    resolved_candidate_ref = ensure_policy_candidate_ref(
        ctx,
        state,
        candidate,
        candidate_ref,
    )
    method_metric_source_run_id, method_metric_source_request_status = (
        _parse_method_metric_source_request(state.params)
    )
    ambiguity_required = phase3_ambiguity_required(ctx, state, candidate=candidate)
    ambiguity_certificate_ref = ensure_optimization_ambiguity_certificate(
        ctx,
        state,
        create_if_missing=not ambiguity_required,
    )
    ambiguity_certificate = load_ambiguity_certificate(ctx, state)
    if ambiguity_certificate is None and ambiguity_certificate_ref is not None:
        artifact = load_optimization_ambiguity_certificate(
            _ensure_ir_artifact_store(ctx.store),
            ambiguity_certificate_ref,
        )
        ambiguity_certificate = dict(artifact.certificate_payload) or {
            "mode": artifact.mode,
            "overall_status": artifact.overall_status,
            "note": artifact.note,
        }
    return PolicyRuntimeRequest(
        candidate=candidate,
        candidate_ref=resolved_candidate_ref,
        uncertainty_envelope=load_search_uncertainty(ctx, state),
        governance_report=load_governance_report(ctx, state),
        causal_report=load_causal_report(ctx, state),
        distributional_report=load_distributional_report_for_state(ctx, state),
        cross_graph_profile=load_cross_graph_profile(ctx, state),
        evidence_sources=normalize_evidence_sources_config(state.params),
        simulation_metrics=load_simulation_metrics(ctx, state) or None,
        ambiguity_certificate=ambiguity_certificate,
        ambiguity_certificate_ref=ambiguity_certificate_ref,
        execution_plan_ref=state.execution_plan_ref,
        method_catalog_snapshot_ref=state.method_catalog_snapshot_ref,
        execution_profile=state.execution_profile,
        causal_method_fqn=state.causal_method_fqn,
        causal_method_params=dict(state.causal_method_params),
        method_metric_source_run_id=method_metric_source_run_id,
        method_metric_source_request_status=method_metric_source_request_status,
    )


__all__ = [
    "PolicyRuntimeRequest",
    "resolve_policy_runtime_request",
]
