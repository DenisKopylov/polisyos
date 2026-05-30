"""Compile legal provisions into policy interventions and temporal DTR execution plans.

Use this module after NormPack/provision mapping steps when legal clauses must be turned into
``InterventionSpec`` objects, tunable ``ParameterSpec`` knobs, temporal treatment sequences, or
hierarchical Scientist policy-search requests.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import numpy as np
from pydantic import Field, model_validator

from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
from polisyos.foundry.methods.catalog.causal.dtr import (
    ALearningDTR,
    DoublyRobustDTR,
    OutcomeWeightedLearning,
    QLearningDTR,
)
from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.dynamic_regime import DTRResult, persist_dynamic_treatment_regime
from polisyos.ir.governance.policy_spec import (
    InterventionSpec,
    ParameterSpec,
    TemporalInterventionSequence,
    TemporalInterventionStep,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import (
    CountValue,
    DurationValue,
    MoneyValue,
    ParamValue,
    RateValue,
)
from polisyos.ir.observation.bundles import StrategicResponseSpec, StrategicResponseSpecsBundle
from polisyos.ir.observation.causal_execution import (
    TemporalDTRExecutionEntry,
    TemporalDTRTask,
)
from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel
from polisyos.ir.registry.refs import EffectTrajectoryBundleRef
from polisyos.ir.trinity import TrinityBundle
from polisyos.lex.intervention_artifacts import (
    LexPolicyBundleInput,
    LexProvisionMappingRegistry,
)
from polisyos.scientist.methods.search.controller import SearchIteration, SearchResult, SearchStatus
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.policy_design.search import (
    HierarchicalSearchConfig,
    HierarchicalSearchCoordinator,
    PolicySearchLevel,
)

if TYPE_CHECKING:
    from polisyos.ir.artifacts import ArtifactStore, InputRef


class InterventionKnobSpec(KernelModel):
    """Tunable parameter exposed by a legal provision mapping.

    Bounds are validated by ``LexInterventionCompiler`` against ``default_value`` and duplicate
    ``param_id`` / ``param_path`` values are rejected per directive.
    """

    param_id: str = Field(..., pattern=ID_PATTERN)
    param_path: str = Field(..., min_length=1, max_length=120)
    default_value: ParamValue
    min_value: ParamValue | None = None
    max_value: ParamValue | None = None
    tunable: bool = True
    sensitivity_priority: int = Field(default=5, ge=1, le=10)
    notes: list[str] = Field(default_factory=list, max_length=10)


class LexProvisionDirective(KernelModel):
    """Provision-level request that compiles one legal clause into an ``InterventionSpec``.

    The directive is usually produced by ``LexProvisionMappingRegistry.resolve`` and then passed
    to ``LexInterventionCompiler.compile``. Strategic-response settings must be internally
    consistent: when ``strategic_response_expected`` is true, at least one transmission channel
    must be declared.
    """

    provision_ref: str = Field(..., min_length=1, max_length=200)
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    intervention_kind: str = Field(..., pattern=ID_PATTERN)
    target: SelectorExpr
    schedule: ScheduleSpec
    params: dict[str, ParamValue] = Field(default_factory=dict)
    knobs: list[InterventionKnobSpec] = Field(default_factory=list)
    target_population_type: str | None = Field(None, max_length=120)
    target_sector_ids: list[str] = Field(default_factory=list)
    target_region_ids: list[str] = Field(default_factory=list)
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    identification_mode: IdentificationMode | None = None
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list, max_length=10)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_strategy_channels(self) -> LexProvisionDirective:
        if self.strategic_response_expected and not self.transmission_channels:
            raise ValueError(
                "transmission_channels are required when strategic_response_expected=True"
            )
        return self


class CompiledLexIntervention(KernelModel):
    """Compiled intervention plus tunable parameter specs."""

    intervention: InterventionSpec
    parameters: list[ParameterSpec] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalInterventionStepInput(KernelModel):
    """Friendly input shape for one time-ordered intervention activation step."""

    step_id: str | None = Field(None, pattern=ID_PATTERN)
    effective_date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}(-\d{2})?$",
    )
    intervention_id: str = Field(..., pattern=ID_PATTERN)
    parameter_overrides: dict[str, ParamValue] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list, max_length=20)


class StrategicResponseRegistryEntry(KernelModel):
    """Registry entry layered on top of the IR strategic response contract."""

    spec: StrategicResponseSpec
    expected_response_type: str = Field(default="performative_shift", min_length=1, max_length=120)
    hook_config: dict[str, Any] = Field(default_factory=dict)


class HierarchicalPolicySearchPlan(KernelModel):
    """Serializable handoff contract for Scientist hierarchical policy search."""

    coordinator_fqn: str = Field(
        default="polisyos.scientist.policy_design.search.HierarchicalSearchCoordinator",
        min_length=1,
        max_length=255,
    )
    candidate_id: str = Field(..., min_length=1, max_length=120)
    candidate_hash: str = Field(..., min_length=1, max_length=120)
    policy_family: str = Field(..., min_length=1, max_length=120)
    level_order: list[PolicySearchLevel] = Field(
        default_factory=lambda: [
            PolicySearchLevel.STRUCTURE,
            PolicySearchLevel.PARAMETER,
            PolicySearchLevel.NARRATIVE,
        ]
    )
    search_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LexInterventionCompiler:
    """Compile Lex provision directives into executable intervention contracts."""

    def compile(
        self,
        directive: LexProvisionDirective | Mapping[str, Any],
    ) -> CompiledLexIntervention:
        """Compile one directive into an intervention contract plus tunable parameter specs.

        Args:
            directive: Typed ``LexProvisionDirective`` or a mapping accepted by its Pydantic model.

        Returns:
            ``CompiledLexIntervention`` containing the IR intervention contract, generated
            ``ParameterSpec`` rows, and mapping metadata.

        Raises:
            ValueError: If knob identifiers/paths are duplicated, point to unknown params, or
                define inverted/out-of-range bounds.
        """
        resolved = (
            directive
            if isinstance(directive, LexProvisionDirective)
            else LexProvisionDirective.model_validate(directive)
        )
        self._validate_knobs(resolved)
        intervention = InterventionSpec(
            intervention_id=resolved.intervention_id,
            kind=resolved.intervention_kind,
            target=resolved.target,
            schedule=resolved.schedule,
            params=resolved.params,
            lex_provision_ref=resolved.provision_ref,
            target_population_type=resolved.target_population_type,
            target_sector_ids=resolved.target_sector_ids,
            target_region_ids=resolved.target_region_ids,
            measurement_expectations=resolved.measurement_expectations,
            identification_mode=resolved.identification_mode,
            strategic_response_expected=resolved.strategic_response_expected,
            transmission_channels=resolved.transmission_channels,
            notes=resolved.notes,
        )
        parameters = [
            ParameterSpec(
                param_id=knob.param_id,
                intervention_id=resolved.intervention_id,
                param_path=knob.param_path,
                default_value=knob.default_value,
                min_value=knob.min_value,
                max_value=knob.max_value,
                tunable=knob.tunable,
                sensitivity_priority=knob.sensitivity_priority,
            )
            for knob in resolved.knobs
        ]
        compiled_metadata = dict(resolved.metadata)
        compiled_metadata.setdefault("knob_ids", [knob.param_id for knob in resolved.knobs])
        compiled_metadata.setdefault("provision_ref", resolved.provision_ref)
        return CompiledLexIntervention(
            intervention=intervention,
            parameters=parameters,
            metadata=compiled_metadata,
        )

    def compile_from_mapping(
        self,
        registry: LexProvisionMappingRegistry,
        provision_ref: str,
        *,
        intervention_id: str,
        target: SelectorExpr | Mapping[str, Any],
        schedule: ScheduleSpec | Mapping[str, Any],
        params: Mapping[str, ParamValue] | None = None,
        knob_value_overrides: Mapping[str, ParamValue] | None = None,
        target_population_type: str | None = None,
        target_sector_ids: Sequence[str] | None = None,
        target_region_ids: Sequence[str] | None = None,
        measurement_expectations: Mapping[str, Any] | None = None,
        identification_mode: IdentificationMode | None = None,
        strategic_response_expected: bool | None = None,
        transmission_channels: Sequence[StrategicResponseChannel] | None = None,
        notes: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CompiledLexIntervention:
        """Resolve a provision mapping from a registry and compile it into IR contracts.

        Args:
            registry: Provision mapping and knob registry.
            provision_ref: Legal provision key expected by the registry.
            intervention_id: Target intervention id to place on the compiled IR contract.
            target: Selector expression for intervention targeting.
            schedule: Schedule contract for the intervention lifecycle.
            params: Optional base parameter payload before knob overrides are applied.
            knob_value_overrides: Optional values keyed by knob id.
            target_population_type: Optional override for registry population metadata.
            target_sector_ids: Optional explicit sector override.
            target_region_ids: Optional explicit region override.
            measurement_expectations: Optional expectation metadata merged with the registry entry.
            identification_mode: Optional override for the registry identification mode.
            strategic_response_expected: Optional consistency-checked override.
            transmission_channels: Optional consistency-checked channel override.
            notes: Additional notes appended to the compiled directive.
            metadata: Additional metadata merged into the compiled payload.

        Returns:
            Compiled intervention and parameter specs.

        Raises:
            KeyError: If the provision mapping or one of its knob ids is unknown.
            ValueError: If explicit strategic-response overrides conflict with the registry.
        """
        mapping_entry = registry.require_mapping(provision_ref)
        if (
            strategic_response_expected is not None
            and strategic_response_expected != mapping_entry.strategic_response_expected
        ):
            raise ValueError("explicit strategic_response_expected conflicts with registry mapping")
        if transmission_channels is not None and tuple(transmission_channels) != tuple(
            mapping_entry.transmission_channels
        ):
            raise ValueError("explicit transmission_channels conflict with registry mapping")
        directive = registry.resolve(
            provision_ref,
            intervention_id=intervention_id,
            target=target,
            schedule=schedule,
            params=params,
            knob_value_overrides=knob_value_overrides,
            target_population_type=target_population_type,
            target_sector_ids=target_sector_ids,
            target_region_ids=target_region_ids,
            measurement_expectations=measurement_expectations,
            identification_mode=identification_mode,
            strategic_response_expected=strategic_response_expected,
            transmission_channels=transmission_channels,
            notes=notes,
            metadata=metadata,
        )
        return self.compile(directive)

    def _validate_knobs(self, directive: LexProvisionDirective) -> None:
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for knob in directive.knobs:
            if knob.param_id in seen_ids:
                raise ValueError(f"duplicate knob param_id '{knob.param_id}'")
            if knob.param_path in seen_paths:
                raise ValueError(f"duplicate knob param_path '{knob.param_path}'")
            seen_ids.add(knob.param_id)
            seen_paths.add(knob.param_path)
            self._validate_knob_path(knob, directive.params)
            self._validate_knob_bounds(knob)

    def _validate_knob_path(
        self,
        knob: InterventionKnobSpec,
        params: Mapping[str, Any],
    ) -> None:
        value, ok = _resolve_param_path(params, knob.param_path)
        if not ok:
            raise ValueError(
                f"knob '{knob.param_id}' references unknown intervention param '{knob.param_path}'"
            )
        if value != knob.default_value and _param_value_to_decimal(
            value
        ) == _param_value_to_decimal(knob.default_value):
            return

    def _validate_knob_bounds(self, knob: InterventionKnobSpec) -> None:
        default_value = _param_value_to_decimal(knob.default_value)
        min_value = _param_value_to_decimal(knob.min_value)
        max_value = _param_value_to_decimal(knob.max_value)
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError(f"knob '{knob.param_id}' has inverted bounds")
        if min_value is not None and default_value is not None and default_value < min_value:
            raise ValueError(f"knob '{knob.param_id}' default_value is below min_value")
        if max_value is not None and default_value is not None and default_value > max_value:
            raise ValueError(f"knob '{knob.param_id}' default_value is above max_value")


class TemporalInterventionSequencer:
    """Compile legal intervention timelines into DTR-ready sequence contracts."""

    def compile_sequence(
        self,
        *,
        sequence_id: str,
        dynamic_intervention_id: str,
        steps: Sequence[
            TemporalInterventionStepInput | TemporalInterventionStep | Mapping[str, Any]
        ],
        compiled_interventions: (
            Sequence[CompiledLexIntervention | Mapping[str, Any]]
            | Mapping[str, CompiledLexIntervention | Mapping[str, Any]]
            | None
        ) = None,
        identification_mode: IdentificationMode = IdentificationMode.SEQUENTIAL,
        strategic_response_expected: bool = False,
        transmission_channels: Sequence[StrategicResponseChannel] = (),
        notes: Sequence[str] = (),
    ) -> TemporalInterventionSequence:
        """Build an ordered ``TemporalInterventionSequence`` from step inputs.

        Raises:
            ValueError: If a step references an unknown intervention id or unknown parameter
                override when ``compiled_interventions`` are provided.
        """
        compiled_catalog = _normalize_compiled_intervention_catalog(compiled_interventions)
        normalized_steps = [
            self._normalize_step(step, index) for index, step in enumerate(steps, start=1)
        ]
        if compiled_catalog:
            for step in normalized_steps:
                compiled = compiled_catalog.get(step.intervention_id)
                if compiled is None:
                    raise ValueError(
                        f"unknown intervention_id '{step.intervention_id}' for temporal sequence"
                    )
                known_params = {parameter.param_id for parameter in compiled.parameters}
                unknown_params = sorted(set(step.parameter_overrides) - known_params)
                if unknown_params:
                    raise ValueError(
                        "unknown parameter_overrides for "
                        f"'{step.intervention_id}': {', '.join(unknown_params)}"
                    )
        return TemporalInterventionSequence(
            sequence_id=sequence_id,
            dynamic_intervention_id=dynamic_intervention_id,
            identification_mode=identification_mode,
            strategic_response_expected=strategic_response_expected,
            transmission_channels=list(transmission_channels),
            steps=normalized_steps,
            notes=list(notes),
        )

    def to_dynamic_treatment(
        self,
        sequence: TemporalInterventionSequence | Mapping[str, Any],
        *,
        n_units: int = 10,
        time_ids: Sequence[Any] | None = None,
        covariate_names: Sequence[str] | None = None,
        outcome: Sequence[float] | np.ndarray | None = None,
    ) -> DynamicTreatmentData:
        """Render a temporal intervention sequence into a synthetic DTR design matrix.

        This helper is a bridge into the DTR estimators in Foundry and should be treated as a
        scaffolded default when no empirical ``DynamicTreatmentData`` payload is available.
        """
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
                "transmission_channels": [
                    channel.value for channel in resolved.transmission_channels
                ],
                "intervention_ids": [step.intervention_id for step in resolved.steps],
                "parameter_override_summary": {
                    step.step_id: sorted(step.parameter_overrides)
                    for step in resolved.steps
                    if step.parameter_overrides
                },
            },
        )

    def _normalize_step(
        self,
        step: TemporalInterventionStepInput | TemporalInterventionStep | Mapping[str, Any],
        index: int,
    ) -> TemporalInterventionStep:
        if isinstance(step, TemporalInterventionStep):
            return step
        if isinstance(step, TemporalInterventionStepInput):
            payload = step.model_dump(mode="python", exclude_none=True)
        else:
            payload = dict(step)
        payload.setdefault("step_id", f"step_{index}")
        return TemporalInterventionStep.model_validate(payload)


class TemporalInterventionSequenceCompileResult(KernelModel):
    """Compiled DTR execution entry plus the synthetic data used to produce it."""

    entry: TemporalDTRExecutionEntry
    dynamic_treatment_data: DynamicTreatmentData
    dtr_result: DTRResult | None = None


class TemporalInterventionSequenceCompiler:
    """Resolve temporal intervention tasks into DTR outputs and persisted artifacts."""

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
        """Execute one temporal DTR task and persist optional regime/effect artifacts.

        Returns:
            Execution entry, the dynamic treatment data used for estimation, and the optional
            ``DTRResult`` returned by the selected estimator.

        Raises:
            ValueError: If ``task.dtr_method`` is unsupported or sequence synthesis fails.
        """
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
                    "Continuous-time query requested without ArtifactStore; effect trajectory was not persisted."
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
        """Compile multiple temporal DTR tasks using the same artifact-store context."""
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
        dynamic_data = self.sequencer.to_dynamic_treatment(
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


class StrategicResponseSpecRegistry:
    """Lookup helper for strategic-response expectations by intervention kind."""

    def __init__(
        self,
        entries: Iterable[StrategicResponseRegistryEntry | Mapping[str, Any]] = (),
    ) -> None:
        self._entries: dict[str, StrategicResponseRegistryEntry] = {}
        for entry in entries:
            self.register(entry)

    @classmethod
    def from_bundle(
        cls,
        bundle: StrategicResponseSpecsBundle | Mapping[str, Any],
    ) -> StrategicResponseSpecRegistry:
        resolved_bundle = (
            bundle
            if isinstance(bundle, StrategicResponseSpecsBundle)
            else StrategicResponseSpecsBundle.model_validate(bundle)
        )
        return cls(
            StrategicResponseRegistryEntry(spec=spec) for spec in resolved_bundle.expectations
        )

    def register(
        self,
        entry: StrategicResponseRegistryEntry | Mapping[str, Any],
    ) -> StrategicResponseRegistryEntry:
        """Register one strategic-response spec and reject duplicate intervention kinds."""
        resolved = (
            entry
            if isinstance(entry, StrategicResponseRegistryEntry)
            else StrategicResponseRegistryEntry.model_validate(entry)
        )
        if resolved.spec.intervention_kind in self._entries:
            raise ValueError(
                f"duplicate strategic response spec for '{resolved.spec.intervention_kind}'"
            )
        self._entries[resolved.spec.intervention_kind] = resolved
        return resolved

    def get(self, intervention_kind: str) -> StrategicResponseRegistryEntry | None:
        return self._entries.get(intervention_kind)

    def require(self, intervention_kind: str) -> StrategicResponseRegistryEntry:
        resolved = self.get(intervention_kind)
        if resolved is None:
            raise KeyError(f"strategic response spec not found for '{intervention_kind}'")
        return resolved

    def channels_for(self, intervention_kind: str) -> tuple[StrategicResponseChannel, ...]:
        resolved = self.get(intervention_kind)
        if resolved is None:
            return ()
        return tuple(resolved.spec.channels)

    def hook_fqn_for(self, intervention_kind: str) -> str | None:
        resolved = self.get(intervention_kind)
        return None if resolved is None else resolved.spec.hook_fqn

    def hook_config_for(self, intervention_kind: str) -> dict[str, Any]:
        resolved = self.get(intervention_kind)
        return {} if resolved is None else dict(resolved.hook_config)

    def expected_response_type_for(self, intervention_kind: str) -> str | None:
        resolved = self.get(intervention_kind)
        return None if resolved is None else resolved.expected_response_type

    def strategic_required_for(self, intervention_kind: str) -> bool:
        resolved = self.get(intervention_kind)
        return bool(resolved is not None and resolved.spec.strategic_response_expected)

    def bundle(self) -> StrategicResponseSpecsBundle:
        return StrategicResponseSpecsBundle(
            expectations=[self._entries[key].spec for key in sorted(self._entries)]
        )


class HierarchicalPolicySearchAdapter:
    """Bridge from Lex policy bundles into runtime hierarchical search."""

    coordinator_fqn = "polisyos.scientist.policy_design.search.HierarchicalSearchCoordinator"

    def build_request(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalPolicySearchPlan:
        """Create a Scientist search-plan payload from a Trinity or Lex policy bundle."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        resolved_config = self.instantiate_search_config(search_config)
        resolved_policy_family = str(
            policy_family
            or resolved_candidate.metadata.get("policy_family")
            or resolved_candidate.candidate_id
        )
        request_metadata = {
            **dict(resolved_candidate.metadata),
            **dict(metadata or {}),
        }
        request_metadata.setdefault("policy_family", resolved_policy_family)
        return HierarchicalPolicySearchPlan(
            coordinator_fqn=self.coordinator_fqn,
            candidate_id=resolved_candidate.candidate_id,
            candidate_hash=resolved_candidate.candidate_hash(),
            policy_family=resolved_policy_family,
            search_config=resolved_config.model_dump(mode="json"),
            metadata=request_metadata,
        )

    def build_candidate(
        self,
        bundle_input: LexPolicyBundleInput | TrinityBundle | Mapping[str, Any],
        *,
        candidate_id: str | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> PolicyCandidateSchema:
        """Convert a Lex policy bundle into a ``PolicyCandidateSchema`` with runtime metadata."""
        resolved_input = _coerce_lex_policy_bundle_input(bundle_input)
        domain = _bundle_domain(resolved_input.trinity_bundle)
        resolved_policy_family = str(
            policy_family
            or resolved_input.metadata.get("policy_family")
            or candidate_id
            or resolved_input.trinity_bundle.policy_spec.policy_id
        )
        compiled_interventions = list(resolved_input.compiled_interventions)
        temporal_sequences = list(resolved_input.temporal_sequences)
        strategic_response_bundle = resolved_input.strategic_response_bundle

        dynamic_intervention_ids = [
            sequence.dynamic_intervention_id for sequence in temporal_sequences
        ]
        strategic_intervention_kinds = {
            compiled.intervention.kind
            for compiled in compiled_interventions
            if compiled.intervention.strategic_response_expected
        }
        if strategic_response_bundle is not None:
            strategic_intervention_kinds.update(
                spec.intervention_kind
                for spec in strategic_response_bundle.expectations
                if spec.strategic_response_expected
            )

        candidate_metadata = {
            **dict(resolved_input.metadata),
            **dict(metadata or {}),
            "policy_family": resolved_policy_family,
            "jurisdiction": "UA",
            "country": "ua",
            "domain": domain,
            "dynamic_intervention_ids": dynamic_intervention_ids,
            "strategic_intervention_kinds": sorted(strategic_intervention_kinds),
            "compiled_intervention_ids": [
                compiled.intervention.intervention_id for compiled in compiled_interventions
            ],
            "sequence_ids": [sequence.sequence_id for sequence in temporal_sequences],
        }
        return PolicyCandidateSchema.from_trinity_bundle(
            resolved_input.trinity_bundle,
            candidate_id=candidate_id,
            metadata=candidate_metadata,
        )

    def build_request_from_trinity(
        self,
        bundle: TrinityBundle | Mapping[str, Any],
        *,
        candidate_id: str | None = None,
        policy_family: str | None = None,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalPolicySearchPlan:
        """Build a hierarchical policy-search plan directly from a ``TrinityBundle`` payload."""
        candidate = self.build_candidate(
            bundle,
            candidate_id=candidate_id,
            policy_family=policy_family,
            metadata=metadata,
        )
        return self.build_request(
            candidate,
            search_config=search_config,
            policy_family=policy_family,
            metadata=metadata,
        )

    def instantiate_search_config(
        self,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None,
    ) -> HierarchicalSearchConfig:
        if search_config is None:
            return HierarchicalSearchConfig()
        if isinstance(search_config, HierarchicalSearchConfig):
            return search_config
        return HierarchicalSearchConfig.model_validate(search_config)

    def instantiate_coordinator(
        self,
        plan: HierarchicalPolicySearchPlan | Mapping[str, Any],
    ) -> HierarchicalSearchCoordinator:
        resolved_plan = (
            plan
            if isinstance(plan, HierarchicalPolicySearchPlan)
            else HierarchicalPolicySearchPlan.model_validate(plan)
        )
        return HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(resolved_plan.search_config)
        )

    def validate_policy_design_api(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> HierarchicalSearchCoordinator:
        """Sanity-check that the generated candidate is accepted by Scientist policy-design APIs."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        coordinator = HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(search_config)
        )
        try:
            coordinator.build_parameter_search_spec(resolved_candidate)
        except ValueError as exc:
            if "No tunable policy parameters" not in str(exc):
                raise
        coordinator.build_optimizer_objective_spec(resolved_candidate)
        return coordinator

    def build_runtime_context(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        loop_id: str,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return the runtime context block expected by orchestration and policy-search loops."""
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        request = self.build_request(
            resolved_candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        return {
            "loop_id": loop_id,
            "candidate_id": resolved_candidate.candidate_id,
            "candidate_hash": resolved_candidate.candidate_hash(),
            "policy_family": request.policy_family,
            "policy_search_plan": request.model_dump(mode="json"),
            "policy_search_context": {
                "structure_id": resolved_candidate.candidate_id,
                "policy_family": request.policy_family,
                "candidate_hash": resolved_candidate.candidate_hash(),
                "task_family": request.policy_family,
                "domain": str(request.metadata.get("domain") or resolved_candidate.candidate_id),
            },
            "ukraine_metadata": {
                "jurisdiction": request.metadata.get("jurisdiction"),
                "country": request.metadata.get("country"),
                "domain": request.metadata.get("domain"),
            },
            "dynamic_intervention_ids": list(
                request.metadata.get("dynamic_intervention_ids") or []
            ),
            "strategic_intervention_kinds": list(
                request.metadata.get("strategic_intervention_kinds") or []
            ),
            "compiled_intervention_ids": list(
                request.metadata.get("compiled_intervention_ids") or []
            ),
            "sequence_ids": list(request.metadata.get("sequence_ids") or []),
        }

    def run_search(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        loop_id: str,
        stage_b_evaluator: Any | None = None,
        stage_a_evaluator: Any | None = None,
        structure_validator: Any | None = None,
        narrative_input_builder: Any | None = None,
        search_config: HierarchicalSearchConfig | Mapping[str, Any] | None = None,
        policy_family: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        initial_context: Mapping[str, Any] | None = None,
    ) -> Any:
        resolved_candidate = self._resolve_candidate_payload(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )
        coordinator = HierarchicalSearchCoordinator(
            config=self.instantiate_search_config(search_config)
        )
        runtime_context = self.build_runtime_context(
            resolved_candidate,
            loop_id=loop_id,
            policy_family=policy_family,
            metadata=metadata,
        )
        merged_context = {**runtime_context, **dict(initial_context or {})}
        try:
            coordinator.build_parameter_search_spec(resolved_candidate)
        except ValueError as exc:
            if "No tunable policy parameters" not in str(exc):
                raise
            return self._run_parameterless_search(
                coordinator,
                resolved_candidate,
                loop_id=loop_id,
                stage_b_evaluator=stage_b_evaluator,
                structure_validator=structure_validator,
                narrative_input_builder=narrative_input_builder,
                initial_context=merged_context,
            )
        return coordinator.run(
            resolved_candidate,
            loop_id=loop_id,
            stage_b_evaluator=stage_b_evaluator,
            stage_a_evaluator=stage_a_evaluator,
            structure_validator=structure_validator,
            narrative_input_builder=narrative_input_builder,
            initial_context=merged_context,
        )

    def _resolve_candidate_payload(
        self,
        candidate: (
            PolicyCandidateSchema | LexPolicyBundleInput | TrinityBundle | Mapping[str, Any]
        ),
        *,
        policy_family: str | None,
        metadata: Mapping[str, Any] | None,
    ) -> PolicyCandidateSchema:
        if isinstance(candidate, PolicyCandidateSchema):
            if policy_family is None and not metadata:
                return candidate
            updated_metadata = {
                **dict(candidate.metadata),
                **dict(metadata or {}),
            }
            if policy_family is not None:
                updated_metadata["policy_family"] = policy_family
            return candidate.model_copy(update={"metadata": updated_metadata})
        return self.build_candidate(
            candidate,
            policy_family=policy_family,
            metadata=metadata,
        )

    def _run_parameterless_search(
        self,
        coordinator: HierarchicalSearchCoordinator,
        candidate: PolicyCandidateSchema,
        *,
        loop_id: str,
        stage_b_evaluator: Any | None,
        structure_validator: Any | None,
        narrative_input_builder: Any | None,
        initial_context: Mapping[str, Any] | None,
    ) -> Any:
        from polisyos.scientist.policy_design.search import HierarchicalSearchResult

        state = coordinator.run(
            candidate,
            loop_id=loop_id,
            stage_b_evaluator=None,
            structure_validator=structure_validator,
            narrative_input_builder=None,
            initial_context=dict(initial_context or {}),
        ).state
        accepted_structures = [item for item in state.structure_candidates if item.accepted]
        if stage_b_evaluator is not None:
            state.current_level = PolicySearchLevel.PARAMETER
            base_context = dict(initial_context or {})
            for structure in accepted_structures:
                candidate_payload = structure.candidate.as_search_payload()
                context = {
                    **base_context,
                    "loop_id": loop_id,
                    "candidate_hash": structure.candidate_hash,
                    "policy_search_context": {
                        "structure_id": structure.structure_id,
                        "policy_family": structure.policy_family,
                        "candidate_hash": structure.candidate_hash,
                        "task_family": structure.policy_family,
                        "domain": str(
                            structure.candidate.metadata.get("domain")
                            or structure.candidate.candidate_id
                        ),
                    },
                }
                stage_b_result = stage_b_evaluator(candidate_payload, context)
                state.parameter_search_results[structure.structure_id] = SearchResult(
                    search_id=f"{loop_id}:{structure.structure_id}",
                    status=SearchStatus.CONVERGED,
                    best_candidate=candidate_payload,
                    best_objective=float(stage_b_result.get("objective_value", 0.0)),
                    iterations_completed=1,
                    history=[
                        SearchIteration(
                            iteration=0,
                            candidate=candidate_payload,
                            objective_value=float(stage_b_result.get("objective_value", 0.0)),
                            objective_details=[],
                            is_promising=bool(stage_b_result.get("feasible", True)),
                            stage_a_passed=True,
                            stage_b_result=stage_b_result,
                            duration_seconds=0.0,
                            policy_evaluation=stage_b_result.get("policy_evaluation"),
                        )
                    ],
                    stopping_reason="parameter_search_not_required",
                    total_duration_seconds=0.0,
                    stage_a_evaluations=0,
                    stage_b_evaluations=1,
                    telemetry={"parameterless_candidate": True},
                )
        if narrative_input_builder is not None:
            state.current_level = PolicySearchLevel.NARRATIVE
            bundles: list[tuple[str, Any]] = []
            for structure in accepted_structures:
                result = state.parameter_search_results.get(structure.structure_id)
                bundle = narrative_input_builder(structure, result)
                if bundle is None:
                    continue
                bundles.append((structure.candidate_hash, bundle))
            state.narrative_variants = coordinator.run_narrative_search(bundles)
        state_payload = state.model_dump(mode="python") if hasattr(state, "model_dump") else state
        return HierarchicalSearchResult(state=state_payload, shared_frontier=[])


def _resolve_param_key(param_path: str) -> str:
    normalized = param_path.removeprefix("params.")
    return normalized.split(".", 1)[0]


def _resolve_param_path(
    params: Mapping[str, Any],
    param_path: str,
) -> tuple[Any, bool]:
    parts = [part for part in param_path.removeprefix("params.").split(".") if part]
    if not parts:
        return None, False
    current: Any = dict(params)
    for part in parts:
        if not isinstance(current, Mapping) or part not in current:
            return None, False
        current = current[part]
    return current, True


def _param_value_to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, MoneyValue):
        return value.amount
    if isinstance(value, RateValue):
        return value.as_ratio()
    if isinstance(value, CountValue):
        return Decimal(value.value)
    if isinstance(value, DurationValue):
        return Decimal(value.value)
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except Exception:
            return None
    return None


def _normalize_compiled_intervention_catalog(
    compiled_interventions: (
        Sequence[CompiledLexIntervention | Mapping[str, Any]]
        | Mapping[str, CompiledLexIntervention | Mapping[str, Any]]
        | None
    ),
) -> dict[str, CompiledLexIntervention]:
    if compiled_interventions is None:
        return {}
    if isinstance(compiled_interventions, Mapping):
        values = compiled_interventions.values()
    else:
        values = compiled_interventions
    catalog: dict[str, CompiledLexIntervention] = {}
    for item in values:
        compiled = (
            item
            if isinstance(item, CompiledLexIntervention)
            else CompiledLexIntervention.model_validate(item)
        )
        catalog[compiled.intervention.intervention_id] = compiled
    return catalog


def _coerce_lex_policy_bundle_input(
    bundle_input: LexPolicyBundleInput | TrinityBundle | Mapping[str, Any],
) -> LexPolicyBundleInput:
    if isinstance(bundle_input, LexPolicyBundleInput):
        return bundle_input
    if isinstance(bundle_input, TrinityBundle):
        return LexPolicyBundleInput(trinity_bundle=bundle_input)
    if isinstance(bundle_input, Mapping) and "trinity_bundle" in bundle_input:
        return LexPolicyBundleInput.model_validate(bundle_input)
    return LexPolicyBundleInput(trinity_bundle=TrinityBundle.model_validate(bundle_input))


def _bundle_domain(bundle: TrinityBundle) -> str:
    domain = bundle.problem_frame.domain
    return str(domain.value if hasattr(domain, "value") else domain)


def _optional_id(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


__all__ = [
    "CompiledLexIntervention",
    "HierarchicalPolicySearchAdapter",
    "HierarchicalPolicySearchPlan",
    "InterventionKnobSpec",
    "LexInterventionCompiler",
    "LexProvisionDirective",
    "StrategicResponseRegistryEntry",
    "StrategicResponseSpecRegistry",
    "TemporalInterventionSequenceCompileResult",
    "TemporalInterventionSequenceCompiler",
    "TemporalInterventionSequencer",
    "TemporalInterventionStepInput",
]
