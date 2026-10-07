"""Public simulate propagate uncertainty module API."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core import canon as core_canon
from polisyos.core import contracts as core_contracts
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import Metrics, SimulationResult, SimulationResultRef
from polisyos.foundry.uncertainty import (
    BayesianFitBinding,
    BoundedIndicatorResponse,
    load_foundry_calibration_report,
    persist_bayesian_fit_envelopes,
    reconcile_draw_outcomes,
    verify_mean_certificate,
)
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.foundry.uncertainty.dispatcher import PropagationDispatcher
from polisyos.foundry.uncertainty.protocol import PropagationResult
from polisyos.ir.analytics import (
    UncertaintyEnvelope,
    admit_posterior_summary_profiles,
    posterior_nominal_mean,
)
from polisyos.ir.analytics import load_posterior_summary_envelope as load_uncertainty_envelope
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

CanonSpec = core_canon.CanonSpec
from_canonical_bytes = core_canon.from_canonical_bytes

logger = get_logger(__name__)

_PROPAGATION_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_PROPAGATION_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)


class _PropagationFunction(Protocol):
    """Callable response carrying its resolved sensitivity map."""

    _sensitivity_map: dict[str, dict[str, float]]

    def __call__(self, **current_params: Any) -> dict[str, Any]: ...


def _admit_output_envelope_ref(
    ctx: ExecutionContext, raw_ref: ArtifactRef, payload: dict[str, Any]
) -> tuple[ArtifactRef, core_contracts.UncertaintyEnvelopeRef]:
    """Bind a complete returned handle and actual CAS object before publication."""
    ref = ArtifactRef.model_validate(raw_ref.model_dump(mode="json"))
    # Preserve the old publisher's literal DTO and three-field normalization.
    typed = core_contracts.UncertaintyEnvelopeRef.model_validate(
        {"artifact_id": str(ref.artifact_id), "kind": ref.kind, "media_type": ref.media_type}
    )
    expected_id = core_canon.content_hash(
        core_canon.to_canonical_bytes(payload, CanonSpec(forbid_floats=False)), prefix=True
    )
    try:
        manifest = ctx.store.get_manifest(ref)
        data = ctx.store.get_bytes(ref)
        verification = ctx.store.verify(ref)
    except _PROPAGATION_LOAD_ERRORS as exc:
        raise ValueError("persisted output envelope cannot be resolved") from exc
    schema = manifest.artifact_schema
    if (
        str(ref.artifact_id) != expected_id
        or core_canon.content_hash(data, prefix=True) != expected_id
        or manifest.kind != "ir.uncertainty_envelope"
        or manifest.media_type != "application/json"
        or schema is None
        or schema.name != "ir.uncertainty_envelope"
        or schema.version != "1.1"
        or not verification.ok
    ):
        raise ValueError("persisted output envelope kind/schema/content is invalid")
    # A declared selected view was resolved above; the existing SimulationResult
    # contract carries the same three fields as the old typed IR publisher.
    return ArtifactRef.model_validate(typed.model_dump(mode="json")), typed


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
        "inputs.bayesian_method_result_ref",
        "inputs.bayesian_method_evidence_ref",
        "params.posterior_fit",
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

        fit_envelope_refs: dict[str, ArtifactRef] = {}
        input_envelopes = _collect_input_envelopes(ctx, state, fit_envelope_refs=fit_envelope_refs)
        if not input_envelopes:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[NodeEvent(level="info", message="No input uncertainty envelopes")],
            )

        config = _load_config(state)
        dispatcher = PropagationDispatcher(config)
        admit_posterior_summary_profiles(input_envelopes)

        nominal_params = {
            name: posterior_nominal_mean(env, parameter_name=name)
            for name, env in input_envelopes.items()
        }
        simulation_fn, mapped_params = _build_propagation_fn(
            state.params,
            base_metric_values=metric_values,
            nominal_params=nominal_params,
        )
        output_metric_ids = sorted(metric_values.keys())
        mean_plan = config.bounded_iid_mean
        if mean_plan is not None and mean_plan.response_threshold is not None:
            if len(input_envelopes) != 1 or output_metric_ids != [mean_plan.metric_id]:
                raise ValueError("bounded indicator profile requires one input and output")
            input_name = next(iter(input_envelopes))
            simulation_fn = BoundedIndicatorResponse(
                input_name=input_name,
                metric_id=mean_plan.metric_id,
                threshold=mean_plan.response_threshold,
            )

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
        if type(simulation_fn) is BoundedIndicatorResponse:
            sensitivity_map = {simulation_fn.metric_id: {simulation_fn.input_name: 1.0}}
            mapped_params = {simulation_fn.input_name}
        unmapped_metric_ids = [
            metric_id for metric_id in output_metric_ids if not sensitivity_map.get(metric_id)
        ]
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

        envelope_refs: dict[str, ArtifactRef] = {}
        simulation_envelope_refs: dict[str, core_contracts.UncertaintyEnvelopeRef] = {}
        artifacts: list[ArtifactRef] = []
        for item in results:
            payload = item.envelope.model_dump(mode="python", round_trip=True)
            raw_ref = ctx.store.put_json(
                payload,
                PutOptions(
                    kind="ir.uncertainty_envelope",
                    media_type="application/json",
                    schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            ref, typed_ref = _admit_output_envelope_ref(ctx, raw_ref, payload)
            persisted_envelope = load_uncertainty_envelope(ctx.store, ref)
            verify_mean_certificate(persisted_envelope)
            if item.diagnostics.get("output_coverage_complete") is False:
                if persisted_envelope.gate_eligible:
                    raise ValueError("incomplete execution cannot publish a gating envelope")
            envelope_refs[item.metric_id] = ref
            simulation_envelope_refs[item.metric_id] = typed_ref
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
            input_envelope_refs=fit_envelope_refs,
        )
        report_payload = from_canonical_bytes(ctx.store.get_bytes(report_ref.artifact_id))
        outcome_receipt = report_payload.get("draw_outcome_provenance")
        if outcome_receipt is not None:
            failed_ids = reconcile_draw_outcomes(outcome_receipt, output_metric_ids)
            if not failed_ids.issubset(set(report_payload["incomplete_output_metric_ids"])):
                raise ValueError("persisted propagation report hides failed output support")

        updated_sim = sim_result.model_copy(
            update={
                "uncertainty_envelopes": simulation_envelope_refs,
                "propagation_config_ref": config_ref,
                "propagation_report_ref": report_ref,
            }
        )
        update_inputs = [
            InputRef(
                artifact_id=sim_result_ref.artifact_id,
                role="base_simulation_result",
            ),
            InputRef(
                artifact_id=report_ref.artifact_id,
                role="propagation_report",
            ),
            InputRef(
                artifact_id=config_ref.artifact_id,
                role="propagation_config",
            ),
        ]
        for metric_id, ref in envelope_refs.items():
            update_inputs.append(
                InputRef(
                    artifact_id=ref.artifact_id,
                    role=f"metric_envelope.{metric_id}",
                )
            )

        updated_ref_payload = ctx.store.put_json(
            updated_sim,
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.1"),
                inputs=update_inputs,
            ),
        )
        updated_ref = SimulationResultRef(artifact_id=updated_ref_payload.artifact_id)

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


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
    payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
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
    *,
    fit_envelope_refs: dict[str, ArtifactRef] | None = None,
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
        # A configured report is an explicit input, not an optional payload
        # hint. Preserve its selected CAS profile and reject an invalid report
        # before a different valid input could hide the missing calibration law.
        report = load_foundry_calibration_report(ctx.store, calibration_ref)
        if report.uncertainty_envelopes:
            for name, env in report.uncertainty_envelopes.items():
                envelopes[str(name)] = env
        elif report.uncertainty_envelope_refs:
            for name, ref in report.uncertainty_envelope_refs.items():
                envelopes[str(name)] = load_uncertainty_envelope(ctx.store, ref)

    result_ref = state.inputs.get("bayesian_method_result_ref")
    evidence_ref = state.inputs.get("bayesian_method_evidence_ref")
    if result_ref is not None or evidence_ref is not None:
        if result_ref is None or evidence_ref is None:
            raise ValueError("Bayesian fit requires both result and evidence refs")
        if envelopes:
            raise ValueError("Bayesian fit inlet requires its complete unmixed parameter group")
        binding = BayesianFitBinding.model_validate(state.params.get("posterior_fit"))
        fit = persist_bayesian_fit_envelopes(ctx.store, result_ref, evidence_ref, binding)
        envelopes.update(fit.envelopes)
        if fit_envelope_refs is not None:
            fit_envelope_refs.update(fit.envelope_refs)

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
    """Mark a result non-authoritative when no response map was established."""

    metadata = {
        **result.envelope.metadata,
        "sensitivity_mapping": "unresolved",
    }
    envelope = result.envelope.model_copy(
        update={
            "gate_eligible": False,
            "metadata": metadata,
        }
    )
    return PropagationResult(
        metric_id=result.metric_id,
        envelope=envelope,
        input_envelopes_used=result.input_envelopes_used,
        method_used=result.method_used,
        diagnostics={
            **result.diagnostics,
            "sensitivity_mapping": "unresolved",
        },
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
    input_envelope_refs: Mapping[str, ArtifactRef] | None = None,
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
        "bayesian_fit_envelope_refs": {
            name: ref.model_dump(mode="json") for name, ref in (input_envelope_refs or {}).items()
        },
        "output_metric_count": len(output_metrics),
        "mapped_param_count": len(mapped_params),
        "mapped_params": sorted(mapped_params),
        "mapping_status": mapping_status,
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
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role=f"input_envelope:{name}")
                for name, ref in (input_envelope_refs or {}).items()
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = ["PropagateUncertaintyNode"]
