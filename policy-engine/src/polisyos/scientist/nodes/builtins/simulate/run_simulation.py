"""Public simulate run simulation module API."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    ParameterOverrideBundleRef,
    SimulationResult,
)
from polisyos.core.observability import get_metrics
from polisyos.foundry.methods.catalog.causal.strategic import evaluate_strategic_hook
from polisyos.ir.analytics.phase4_dynamics import Phase4DynamicsGate, Phase4DynamicsGateError
from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationProofBridgeArtifacts,
    build_simulation_proof_bridge_artifacts,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.c6c_runtime_support import (
    build_runtime_abstraction_metadata,
    load_runtime_abstraction_certificate,
    maybe_materialize_policy_override_bundle,
    persist_runtime_strategic_artifacts,
    resolve_baseline_policy_value,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    ensure_policy_candidate_ref,
    load_simulation_metrics,
)
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF,
    ARTIFACT_CAUSAL_QUERY_RESULT_REF,
    ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
    ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF,
    ARTIFACT_CONSTRAINT_REPORT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_INTERFACE_MAPPING_REF,
    ARTIFACT_LOWERED_IR_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_PROGRAM_GRAPH_REF,
    ARTIFACT_PROOF_BUNDLE_REF,
    ARTIFACT_PROOF_COMPOSABILITY_CERTIFICATE_REF,
    ARTIFACT_PROOF_WITNESS_INDEX_REF,
    ARTIFACT_SBOM_REF,
    ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF,
    ARTIFACT_SIMULATION_PROOF_BRIDGE_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_DELTA_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_STRATEGIC_SCM_REF,
    ARTIFACT_TEE_ATTESTATION_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_PARAMETER_OVERRIDE_BUNDLE_REF,
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
)
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

logger = get_logger(__name__)


def _default_metrics():
    return get_metrics()


_SIMULATION_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_SIMULATION_LOAD_ERRORS = (
    TypeError,
    ValueError,
    ValidationError,
    FileNotFoundError,
    OSError,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_simulation@1.0.1"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Simulation",
    description="Execute Foundry exec plan against a data snapshot.",
    tags=["builtin", "simulate"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_EXEC_PLAN_REF}",
        f"artifacts_index.{ARTIFACT_LOWERED_IR_REF}",
        f"artifacts_index.{ARTIFACT_PROGRAM_GRAPH_REF}",
        f"artifacts_index.{ARTIFACT_ABSTRACTION_CERTIFICATE_REF}",
        f"artifacts_index.{ARTIFACT_INTERFACE_MAPPING_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_READINESS_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_QUERY_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_PROOF_BUNDLE_REF}",
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"inputs.{INPUT_PARAMETER_OVERRIDE_BUNDLE_REF}",
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        "params.policy_candidate_schema",
        "params.lex_policy_bundle_input",
        "params.simulation_method",
        "params.strategic_scm",
        "params.strategic_payoff_tables",
        "params.macro_strategic_payoff_tables",
        "params.performative_loop_spec",
        "params.causal_query",
    ],
    state_writes=[
        f"inputs.{INPUT_PARAMETER_OVERRIDE_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_METRICS_REF}",
        f"artifacts_index.{ARTIFACT_STATE_DELTA_REF}",
        f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
        f"artifacts_index.{ARTIFACT_CONSTRAINT_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_ENVIRONMENT_MANIFEST_REF}",
        f"artifacts_index.{ARTIFACT_TEE_ATTESTATION_REF}",
        f"artifacts_index.{ARTIFACT_SBOM_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_PROOF_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_PROOF_WITNESS_INDEX_REF}",
        f"artifacts_index.{ARTIFACT_PROOF_COMPOSABILITY_CERTIFICATE_REF}",
        f"artifacts_index.{ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF}",
        f"artifacts_index.{ARTIFACT_SIMULATION_PROOF_BRIDGE_REF}",
        f"artifacts_index.{ARTIFACT_STRATEGIC_SCM_REF}",
        f"artifacts_index.{ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF}",
        "params.strategic_response",
        "params.strategic_response_source",
    ],
    produces=[
        ARTIFACT_SIMULATION_RESULT_REF,
        ARTIFACT_METRICS_REF,
        ARTIFACT_STATE_DELTA_REF,
        ARTIFACT_STATE_SNAPSHOT_REF,
        ARTIFACT_CONSTRAINT_REPORT_REF,
        ARTIFACT_ENVIRONMENT_MANIFEST_REF,
        ARTIFACT_TEE_ATTESTATION_REF,
        ARTIFACT_SBOM_REF,
        ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF,
        ARTIFACT_PROOF_BUNDLE_REF,
        ARTIFACT_PROOF_WITNESS_INDEX_REF,
        ARTIFACT_PROOF_COMPOSABILITY_CERTIFICATE_REF,
        ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF,
        ARTIFACT_SIMULATION_PROOF_BRIDGE_REF,
        ARTIFACT_STRATEGIC_SCM_REF,
        ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ],
)


@dataclass(frozen=True)
class RunSimulationNode:
    """Simulation-stage DAG node that executes the Foundry plan with materialized runtime bindings.

    Requires an execution plan, input bindings, and a configured Foundry port, then
    writes simulation results, metrics, state deltas, snapshots, constraint reports,
    and environment manifests back into workflow state.
    """

    exec_config: FoundryExecConfig = field(default_factory=FoundryExecConfig)

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> RunSimulationNode:
        if not params:
            return self
        config = self.exec_config.model_copy(deep=False)
        for key, value in params.items():
            if key in config.model_fields:
                setattr(config, key, value)
        return replace(self, exec_config=config)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        injected_metrics = ctx.metrics if ctx.metrics is not None else None
        metrics = (
            injected_metrics
            if injected_metrics is not None
            and hasattr(injected_metrics, "record_slo_simulation_run")
            else _default_metrics()
        )
        method = str(state.params.get("simulation_method", "foundry.execute"))
        new_state = branch_state(
            state,
            write_paths=(
                f"inputs.{INPUT_PARAMETER_OVERRIDE_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
                f"artifacts_index.{ARTIFACT_METRICS_REF}",
                f"artifacts_index.{ARTIFACT_STATE_DELTA_REF}",
                f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
                f"artifacts_index.{ARTIFACT_CONSTRAINT_REPORT_REF}",
                f"artifacts_index.{ARTIFACT_ENVIRONMENT_MANIFEST_REF}",
                f"artifacts_index.{ARTIFACT_TEE_ATTESTATION_REF}",
                f"artifacts_index.{ARTIFACT_SBOM_REF}",
                f"artifacts_index.{ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_PROOF_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_PROOF_WITNESS_INDEX_REF}",
                f"artifacts_index.{ARTIFACT_PROOF_COMPOSABILITY_CERTIFICATE_REF}",
                f"artifacts_index.{ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF}",
                f"artifacts_index.{ARTIFACT_SIMULATION_PROOF_BRIDGE_REF}",
                f"artifacts_index.{ARTIFACT_STRATEGIC_SCM_REF}",
                f"artifacts_index.{ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF}",
                "params.strategic_response",
                "params.strategic_response_source",
            ),
        ).state
        materialized_artifacts = []
        runtime_events: list[NodeEvent] = []

        if ctx.foundry is None:
            error = NodeError(
                code=node_errors.ERROR_FOUNDATION_MISSING,
                message="Foundry port is not configured",
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=state, error=error)

        try:
            materialized = maybe_materialize_policy_override_bundle(ctx, new_state)
        except _SIMULATION_VALIDATION_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Failed to materialize policy override bundle: {exc}",
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=new_state, error=error)
        if materialized.bundle_ref is not None:
            new_state.inputs[INPUT_PARAMETER_OVERRIDE_BUNDLE_REF] = materialized.bundle_ref
            materialized_artifacts.append(materialized.bundle_ref)

        exec_plan_ref = new_state.artifacts_index.get(ARTIFACT_EXEC_PLAN_REF)
        if exec_plan_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing exec_plan_ref for simulation",
                details={"required": ARTIFACT_EXEC_PLAN_REF},
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=new_state, error=error)

        input_bindings_ref = new_state.inputs.get(INPUT_INPUT_BINDINGS_REF)
        if input_bindings_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message=("Missing input source for simulation: input_bindings_ref is required"),
                details={"required": [INPUT_INPUT_BINDINGS_REF]},
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=new_state, error=error)

        registry_ref = new_state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
        parameter_override_bundle_ref = new_state.inputs.get(INPUT_PARAMETER_OVERRIDE_BUNDLE_REF)
        try:
            Phase4DynamicsGate().enforce(
                horizon=int(
                    state.params.get(
                        "simulation_horizon",
                        state.params.get("horizon", state.params.get("n_periods", 1)),
                    )
                    or 1
                ),
                regime_bundle=state.params.get("regime_shift_forecast_bundle"),
                regime_bundle_ref=state.params.get("regime_shift_forecast_bundle_ref"),
                artifact_store=ctx.store,
                metadata={"surface": "scientist.run_simulation", "method": method},
            )
        except Phase4DynamicsGateError as exc:
            error = NodeError(
                code=exc.code,
                message=str(exc),
                details=exc.verdict.model_dump(mode="json"),
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=new_state, error=error)

        try:
            request = ExecuteRequest(
                exec_plan_ref=ExecPlanRef.model_validate(exec_plan_ref.model_dump(mode="json")),
                input_bindings_ref=FoundryInputBindingsRef.model_validate(
                    input_bindings_ref.model_dump(mode="json")
                ),
                registry_bundle_ref=registry_ref,
                parameter_override_bundle_ref=(
                    ParameterOverrideBundleRef.model_validate(
                        parameter_override_bundle_ref.model_dump(mode="json")
                    )
                    if parameter_override_bundle_ref is not None
                    else None
                ),
                exec_config=self.exec_config,
            )
        except _SIMULATION_VALIDATION_ERRORS as exc:
            error = NodeError(
                code=node_errors.ERROR_INVALID_STATE,
                message=f"Simulation request is invalid: {exc}",
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=new_state, error=error)

        result = ctx.foundry.execute(ctx.store, request)

        artifacts = list(materialized_artifacts)
        simulation_payload: dict[str, Any] | None = None

        if result.simulation_result_ref is not None:
            new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = result.simulation_result_ref
            artifacts.append(result.simulation_result_ref)

            try:
                payload = from_canonical_bytes(
                    ctx.store.get_bytes(result.simulation_result_ref.artifact_id)
                )
                if isinstance(payload, dict):
                    simulation_payload = dict(payload)
                sim_result = SimulationResult.model_validate(payload)
                if sim_result.state_snapshot_ref is not None:
                    new_state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF] = (
                        sim_result.state_snapshot_ref
                    )
            except _SIMULATION_LOAD_ERRORS as exc:
                logger.debug(
                    "Failed to load simulation result payload for runtime bookkeeping: %s",
                    exc,
                    exc_info=True,
                )
                runtime_events.append(
                    NodeEvent(
                        level="warn",
                        code="simulation_result_payload_invalid",
                        message="Simulation result payload could not be loaded for state snapshot bookkeeping",
                        attrs={"reason": str(exc)},
                    )
                )

        for item in result.derived_refs:
            artifacts.append(item.ref)
            if item.role == "metrics":
                new_state.artifacts_index[ARTIFACT_METRICS_REF] = item.ref
            elif item.role == "state_delta":
                new_state.artifacts_index[ARTIFACT_STATE_DELTA_REF] = item.ref
            elif item.role == "constraint_report":
                new_state.artifacts_index[ARTIFACT_CONSTRAINT_REPORT_REF] = item.ref
            elif item.role == "environment_manifest":
                new_state.artifacts_index[ARTIFACT_ENVIRONMENT_MANIFEST_REF] = item.ref
                ctx.run.run_manifest.environment_manifest_ref = item.ref
            elif item.role == "tee_attestation":
                new_state.artifacts_index[ARTIFACT_TEE_ATTESTATION_REF] = item.ref
                ctx.run.run_manifest.tee_attestation_ref = item.ref
            elif item.role == "sbom":
                new_state.artifacts_index[ARTIFACT_SBOM_REF] = item.ref
                ctx.run.run_manifest.sbom_ref = item.ref

        if not result.ok:
            error = NodeError(
                code=node_errors.ERROR_FOUNDRY_EXECUTE_FAILED,
                message="Foundry execute failed",
                details={
                    "simulation_result_ref": getattr(
                        result.simulation_result_ref, "model_dump", lambda: None
                    )(),
                    "notes": list(result.notes),
                },
            )
            event = NodeEvent(level="error", message="Foundry execute returned ok=False")
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=artifacts,
                events=[*runtime_events, event],
                error=error,
            )

        proof_events: list[NodeEvent] = []
        if result.simulation_result_ref is not None:
            try:
                bridge_output = _materialize_simulation_proof_bridge(
                    ctx,
                    new_state,
                    simulation_result_ref=result.simulation_result_ref,
                    simulation_payload=simulation_payload,
                    method=method,
                )
            except _SIMULATION_LOAD_ERRORS as exc:
                logger.debug(
                    "Failed to materialize simulation proof bridge: %s",
                    exc,
                    exc_info=True,
                )
                event = NodeEvent(
                    level="error",
                    code="simulation_proof_bridge_failed",
                    message="Simulation proof bridge could not be materialized",
                    attrs={"reason": str(exc)},
                )
                error = NodeError(
                    code=node_errors.ERROR_SIMULATION_PROOF_BRIDGE_FAILED,
                    message="Simulation proof bridge failed after Foundry execute",
                    details={
                        "simulation_result_ref": result.simulation_result_ref.model_dump(mode="json"),
                        "reason": str(exc),
                    },
                )
                metrics.record_slo_simulation_run("error", method=method)
                return NodeOutcome(
                    status="fail",
                    state=new_state,
                    artifacts=artifacts,
                    events=[*runtime_events, event],
                    error=error,
                )
            else:
                _attach_simulation_proof_bridge(new_state, bridge_output)
                artifacts.extend(_simulation_proof_bridge_artifacts(bridge_output))
                proof_events.append(
                    NodeEvent(
                        level="info",
                        code="simulation_proof_bridge_materialized",
                        message="Simulation result linked to calibration receipt and proof bundle",
                        attrs={"certification_status": bridge_output.certification_status.value},
                    )
                )

        if _has_nan_signal(result):
            metrics.record_slo_simulation_run("nan", method=method)
        else:
            metrics.record_slo_simulation_run("ok", method=method)

        strategic_events: list[NodeEvent] = []
        if new_state.params.get("strategic_scm") is not None:
            hook_params = dict(new_state.params)
            abstraction_certificate = load_runtime_abstraction_certificate(
                ctx,
                new_state.artifacts_index,
            )
            if abstraction_certificate is not None:
                hook_params["abstraction_certificate"] = abstraction_certificate
            hook_summary, hook_warnings, _ = evaluate_strategic_hook(
                params=hook_params,
                baseline_policy_value=resolve_baseline_policy_value(
                    load_simulation_metrics(ctx, new_state) or simulation_payload
                ),
            )
            for warning in hook_warnings:
                strategic_events.append(
                    NodeEvent(
                        level="warn",
                        message=f"Strategic hook warning: {warning}",
                    )
                )

            candidate_ref = None
            candidate = _coerce_policy_candidate(new_state.params.get("policy_candidate_schema"))
            if candidate is not None:
                candidate_ref = ensure_policy_candidate_ref(
                    ctx,
                    new_state,
                    candidate,
                    None,
                )
            evidence_ref = new_state.artifacts_index.get(
                ARTIFACT_METRICS_REF
            ) or new_state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
            strategic_output = persist_runtime_strategic_artifacts(
                ctx,
                new_state,
                artifacts_index=dict(new_state.artifacts_index),
                candidate_ref=candidate_ref,
                evidence_ref=evidence_ref,
                evidence_role="metrics"
                if evidence_ref == new_state.artifacts_index.get(ARTIFACT_METRICS_REF)
                else "simulation_result",
                baseline_payload=load_simulation_metrics(ctx, new_state) or simulation_payload,
            )
            if strategic_output.strategic_scm_ref is not None:
                new_state.artifacts_index[ARTIFACT_STRATEGIC_SCM_REF] = (
                    strategic_output.strategic_scm_ref
                )
                artifacts.append(strategic_output.strategic_scm_ref)
            if strategic_output.strategic_response_bundle_ref is not None:
                new_state.artifacts_index[ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF] = (
                    strategic_output.strategic_response_bundle_ref
                )
                artifacts.append(strategic_output.strategic_response_bundle_ref)
            final_summary = strategic_output.strategic_response_summary or hook_summary
            if final_summary is not None:
                final_summary = {
                    **dict(final_summary),
                    **build_runtime_abstraction_metadata(
                        ctx,
                        artifacts_index=new_state.artifacts_index,
                    ),
                }
                new_state.params["strategic_response"] = final_summary
                new_state.params["strategic_response_source"] = "run_simulation"
            for warning in strategic_output.warnings:
                strategic_events.append(
                    NodeEvent(
                        level="warn",
                        message=f"Strategic runtime warning: {warning}",
                    )
                )

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=artifacts,
            events=[*runtime_events, *proof_events, *strategic_events],
        )


def _materialize_simulation_proof_bridge(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    simulation_result_ref: ArtifactRef,
    simulation_payload: dict[str, Any] | None,
    method: str,
) -> SimulationProofBridgeArtifacts:
    metrics_ref = _state_or_payload_ref(
        state,
        ARTIFACT_METRICS_REF,
        simulation_payload,
        "metrics_ref",
    )
    state_snapshot_ref = _state_or_payload_ref(
        state,
        ARTIFACT_STATE_SNAPSHOT_REF,
        simulation_payload,
        "state_snapshot_ref",
    )
    causal_query = state.params.get("causal_query")
    return build_simulation_proof_bridge_artifacts(
        ctx.store,
        run_id=state.run_id,
        simulation_result_ref=simulation_result_ref,
        metrics_ref=metrics_ref,
        state_snapshot_ref=state_snapshot_ref,
        constraint_report_ref=state.artifacts_index.get(ARTIFACT_CONSTRAINT_REPORT_REF),
        environment_manifest_ref=state.artifacts_index.get(ARTIFACT_ENVIRONMENT_MANIFEST_REF),
        tee_attestation_ref=state.artifacts_index.get(ARTIFACT_TEE_ATTESTATION_REF),
        sbom_ref=state.artifacts_index.get(ARTIFACT_SBOM_REF),
        interface_mapping_ref=state.artifacts_index.get(ARTIFACT_INTERFACE_MAPPING_REF),
        causal_readiness_bundle_ref=state.artifacts_index.get(ARTIFACT_CAUSAL_READINESS_BUNDLE_REF),
        causal_validity_bundle_ref=state.artifacts_index.get(ARTIFACT_CAUSAL_VALIDITY_BUNDLE_REF),
        causal_query_ref=state.artifacts_index.get(ARTIFACT_CAUSAL_QUERY_RESULT_REF),
        base_proof_bundle_ref=state.artifacts_index.get(ARTIFACT_PROOF_BUNDLE_REF),
        simulation_payload=simulation_payload,
        causal_query=causal_query if isinstance(causal_query, str) else None,
        metadata={"simulation_method": method},
    )


def _state_or_payload_ref(
    state: ExperimentState,
    state_key: str,
    payload: dict[str, Any] | None,
    payload_key: str,
) -> ArtifactRef | None:
    ref = state.artifacts_index.get(state_key)
    if ref is not None:
        return ref
    if not isinstance(payload, dict):
        return None
    raw = payload.get(payload_key)
    if raw is None:
        return None
    return ArtifactRef.model_validate(raw)


def _attach_simulation_proof_bridge(
    state: ExperimentState,
    output: SimulationProofBridgeArtifacts,
) -> None:
    state.artifacts_index[ARTIFACT_SIMULATION_PROOF_BRIDGE_REF] = _to_core_ref(output.bridge_ref)
    state.artifacts_index[ARTIFACT_SIMULATION_CALIBRATION_RECEIPT_REF] = _to_core_ref(
        output.calibration_receipt_ref
    )
    state.artifacts_index[ARTIFACT_CAUSAL_EVIDENCE_BUNDLE_REF] = _to_core_ref(
        output.evidence_bundle_ref
    )
    state.artifacts_index[ARTIFACT_PROOF_BUNDLE_REF] = _to_core_ref(output.proof_bundle_ref)
    state.artifacts_index[ARTIFACT_PROOF_WITNESS_INDEX_REF] = _to_core_ref(
        output.witness_index_ref
    )
    state.artifacts_index[ARTIFACT_PROOF_COMPOSABILITY_CERTIFICATE_REF] = _to_core_ref(
        output.composability_certificate_ref
    )


def _simulation_proof_bridge_artifacts(output: SimulationProofBridgeArtifacts) -> list[ArtifactRef]:
    return [
        _to_core_ref(output.bridge_ref),
        _to_core_ref(output.calibration_receipt_ref),
        _to_core_ref(output.evidence_bundle_ref),
        _to_core_ref(output.proof_bundle_ref),
        _to_core_ref(output.witness_index_ref),
        _to_core_ref(output.composability_certificate_ref),
    ]


def _to_core_ref(ref: Any) -> ArtifactRef:
    if isinstance(ref, ArtifactRef):
        return ref
    if hasattr(ref, "model_dump"):
        return ArtifactRef.model_validate(ref.model_dump(mode="json"))
    return ArtifactRef.model_validate(ref)


def _has_nan_signal(result: Any) -> bool:
    notes = getattr(result, "notes", None)
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, str) and "nan" in note.lower():
                return True
    return False


def _coerce_policy_candidate(payload: Any) -> PolicyCandidateSchema | None:
    if isinstance(payload, PolicyCandidateSchema):
        return payload
    if payload is None:
        return None
    try:
        return PolicyCandidateSchema.model_validate(payload)
    except _SIMULATION_VALIDATION_ERRORS:
        return None
