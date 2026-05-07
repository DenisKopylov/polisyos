"""Public causal resolve parameters module API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.data_forge.read_api.academic import ParameterSelector, SKGQuery
from polisyos.foundry.methods.catalog.causal.parameter_transfer import ParameterTransfer
from polisyos.foundry.methods.catalog.causal.protocols import ParameterTransferData
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.cross_graph import load_cross_graph_evidence_profile
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundle,
    ParameterApplicability,
    persist_context_adaptive_parameter_bundle,
)
from polisyos.ir.artifacts import InputRef
from polisyos.ir.refs import CausalGraphModelRef, CrossGraphEvidenceProfileRef
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_resolve_parameters@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Resolve Parameters",
    description="Resolve context-adaptive simulation parameters from SKG.",
    tags=["builtin", "causal", "parameters"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.target_context",
        "params.required_parameters",
        "params.skg_db_path",
        "params.skg_index_dir",
        "params.phase15_runtime_backend",
        "params.phase15_runtime_draws",
        "params.phase15_runtime_seed",
        "params.causal_graph_ref",
        f"artifacts_index.{ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF}",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF}",
        "params.literature_priors",
        "params.parameter_uncertainty_multipliers",
        "params.phase15_runtime_backend_used",
        "params.phase15_runtime_parameter_intervals",
        "params.phase15_runtime_ready",
    ],
    produces=[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF],
)

_RESOLVE_PARAMETERS_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)


@dataclass(frozen=True)
class ResolveParametersNode:
    """Resolve context-adaptive parameters from SKG and graph evidence.

    Converts workflow state into ``ContextAdaptiveParameterBundle`` plus runtime
    uncertainty payloads that Foundry simulation can consume directly.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        target_context = _resolve_target_context(state)
        if target_context is None:
            return _skip(
                state,
                "Missing params.target_context; parameter resolution skipped.",
            )

        required_parameters = _resolve_required_parameters(state)
        if not required_parameters:
            return _skip(
                state,
                "Missing params.required_parameters; parameter resolution skipped.",
            )

        graph_ref = _resolve_causal_graph_ref(state)
        if graph_ref is None:
            return _skip(
                state,
                "No causal graph reference available; parameter resolution skipped.",
            )

        try:
            causal_graph = load_causal_graph_model(ctx.store, graph_ref)
        except _RESOLVE_PARAMETERS_LOAD_ERRORS:
            return _skip(
                state,
                "Failed to load causal graph artifact; parameter resolution skipped.",
            )

        db_path_raw = state.params.get("skg_db_path")
        if not isinstance(db_path_raw, str) or not db_path_raw.strip():
            return _skip(
                state,
                "Missing params.skg_db_path; parameter resolution skipped.",
            )
        db_path = Path(db_path_raw)
        if not db_path.exists():
            return _skip(
                state,
                f"SKG database '{db_path}' is unavailable; parameter resolution skipped.",
            )
        index_dir_raw = state.params.get("skg_index_dir")
        index_dir = Path(str(index_dir_raw)) if index_dir_raw else db_path.parent

        parameters: dict[str, Any] = {}
        applicability: dict[str, ParameterApplicability] = {}
        unsupported: list[str] = []
        cross_graph_profile = _resolve_cross_graph_profile(ctx, state)

        skg_query = SKGQuery(db_path=db_path, index_dir=index_dir)
        try:
            selector = ParameterSelector(skg_query)
            for parameter_name in required_parameters:
                parameter, appl = selector.select_for_context(
                    parameter_name=parameter_name,
                    target_context=target_context,
                    causal_graph=causal_graph,
                    cross_graph_profile=cross_graph_profile,
                )
                applicability[parameter_name] = appl
                if parameter is None:
                    unsupported.append(parameter_name)
                    continue
                parameters[parameter_name] = parameter

            skg_version_id = skg_query.latest_skg_version_id()
            skg_snapshot_ref = skg_query.skg_snapshot_ref(version_id=skg_version_id) or ""
        finally:
            skg_query.close()

        bundle = ContextAdaptiveParameterBundle(
            target_context=target_context,
            simulation_domain=str(state.params.get("domain", "unknown")),
            parameters=parameters,
            applicability=applicability,
            unsupported_parameters=unsupported,
            skg_snapshot_ref=skg_snapshot_ref,
            skg_version_id=skg_version_id,
            selection_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )

        input_refs = [InputRef(artifact_id=str(graph_ref.artifact_id), role="causal_graph")]
        bundle_ref = persist_context_adaptive_parameter_bundle(
            ctx.store,
            bundle,
            inputs=input_refs,
        )
        bridge_payload = ParameterTransfer.pure_step(
            ParameterTransferData(parameter_bundle=bundle),
            params={
                "runtime_backend": state.params.get("phase15_runtime_backend", "auto"),
                "runtime_draws": state.params.get("phase15_runtime_draws", 256),
                "runtime_seed": state.params.get("phase15_runtime_seed", 0),
            },
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = bundle_ref
        new_state.params["literature_priors"] = bridge_payload.get("literature_priors", {})
        new_state.params["parameter_uncertainty_multipliers"] = bridge_payload.get(
            "uncertainty_multipliers",
            {},
        )
        new_state.params["phase15_runtime_backend_used"] = bridge_payload.get(
            "runtime_backend_used",
            "numpy",
        )
        new_state.params["phase15_runtime_parameter_intervals"] = bridge_payload.get(
            "runtime_parameter_intervals",
            {},
        )
        new_state.params["phase15_runtime_ready"] = bool(bridge_payload.get("runtime_ready", False))

        events = []
        if unsupported:
            events.append(
                NodeEvent(
                    level="warn",
                    code="PARAMS_WITHOUT_EVIDENCE",
                    message=(
                        "Parameters without applicable literature support: "
                        + ", ".join(sorted(unsupported))
                    ),
                )
            )
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[bundle_ref],
            events=events,
        )


def _resolve_target_context(state: ExperimentState) -> ContextProfile | None:
    payload = state.params.get("target_context")
    if payload is None:
        return None
    try:
        return ContextProfile.model_validate(payload)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return None


def _resolve_required_parameters(state: ExperimentState) -> list[str]:
    raw = state.params.get("required_parameters")
    if not isinstance(raw, list):
        return []
    values = [str(item).strip() for item in raw if str(item).strip()]
    return sorted(set(values))


def _resolve_causal_graph_ref(state: ExperimentState) -> CausalGraphModelRef | None:
    raw = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
    if raw is None:
        raw = state.params.get("causal_graph_ref")
    if raw is None:
        return None

    if hasattr(raw, "model_dump"):
        payload = raw.model_dump(mode="json")
    else:
        payload = raw
    try:
        return CausalGraphModelRef.model_validate(payload)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return None


def _resolve_cross_graph_profile(ctx: ExecutionContext, state: ExperimentState):
    raw = state.artifacts_index.get(ARTIFACT_CROSS_GRAPH_EVIDENCE_PROFILE_REF)
    if raw is None:
        return None
    try:
        if hasattr(raw, "model_dump"):
            payload = raw.model_dump(mode="json")
        else:
            payload = raw
        ref = CrossGraphEvidenceProfileRef.model_validate(payload)
        return load_cross_graph_evidence_profile(ctx.store, ref)
    except _RESOLVE_PARAMETERS_LOAD_ERRORS:
        return None


def _skip(state: ExperimentState, message: str) -> NodeOutcome:
    return NodeOutcome(
        status="skip",
        state=state,
        events=[NodeEvent(level="warn", message=message)],
    )


__all__ = ["ResolveParametersNode"]
