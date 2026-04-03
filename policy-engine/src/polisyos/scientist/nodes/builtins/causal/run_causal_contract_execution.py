"""Public causal run causal contract execution module API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.artifacts import InputRef
from polisyos.ir.observation.causal_execution import (
    BoundsEstimationTask,
    CausalExecutionBundle,
    TemporalDTRTask,
    persist_causal_execution_bundle,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.lex.interventions import TemporalInterventionSequenceCompiler
from polisyos.scientist.causal.execution import BoundsEstimationRunner
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF,
    ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF,
    ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_contract_execution@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Causal Contract Execution",
    description=(
        "Execute C4b bounds-estimation and temporal-DTR tasks over compiled observation-plane contracts."
    ),
    tags=["builtin", "causal", "wave3", "c4b"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.bounds_estimation_tasks",
        "params.temporal_dtr_tasks",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_BOUNDS_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF}",
        f"artifacts_index.{ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF,
        ARTIFACT_BOUNDS_BUNDLE_REF,
        ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF,
        ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF,
    ],
)


def _artifact_input_ref(ref: ArtifactRefModel | None, *, role: str) -> InputRef | None:
    if ref is None:
        return None
    return InputRef(artifact_id=ref.artifact_id, role=role)


class RunCausalContractExecutionNode:
    """Execute compiled observation-plane bounds and temporal-DTR contracts."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        bounds_payload = state.params.get("bounds_estimation_tasks")
        temporal_payload = state.params.get("temporal_dtr_tasks")
        if not bounds_payload and not temporal_payload:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No C4b execution tasks found; skip causal contract execution.",
                    )
                ],
            )
        if bounds_payload is not None and not isinstance(bounds_payload, Sequence):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="params.bounds_estimation_tasks must be a sequence when provided.",
                ),
            )
        if temporal_payload is not None and not isinstance(temporal_payload, Sequence):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="params.temporal_dtr_tasks must be a sequence when provided.",
                ),
            )

        try:
            bounds_tasks = [
                task if isinstance(task, BoundsEstimationTask) else BoundsEstimationTask.model_validate(task)
                for task in (bounds_payload or [])
            ]
            temporal_tasks = [
                task if isinstance(task, TemporalDTRTask) else TemporalDTRTask.model_validate(task)
                for task in (temporal_payload or [])
            ]
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid C4b task payload: {exc}",
                ),
            )

        bounds_entries = BoundsEstimationRunner(store=ctx.store).run(bounds_tasks)
        temporal_results = TemporalInterventionSequenceCompiler(store=ctx.store).compile_many(temporal_tasks)
        temporal_entries = [result.entry for result in temporal_results]

        aggregate_bundle = CausalExecutionBundle(
            bounds_results=bounds_entries,
            temporal_results=temporal_entries,
            metadata={"run_id": state.run_id},
        )
        aggregate_inputs = [
            ref
            for ref in (
                *(
                    _artifact_input_ref(entry.bounds_bundle_ref, role="bounds_bundle")
                    for entry in bounds_entries
                ),
                *(
                    _artifact_input_ref(entry.dynamic_treatment_regime_ref, role="dynamic_treatment_regime")
                    for entry in temporal_entries
                ),
                *(
                    _artifact_input_ref(entry.effect_trajectory_bundle_ref, role="effect_trajectory_bundle")
                    for entry in temporal_entries
                ),
            )
            if ref is not None
        ]
        aggregate_ref = persist_causal_execution_bundle(
            ctx.store,
            aggregate_bundle,
            inputs=aggregate_inputs,
        )

        next_state = state.model_copy(deep=True)
        next_state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF] = ArtifactRef.model_validate(
            aggregate_ref.model_dump(mode="json")
        )
        primary_artifacts: list[ArtifactRef] = [
            ArtifactRef.model_validate(aggregate_ref.model_dump(mode="json"))
        ]
        for entry in bounds_entries:
            if entry.bounds_bundle_ref is not None:
                ref = ArtifactRef.model_validate(entry.bounds_bundle_ref.model_dump(mode="json"))
                next_state.artifacts_index[ARTIFACT_BOUNDS_BUNDLE_REF] = ref
                primary_artifacts.append(ref)
                break
        for entry in temporal_entries:
            if entry.dynamic_treatment_regime_ref is not None:
                ref = ArtifactRef.model_validate(entry.dynamic_treatment_regime_ref.model_dump(mode="json"))
                next_state.artifacts_index[ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF] = ref
                primary_artifacts.append(ref)
                break
        for entry in temporal_entries:
            if entry.effect_trajectory_bundle_ref is not None:
                ref = ArtifactRef.model_validate(entry.effect_trajectory_bundle_ref.model_dump(mode="json"))
                next_state.artifacts_index[ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF] = ref
                primary_artifacts.append(ref)
                break

        successful_runs = sum(1 for entry in (*bounds_entries, *temporal_entries) if entry.status == "ok")
        blocked_runs = sum(1 for entry in (*bounds_entries, *temporal_entries) if entry.status == "blocked")
        return NodeOutcome(
            status="ok",
            state=next_state,
            artifacts=primary_artifacts,
            events=[
                NodeEvent(
                    level="info",
                    message="C4b causal contract execution completed.",
                    attrs={
                        "bounds_tasks": len(bounds_entries),
                        "temporal_tasks": len(temporal_entries),
                        "successful_runs": successful_runs,
                        "blocked_runs": blocked_runs,
                        "temporal_trajectory_emitted": any(
                            entry.effect_trajectory_bundle_ref is not None for entry in temporal_entries
                        ),
                    },
                )
            ],
        )


__all__ = ["RunCausalContractExecutionNode"]
