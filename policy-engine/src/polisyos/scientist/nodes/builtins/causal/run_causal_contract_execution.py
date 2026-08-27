"""Node adapter for executing observation-plane bounds and temporal-DTR contracts.

The node bridges `ExperimentState.params` task payloads into the pure
`BoundsEstimationRunner` and Lex temporal sequence compiler, then persists a
`CausalExecutionBundle` plus the first concrete bounds/DTR artifacts for
downstream decision packaging and audit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.dtr import (
    ALearningDTR,
    DoublyRobustDTR,
    OutcomeWeightedLearning,
    QLearningDTR,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.dynamic_regime import DTRResult, persist_dynamic_treatment_regime
from polisyos.ir.artifacts import InputRef
from polisyos.ir.governance.policy_spec import TemporalInterventionSequence
from polisyos.ir.kernel.base import KernelModel
from polisyos.ir.observation.causal_execution import (
    BoundsEstimationTask,
    CausalExecutionBundle,
    TemporalDTRExecutionEntry,
    TemporalDTRTask,
    persist_causal_execution_bundle,
)
from polisyos.ir.registry.refs import ArtifactRefModel, EffectTrajectoryBundleRef
from polisyos.lex.interventions import TemporalInterventionSequencer
from polisyos.scientist.methods.causal.execution import BoundsEstimationRunner
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_BOUNDS_BUNDLE_REF,
    ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF,
    ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF,
    ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

if TYPE_CHECKING:
    from polisyos.ir.artifacts import ArtifactStore


class TemporalInterventionSequenceCompileResult(KernelModel):
    """Compiled DTR execution entry plus the data used to produce it."""

    entry: TemporalDTRExecutionEntry
    dynamic_treatment_data: DynamicTreatmentData
    dtr_result: DTRResult | None = None


class TemporalInterventionSequenceCompiler:
    """Resolve temporal intervention tasks into Foundry-owned DTR outputs."""

    def __init__(
        self,
        *,
        store: ArtifactStore | None = None,
        sequencer: TemporalInterventionSequencer | None = None,
    ) -> None:
        self.store = store
        self.sequencer = sequencer or TemporalInterventionSequencer()

    def compile(
        self,
        task: TemporalDTRTask | Mapping[str, Any],
        *,
        inputs: Sequence[InputRef] | None = None,
    ) -> TemporalInterventionSequenceCompileResult:
        """Execute one temporal DTR task and persist optional causal artifacts."""
        resolved_task = (
            task if isinstance(task, TemporalDTRTask) else TemporalDTRTask.model_validate(task)
        )
        base_inputs = list(inputs or [])
        warnings: list[str] = []
        dynamic_data, sequence = self._resolve_dynamic_treatment_data(resolved_task)
        output = self._run_dtr_method(
            dynamic_data,
            method=resolved_task.dtr_method,
            params=resolved_task.params,
        )
        dtr_payload = output.get("dtr_result")
        dtr_result = None
        if dtr_payload is not None:
            dtr_result = (
                dtr_payload
                if isinstance(dtr_payload, DTRResult)
                else DTRResult.model_validate(dtr_payload)
            )
        else:
            warnings.append("DTR estimator did not return an optimal regime result.")

        regime_ref = None
        if self.store is not None and dtr_result is not None:
            regime_ref = persist_dynamic_treatment_regime(
                self.store,
                dtr_result.optimal_regime,
                inputs=base_inputs,
            )

        effect_ref = None
        if resolved_task.continuous_time_query is not None:
            if self.store is None:
                warnings.append(
                    "Continuous-time query requested without ArtifactStore; "
                    "effect trajectory was not persisted."
                )
            else:
                trajectory = CausalEngine(artifact_store=self.store).temporal_causal_effect(
                    dynamic_data,
                    resolved_task.continuous_time_query,
                    intervention=resolved_task.intervention_trajectory,
                    method=resolved_task.dtr_method,
                )
                effect_bundle_artifact_id = trajectory.metadata.get("effect_bundle_artifact_id")
                if isinstance(effect_bundle_artifact_id, str) and effect_bundle_artifact_id.strip():
                    effect_ref = EffectTrajectoryBundleRef(
                        artifact_id=effect_bundle_artifact_id,
                        kind="ir.effect_trajectory_bundle",
                        media_type="application/json",
                    )
                else:
                    warnings.append(
                        "Continuous-time execution completed without a persisted effect bundle."
                    )

        entry = TemporalDTRExecutionEntry(
            task_id=resolved_task.task_id,
            sequence_id=_optional_id(
                sequence.sequence_id
                if sequence is not None
                else dynamic_data.metadata.get("sequence_id")
            ),
            dynamic_intervention_id=_optional_id(
                sequence.dynamic_intervention_id
                if sequence is not None
                else dynamic_data.metadata.get("dynamic_intervention_id")
            ),
            status="ok" if dtr_result is not None else "blocked",
            dtr_method=resolved_task.dtr_method,
            value_estimate=None if dtr_result is None else float(dtr_result.value_estimate),
            warnings=warnings,
            dynamic_treatment_regime_ref=regime_ref,
            effect_trajectory_bundle_ref=effect_ref,
            metadata={
                "n_units": dynamic_data.n_units,
                "n_periods": dynamic_data.n_periods,
                "n_stages": None if dtr_result is None else dtr_result.n_stages,
                "source_precedence": self._source_precedence(resolved_task),
                **dict(resolved_task.metadata),
            },
        )
        return TemporalInterventionSequenceCompileResult(
            entry=entry,
            dynamic_treatment_data=dynamic_data,
            dtr_result=dtr_result,
        )

    def compile_many(
        self,
        tasks: Sequence[TemporalDTRTask | Mapping[str, Any]],
        *,
        inputs: Sequence[InputRef] | None = None,
    ) -> list[TemporalInterventionSequenceCompileResult]:
        """Compile multiple temporal DTR tasks using one artifact-store context."""
        return [self.compile(task, inputs=inputs) for task in tasks]

    def _resolve_dynamic_treatment_data(
        self,
        task: TemporalDTRTask,
    ) -> tuple[DynamicTreatmentData, TemporalInterventionSequence | None]:
        if task.dynamic_treatment_data is not None:
            return task.dynamic_treatment_data, task.temporal_sequence
        if task.bundle_manifest is not None and task.bundle_manifest.contract_payload:
            return DynamicTreatmentData.model_validate(
                task.bundle_manifest.contract_payload
            ), task.temporal_sequence
        sequence = task.temporal_sequence
        if sequence is None:
            sequence = self.sequencer.compile_sequence(
                sequence_id=task.sequence_id or f"{task.task_id}.sequence",
                dynamic_intervention_id=task.dynamic_intervention_id or f"{task.task_id}.dynamic",
                steps=task.steps,
                compiled_interventions=task.compiled_interventions,
                identification_mode=task.identification_mode,
                strategic_response_expected=task.strategic_response_expected,
                transmission_channels=task.transmission_channels,
                notes=task.notes,
            )
        dynamic_data = _to_dynamic_treatment(
            sequence,
            n_units=task.n_units,
            time_ids=None if not task.time_ids else task.time_ids,
            covariate_names=None if not task.covariate_names else task.covariate_names,
            outcome=task.outcome,
        )
        return dynamic_data, sequence

    def _run_dtr_method(
        self,
        data: DynamicTreatmentData,
        *,
        method: str,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        dispatch = {
            "q_learning": QLearningDTR,
            "a_learning": ALearningDTR,
            "owl": OutcomeWeightedLearning,
            "dr_dtr": DoublyRobustDTR,
        }
        method_cls = dispatch.get(method)
        if method_cls is None:
            raise ValueError(f"unsupported dtr_method '{method}'")
        return method_cls.pure_step(data, dict(params))

    def _source_precedence(self, task: TemporalDTRTask) -> str:
        if task.dynamic_treatment_data is not None:
            return "dynamic_treatment_data"
        if task.bundle_manifest is not None and task.bundle_manifest.contract_payload:
            return "bundle_manifest.contract_payload"
        if task.temporal_sequence is not None:
            return "temporal_sequence"
        return "sequence_steps"


def _to_dynamic_treatment(
    sequence: TemporalInterventionSequence | Mapping[str, Any],
    *,
    n_units: int = 10,
    time_ids: Sequence[Any] | None = None,
    covariate_names: Sequence[str] | None = None,
    outcome: Sequence[float] | np.ndarray | None = None,
) -> DynamicTreatmentData:
    """Render a neutral temporal sequence into Foundry dynamic-treatment data."""
    resolved = (
        sequence
        if isinstance(sequence, TemporalInterventionSequence)
        else TemporalInterventionSequence.model_validate(sequence)
    )
    if n_units < 10:
        raise ValueError("n_units must be >= 10 for DynamicTreatmentData")

    step_dates = [step.effective_date for step in resolved.steps]
    if time_ids is None:
        ordered_time_ids = ["baseline", *step_dates]
    else:
        ordered_time_ids = list(time_ids)
        required_periods = len(step_dates) + 1
        if len(ordered_time_ids) < required_periods:
            raise ValueError(
                f"time_ids must provide at least {required_periods} periods for the sequence"
            )
    n_periods = len(ordered_time_ids)
    treatment_sequence = np.zeros((n_units, n_periods), dtype=np.int8)
    for activation_index in range(1, min(len(step_dates) + 1, n_periods)):
        treatment_sequence[:, activation_index:] = 1

    covariate_names_resolved = list(covariate_names or ["unit_index", "time_index"])
    covariate_sequence = np.zeros(
        (n_units, n_periods, len(covariate_names_resolved)),
        dtype=np.float32,
    )
    unit_axis = np.linspace(0.0, 1.0, num=n_units, dtype=np.float32)
    time_axis = np.linspace(0.0, 1.0, num=n_periods, dtype=np.float32)
    for unit_index, unit_value in enumerate(unit_axis):
        covariate_sequence[unit_index, :, 0] = unit_value
    if len(covariate_names_resolved) > 1:
        covariate_sequence[:, :, 1] = time_axis
    for extra_index in range(2, len(covariate_names_resolved)):
        covariate_sequence[:, :, extra_index] = treatment_sequence

    if outcome is None:
        outcome_array = treatment_sequence.mean(axis=1, dtype=np.float32) + np.linspace(
            0.0, 0.09, num=n_units, dtype=np.float32
        )
    else:
        outcome_array = np.asarray(outcome, dtype=np.float32)

    return DynamicTreatmentData(
        outcome=outcome_array,
        treatment_sequence=treatment_sequence,
        covariate_sequence=covariate_sequence,
        time_ids=np.asarray(ordered_time_ids, dtype=object),
        variable_names=covariate_names_resolved,
        metadata={
            "data_origin": "c6a_synthetic_scaffold",
            "sequence_id": resolved.sequence_id,
            "dynamic_intervention_id": resolved.dynamic_intervention_id,
            "identification_mode": resolved.identification_mode.value,
            "strategic_response_expected": resolved.strategic_response_expected,
            "transmission_channels": [channel.value for channel in resolved.transmission_channels],
            "intervention_ids": [step.intervention_id for step in resolved.steps],
            "parameter_override_summary": {
                step.step_id: sorted(step.parameter_overrides)
                for step in resolved.steps
                if step.parameter_overrides
            },
        },
    )


def _optional_id(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None

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
        "run_id",
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

_CAUSAL_CONTRACT_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)


def _artifact_input_ref(ref: ArtifactRefModel | None, *, role: str) -> InputRef | None:
    if ref is None:
        return None
    return InputRef(artifact_id=ref.artifact_id, role=role)


class RunCausalContractExecutionNode:
    """Run C4b execution tasks and publish aggregate plus primary causal artifacts.

    Upstream assumptions: planners or loaders have placed
    `params.bounds_estimation_tasks` and/or `params.temporal_dtr_tasks` into the
    state as sequences of typed task dicts. When neither list is present the node
    skips; when a payload is non-sequence or invalid it fails with
    `ERROR_INVALID_STATE`.

    Writes to state:
        `artifacts_index.causal_execution_bundle_ref`,
        `artifacts_index.bounds_bundle_ref`,
        `artifacts_index.dynamic_treatment_regime_ref`,
        `artifacts_index.effect_trajectory_bundle_ref`.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        """Execute the task lists and persist the aggregate execution bundle."""
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
                task
                if isinstance(task, BoundsEstimationTask)
                else BoundsEstimationTask.model_validate(task)
                for task in (bounds_payload or [])
            ]
            temporal_tasks = [
                task if isinstance(task, TemporalDTRTask) else TemporalDTRTask.model_validate(task)
                for task in (temporal_payload or [])
            ]
        except _CAUSAL_CONTRACT_VALIDATION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid C4b task payload: {exc}",
                ),
            )

        bounds_entries = BoundsEstimationRunner(store=ctx.store).run(bounds_tasks)
        temporal_results = TemporalInterventionSequenceCompiler(store=ctx.store).compile_many(
            temporal_tasks
        )
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
                    _artifact_input_ref(
                        entry.dynamic_treatment_regime_ref, role="dynamic_treatment_regime"
                    )
                    for entry in temporal_entries
                ),
                *(
                    _artifact_input_ref(
                        entry.effect_trajectory_bundle_ref, role="effect_trajectory_bundle"
                    )
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

        next_state = branch_state(
            state,
            write_paths=(
                f"artifacts_index.{ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_BOUNDS_BUNDLE_REF}",
                f"artifacts_index.{ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF}",
                f"artifacts_index.{ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF}",
            ),
        ).state
        next_state.artifacts_index[ARTIFACT_CAUSAL_EXECUTION_BUNDLE_REF] = (
            ArtifactRef.model_validate(aggregate_ref.model_dump(mode="json"))
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
                ref = ArtifactRef.model_validate(
                    entry.dynamic_treatment_regime_ref.model_dump(mode="json")
                )
                next_state.artifacts_index[ARTIFACT_DYNAMIC_TREATMENT_REGIME_REF] = ref
                primary_artifacts.append(ref)
                break
        for entry in temporal_entries:
            if entry.effect_trajectory_bundle_ref is not None:
                ref = ArtifactRef.model_validate(
                    entry.effect_trajectory_bundle_ref.model_dump(mode="json")
                )
                next_state.artifacts_index[ARTIFACT_EFFECT_TRAJECTORY_BUNDLE_REF] = ref
                primary_artifacts.append(ref)
                break

        successful_runs = sum(
            1 for entry in (*bounds_entries, *temporal_entries) if entry.status == "ok"
        )
        blocked_runs = sum(
            1 for entry in (*bounds_entries, *temporal_entries) if entry.status == "blocked"
        )
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
                            entry.effect_trajectory_bundle_ref is not None
                            for entry in temporal_entries
                        ),
                    },
                )
            ],
        )


__all__ = ["RunCausalContractExecutionNode"]
