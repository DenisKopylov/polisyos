"""Typed input resolution for policy blueprint runtime execution."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.causal import CausalEffectReport
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile
from polisyos.ir.analytics.distributional import DistributionalReport
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.evidence_sources import (
    EvidenceSourcesConfig,
    normalize_evidence_sources_config,
)
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
    _resolve_candidate,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ensure_policy_candidate_ref,
    load_causal_report,
    load_cross_graph_profile,
    load_distributional_report_for_state,
    load_governance_report,
    load_search_uncertainty,
    load_simulation_metrics,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.search.uncertainty import UncertaintyEnvelope


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
    )


__all__ = [
    "PolicyRuntimeRequest",
    "resolve_policy_runtime_request",
]
