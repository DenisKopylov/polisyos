"""Public simulate propagate uncertainty module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from numbers import Real
from typing import Any, Literal, Protocol, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    artifact_manifest_profile_sha256,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactManifest, ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.registry import RegistryBundlePayload
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.contracts import UncertaintyEnvelopeRef
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CalibrationReportRef,
    ExecPlan,
    Metrics,
    ProgramGraph,
    SimulationResult,
    SimulationResultRef,
    StateSnapshot,
)
from polisyos.foundry.calibration import (
    CalibrationExecutionInputBasis,
    CalibrationSourceStatus,
    ExecuteResponseBasisCandidate,
    calibration_report_series_sha256,
    calibration_report_time_axis_sha256,
    canonical_input_sha256,
    classify_calibration_source_error,
    load_calibration_execution_input_basis,
    load_execute_response_basis_candidate,
    read_calibration_config_source,
    read_calibration_execution_input_basis_source,
    read_calibration_model_source,
    read_calibration_report_source,
    read_calibration_source,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.protocol import PropagationResult
from polisyos.ir import ArtifactRefModel, get_json_artifact
from polisyos.ir.analytics.calibration import CalibrationConfig
from polisyos.ir.analytics.uncertainty import (
    UncertaintyEnvelope,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.kernel import MechanismTypeRegistry, UnitsRegistry
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
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

logger = get_logger(__name__)

_PROPAGATION_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_PROPAGATION_LOAD_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_SENSITIVITY_MAPPING_PARAM = "propagation_sensitivity"
_RESPONSE_BASIS_PARAM = "propagation_response_basis"


class _InvalidSensitivityMapping(ValueError):
    """A supplied sensitivity map cannot be interpreted against this run."""


class _InvalidPropagationConfig(ValueError):
    """A supplied propagation configuration cannot be admitted for this run."""


class _InvalidResponseBasis(ValueError):
    """A response refusal retaining the shared source status when applicable."""

    def __init__(
        self, message: str, *, source_status: CalibrationSourceStatus | None = None
    ) -> None:
        self.source_status = source_status
        super().__init__(message)


class _ResponseProjectionSpec(BaseModel):
    """Select exact persisted state-slot subjects from a response matrix."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    state_slot_ids: tuple[StrictStr, ...] = Field(min_length=1)

    @field_validator("state_slot_ids")
    @classmethod
    def validate_state_slot_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not slot_id.strip() for slot_id in value):
            raise ValueError("state_slot_ids must contain non-empty slot identifiers")
        if len(set(value)) != len(value):
            raise ValueError("state_slot_ids must be unique")
        return value


@dataclass(frozen=True, slots=True)
class _CalibrationResponseSource:
    """Bind calibration report values and input identities to one selected CAS view."""

    report_ref: CalibrationReportRef
    basis_ref: ArtifactRef
    report: CalibrationReport
    basis: CalibrationExecutionInputBasis
    input_envelopes: Mapping[str, UncertaintyEnvelope]
    input_envelope_refs: Mapping[str, UncertaintyEnvelopeRef]
    input_envelope_sources: Mapping[str, Mapping[str, Any]]
    limitation_codes: tuple[str, ...]


class _PropagationFunction(Protocol):
    """Callable response carrying its resolved sensitivity map."""

    _sensitivity_map: dict[str, dict[str, float]]
    _sensitivity_mapping_source: Literal["absent", "caller_parameters", "execute_response_matrix"]

    def __call__(self, **current_params: Any) -> dict[str, Any]: ...


def _has_missing_output(result: PropagationResult) -> bool:
    """Read the method-neutral missing-output signal from a propagation result."""
    return result.diagnostics.get("missing_output") is True


_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_propagate_uncertainty@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Propagate Uncertainty",
    description="Propagate input uncertainty envelopes to simulation output metrics.",
    tags=["builtin", "simulate", "uncertainty"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params",
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_CALIBRATION_REPORT_REF}",
        "params.propagation_config",
        "params.propagation_sensitivity",
        "params.propagation_response_basis",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_PROPAGATION_REPORT_REF}",
    ],
    produces=[ARTIFACT_SIMULATION_RESULT_REF, ARTIFACT_PROPAGATION_REPORT_REF],
)


@dataclass(frozen=True)
class PropagateUncertaintyNode:
    """Propagate uncertainty node implementation."""

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        raw_mapping_supplied = _SENSITIVITY_MAPPING_PARAM in state.params
        try:
            _validate_sensitivity_mapping_shape(state.params)
        except _InvalidSensitivityMapping as exc:
            return _sensitivity_mapping_failure(state, exc)

        try:
            response_projection = _load_response_projection(state.params)
        except _InvalidResponseBasis as exc:
            return _response_basis_failure(state, exc)
        if response_projection is not None and raw_mapping_supplied:
            return _response_basis_failure(
                state,
                _InvalidResponseBasis(
                    "provide propagation_response_basis or propagation_sensitivity, not both"
                ),
            )

        try:
            config = _load_config(state)
        except _InvalidPropagationConfig as exc:
            return _propagation_config_failure(state, exc)

        sim_result_ref = state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
        if sim_result_ref is None:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No simulation_result_ref; skip uncertainty",
                    )
                ],
            )

        response_intake = None
        if response_projection is not None:
            try:
                response_intake = _read_calibration_response_intake(
                    ctx,
                    state.inputs.get(INPUT_CALIBRATION_REPORT_REF),
                )
            except _InvalidResponseBasis as exc:
                return _response_basis_failure(state, exc)
        sim_result = _load_model(ctx, sim_result_ref, SimulationResult)
        response_candidate: ExecuteResponseBasisCandidate | None = None
        if response_projection is not None:
            try:
                if not isinstance(ctx.store, FileSystemCAS):
                    raise _InvalidResponseBasis(
                        "execute response validation requires the supported FileSystemCAS reader"
                    )
                response_candidate = load_execute_response_basis_candidate(
                    ctx.store,
                    SimulationResultRef.model_validate(sim_result_ref.model_dump(mode="python")),
                )
            except _InvalidResponseBasis as exc:
                return _response_basis_failure(state, exc)
            except _PROPAGATION_LOAD_ERRORS as exc:
                return _response_basis_failure(
                    state,
                    _InvalidResponseBasis(
                        f"selected execute response basis could not be revalidated: {exc}",
                        source_status=classify_calibration_source_error(
                            exc, role="calibration_response_source"
                        ).status,
                    ),
                )

        response_source: _CalibrationResponseSource | None = None
        if response_candidate is not None and response_projection is not None:
            calibration_ref = state.inputs.get(INPUT_CALIBRATION_REPORT_REF)
            try:
                response_source = _load_calibration_response_source(
                    ctx,
                    calibration_ref,
                    response_candidate,
                    intake=response_intake,
                )
            except _InvalidResponseBasis as exc:
                return _response_basis_failure(state, exc)
            except _PROPAGATION_LOAD_ERRORS as exc:
                return _response_basis_failure(
                    state,
                    _InvalidResponseBasis(
                        f"selected calibration response source could not be rebound: {exc}",
                        source_status=classify_calibration_source_error(
                            exc, role="calibration_response_source"
                        ).status,
                    ),
                )
            input_envelopes = dict(response_source.input_envelopes)
            output_metric_ids = list(response_projection.state_slot_ids)
            if not input_envelopes:
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[
                        NodeEvent(
                            level="info",
                            message=(
                                "Selected calibration report has no response-bound parameter "
                                "uncertainty envelopes"
                            ),
                        )
                    ],
                )
            metric_values: dict[str, float] = {}
        else:
            metrics = _load_model(ctx, sim_result.metrics_ref, Metrics)
            metric_values = _extract_numeric_metrics(metrics)
            if not metric_values:
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[NodeEvent(level="info", message="No numeric metrics for propagation")],
                )

            input_envelopes = _collect_input_envelopes(ctx, state)
            if not input_envelopes:
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[NodeEvent(level="info", message="No input uncertainty envelopes")],
                )
            output_metric_ids = sorted(metric_values.keys())

        dispatcher = PropagationDispatcher(config)

        nominal_params = {name: env.point_estimate for name, env in input_envelopes.items()}
        response_status_by_metric: dict[str, str] = {}
        missing_response_parameters: list[str] = []
        try:
            if (
                response_candidate is not None
                and response_projection is not None
                and response_source is not None
            ):
                (
                    simulation_fn,
                    mapped_params,
                    response_status_by_metric,
                    missing_response_parameters,
                ) = _build_execute_response_state_projection_fn(
                    response_candidate,
                    selected_state_slot_ids=output_metric_ids,
                    input_envelopes=input_envelopes,
                    response_source=response_source,
                )
            else:
                simulation_fn, mapped_params = _build_propagation_fn(
                    state.params,
                    base_metric_values=metric_values,
                    nominal_params=nominal_params,
                )
        except _InvalidSensitivityMapping as exc:
            return _sensitivity_mapping_failure(state, exc)
        except _InvalidResponseBasis as exc:
            return _response_basis_failure(state, exc)
        results = dispatcher.propagate(
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            output_metric_ids=output_metric_ids,
            is_jax_differentiable=True,
        )

        if not results:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="Propagation yielded no results")],
            )

        sensitivity_map = getattr(simulation_fn, "_sensitivity_map", {})
        unmapped_metric_ids = [
            metric_id for metric_id in output_metric_ids if not sensitivity_map.get(metric_id)
        ]
        if response_candidate is not None:
            results = [
                _mark_sensitivity_mapping(
                    item,
                    mapping_status=response_status_by_metric.get(item.metric_id, "unresolved"),
                    mapping_source="execute_response_matrix",
                )
                for item in results
            ]
        elif raw_mapping_supplied:
            results = [
                _mark_sensitivity_mapping(
                    item,
                    mapping_status=(
                        "consumer_asserted" if sensitivity_map.get(item.metric_id) else "unresolved"
                    ),
                    mapping_source="caller_parameters",
                )
                for item in results
            ]
        elif unmapped_metric_ids:
            results = [
                _mark_sensitivity_mapping(
                    item,
                    mapping_status="unresolved",
                    mapping_source="not_established",
                )
                if item.metric_id in unmapped_metric_ids
                else item
                for item in results
            ]
        missing_output_metric_ids = [
            item.metric_id for item in results if _has_missing_output(item)
        ]
        incomplete_output_metric_ids = [
            item.metric_id
            for item in results
            if (
                _has_missing_output(item)
                or item.diagnostics.get("output_coverage_complete") is False
                or (
                    response_candidate is not None
                    and response_status_by_metric.get(item.metric_id) != "recomputed"
                )
            )
        ]

        config_ref = _persist_config(
            ctx,
            config,
            return_selected_profile=response_candidate is not None,
        )
        response_lineage_inputs: list[InputRef] = []
        if response_candidate is not None and response_source is not None:
            response_lineage_inputs = _response_lineage_inputs(
                response_candidate,
                response_source,
                config_ref=config_ref,
            )

        envelope_refs: dict[str, UncertaintyEnvelopeRef] = {}
        artifacts: list[ArtifactRef] = []
        for item in results:
            envelope = item.envelope
            if response_candidate is not None and response_source is not None:
                moment_name = next(
                    moment
                    for moment, slot_id in response_candidate.response_slots.items()
                    if slot_id == item.metric_id
                )
                envelope = _mark_state_slot_projection(
                    item,
                    candidate=response_candidate,
                    response_source=response_source,
                    moment_name=moment_name,
                ).envelope
                envelope_ref = persist_uncertainty_envelope(
                    _ensure_ir_artifact_store(ctx.store),
                    envelope,
                    inputs=response_lineage_inputs,
                    return_selected_profile=True,
                )
            else:
                envelope_ref = persist_uncertainty_envelope(
                    _ensure_ir_artifact_store(ctx.store), envelope
                )
            envelope_refs[item.metric_id] = envelope_ref
            artifacts.append(ArtifactRef.model_validate(envelope_ref.model_dump(mode="python")))

        state_slot_to_moment = (
            None
            if response_candidate is None
            else {
                slot_id: moment_name
                for moment_name, slot_id in response_candidate.response_slots.items()
                if slot_id in envelope_refs
            }
        )
        report_ref = _persist_report(
            ctx,
            results=results,
            input_envelopes=input_envelopes,
            output_metrics=output_metric_ids,
            mapped_params=mapped_params,
            unmapped_metric_ids=unmapped_metric_ids,
            missing_output_metric_ids=missing_output_metric_ids,
            incomplete_output_metric_ids=incomplete_output_metric_ids,
            mapping_source=(
                "execute_response_matrix"
                if response_candidate is not None
                else "caller_parameters"
                if raw_mapping_supplied
                else "not_established"
            ),
            response_candidate=response_candidate,
            response_source=response_source,
            response_projection=state_slot_to_moment,
            response_lineage_inputs=response_lineage_inputs,
            propagation_config_ref=config_ref,
            output_envelope_refs=envelope_refs if response_candidate is not None else None,
            missing_response_parameters=missing_response_parameters,
        )

        updated_sim = sim_result.model_copy(
            update={
                "uncertainty_envelopes": envelope_refs,
                "propagation_config_ref": config_ref,
                "propagation_report_ref": report_ref,
            }
        )
        update_inputs = [
            _input_ref(sim_result_ref, role="base_simulation_result"),
            _input_ref(report_ref, role="propagation_report"),
            _input_ref(config_ref, role="propagation_config"),
        ]
        if updated_sim.execution_input_basis_ref is not None:
            update_inputs.append(
                _input_ref(
                    updated_sim.execution_input_basis_ref,
                    role="execution_input_basis",
                )
            )
        if updated_sim.feedback_result_ref is not None:
            update_inputs.append(
                _input_ref(
                    updated_sim.feedback_result_ref,
                    role="artifact.feedback_result_ref",
                )
            )
        for subject_id, envelope_ref in envelope_refs.items():
            role = (
                f"state_slot_envelope.{subject_id}"
                if response_candidate is not None
                else f"metric_envelope.{subject_id}"
            )
            update_inputs.append(_input_ref(envelope_ref, role=role))

        return_selected_profile = (
            sim_result_ref.manifest_profile_sha256 is not None
            or updated_sim.schema_version == SimulationResult.ARTIFACT_SCHEMA_VERSION
        )
        updated_ref_payload = ctx.store.put_json(
            updated_sim.to_artifact_payload(),
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(
                    name=SimulationResult.ARTIFACT_SCHEMA_NAME,
                    version=updated_sim.schema_version,
                ),
                inputs=update_inputs,
            ),
            return_selected_profile=return_selected_profile,
        )
        updated_ref = SimulationResultRef.model_validate(
            updated_ref_payload.model_dump(mode="python")
        )

        new_state = branch_state(state, write_paths=("artifacts_index",)).state
        new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = updated_ref
        new_state.artifacts_index[ARTIFACT_PROPAGATION_REPORT_REF] = report_ref

        artifacts.insert(0, updated_ref)
        artifacts.append(report_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=artifacts,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        f"Propagated uncertainty for {len(results)} "
                        f"{'state slots' if response_candidate is not None else 'metrics'} "
                        f"(inputs={len(input_envelopes)})"
                    ),
                )
            ],
        )


def _response_basis_failure(
    state: ExperimentState,
    error: _InvalidResponseBasis,
) -> NodeOutcome:
    """Return a typed refusal when the selected source response cannot be bound."""
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code="propagation_response_basis_invalid",
            message=str(error),
            details={
                "input": f"params.{_RESPONSE_BASIS_PARAM}",
                **(
                    {"source_status": error.source_status}
                    if error.source_status is not None
                    else {}
                ),
            },
        ),
    )


def _load_response_projection(
    params: Mapping[str, Any],
) -> _ResponseProjectionSpec | None:
    """Validate an explicit, candidate-only output-to-moment projection."""
    if _RESPONSE_BASIS_PARAM not in params:
        return None
    raw = params[_RESPONSE_BASIS_PARAM]
    if not isinstance(raw, Mapping):
        raise _InvalidResponseBasis("propagation_response_basis must be a mapping")
    try:
        import json

        # ExperimentState.params carries JSON values. Use the DTO's strict
        # JSON wire law; internal tuple shape is not a Python-input demand.
        return _ResponseProjectionSpec.model_validate_json(
            json.dumps(dict(raw), allow_nan=False), strict=True
        )
    except _PROPAGATION_VALIDATION_ERRORS as exc:
        raise _InvalidResponseBasis("propagation_response_basis is invalid") from exc


def _propagation_config_failure(
    state: ExperimentState,
    error: _InvalidPropagationConfig,
) -> NodeOutcome:
    """Return a typed refusal for malformed or invalid supplied config input."""
    input_path = (
        "params.propagation_config"
        if "propagation_config" in state.params
        else "params.propagation_*"
    )
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code="propagation_config_invalid",
            message=str(error),
            details={"input": input_path},
        ),
    )


def _sensitivity_mapping_failure(
    state: ExperimentState,
    error: _InvalidSensitivityMapping,
) -> NodeOutcome:
    """Return a typed refusal for malformed or unbindable caller sensitivity input."""
    return NodeOutcome(
        status="fail",
        state=state,
        error=NodeError(
            code="propagation_sensitivity_invalid",
            message=str(error),
            details={"input": f"params.{_SENSITIVITY_MAPPING_PARAM}"},
        ),
    )


def _validate_sensitivity_mapping_shape(
    params: Mapping[str, Any],
) -> dict[str, dict[str, float]] | None:
    """Validate supplied map structure before any skip/default can hide malformed input."""
    if _SENSITIVITY_MAPPING_PARAM not in params:
        return None

    raw = params[_SENSITIVITY_MAPPING_PARAM]
    if not isinstance(raw, Mapping) or not raw:
        raise _InvalidSensitivityMapping(
            "propagation_sensitivity must be a non-empty mapping of output ids to coefficients"
        )

    normalized: dict[str, dict[str, float]] = {}
    for metric_id, raw_metric in raw.items():
        if not isinstance(metric_id, str) or not metric_id.strip():
            raise _InvalidSensitivityMapping(
                "propagation_sensitivity output ids must be non-empty strings"
            )
        if not isinstance(raw_metric, Mapping) or not raw_metric:
            raise _InvalidSensitivityMapping(
                f"propagation_sensitivity[{metric_id!r}] must be a non-empty mapping"
            )
        normalized_metric: dict[str, float] = {}
        for param_name, coefficient in raw_metric.items():
            if not isinstance(param_name, str) or not param_name.strip():
                raise _InvalidSensitivityMapping(
                    f"propagation_sensitivity[{metric_id!r}] parameter ids must be strings"
                )
            if isinstance(coefficient, bool) or not isinstance(coefficient, (Real, Decimal)):
                raise _InvalidSensitivityMapping(
                    f"propagation_sensitivity[{metric_id!r}][{param_name!r}] "
                    "must be a finite numeric coefficient"
                )
            try:
                coefficient_value = float(coefficient)
            except (OverflowError, TypeError, ValueError) as exc:
                raise _InvalidSensitivityMapping(
                    f"propagation_sensitivity[{metric_id!r}][{param_name!r}] "
                    "must be a finite numeric coefficient"
                ) from exc
            if not math.isfinite(coefficient_value):
                raise _InvalidSensitivityMapping(
                    f"propagation_sensitivity[{metric_id!r}][{param_name!r}] "
                    "must be a finite numeric coefficient"
                )
            normalized_metric[param_name] = coefficient_value
        normalized[metric_id] = normalized_metric
    return normalized


def _load_model[ModelT: BaseModel](
    ctx: ExecutionContext,
    ref: ArtifactRef | ArtifactRefModel,
    model_cls: type[ModelT],
) -> ModelT:
    payload = get_json_artifact(_ensure_ir_artifact_store(ctx.store), ref)
    return model_cls.model_validate(payload)


def _input_ref(ref: ArtifactRef | ArtifactRefModel, *, role: str) -> InputRef:
    """Build one producer lineage edge without discarding its selected manifest view."""
    return InputRef(
        artifact_id=ref.artifact_id,
        role=role,
        manifest_profile_sha256=ref.manifest_profile_sha256,
    )


def _extract_numeric_metrics(metrics: Metrics) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in metrics.values.items():
        numeric: float | None = None
        if isinstance(value, int):
            numeric = float(value)
        elif isinstance(value, float):
            numeric = value
        elif isinstance(value, str):
            try:
                numeric = float(value)
            except ValueError:
                numeric = None
        if numeric is None or not math.isfinite(numeric):
            continue
        out[str(key)] = numeric
    return out


def _collect_input_envelopes(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> dict[str, UncertaintyEnvelope]:
    envelopes: dict[str, UncertaintyEnvelope] = {}

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        try:
            snapshot = _load_model(ctx, data_snapshot_ref, DataSnapshot)
            if snapshot.uncertainty_envelope_ref is not None:
                snapshot_env = load_uncertainty_envelope(
                    _ensure_ir_artifact_store(ctx.store),
                    snapshot.uncertainty_envelope_ref,
                )
                name = snapshot_env.metadata.get("param_name")
                key = str(name) if isinstance(name, str) else "data_snapshot"
                envelopes[key] = snapshot_env
        except _PROPAGATION_LOAD_ERRORS:
            logger.debug("Failed to load data snapshot uncertainty envelope", exc_info=True)

    calibration_ref = state.inputs.get(INPUT_CALIBRATION_REPORT_REF)
    if calibration_ref is not None:
        try:
            report = _load_model(ctx, calibration_ref, CalibrationReport)
            if report.uncertainty_envelopes:
                for name, env in report.uncertainty_envelopes.items():
                    envelopes[str(name)] = env
            elif report.uncertainty_envelope_refs:
                for name, ref in report.uncertainty_envelope_refs.items():
                    envelopes[str(name)] = load_uncertainty_envelope(
                        _ensure_ir_artifact_store(ctx.store), ref
                    )
        except _PROPAGATION_LOAD_ERRORS:
            logger.debug("Failed to load calibration uncertainty envelopes", exc_info=True)

    return envelopes


def _selected_core_ref(ref: Any, *, description: str) -> ArtifactRef:
    """Normalize a typed boundary ref without dropping its selected manifest view."""
    try:
        payload = ref.model_dump(mode="python") if isinstance(ref, BaseModel) else ref
        selected = ArtifactRef.model_validate(payload)
    except _PROPAGATION_VALIDATION_ERRORS as exc:
        raise _InvalidResponseBasis(
            f"{description} is not a typed artifact reference", source_status="mismatch"
        ) from exc
    if selected.manifest_profile_sha256 is None:
        raise _InvalidResponseBasis(
            f"{description} does not select a manifest profile", source_status="not_established"
        )
    return selected


def _reference_identity(ref: ArtifactRef) -> tuple[str, str, str, str | None]:
    return (
        str(ref.artifact_id),
        ref.kind,
        ref.media_type,
        ref.manifest_profile_sha256,
    )


def _selected_manifest(
    ctx: ExecutionContext,
    ref: ArtifactRef,
    *,
    expected_kind: str,
    model: type[BaseModel] | None,
    expected_schema: str | None = None,
    expected_version: str | None = None,
) -> Any:
    """Use the common exact source intake; source absence is not contradiction."""
    if not isinstance(ctx.store, FileSystemCAS):
        raise _InvalidResponseBasis(
            "selected response reads require FileSystemCAS", source_status="not_established"
        )
    if model is None:
        result = read_calibration_source(
            ctx.store,
            role=expected_kind,
            ref=ref,
            expected_kind=expected_kind,
            expected_schema=expected_schema,
            expected_versions=None if expected_version is None else (expected_version,),
            decoder=lambda _ref, manifest, _payload: manifest,
        )
    else:
        result = read_calibration_model_source(
            ctx.store,
            role=expected_kind,
            model=model,
            ref=ref,
            expected_kind=expected_kind,
            expected_schema=expected_schema,
            expected_versions=None if expected_version is None else (expected_version,),
            decoder=lambda _ref, manifest, _payload: manifest,
        )
    if result.status != "matched":
        raise _InvalidResponseBasis(result.code, source_status=result.status)
    return result.require_value()


def _optional_selected_basis_ref(
    ctx: ExecutionContext,
    basis_manifest: Any,
    *,
    role: str,
    ref: ArtifactRef | None,
    status: str,
    model: type[BaseModel],
) -> tuple[ArtifactRef | None, tuple[str, ...]]:
    """Bind a basis object's optional source ref to its exact persisted edge."""
    limitations: list[str] = []
    if status == "selected_source_mismatch":
        raise _InvalidResponseBasis(
            f"calibration input basis records a mismatch for {role}",
            source_status="mismatch",
        )
    result = read_calibration_model_source(
        ctx.store,
        role=role,
        model=model,
        ref=ref,
        inputs=basis_manifest.inputs,
        expected_kind=None if ref is None else ref.kind,
        decoder=lambda selected, _manifest, _payload: selected,
    )
    if ref is None and result.status == "matched":
        raise _InvalidResponseBasis(
            f"calibration input basis has an unbound {role} edge",
            source_status="mismatch",
        )
    if result.status == "mismatch":
        raise _InvalidResponseBasis(result.code, source_status=result.status)
    if result.status == "not_established":
        limitations.extend((f"calibration_basis_{role}_source_not_established", result.code))
        return None, tuple(limitations)
    if status != "selected_source_matched":
        limitations.append(f"calibration_basis_{role}_source_status:{status}")
    return result.require_value(), tuple(limitations)


def _selected_basis_input_sha256(
    ctx: ExecutionContext,
    ref: ArtifactRef,
    model_type: type[BaseModel],
) -> str:
    """Hash one freshly resolved source using the basis producer's typed representation."""
    result = read_calibration_model_source(
        ctx.store,
        role=ref.kind,
        ref=ref,
        expected_kind=ref.kind,
        model=model_type,
        decoder=lambda _ref, _manifest, value: value,
    )
    if result.status != "matched":
        raise _InvalidResponseBasis(result.code, source_status=result.status)
    return canonical_input_sha256(result.require_value())


@dataclass(frozen=True)
class _CalibrationResponseIntake:
    report_ref: ArtifactRef
    report_manifest: ArtifactManifest
    report: CalibrationReport
    basis_ref: ArtifactRef
    basis_manifest: ArtifactManifest
    basis: CalibrationExecutionInputBasis
    config_ref: ArtifactRef
    config: CalibrationConfig
    limitations: tuple[str, ...]


def _read_calibration_response_intake(
    ctx: ExecutionContext, raw_report_ref: Any
) -> _CalibrationResponseIntake:
    """Qualify the complete modelled scalar intake before candidate evaluation."""
    report_source = read_calibration_report_source(ctx.store, ref=raw_report_ref)
    if report_source.status != "matched":
        raise _InvalidResponseBasis(report_source.code, source_status=report_source.status)
    assert report_source.ref is not None
    report_ref = CalibrationReportRef.model_validate(report_source.ref.model_dump(mode="python"))
    report_manifest = report_source.manifest
    report = report_source.require_value()
    assert report_manifest is not None
    if report.ordered_batch_execution is not None:
        raise _InvalidResponseBasis("ordered_batch_response_basis_not_supported")
    if report.schema_version != "2.0":
        raise _InvalidResponseBasis("execute response requires a scalar v2 calibration report")

    basis_source = read_calibration_execution_input_basis_source(
        ctx.store, inputs=report_manifest.inputs
    )
    if basis_source.status != "matched":
        raise _InvalidResponseBasis(basis_source.code, source_status=basis_source.status)
    basis_ref = basis_source.ref
    basis_manifest = basis_source.manifest
    basis = basis_source.require_value()
    assert basis_ref is not None
    assert basis_manifest is not None
    if basis.schema_version == "1.2":
        # The response executor currently has one selected starting state, not
        # an ordered-row experiment. Never reinterpret a batch as scalar v1.0.
        raise _InvalidResponseBasis("ordered_batch_response_basis_not_supported")

    report_config_source = read_calibration_config_source(ctx.store, inputs=report_manifest.inputs)
    if report_config_source.status != "matched":
        raise _InvalidResponseBasis(
            report_config_source.code, source_status=report_config_source.status
        )
    report_config_ref = report_config_source.ref
    assert report_config_ref is not None
    basis_config_source = read_calibration_config_source(
        ctx.store,
        ref=basis.calibration_config_ref,
        inputs=basis_manifest.inputs,
    )
    if basis_config_source.status != "matched":
        raise _InvalidResponseBasis(
            basis_config_source.code, source_status=basis_config_source.status
        )
    config_ref = basis_config_source.ref
    assert config_ref is not None
    if _reference_identity(config_ref) != _reference_identity(report_config_ref):
        raise _InvalidResponseBasis(
            "calibration report and execution basis select different configs",
            source_status="mismatch",
        )
    limitations = list(basis.limitations)
    if basis.input_capture_status != "content_bound":
        limitations.append(
            f"calibration_execution_input_capture_status:{basis.input_capture_status}"
        )

    return _CalibrationResponseIntake(
        report_ref=report_ref,
        report_manifest=report_manifest,
        report=report,
        basis_ref=basis_ref,
        basis_manifest=basis_manifest,
        basis=basis,
        config_ref=config_ref,
        config=basis_config_source.require_value(),
        limitations=tuple(limitations),
    )


def _load_calibration_response_source(
    ctx: ExecutionContext,
    raw_report_ref: Any,
    candidate: ExecuteResponseBasisCandidate,
    *,
    intake: _CalibrationResponseIntake | None = None,
) -> _CalibrationResponseSource:
    """Rebind calibration envelopes and basis identities to the response candidate."""
    selected = intake or _read_calibration_response_intake(ctx, raw_report_ref)
    report_ref, report_manifest, report = (
        selected.report_ref,
        selected.report_manifest,
        selected.report,
    )
    basis_ref, basis_manifest, basis = selected.basis_ref, selected.basis_manifest, selected.basis
    config_ref = selected.config_ref
    limitations = list(selected.limitations)

    source_specs = (
        ("exec_plan_ref", "exec_plan", "exec_plan_source_status", "exec_plan", ExecPlan),
        ("program_graph_ref", "program", "program_graph_status", "program_graph", ProgramGraph),
        (
            "base_state_snapshot_ref",
            "bound_state",
            "base_state_source_status",
            "base_state_snapshot",
            StateSnapshot,
        ),
        (
            "registry_bundle_ref",
            "registry",
            "registry_bundle_status",
            "registry_bundle",
            RegistryBundlePayload,
        ),
        (
            "mechanism_registry_ref",
            "registry.mechanism_registry",
            "mechanism_registry_status",
            "mechanism_registry",
            MechanismTypeRegistry,
        ),
        (
            "unit_registry_ref",
            "registry.units_registry",
            "unit_registry_status",
            "unit_registry",
            UnitsRegistry,
        ),
    )
    resolved_basis_refs: dict[str, ArtifactRef | None] = {"calibration_config": config_ref}
    for field_name, candidate_role, status_name, basis_role, model_type in source_specs:
        basis_ref_value = getattr(basis, field_name)
        status = getattr(basis, status_name)
        selected, ref_limitations = _optional_selected_basis_ref(
            ctx,
            basis_manifest,
            role=basis_role,
            ref=basis_ref_value,
            status=status,
            model=model_type,
        )
        resolved_basis_refs[basis_role] = selected
        limitations.extend(ref_limitations)
        candidate_identity = candidate.source_inputs.get(candidate_role)
        if selected is not None and selected.manifest_profile_sha256 is not None:
            if candidate_identity is None:
                raise _InvalidResponseBasis(
                    f"execute response source omits calibration basis input {candidate_role}"
                )
            if _reference_identity(selected) != _reference_identity(candidate_identity.ref):
                raise _InvalidResponseBasis(
                    f"calibration basis and response source select different {basis_role} objects"
                )
        elif status == "selected_source_matched":
            raise _InvalidResponseBasis(
                f"calibration basis {basis_role} source is not selected",
                source_status="not_established",
            )
        else:
            limitations.append(f"calibration_basis_{basis_role}_candidate_join_not_established")

    for basis_role, digest_name, model_type in (
        ("exec_plan", "exec_plan_sha256", ExecPlan),
        ("program_graph", "program_graph_sha256", ProgramGraph),
        ("registry_bundle", "registry_bundle_sha256", RegistryBundlePayload),
        ("mechanism_registry", "mechanism_registry_sha256", MechanismTypeRegistry),
        ("unit_registry", "unit_registry_sha256", UnitsRegistry),
    ):
        selected = resolved_basis_refs.get(basis_role)
        expected_digest = getattr(basis, digest_name)
        status_name = {
            "exec_plan": basis.exec_plan_source_status,
            "program_graph": basis.program_graph_status,
            "registry_bundle": basis.registry_bundle_status,
            "mechanism_registry": basis.mechanism_registry_status,
            "unit_registry": basis.unit_registry_status,
        }[basis_role]
        if selected is None:
            continue
        if expected_digest is None:
            if status_name == "selected_source_matched":
                raise _InvalidResponseBasis(f"calibration basis {basis_role} digest is missing")
            limitations.append(f"calibration_basis_{basis_role}_digest_not_established")
        elif _selected_basis_input_sha256(ctx, selected, model_type) != expected_digest:
            raise _InvalidResponseBasis(f"calibration basis {basis_role} digest mismatch")

    program_graph_ref = resolved_basis_refs.get("program_graph")
    program_graph = (
        None
        if program_graph_ref is None
        else validate_core_model_json_artifact(ProgramGraph, ctx.store, program_graph_ref)
    )
    _reconcile_calibration_parameter_inputs(
        ctx,
        basis_manifest,
        basis,
        candidate,
        program_graph=program_graph,
        limitations=limitations,
    )

    for digest_name, candidate_role in (("base_state_checksum_sha256", "source_state.state_blob"),):
        identity = candidate.source_inputs.get(candidate_role)
        if identity is None:
            raise _InvalidResponseBasis(
                f"execute response source omits calibration basis content {candidate_role}"
            )
        _require_basis_source_digest(
            digest_name,
            getattr(basis, digest_name),
            identity.content_sha256.removeprefix("sha256:"),
        )

    if canonical_input_sha256(report.calibrated_params) != basis.calibrated_parameter_values_sha256:
        raise _InvalidResponseBasis(
            "calibration report parameter values differ from its input basis"
        )
    if set(candidate.parameter_center) - set(report.calibrated_params):
        raise _InvalidResponseBasis(
            "response parameter center is absent from the calibration report"
        )
    for name, center in candidate.parameter_center.items():
        if report.calibrated_params[name] != center:
            raise _InvalidResponseBasis(
                f"response parameter center differs from calibration report for {name!r}"
            )

    target_rows = {item.target_id: item for item in basis.target_inputs}
    if set(report.series_comparison) != set(basis.target_order) or set(target_rows) != set(
        basis.target_order
    ):
        raise _InvalidResponseBasis("calibration report targets differ from its input basis")
    for target_id in basis.target_order:
        comparison = report.series_comparison[target_id]
        identity = target_rows[target_id]
        if calibration_report_series_sha256(real=comparison.real, time=comparison.time) != (
            identity.report_series_sha256
        ):
            raise _InvalidResponseBasis(f"calibration report series changed for {target_id!r}")
        if canonical_input_sha256(comparison.real) != identity.observed_values_sha256:
            raise _InvalidResponseBasis(f"calibration observed values changed for {target_id!r}")
        if calibration_report_time_axis_sha256(comparison.time) != identity.report_time_axis_sha256:
            raise _InvalidResponseBasis(f"calibration report time axis changed for {target_id!r}")

    embedded = dict(report.uncertainty_envelopes or {})
    envelope_digests = dict(basis.report_envelope_sha256)
    if set(embedded) != set(envelope_digests):
        raise _InvalidResponseBasis("calibration envelope roster differs from its input basis")
    for name, envelope in embedded.items():
        if canonical_input_sha256(envelope) != envelope_digests[name]:
            raise _InvalidResponseBasis(f"calibration envelope changed for {name!r}")

    standalone_refs = dict(report.uncertainty_envelope_refs or {})
    if set(standalone_refs) - set(embedded):
        raise _InvalidResponseBasis("standalone calibration envelope has no report-bound digest")
    input_envelopes: dict[str, UncertaintyEnvelope] = {}
    input_envelope_refs: dict[str, UncertaintyEnvelopeRef] = {}
    input_envelope_sources: dict[str, Mapping[str, Any]] = {}
    for name, envelope in embedded.items():
        source: dict[str, Any] = {
            "source_form": "embedded_in_selected_report",
            "calibration_report_ref": report_ref.model_dump(mode="json"),
            "calibration_execution_input_basis_ref": basis_ref.model_dump(mode="json"),
            "content_sha256": envelope_digests[name],
        }
        if name in standalone_refs:
            standalone_ref = _selected_core_ref(
                standalone_refs[name],
                description=f"calibration uncertainty envelope {name!r}",
            )
            _selected_manifest(
                ctx,
                standalone_ref,
                expected_kind="ir.uncertainty_envelope",
                model=UncertaintyEnvelope,
                expected_schema="ir.uncertainty_envelope",
                expected_version="1.1",
            )
            persisted = load_uncertainty_envelope(
                _ensure_ir_artifact_store(ctx.store),
                UncertaintyEnvelopeRef.model_validate(standalone_ref.model_dump(mode="python")),
            )
            if canonical_input_sha256(persisted) != envelope_digests[name]:
                raise _InvalidResponseBasis(
                    f"standalone calibration envelope differs from report value for {name!r}"
                )
            input_envelope_refs[name] = UncertaintyEnvelopeRef.model_validate(
                standalone_ref.model_dump(mode="python")
            )
            source["standalone_envelope_ref"] = standalone_ref.model_dump(mode="json")
        if name not in candidate.parameter_names:
            limitations.append(f"calibration_parameter_outside_response_basis:{name}")
            input_envelope_sources[name] = source
            continue
        expected_center = envelope.numeric_policy.canonicalize(candidate.parameter_center[name])
        if envelope.point_estimate != expected_center:
            raise _InvalidResponseBasis(
                f"calibration envelope center differs from response source for {name!r}"
            )
        input_envelopes[name] = envelope
        input_envelope_sources[name] = source

    unit_identity_rows = tuple(basis.parameter_unit_identities)
    unit_identity_names = tuple(item.field_name for item in unit_identity_rows)
    if len(set(unit_identity_names)) != len(unit_identity_names):
        raise _InvalidResponseBasis("calibration basis repeats a parameter-unit identity")
    unit_identities = {item.field_name: item for item in unit_identity_rows}
    for name in candidate.parameter_names:
        identity = unit_identities.get(name)
        if identity is None:
            limitations.append(f"calibration_parameter_unit_identity_missing:{name}")
            continue
        if identity.parameter_spec_sha256 != candidate.parameter_spec_sha256[name]:
            raise _InvalidResponseBasis(f"calibration parameter specification differs for {name!r}")
        if identity.unit_id != candidate.parameter_unit_ids[name]:
            raise _InvalidResponseBasis(f"calibration parameter unit differs for {name!r}")
        if identity.unit_definition_sha256 is not None:
            if (
                canonical_input_sha256(candidate.parameter_units[name])
                != identity.unit_definition_sha256
            ):
                raise _InvalidResponseBasis(f"calibration unit definition differs for {name!r}")
        else:
            limitations.append(f"calibration_parameter_unit_definition_not_established:{name}")
        if identity.parameter_spec_status != "selected_source_content_bound":
            limitations.append(
                f"calibration_parameter_spec_source_status:{name}:{identity.parameter_spec_status}"
            )

    limitations.extend(
        (
            "calibration_source_attestation_not_established",
            "calibration_uncertainty_law_not_authoritative",
            "response_basis_candidate_only",
            "external_parameter_unit_authority_not_established",
        )
    )

    return _CalibrationResponseSource(
        report_ref=report_ref,
        basis_ref=basis_ref,
        report=report,
        basis=basis,
        input_envelopes=input_envelopes,
        input_envelope_refs=input_envelope_refs,
        input_envelope_sources=input_envelope_sources,
        limitation_codes=tuple(dict.fromkeys(limitations)),
    )


def _require_basis_source_digest(name: str, expected: str | None, actual: str) -> None:
    """Require a captured basis digest to match its independently read source."""
    if expected is None:
        raise _InvalidResponseBasis(f"calibration basis {name} digest is missing")
    if expected != actual:
        raise _InvalidResponseBasis(f"calibration basis {name} digest mismatch")


def _reconcile_calibration_parameter_inputs(
    ctx: ExecutionContext,
    basis_manifest: Any,
    basis: CalibrationExecutionInputBasis,
    candidate: ExecuteResponseBasisCandidate,
    *,
    program_graph: ProgramGraph | None,
    limitations: list[str],
) -> None:
    """Reconcile every captured parameter source with its selected program node."""
    supported_roles = {
        "calibration_config",
        "exec_plan",
        "program_graph",
        "base_state_snapshot",
        "state_blob",
        "registry_bundle",
        "mechanism_registry",
        "unit_registry",
        *(f"parameter_input.{item.ordinal}" for item in basis.parameter_inputs),
    }
    unexpected_roles = sorted({item.role for item in basis_manifest.inputs} - supported_roles)
    if unexpected_roles:
        raise _InvalidResponseBasis(
            f"calibration input basis has unrecognized source edges: {unexpected_roles}"
        )

    state_blob = candidate.source_inputs.get("source_state.state_blob")
    if state_blob is None:
        raise _InvalidResponseBasis("execute response source omits the selected base-state blob")
    state_blob_edges = [item for item in basis_manifest.inputs if item.role == "state_blob"]
    if [(str(item.artifact_id), item.manifest_profile_sha256) for item in state_blob_edges] != [
        (str(state_blob.ref.artifact_id), state_blob.ref.manifest_profile_sha256)
    ]:
        raise _InvalidResponseBasis(
            "calibration input basis state_blob edge differs from the execute response source"
        )

    nodes = {} if program_graph is None else {node.node_id: node for node in program_graph.nodes}
    rows_by_node: dict[str, list[Any]] = {}
    for row in basis.parameter_inputs:
        edge_role = f"parameter_input.{row.ordinal}"
        edges = [item for item in basis_manifest.inputs if item.role == edge_role]
        if row.source_ref is None:
            if edges:
                raise _InvalidResponseBasis(
                    f"calibration parameter input {row.ordinal} has an unbound source edge"
                )
        elif [(str(item.artifact_id), item.manifest_profile_sha256) for item in edges] != [
            (str(row.source_ref.artifact_id), row.source_ref.manifest_profile_sha256)
        ]:
            raise _InvalidResponseBasis(
                f"calibration parameter input {row.ordinal} edge differs from its payload"
            )

        if row.source_status == "selected_source_mismatch":
            raise _InvalidResponseBasis(
                f"calibration parameter input {row.ordinal} records a source mismatch"
            )
        if row.node_id is None:
            limitations.append(f"calibration_parameter_input_node_not_established:{row.ordinal}")
            continue
        node = nodes.get(row.node_id)
        if node is None:
            raise _InvalidResponseBasis(
                f"calibration parameter input node is absent from the selected program: {row.node_id}"
            )
        if node.node_kind not in {"mechanism", "op"}:
            raise _InvalidResponseBasis(
                f"calibration parameter input node is not executable by Calibrator: {row.node_id}"
            )

        mechanism_type = node.mechanism_type
        source: Any = node.params_ref
        if node.node_kind == "op" and node.op is not None:
            if node.op.op_kind == "apply_mechanism":
                mechanism_type = node.op.params.get("mechanism_type") or mechanism_type
                source = node.op.params.get("params_ref") or source
            else:
                raise _InvalidResponseBasis(
                    f"calibration parameter input node is not an apply-mechanism node: {row.node_id}"
                )
        if mechanism_type is None:
            raise _InvalidResponseBasis(
                f"calibration parameter input has no selected mechanism: {row.node_id}"
            )
        if mechanism_type != row.mechanism_type:
            raise _InvalidResponseBasis(
                f"calibration parameter input mechanism differs for {row.node_id}"
            )
        expected_ref = source if isinstance(source, ArtifactRef) else None
        if expected_ref is None:
            if row.source_ref is not None:
                raise _InvalidResponseBasis(
                    f"calibration parameter input {row.ordinal} binds a foreign source ref"
                )
            limitations.append(f"calibration_parameter_input_source_not_selected:{row.node_id}")
        else:
            if row.source_ref is None:
                raise _InvalidResponseBasis(
                    f"calibration parameter input {row.ordinal} omits its selected program source"
                )
            if _reference_identity(row.source_ref) != _reference_identity(expected_ref):
                raise _InvalidResponseBasis(
                    f"calibration parameter input source differs from program node {row.node_id}"
                )
            _selected_manifest(ctx, expected_ref, expected_kind=expected_ref.kind, model=None)
            payload = get_json_artifact(_ensure_ir_artifact_store(ctx.store), expected_ref)
            actual_payload_digest = canonical_input_sha256(payload)
            if row.payload_sha256 is None:
                limitations.append(
                    f"calibration_parameter_input_payload_not_established:{row.ordinal}"
                )
            elif row.payload_sha256 != actual_payload_digest:
                raise _InvalidResponseBasis(
                    f"calibration parameter loader payload differs from program node {row.node_id}"
                )
            if row.source_payload_sha256 is not None:
                if row.source_payload_sha256 != actual_payload_digest:
                    raise _InvalidResponseBasis(
                        f"calibration parameter source digest differs for {row.node_id}"
                    )
            elif row.source_status == "selected_source_matched":
                raise _InvalidResponseBasis(
                    f"calibration parameter source digest is missing for {row.node_id}"
                )
            else:
                limitations.append(
                    f"calibration_parameter_source_digest_not_established:{row.node_id}"
                )
            if row.source_status != "selected_source_matched":
                limitations.append(
                    f"calibration_parameter_source_status:{row.node_id}:{row.source_status}"
                )

        if row.status != "content_bound" or row.effective_values_status != "content_bound":
            limitations.append(
                f"calibration_parameter_effective_values_not_established:{row.node_id}"
            )
        rows_by_node.setdefault(row.node_id, []).append(row)

    for parameter_name in candidate.parameter_names:
        node_id, separator, parameter_id = parameter_name.rpartition(".")
        if not separator:
            raise _InvalidResponseBasis(
                f"execute response parameter name is not node-qualified: {parameter_name}"
            )
        matching_rows = [
            row for row in rows_by_node.get(node_id, ()) if parameter_id in row.parameter_ids
        ]
        if len(matching_rows) > 1:
            raise _InvalidResponseBasis(
                f"calibration parameter input is ambiguous for {parameter_name}"
            )
        if not matching_rows:
            if basis.input_capture_status == "content_bound":
                raise _InvalidResponseBasis(
                    f"content-bound calibration input omits response parameter {parameter_name}"
                )
            limitations.append(f"calibration_parameter_input_not_established:{parameter_name}")


def _response_lineage_inputs(
    candidate: ExecuteResponseBasisCandidate,
    source: _CalibrationResponseSource,
    *,
    config_ref: ArtifactRef,
) -> list[InputRef]:
    """Preserve all selected response, calibration, and configuration lineage."""
    inputs = [
        _input_ref(
            candidate.selected_simulation_result_ref,
            role="response_basis.selected_simulation_result",
        ),
        _input_ref(
            candidate.source_simulation_result_ref,
            role="response_basis.source_simulation_result",
        ),
        _input_ref(candidate.diagnostic_ref, role="response_basis.identifiability_diagnostic"),
        _input_ref(candidate.sensitivity_matrix_ref, role="response_basis.sensitivity_matrix"),
        _input_ref(source.report_ref, role="response_basis.calibration_report"),
        _input_ref(source.basis_ref, role="response_basis.calibration_execution_input_basis"),
        _input_ref(config_ref, role="response_basis.propagation_config"),
    ]
    inputs.extend(
        _input_ref(identity.ref, role=f"response_context.{role}")
        for role, identity in sorted(candidate.source_inputs.items())
    )
    inputs.extend(
        _input_ref(ref, role=f"input_envelope.{name}")
        for name, ref in sorted(source.input_envelope_refs.items())
    )
    return inputs


def _build_execute_response_state_projection_fn(
    candidate: ExecuteResponseBasisCandidate,
    *,
    selected_state_slot_ids: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    response_source: _CalibrationResponseSource,
) -> tuple[_PropagationFunction, set[str], dict[str, str], list[str]]:
    """Project exact state-slot rows of the recomputed absolute Jacobian."""
    inverse_slots: dict[str, str] = {}
    for moment_name, slot_id in candidate.response_slots.items():
        if slot_id in inverse_slots:
            raise _InvalidResponseBasis("response matrix repeats a state-slot subject")
        inverse_slots[slot_id] = moment_name
    unknown_slots = sorted(set(selected_state_slot_ids) - set(inverse_slots))
    if unknown_slots:
        raise _InvalidResponseBasis(
            f"requested state slots are absent from the response basis: {unknown_slots}"
        )
    if len(set(selected_state_slot_ids)) != len(selected_state_slot_ids):
        raise _InvalidResponseBasis("requested response state slots must be unique")

    input_names = set(input_envelopes)
    if input_names != set(response_source.input_envelopes):
        raise _InvalidResponseBasis(
            "calibration response source changed while projecting envelopes"
        )
    extra_input_names = sorted(input_names - set(candidate.parameter_names))
    if extra_input_names:
        raise _InvalidResponseBasis(
            f"input envelopes are outside the response basis: {extra_input_names}"
        )
    for name, envelope in input_envelopes.items():
        expected_center = envelope.numeric_policy.canonicalize(candidate.parameter_center[name])
        if envelope.point_estimate != expected_center:
            raise _InvalidResponseBasis(f"input envelope point estimate differs for {name!r}")

    missing_parameters = sorted(set(candidate.parameter_names) - input_names)
    extra_report_parameters = sorted(
        set(response_source.report.uncertainty_envelopes or {}) - set(candidate.parameter_names)
    )
    incomplete_parameters = sorted(set(missing_parameters) | set(extra_report_parameters))
    parameter_indexes = {name: index for index, name in enumerate(candidate.parameter_names)}
    moment_indexes = {name: index for index, name in enumerate(candidate.moment_names)}
    frozen = {
        slot_id: float(candidate.fitted_moments[inverse_slots[slot_id]])
        for slot_id in selected_state_slot_ids
    }
    sensitivity_map: dict[str, dict[str, float]] = {}
    status_by_slot: dict[str, str] = {}
    for slot_id in selected_state_slot_ids:
        moment_name = inverse_slots[slot_id]
        row = candidate.jacobian[moment_indexes[moment_name]]
        sensitivity_map[slot_id] = {
            name: float(row[parameter_indexes[name]]) for name in candidate.parameter_names
        }
        status_by_slot[slot_id] = "partial" if incomplete_parameters else "recomputed"

    def _fn(**current_params: Any) -> dict[str, Any]:
        projected = dict(frozen)
        for slot_id, coefficients in sensitivity_map.items():
            projected[slot_id] = frozen[slot_id] + sum(
                coefficient
                * (
                    current_params.get(name, candidate.parameter_center[name])
                    - candidate.parameter_center[name]
                )
                for name, coefficient in coefficients.items()
            )
        return projected

    propagation_fn = cast("_PropagationFunction", _fn)
    propagation_fn._sensitivity_map = sensitivity_map  # pyright: ignore[reportPrivateUsage]
    propagation_fn._sensitivity_mapping_source = "execute_response_matrix"  # pyright: ignore[reportPrivateUsage]
    return (
        propagation_fn,
        set(candidate.parameter_names),
        status_by_slot,
        incomplete_parameters,
    )


def _mark_state_slot_projection(
    result: PropagationResult,
    *,
    candidate: ExecuteResponseBasisCandidate,
    response_source: _CalibrationResponseSource,
    moment_name: str,
) -> UncertaintyEnvelope:
    """Persist a candidate-only output tied to one verified state-slot row."""
    slot_id = result.metric_id
    subject = {
        "kind": "state_slot",
        "id": slot_id,
        "state_path": candidate.state_paths[moment_name],
        "unit_id": candidate.moment_unit_ids[moment_name],
    }
    source_identity = {
        "response_diagnostic_ref": candidate.diagnostic_ref.model_dump(mode="json"),
        "sensitivity_matrix_ref": candidate.sensitivity_matrix_ref.model_dump(mode="json"),
        "calibration_report_ref": response_source.report_ref.model_dump(mode="json"),
        "calibration_execution_input_basis_ref": response_source.basis_ref.model_dump(mode="json"),
        "selected_source_simulation_result_ref": candidate.source_simulation_result_ref.model_dump(
            mode="json"
        ),
        "state_response_moment": moment_name,
        "input_envelope_sources": {
            name: dict(source)
            for name, source in sorted(response_source.input_envelope_sources.items())
        },
        "limitation_codes": list(response_source.limitation_codes),
    }
    envelope = result.envelope
    return envelope.model_copy(
        update={
            "gate_eligible": False,
            "metadata": {
                **envelope.metadata,
                "candidate_only": True,
                "uncertainty_subject": subject,
                "state_slot_response_basis": source_identity,
            },
        }
    )


def _build_propagation_fn(
    params: Mapping[str, Any],
    *,
    base_metric_values: Mapping[str, float],
    nominal_params: Mapping[str, float],
) -> tuple[_PropagationFunction, set[str]]:
    frozen = dict(base_metric_values)
    nominal = dict(nominal_params)
    metric_ids = sorted(frozen.keys())
    param_names = sorted(nominal.keys())

    sensitivity_map, mapped_params = _resolve_sensitivity_map(
        params=params,
        metric_ids=metric_ids,
        param_names=param_names,
        base_metric_values=frozen,
    )

    def _fn(**current_params: Any) -> dict[str, Any]:
        result = dict(frozen)
        for metric_id in metric_ids:
            base_value = frozen[metric_id]
            metric_sens = sensitivity_map.get(metric_id, {})
            if not metric_sens:
                continue
            delta = 0.0
            for param_name, coef in metric_sens.items():
                current = current_params.get(param_name, nominal.get(param_name, 0.0))
                baseline = nominal.get(param_name, 0.0)
                if base_value == 0.0:
                    delta += float(coef) * (current - baseline)
                else:
                    denom = max(abs(baseline), 1.0)
                    delta += float(coef) * ((current - baseline) / denom)
            result[metric_id] = (
                base_value + delta if base_value == 0.0 else base_value * (1.0 + delta)
            )
        return result

    propagation_fn = cast("_PropagationFunction", _fn)
    # This private attribute is an intentional metadata bridge for the local node.
    propagation_fn._sensitivity_map = sensitivity_map  # pyright: ignore[reportPrivateUsage]
    propagation_fn._sensitivity_mapping_source = (  # pyright: ignore[reportPrivateUsage]
        "caller_parameters" if _SENSITIVITY_MAPPING_PARAM in params else "absent"
    )
    return propagation_fn, mapped_params


def _resolve_sensitivity_map(
    *,
    params: Mapping[str, Any],
    metric_ids: list[str],
    param_names: list[str],
    base_metric_values: Mapping[str, float],
) -> tuple[dict[str, dict[str, float]], set[str]]:
    raw = _validate_sensitivity_mapping_shape(params)
    sensitivity: dict[str, dict[str, float]] = {}
    mapped: set[str] = set()
    if raw is None:
        return sensitivity, mapped

    known_metrics = set(metric_ids)
    unknown_metrics = sorted(set(raw) - known_metrics)
    if unknown_metrics:
        raise _InvalidSensitivityMapping(
            f"propagation_sensitivity references unknown output metric ids: {unknown_metrics}"
        )

    known_params = set(param_names)
    for metric_id, per_metric in raw.items():
        unknown_params = sorted(set(per_metric) - known_params)
        if unknown_params:
            raise _InvalidSensitivityMapping(
                f"propagation_sensitivity[{metric_id!r}] references unknown input ids: "
                f"{unknown_params}"
            )
        sensitivity[metric_id] = dict(per_metric)
        mapped.update(per_metric)

    return sensitivity, mapped


def _mark_sensitivity_mapping(
    result: PropagationResult,
    *,
    mapping_status: str,
    mapping_source: str,
) -> PropagationResult:
    """Keep caller-mapped output candidate-only and label its non-authoritative origin."""
    mapping_evidence = {
        "sensitivity_mapping": mapping_status,
        "sensitivity_mapping_source": mapping_source,
        "sensitivity_mapping_limited": True,
        "candidate_only": True,
    }
    envelope = result.envelope.model_copy(
        update={
            "gate_eligible": False,
            "metadata": {**result.envelope.metadata, **mapping_evidence},
        }
    )
    return PropagationResult(
        metric_id=result.metric_id,
        envelope=envelope,
        input_envelopes_used=result.input_envelopes_used,
        method_used=result.method_used,
        diagnostics={**result.diagnostics, **mapping_evidence},
    )


def _load_config(state: ExperimentState) -> PropagationConfig:
    if "propagation_config" in state.params:
        raw = state.params["propagation_config"]
        if not isinstance(raw, Mapping):
            raise _InvalidPropagationConfig(
                "params.propagation_config must be a mapping when provided"
            )
        try:
            return PropagationConfig.model_validate(raw)
        except _PROPAGATION_VALIDATION_ERRORS as exc:
            raise _InvalidPropagationConfig("params.propagation_config is invalid") from exc

    overrides: dict[str, Any] = {}
    for field_name in PropagationConfig.model_fields:
        prefixed = f"propagation_{field_name}"
        if prefixed in state.params:
            overrides[field_name] = state.params[prefixed]
    if overrides:
        try:
            return PropagationConfig.model_validate(overrides)
        except _PROPAGATION_VALIDATION_ERRORS as exc:
            raise _InvalidPropagationConfig("params.propagation_* overrides are invalid") from exc
    return PropagationConfig()


def _persist_config(
    ctx: ExecutionContext,
    config: PropagationConfig,
    *,
    return_selected_profile: bool = False,
) -> ArtifactRef:
    return ctx.store.put_json(
        config,
        PutOptions(
            kind="foundry.propagation_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationConfig", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=return_selected_profile,
    )


def _persist_report(
    ctx: ExecutionContext,
    *,
    results: list[PropagationResult],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    output_metrics: list[str],
    mapped_params: set[str],
    unmapped_metric_ids: list[str],
    missing_output_metric_ids: list[str],
    incomplete_output_metric_ids: list[str],
    mapping_source: Literal["caller_parameters", "execute_response_matrix", "not_established"],
    response_candidate: ExecuteResponseBasisCandidate | None = None,
    response_source: _CalibrationResponseSource | None = None,
    response_projection: Mapping[str, str] | None = None,
    response_lineage_inputs: list[InputRef] | None = None,
    propagation_config_ref: ArtifactRef | None = None,
    output_envelope_refs: Mapping[str, UncertaintyEnvelopeRef] | None = None,
    missing_response_parameters: list[str] | None = None,
) -> ArtifactRef:
    declared_mapping = mapping_source in {
        "caller_parameters",
        "execute_response_matrix",
    }
    result_mapping_statuses = [
        item.diagnostics.get("sensitivity_mapping")
        for item in results
        if item.diagnostics.get("sensitivity_mapping") is not None
    ]
    if mapping_source == "execute_response_matrix":
        mapping_status = "partial" if incomplete_output_metric_ids else "candidate_only"
    elif (
        declared_mapping
        and result_mapping_statuses
        and all(value == "consumer_asserted" for value in result_mapping_statuses)
    ):
        mapping_status = "consumer_asserted"
    elif declared_mapping and any(
        value in {"consumer_asserted", "partial"} for value in result_mapping_statuses
    ):
        mapping_status = "partial"
    elif mapping_source == "caller_parameters" and not unmapped_metric_ids:
        mapping_status = "consumer_asserted"
    elif not unmapped_metric_ids:
        mapping_status = "resolved"
    elif len(unmapped_metric_ids) < len(output_metrics):
        mapping_status = "partial"
    else:
        mapping_status = "unresolved"
    shared_provenance = results[0].diagnostics.get("draw_outcome_provenance") if results else None
    if shared_provenance is not None and not all(
        item.diagnostics.get("draw_outcome_provenance") is shared_provenance for item in results
    ):
        shared_provenance = None

    diagnostics: list[dict[str, Any]] = []
    for item in results:
        item_diagnostics = dict(item.diagnostics)
        if shared_provenance is not None:
            item_diagnostics.pop("draw_outcome_provenance", None)
        diagnostics.append(
            {
                "metric_id": item.metric_id,
                "method": item.method_used.value,
                "diagnostics": item_diagnostics,
            }
        )

    payload = {
        "schema_version": "1.1",
        "input_envelope_count": len(input_envelopes),
        "output_metric_count": len(output_metrics),
        "mapped_param_count": len(mapped_params),
        "mapped_params": sorted(mapped_params),
        "mapping_status": mapping_status,
        "mapping_source": mapping_source,
        "mapping_basis_status": (
            "candidate_only"
            if mapping_source == "execute_response_matrix"
            else "consumer_asserted"
            if declared_mapping
            else "not_established"
        ),
        "unmapped_metric_ids": sorted(unmapped_metric_ids),
        "missing_output_metric_ids": sorted(missing_output_metric_ids),
        "methods": [item.method_used.value for item in results],
        "diagnostics": diagnostics,
        "incomplete_output_metric_ids": sorted(incomplete_output_metric_ids),
    }
    report_inputs: list[InputRef] = []
    if (
        response_candidate is not None
        and response_source is not None
        and response_projection is not None
        and propagation_config_ref is not None
    ):
        response_status = "partial" if incomplete_output_metric_ids else "candidate_only"
        payload["response_basis_candidate"] = {
            "schema_version": "1.0",
            "evidence_grade": "candidate",
            "gate_eligible": False,
            "mapping_status": response_status,
            "mapping_basis_status": "candidate_only",
            "state_slot_to_moment": dict(response_projection),
            "source_inputs": {
                role: identity.model_dump(mode="json")
                for role, identity in sorted(response_candidate.source_inputs.items())
            },
            "selected_simulation_result_ref": response_candidate.selected_simulation_result_ref.model_dump(
                mode="json"
            ),
            "source_simulation_result_ref": response_candidate.source_simulation_result_ref.model_dump(
                mode="json"
            ),
            "diagnostic_ref": response_candidate.diagnostic_ref.model_dump(mode="json"),
            "sensitivity_matrix_ref": response_candidate.sensitivity_matrix_ref.model_dump(
                mode="json"
            ),
            "calibration_report_ref": response_source.report_ref.model_dump(mode="json"),
            "calibration_execution_input_basis_ref": response_source.basis_ref.model_dump(
                mode="json"
            ),
            "propagation_config_ref": propagation_config_ref.model_dump(mode="json"),
            "limitation_codes": list(response_source.limitation_codes),
            "missing_parameter_envelopes": sorted(missing_response_parameters or []),
        }
        payload["state_slot_outputs"] = {
            slot_id: {
                "subject_kind": "state_slot",
                "subject_id": slot_id,
                "state_path": response_candidate.state_paths[moment_name],
                "unit_id": response_candidate.moment_unit_ids[moment_name],
                "response_moment": moment_name,
                "envelope_ref": (
                    output_envelope_refs[slot_id].model_dump(mode="json")
                    if output_envelope_refs is not None and slot_id in output_envelope_refs
                    else None
                ),
                "evidence_grade": "candidate",
                "gate_eligible": False,
                "input_envelope_sources": {
                    name: dict(source)
                    for name, source in sorted(response_source.input_envelope_sources.items())
                },
            }
            for slot_id, moment_name in response_projection.items()
        }
        report_inputs.extend(response_lineage_inputs or [])
        report_inputs.extend(
            _input_ref(ref, role=f"state_slot_envelope.{slot_id}")
            for slot_id, ref in sorted((output_envelope_refs or {}).items())
        )
    elif response_candidate is not None or response_source is not None:
        raise ValueError("execute response report is missing a bound source or projection")
    if shared_provenance is not None:
        payload["draw_outcome_provenance"] = shared_provenance
    return ctx.store.put_json(
        payload,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
            inputs=report_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=response_candidate is not None,
    )


__all__ = ["PropagateUncertaintyNode"]
