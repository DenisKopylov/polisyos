"""Public causal build literature prior module API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.invariance_tests import (
    build_environment_audit_report,
)
from polisyos.foundry.methods.catalog.causal.literature_prior import BuildLiteraturePrior
from polisyos.foundry.methods.catalog.causal.protocols import LiteraturePriorBuildData
from polisyos.ir.analytics.causal_graph import persist_causal_graph_model
from polisyos.ir.analytics.literature import (
    EnvironmentAuditReport,
    persist_literature_causal_prior,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_LITERATURE_PRIOR_GRAPH_REF,
    ARTIFACT_LITERATURE_PRIOR_REF,
    INPUT_KNOWLEDGE_BUNDLE_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_literature_prior@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Literature Prior",
    description="Build LiteratureCausalPrior from SKG and persist prior + projected graph.",
    tags=["builtin", "causal", "prior"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.causal_variables",
        "params.skg_db_path",
        "params.skg_index_dir",
        "params.literature_prior_min_confidence",
        "params.literature_prior_limit",
        "params.literature_prior_domain",
        "params.discovery_data",
        "params.discovery_variable_names",
        "params.discovery_environment_labels",
        "params.discovery_target_col",
        "params.discovery_domain",
        "params.environment_audit_enabled",
        "params.environment_audit_alpha",
        "params.environment_audit_correction",
        "artifacts_index",
        f"inputs.{INPUT_KNOWLEDGE_BUNDLE_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_REF}",
        f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_GRAPH_REF}",
        "params.literature_prior_warnings",
        "params.environment_audit_summary",
        "params.environment_audit_status",
    ],
    produces=[ARTIFACT_LITERATURE_PRIOR_REF, ARTIFACT_LITERATURE_PRIOR_GRAPH_REF],
)

_LITERATURE_PRIOR_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_LITERATURE_PRIOR_EXECUTION_ERRORS = (RuntimeError, TypeError, ValueError, ValidationError)


def _resolve_variables(state: ExperimentState) -> list[str]:
    raw = state.params.get("causal_variables")
    if not isinstance(raw, list):
        raw = state.params.get("causal_graph_nodes")
    if not isinstance(raw, list):
        return []
    values = [str(item).strip() for item in raw if str(item).strip()]
    return sorted(set(values))


def _optional_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except _LITERATURE_PRIOR_VALIDATION_ERRORS:
        return int(default)


def _optional_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except _LITERATURE_PRIOR_VALIDATION_ERRORS:
        return float(default)


def _build_environment_audit(state: ExperimentState) -> EnvironmentAuditReport:
    if not bool(state.params.get("environment_audit_enabled", True)):
        return EnvironmentAuditReport(
            status="skipped",
            warnings=["environment_audit_disabled"],
            metadata={"reason": "disabled"},
        )

    return build_environment_audit_report(
        data=state.params.get("discovery_data"),
        variable_names=[
            str(item).strip()
            for item in state.params.get("discovery_variable_names", [])
            if str(item).strip()
        ]
        if isinstance(state.params.get("discovery_variable_names"), list)
        else [],
        domain_labels=state.params.get("discovery_environment_labels"),
        target_col=state.params.get("discovery_target_col"),
        alpha=_optional_float(state.params.get("environment_audit_alpha"), default=0.05),
        correction=str(state.params.get("environment_audit_correction", "bh") or "bh"),
        metadata={
            "source": "scientist.node_build_literature_prior",
            "discovery_domain": str(state.params.get("discovery_domain") or "").strip() or None,
        },
    )


def _environment_audit_summary(report: EnvironmentAuditReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "n_environments": report.n_environments,
        "ks_passed": report.ks_passed,
        "ks_rejected_variables": list(report.ks_rejected_variables),
        "icp_run": report.icp_run,
        "icp_passed": report.icp_passed,
        "variant_features": list(report.variant_features),
        "warnings": list(report.warnings),
    }


@dataclass(frozen=True)
class BuildLiteraturePriorNode:
    """Build a literature prior and projected causal graph from SKG evidence.

    Reads causal variables plus optional environment-audit settings from
    ``ExperimentState``, runs the Foundry literature-prior builder, and writes
    both the prior artifact and its projected graph back into the workflow
    state for downstream reconciliation.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_LITERATURE_PRIOR_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        variables = _resolve_variables(state)
        if not variables:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info", message="No causal variables; skip literature prior build."
                    )
                ],
            )

        try:
            request = LiteraturePriorBuildData(
                variables=variables,
                skg_db_path=(
                    str(state.params["skg_db_path"]) if "skg_db_path" in state.params else None
                ),
                skg_index_dir=(
                    str(state.params["skg_index_dir"]) if "skg_index_dir" in state.params else None
                ),
                min_confidence=_optional_float(
                    state.params.get("literature_prior_min_confidence"),
                    default=0.2,
                ),
                limit=_optional_int(state.params.get("literature_prior_limit"), default=256),
                domain=(
                    str(state.params["literature_prior_domain"])
                    if "literature_prior_domain" in state.params
                    else None
                ),
            )
            result = BuildLiteraturePrior.pure_step(request, params={})
        except _LITERATURE_PRIOR_EXECUTION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                    message=f"build_literature_prior execution failed: {exc}",
                ),
            )

        prior = result.get("literature_prior")
        graph = result.get("literature_prior_graph")
        if prior is None or graph is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="build_literature_prior did not return prior and graph artifacts",
                ),
            )

        environment_audit = _build_environment_audit(state)
        prior = prior.model_copy(update={"environment_audit": environment_audit})
        graph = prior.to_causal_graph_model(
            nodes=list(graph.nodes),
            min_confidence=_optional_float(
                prior.metadata.get("confidence_threshold"),
                default=_optional_float(
                    state.params.get("literature_prior_min_confidence"),
                    default=0.2,
                ),
            ),
        )

        input_refs: list[InputRef] = []
        if INPUT_KNOWLEDGE_BUNDLE_REF in state.inputs:
            input_refs.append(
                InputRef(
                    artifact_id=state.inputs[INPUT_KNOWLEDGE_BUNDLE_REF].artifact_id,
                    role="knowledge_bundle",
                )
            )

        prior_ref = persist_literature_causal_prior(ctx.store, prior, inputs=input_refs)
        graph_inputs = [
            *input_refs,
            InputRef(artifact_id=str(prior_ref.artifact_id), role="literature_prior"),
        ]
        graph_ref = persist_causal_graph_model(ctx.store, graph, inputs=graph_inputs)

        new_state = branch_state(
            state,
            write_paths=(
                f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_REF}",
                f"artifacts_index.{ARTIFACT_LITERATURE_PRIOR_GRAPH_REF}",
                "params.literature_prior_warnings",
                "params.environment_audit_summary",
                "params.environment_audit_status",
            ),
        ).state
        new_state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_REF] = prior_ref
        new_state.artifacts_index[ARTIFACT_LITERATURE_PRIOR_GRAPH_REF] = graph_ref
        new_state.params["literature_prior_warnings"] = [
            str(item) for item in result.get("warnings", [])
        ]
        new_state.params["environment_audit_summary"] = _environment_audit_summary(
            environment_audit
        )
        new_state.params["environment_audit_status"] = environment_audit.status

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[prior_ref, graph_ref],
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Literature prior built ({len(prior.edges)} edges, "
                        f"{len(result.get('warnings', []))} warning(s), "
                        f"environment audit: {environment_audit.status})."
                    ),
                )
            ],
        )


__all__ = ["BuildLiteraturePriorNode"]
