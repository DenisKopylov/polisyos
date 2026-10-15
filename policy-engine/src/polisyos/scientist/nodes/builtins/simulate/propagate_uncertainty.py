"""Public simulate propagate uncertainty module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from numbers import Real
from typing import Any, Literal, Protocol, cast

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    Metrics,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.protocol import PropagationResult
from polisyos.ir import ArtifactRefModel, get_json_artifact
from polisyos.ir.analytics.uncertainty import (
    UncertaintyEnvelope,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
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


class _InvalidSensitivityMapping(ValueError):
    """A supplied sensitivity map cannot be interpreted against this run."""


class _PropagationFunction(Protocol):
    """Callable response carrying its resolved sensitivity map."""

    _sensitivity_map: dict[str, dict[str, float]]
    _sensitivity_mapping_source: Literal["absent", "caller_parameters"]

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

        sim_result = _load_model(ctx, sim_result_ref, SimulationResult)
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

        config = _load_config(state)
        dispatcher = PropagationDispatcher(config)

        nominal_params = {name: env.point_estimate for name, env in input_envelopes.items()}
        try:
            simulation_fn, mapped_params = _build_propagation_fn(
                state.params,
                base_metric_values=metric_values,
                nominal_params=nominal_params,
            )
        except _InvalidSensitivityMapping as exc:
            return _sensitivity_mapping_failure(state, exc)
        output_metric_ids = sorted(metric_values.keys())

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
        if raw_mapping_supplied:
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
            )
        ]

        envelope_refs: dict[str, ArtifactRef] = {}
        artifacts: list[ArtifactRef] = []
        for item in results:
            ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(ctx.store), item.envelope)
            envelope_refs[item.metric_id] = ref
            artifacts.append(ref)

        config_ref = _persist_config(ctx, config)
        report_ref = _persist_report(
            ctx,
            results=results,
            input_envelopes=input_envelopes,
            output_metrics=output_metric_ids,
            mapped_params=mapped_params,
            unmapped_metric_ids=unmapped_metric_ids,
            missing_output_metric_ids=missing_output_metric_ids,
            incomplete_output_metric_ids=incomplete_output_metric_ids,
            mapping_source=("caller_parameters" if raw_mapping_supplied else "not_established"),
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
        for metric_id, ref in envelope_refs.items():
            update_inputs.append(_input_ref(ref, role=f"metric_envelope.{metric_id}"))

        updated_ref_payload = ctx.store.put_json(
            updated_sim,
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
                inputs=update_inputs,
            ),
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
                        f"Propagated uncertainty for {len(results)} metrics "
                        f"(inputs={len(input_envelopes)})"
                    ),
                )
            ],
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


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
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
    raw = state.params.get("propagation_config")
    if isinstance(raw, dict):
        try:
            return PropagationConfig.model_validate(raw)
        except _PROPAGATION_VALIDATION_ERRORS:
            logger.debug(
                "Invalid propagation_config override; falling back to defaults",
                exc_info=True,
            )

    overrides: dict[str, Any] = {}
    for field_name in PropagationConfig.model_fields:
        prefixed = f"propagation_{field_name}"
        if prefixed in state.params:
            overrides[field_name] = state.params[prefixed]
    if overrides:
        return PropagationConfig.model_validate(overrides)
    return PropagationConfig()


def _persist_config(ctx: ExecutionContext, config: PropagationConfig) -> ArtifactRef:
    return ctx.store.put_json(
        config,
        PutOptions(
            kind="foundry.propagation_config",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationConfig", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
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
    mapping_source: Literal["caller_parameters", "not_established"],
) -> ArtifactRef:
    if mapping_source == "caller_parameters" and not unmapped_metric_ids:
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
            "consumer_asserted" if mapping_source == "caller_parameters" else "not_established"
        ),
        "unmapped_metric_ids": sorted(unmapped_metric_ids),
        "missing_output_metric_ids": sorted(missing_output_metric_ids),
        "methods": [item.method_used.value for item in results],
        "diagnostics": diagnostics,
        "incomplete_output_metric_ids": sorted(incomplete_output_metric_ids),
    }
    if shared_provenance is not None:
        payload["draw_outcome_provenance"] = shared_provenance
    return ctx.store.put_json(
        payload,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = ["PropagateUncertaintyNode"]
