from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.foundry import ExecuteRequest, FoundryExecConfig, SimulationResult
from polisyos.core.observability import get_metrics
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONSTRAINT_REPORT_REF,
    ARTIFACT_ENVIRONMENT_MANIFEST_REF,
    ARTIFACT_EXEC_PLAN_REF,
    ARTIFACT_METRICS_REF,
    ARTIFACT_SBOM_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_STATE_DELTA_REF,
    ARTIFACT_STATE_SNAPSHOT_REF,
    ARTIFACT_TEE_ATTESTATION_REF,
    INPUT_INPUT_BINDINGS_REF,
    INPUT_REGISTRY_BUNDLE_REF,
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
        f"inputs.{INPUT_INPUT_BINDINGS_REF}",
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
        "params.simulation_method",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_METRICS_REF}",
        f"artifacts_index.{ARTIFACT_STATE_DELTA_REF}",
        f"artifacts_index.{ARTIFACT_STATE_SNAPSHOT_REF}",
        f"artifacts_index.{ARTIFACT_CONSTRAINT_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_ENVIRONMENT_MANIFEST_REF}",
        f"artifacts_index.{ARTIFACT_TEE_ATTESTATION_REF}",
        f"artifacts_index.{ARTIFACT_SBOM_REF}",
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
    ],
)


@dataclass(frozen=True)
class RunSimulationNode:
    exec_config: FoundryExecConfig = field(default_factory=FoundryExecConfig)

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "RunSimulationNode":
        if not params:
            return self
        config = self.exec_config.model_copy(deep=True)
        for key, value in params.items():
            if key in config.model_fields:
                setattr(config, key, value)
        return replace(self, exec_config=config)

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        metrics = get_metrics()
        method = str(state.params.get("simulation_method", "foundry.execute"))

        if ctx.foundry is None:
            error = NodeError(
                code=node_errors.ERROR_FOUNDATION_MISSING,
                message="Foundry port is not configured",
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=state, error=error)

        exec_plan_ref = state.artifacts_index.get(ARTIFACT_EXEC_PLAN_REF)
        if exec_plan_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing exec_plan_ref for simulation",
                details={"required": ARTIFACT_EXEC_PLAN_REF},
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=state, error=error)

        input_bindings_ref = state.inputs.get(INPUT_INPUT_BINDINGS_REF)
        if input_bindings_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message=(
                    "Missing input source for simulation: input_bindings_ref is required"
                ),
                details={"required": [INPUT_INPUT_BINDINGS_REF]},
            )
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(status="fail", state=state, error=error)

        registry_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)

        request = ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=input_bindings_ref,
            registry_bundle_ref=registry_ref,
            exec_config=self.exec_config,
        )

        result = ctx.foundry.execute(ctx.store, request)

        new_state = state.model_copy(deep=True)
        artifacts = []

        if result.simulation_result_ref is not None:
            new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = result.simulation_result_ref
            artifacts.append(result.simulation_result_ref)

            try:
                payload = from_canonical_bytes(
                    ctx.store.get_bytes(result.simulation_result_ref.artifact_id)
                )
                sim_result = SimulationResult.model_validate(payload)
                if sim_result.state_snapshot_ref is not None:
                    new_state.artifacts_index[ARTIFACT_STATE_SNAPSHOT_REF] = (
                        sim_result.state_snapshot_ref
                    )
            except Exception:
                pass

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
                    )()
                },
            )
            event = NodeEvent(level="error", message="Foundry execute returned ok=False")
            metrics.record_slo_simulation_run("error", method=method)
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=artifacts,
                events=[event],
                error=error,
            )

        if _has_nan_signal(result):
            metrics.record_slo_simulation_run("nan", method=method)
        else:
            metrics.record_slo_simulation_run("ok", method=method)
        return NodeOutcome(status="ok", state=new_state, artifacts=artifacts)


def _has_nan_signal(result: Any) -> bool:
    notes = getattr(result, "notes", None)
    if isinstance(notes, list):
        for note in notes:
            if isinstance(note, str) and "nan" in note.lower():
                return True
    return False
