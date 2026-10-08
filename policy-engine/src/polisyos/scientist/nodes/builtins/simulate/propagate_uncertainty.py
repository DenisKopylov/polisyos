"""Public simulate propagate uncertainty module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, SimulationResult, SimulationResultRef
from polisyos.foundry.calibration.identifiability import (
    IdentifiabilityDiagnosticConfig,
    _load_execute_response_matrix,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.delta import _missing_output_result
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.protocol import PropagationResult
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
    load_uncertainty_envelope,
)
from polisyos.ir.registry.refs import UncertaintyEnvelopeRef
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_PROPAGATION_REPORT_REF,
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state

logger = get_logger(__name__)

_PROPAGATION_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_PROPAGATION_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)


class _PropagationFunction(Protocol):
    """Callable response carrying its resolved sensitivity map."""

    _sensitivity_map: dict[str, dict[str, float]]

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
        "params.propagation_response_slots",
        "params.propagation_input_envelope_refs",
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
        native = state.params.get("propagation_response_basis")
        response_metadata: dict[str, Any] = {
            "profile": "consumer_asserted_hypothesis",
            "gate_eligible": False,
        }
        response_inputs = [
            input_ref_from_artifact_ref(sim_result_ref, role="base_simulation_result")
        ]
        if native is not None:
            # Native scientific state slots are distinct from operational Metrics.
            # NATIVE_RESPONSE_BRIDGE: retained-marker control removes this dispatch.
            (
                results,
                input_envelopes,
                output_metric_ids,
                mapped_params,
                unmapped_metric_ids,
                config,
                response_metadata,
                response_inputs,
            ) = _native_response_results(ctx, state, sim_result_ref)
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
            config = _load_config(state)
            nominal_params = {name: env.point_estimate for name, env in input_envelopes.items()}
            simulation_fn, mapped_params = _build_propagation_fn(
                state.params, base_metric_values=metric_values, nominal_params=nominal_params
            )
            output_metric_ids = sorted(metric_values)
            results = PropagationDispatcher(config).propagate(
                simulation_fn=simulation_fn,
                nominal_params=nominal_params,
                input_envelopes=input_envelopes,
                output_metric_ids=output_metric_ids,
                is_jax_differentiable=True,
            )
            sensitivity_map = getattr(simulation_fn, "_sensitivity_map", {})
            unmapped_metric_ids = [
                name for name in output_metric_ids if not sensitivity_map.get(name)
            ]
            # Bare coefficients keep their historical numerics but cannot establish
            # a source/unit-bound response or scientific admission.
            results = [
                _mark_response_scope(item, "consumer_asserted_hypothesis") for item in results
            ]

        if not results:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="Propagation yielded no results")],
            )

        if unmapped_metric_ids:
            results = [
                _mark_unresolved_sensitivity(item)
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

        config_ref = _persist_config(ctx, config)
        response_inputs.append(input_ref_from_artifact_ref(config_ref, role="propagation_config"))
        response_metadata = {
            **response_metadata,
            "propagation_config_ref": config_ref.model_dump(mode="json"),
            "propagation_config": config.model_dump(mode="json"),
        }
        envelope_refs: dict[str, ArtifactRef] = {}
        artifacts: list[ArtifactRef] = []
        for item in results:
            ref = _persist_node_envelope(ctx, item.envelope, inputs=response_inputs)
            envelope_refs[item.metric_id] = ref
            artifacts.append(ref)

        report_ref = _persist_report(
            ctx,
            results=results,
            input_envelopes=input_envelopes,
            output_metrics=output_metric_ids,
            mapped_params=mapped_params,
            unmapped_metric_ids=unmapped_metric_ids,
            missing_output_metric_ids=missing_output_metric_ids,
            incomplete_output_metric_ids=incomplete_output_metric_ids,
            response_metadata=response_metadata,
            inputs=response_inputs,
        )

        updated_sim = sim_result.model_copy(
            update={
                # Preserve the historical strict IR payload ABI. Exact selected
                # views live in this SimulationResult's owned manifest edges.
                "uncertainty_envelopes": {
                    name: UncertaintyEnvelopeRef(
                        artifact_id=str(ref.artifact_id), kind=ref.kind, media_type=ref.media_type
                    )
                    for name, ref in envelope_refs.items()
                },
                "propagation_config_ref": config_ref,
                "propagation_report_ref": report_ref,
            }
        )
        update_inputs = [
            input_ref_from_artifact_ref(sim_result_ref, role="base_simulation_result"),
            input_ref_from_artifact_ref(report_ref, role="propagation_report"),
            input_ref_from_artifact_ref(config_ref, role="propagation_config"),
            *(
                input_ref_from_artifact_ref(ref, role=f"metric_envelope.{name}")
                for name, ref in envelope_refs.items()
            ),
        ]

        updated_ref_payload = ctx.store.put_json(
            updated_sim,
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.core.SimulationResult", version=updated_sim.schema_version
                ),
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


class _NativeResponseRequest(BaseModel):
    """Internal, finite executed-response bridge; no authority is inferred."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    matrix_ref: ArtifactRef
    response_slots: dict[str, str]
    response_units: dict[str, dict[str, Any]]
    parameter_center: dict[str, float]
    diagnostic_config: IdentifiabilityDiagnosticConfig


def _native_response_results(
    ctx: ExecutionContext, state: ExperimentState, source_ref: ArtifactRef
):
    request = _NativeResponseRequest.model_validate(state.params["propagation_response_basis"])
    requested = state.params.get("propagation_response_slots")
    if (
        not isinstance(requested, dict)
        or not requested
        or not all(
            isinstance(k, str) and k and isinstance(v, str) and v for k, v in requested.items()
        )
    ):
        raise ValueError("native response requires the complete requested slot roster")
    if not request.response_slots or any(
        requested.get(k) != v for k, v in request.response_slots.items()
    ):
        raise ValueError("requested slots contradict or omit the verified matrix roster")
    # Resolve the real current SimulationResult and exact selected matrix view.
    matrix_manifest = ctx.store.get_manifest(request.matrix_ref)
    if matrix_manifest.kind != "foundry.identifiability_sensitivity_matrix":
        raise ValueError("native response matrix has the wrong artifact kind")
    payload = _load_execute_response_matrix(
        ctx.store,
        request.matrix_ref,
        source_ref=SimulationResultRef.model_validate(source_ref.model_dump(mode="python")),
        response_slots=request.response_slots,
        parameter_center=request.parameter_center,
        config=request.diagnostic_config,
    )
    basis = payload["response_basis"]
    if request.response_units != basis["moment_units"]:
        raise ValueError("requested response units differ from the registered state slots")
    refs = state.params.get("propagation_input_envelope_refs", {})
    if not isinstance(refs, dict) or not set(refs).issubset(basis["parameter_names"]):
        raise ValueError("input law roster differs from the native parameter axes")
    envelopes = {}
    inputs = [
        input_ref_from_artifact_ref(source_ref, role="base_simulation_result"),
        input_ref_from_artifact_ref(request.matrix_ref, role="response_matrix"),
    ]
    for name, raw_ref in refs.items():
        ref = ArtifactRef.model_validate(raw_ref)
        manifest = ctx.store.get_manifest(ref)
        if manifest.kind != "ir.uncertainty_envelope":
            raise ValueError("native input law has the wrong artifact kind")
        envelope = UncertaintyEnvelope.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(ref))
        )
        if (
            envelope.metadata.get("param_name") != name
            or envelope.metadata.get("unit") != basis["parameter_units"][name]
            or envelope.point_estimate != request.parameter_center[name]
        ):
            raise ValueError("input law parameter/unit/center differs from the executed basis")
        envelopes[name] = envelope
        inputs.append(input_ref_from_artifact_ref(ref, role=f"input_envelope.{name}"))
    # Native config errors must refuse, never silently fall back to defaults.
    config = PropagationConfig.model_validate(state.params.get("propagation_config", {}))
    dispatcher = PropagationDispatcher(config)
    results = []
    mapped = set()
    unavailable = []
    for name in requested:
        if name not in request.response_slots:
            item = _missing_output_result(name, input_param_names=list(basis["parameter_names"]))
            unavailable.append(name)
        else:
            row = payload["jacobian"][basis["moment_names"].index(name)]
            coefficients = dict(zip(basis["parameter_names"], row, strict=True))
            active = {k: v for k, v in coefficients.items() if v != 0.0}
            center_value = payload["center_response"][name]
            if not active:
                item = PropagationResult(
                    metric_id=name,
                    envelope=UncertaintyEnvelope(
                        point_estimate=center_value,
                        confidence_interval=(center_value, center_value),
                        confidence_level=None,
                        distribution_family=DistributionFamily.UNKNOWN,
                        source=UncertaintySource.ENSEMBLE,
                        propagation_method=PropagationMethod.DELTA_METHOD,
                        interval_semantics=IntervalSemantics.DETERMINISTIC_BOUNDS,
                        gate_eligible=False,
                        metadata={
                            "verified_zero_jacobian": True,
                            "output_variance": 0.0,
                            "constant_scope": "local_linearized_response",
                            "global_constancy": "not_established",
                        },
                    ),
                    input_envelopes_used=[],
                    method_used=PropagationMethod.DELTA_METHOD,
                    diagnostics={"output_variance": 0.0, "verified_zero_jacobian": True},
                )
            elif not set(active).issubset(envelopes):
                item = _missing_output_result(name, input_param_names=sorted(active))
                item = PropagationResult(
                    metric_id=name,
                    envelope=item.envelope,
                    input_envelopes_used=item.input_envelopes_used,
                    method_used=item.method_used,
                    diagnostics={
                        **item.diagnostics,
                        "missing_input_laws": sorted(set(active) - set(envelopes)),
                    },
                )
                unavailable.append(name)
            else:
                selected = {k: envelopes[k] for k in active}
                projection = _native_projection(
                    name, center_value, active, request.parameter_center
                )
                item = dispatcher.propagate(
                    simulation_fn=projection,
                    nominal_params={k: request.parameter_center[k] for k in active},
                    input_envelopes=selected,
                    output_metric_ids=[name],
                    is_jax_differentiable=True,
                )[0]
                if item.envelope.distribution_family is DistributionFamily.UNKNOWN:
                    unavailable.append(name)
                else:
                    mapped.update(active)
        results.append(
            _mark_response_scope(
                item, "execute_scalar_state_response_v1", unit=basis["moment_units"].get(name)
            )
        )
    metadata = {
        "profile": "execute_scalar_state_response_v1",
        "gate_eligible": False,
        "matrix_ref": request.matrix_ref.model_dump(mode="json"),
        "source_ref": source_ref.model_dump(mode="json"),
        "requested_slots": dict(requested),
        "verified_slots": request.response_slots,
        "response_units": basis["moment_units"],
        "parameter_units": basis["parameter_units"],
        "parameter_center": request.parameter_center,
        "diagnostic_config": request.diagnostic_config.model_dump(mode="json"),
        "projection": "persisted_state_local_jacobian",
        "authority": "not_established",
    }
    return results, envelopes, list(requested), mapped, unavailable, config, metadata, inputs


def _native_projection(
    name: str, center_value: float, coefficients: Mapping[str, float], center: Mapping[str, float]
):
    """Dimensioned additive local projection, independent of response level."""

    def response(**theta):
        return {
            name: center_value
            + sum(coef * (theta[param] - center[param]) for param, coef in coefficients.items())
        }

    return response


def _mark_response_scope(
    result: PropagationResult, profile: str, *, unit=None
) -> PropagationResult:
    metadata = {
        **result.envelope.metadata,
        "response_profile": profile,
        "authority": "not_established",
    }
    if unit is not None:
        metadata["unit"] = unit
    updates: dict[str, Any] = {"gate_eligible": False, "metadata": metadata}
    if (
        profile == "execute_scalar_state_response_v1"
        and result.envelope.interval_semantics is not IntervalSemantics.DETERMINISTIC_BOUNDS
    ):
        # Local linearization is not an estimator CI or an authority certificate.
        updates.update(
            confidence_level=None,
            interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
            is_heuristic_ci=True,
            composition_provenance=None,
        )
    return PropagationResult(
        metric_id=result.metric_id,
        envelope=UncertaintyEnvelope.model_validate(
            result.envelope.model_copy(update=updates).model_dump(mode="python")
        ),
        input_envelopes_used=result.input_envelopes_used,
        method_used=result.method_used,
        diagnostics={**result.diagnostics, "response_profile": profile, "gate_eligible": False},
    )


def _persist_node_envelope(
    ctx: ExecutionContext, envelope: UncertaintyEnvelope, *, inputs: list[InputRef]
) -> ArtifactRef:
    """Retain the actual CAS view without changing the historical IR ref DTO."""
    return ctx.store.put_json(
        envelope.model_dump(mode="python", round_trip=True),
        PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _load_propagated_envelopes(
    store, simulation_ref: ArtifactRef
) -> dict[str, UncertaintyEnvelope]:
    """Read this finite SimulationResult output roster through its owned views.

    Historical IR payload refs omit selectors. The producer's exact manifest
    edges own those views; no default-latest or shape-only fallback is admitted.
    This reader verifies custody/ABI, not scientific or Runtime authority.
    """
    simulation = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_ref))
    )
    payload_refs = simulation.uncertainty_envelopes or {}
    edges = [
        item
        for item in store.get_manifest(simulation_ref).inputs
        if item.role.startswith("metric_envelope.")
    ]
    if len(edges) != len(payload_refs) or {item.role for item in edges} != {
        f"metric_envelope.{name}" for name in payload_refs
    }:
        raise ValueError("propagated envelope manifest roster differs from the payload")
    refs = {}
    for name, payload_ref in payload_refs.items():
        matches = [item for item in edges if item.role == f"metric_envelope.{name}"]
        if len(matches) != 1 or str(matches[0].artifact_id) != str(payload_ref.artifact_id):
            raise ValueError("propagated envelope has missing/duplicate/contradictory owned view")
        ref = ArtifactRef(
            artifact_id=matches[0].artifact_id,
            kind=payload_ref.kind,
            media_type=payload_ref.media_type,
            manifest_profile_sha256=matches[0].manifest_profile_sha256,
        )
        store.get_manifest(ref)
        refs[name] = ref
    # Resolve the complete roster before loading any output envelope.
    return {
        name: UncertaintyEnvelope.model_validate(from_canonical_bytes(store.get_bytes(ref)))
        for name, ref in refs.items()
    }


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
    payload = from_canonical_bytes(ctx.store.get_bytes(ref))
    return model_cls.model_validate(payload)


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
                    ctx.store,
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
                    envelopes[str(name)] = load_uncertainty_envelope(ctx.store, ref)
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
    raw = params.get("propagation_sensitivity")
    sensitivity: dict[str, dict[str, float]] = {}
    mapped: set[str] = set()

    if isinstance(raw, dict):
        for metric_id in metric_ids:
            per_metric = raw.get(metric_id)
            if not isinstance(per_metric, dict):
                continue
            metric_map: dict[str, float] = {}
            for param_name, coef in per_metric.items():
                if not isinstance(param_name, str):
                    continue
                if param_name not in param_names:
                    continue
                try:
                    coef_float = float(coef)
                except (TypeError, ValueError):
                    continue
                metric_map[param_name] = coef_float
                mapped.add(param_name)
            if metric_map:
                sensitivity[metric_id] = metric_map

    return sensitivity, mapped


def _mark_unresolved_sensitivity(result: PropagationResult) -> PropagationResult:
    """Address an unknown relation without emitting a Normal constant."""
    profile = result.envelope.metadata.get("response_profile", "consumer_asserted_hypothesis")
    unit = result.envelope.metadata.get("unit")
    if result.envelope.distribution_family is not DistributionFamily.UNKNOWN:
        result = _missing_output_result(
            result.metric_id, input_param_names=result.input_envelopes_used
        )
        result = _mark_response_scope(result, profile, unit=unit)
    envelope = result.envelope.model_copy(
        update={
            "gate_eligible": False,
            "metadata": {**result.envelope.metadata, "sensitivity_mapping": "unresolved"},
        }
    )
    return PropagationResult(
        metric_id=result.metric_id,
        envelope=envelope,
        input_envelopes_used=result.input_envelopes_used,
        method_used=result.method_used,
        diagnostics={**result.diagnostics, "sensitivity_mapping": "unresolved"},
    )


def _load_config(state: ExperimentState) -> PropagationConfig:
    raw = state.params.get("propagation_config")
    if isinstance(raw, dict):
        try:
            return PropagationConfig.model_validate(raw)
        except _PROPAGATION_VALIDATION_ERRORS:
            logger.debug(
                "Invalid propagation_config override; falling back to defaults", exc_info=True
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
    response_metadata: Mapping[str, Any],
    inputs: list[InputRef],
) -> ArtifactRef:
    mapping_status = (
        "resolved"
        if not unmapped_metric_ids
        else "partial"
        if len(unmapped_metric_ids) < len(output_metrics)
        else "unresolved"
    )
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
        "unmapped_metric_ids": sorted(unmapped_metric_ids),
        "missing_output_metric_ids": sorted(missing_output_metric_ids),
        "methods": [item.method_used.value for item in results],
        "diagnostics": diagnostics,
        "incomplete_output_metric_ids": sorted(incomplete_output_metric_ids),
        "response_basis": dict(response_metadata),
        "gate_eligible": False,
        "full_mapping_established": not incomplete_output_metric_ids
        and not unmapped_metric_ids
        and response_metadata["profile"] == "execute_scalar_state_response_v1",
    }
    if shared_provenance is not None:
        payload["draw_outcome_provenance"] = shared_provenance
    return ctx.store.put_json(
        payload,
        PutOptions(
            kind="foundry.propagation_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.PropagationReport", version="1.1"),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = ["PropagateUncertaintyNode"]
