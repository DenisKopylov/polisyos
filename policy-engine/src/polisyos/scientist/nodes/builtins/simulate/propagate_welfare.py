"""Public simulate propagate welfare module API."""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Any, Literal

import numpy as np
from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    EquilibriumMultiplicityReport,
    FeedbackSolveResult,
    Metrics,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.foundry.calibration.report import CalibrationReport
from polisyos.foundry.uncertainty.config import PropagationConfig
from polisyos.ir.analytics.dependence_structure import (
    DependenceStructure,
    load_dependence_structure,
)
from polisyos.ir.analytics.phase4_dynamics import EquilibriumMultiplicityWelfareAnnotation
from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    UncertaintyEnvelope,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)
from polisyos.ir.analytics.welfare import (
    ChannelDecompositionTargetKind,
    GEUncertaintyBundle,
    GEUncertaintyRepresentation,
    WelfareBundle,
    WelfareIntervalSemantics,
    WelfareMethod,
    WelfareSampleBundle,
    WelfareStatus,
    build_channel_decomposition_ref,
    load_ge_uncertainty_bundle,
    persist_ge_uncertainty_bundle,
    persist_welfare_bundle,
    persist_welfare_sample_bundle,
)
from polisyos.ir.observation.bundles import LeontiefIOBundle
from polisyos.ir.refs import (
    ArtifactRefModel,
    DependenceStructureRef,
    GEUncertaintyBundleRef,
    UncertaintyEnvelopeRef,
    WelfareSampleBundleRef,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    ARTIFACT_WELFARE_BUNDLE_REF,
    INPUT_CALIBRATION_REPORT_REF,
    INPUT_DATA_SNAPSHOT_REF,
)
from polisyos.scientist.policy_design.phase3 import ensure_social_weight_manifest_artifact

logger = get_logger(__name__)

_WELFARE_LOAD_ERRORS = (OSError, RuntimeError, TypeError, ValueError, ValidationError)
_WELFARE_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)

_ERROR_WELFARE_MODEL_CLASS_MISMATCH = "ERROR_WELFARE_MODEL_CLASS_MISMATCH"
_ERROR_WELFARE_DIMENSION_MISMATCH = "ERROR_WELFARE_DIMENSION_MISMATCH"
_ERROR_GE_OPERATOR_SINGULAR = "ERROR_GE_OPERATOR_SINGULAR"
_ERROR_GE_UNCERTAINTY_REF_KIND = "ERROR_GE_UNCERTAINTY_REF_KIND"
_ERROR_DEPENDENCE_SPEC_INVALID = "ERROR_DEPENDENCE_SPEC_INVALID"
_ERROR_INTERVAL_SEMANTICS_INVALID = "ERROR_INTERVAL_SEMANTICS_INVALID"
_ERROR_MONTE_CARLO_NOT_CONVERGED = "ERROR_MONTE_CARLO_NOT_CONVERGED"
_ERROR_WELFARE_OUTPUT_NONFINITE = "ERROR_WELFARE_OUTPUT_NONFINITE"
_ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID = "ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID"
_ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED = "ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED"

_EXPLICIT_WELFARE_RESPONSE_KEYS = frozenset(("pe_response", "metric_order", "weights"))
_EXPLICIT_GE_UNCERTAINTY_KEYS = frozenset(
    (
        "ge_uncertainty_ref",
        "ge_matrix",
        "ge_lower_matrix",
        "ge_upper_matrix",
        "ge_technical_coefficients",
        "ge_lower_technical_coefficients",
        "ge_upper_technical_coefficients",
        "ge_model_ref",
        "ge_entry_map",
    )
)

_DEFAULT_CONDITION_THRESHOLD = 1e12
_DEFAULT_MAX_VERTEX_ENUMERATION = 10

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_propagate_welfare@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Propagate Welfare",
    description="Aggregate PE and GE uncertainty into a typed welfare bundle.",
    tags=["builtin", "simulate", "welfare"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"inputs.{INPUT_DATA_SNAPSHOT_REF}",
        f"inputs.{INPUT_CALIBRATION_REPORT_REF}",
        "params.welfare_config",
        "params.welfare_channel_decomposition",
        "params.welfare_weights",
        "params.welfare_social_weight_manifest",
        "params.welfare_social_weight_ref",
        "params.welfare_metric_order",
        "params.welfare_pe_response",
        "params.welfare_pe_sensitivity",
        "params.welfare_ge_matrix",
        "params.welfare_ge_lower_matrix",
        "params.welfare_ge_upper_matrix",
        "params.welfare_ge_technical_coefficients",
        "params.welfare_ge_lower_technical_coefficients",
        "params.welfare_ge_upper_technical_coefficients",
        "params.welfare_ge_entry_map",
        "params.welfare_ge_model_ref",
        "params.welfare_ge_uncertainty_ref",
        "params.welfare_dependence_structure_ref",
        "params.social_weight_manifest",
        "params.social_weight_ref",
        "params.propagation_config",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_SIMULATION_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_WELFARE_BUNDLE_REF}",
    ],
    produces=[ARTIFACT_SIMULATION_RESULT_REF, ARTIFACT_WELFARE_BUNDLE_REF],
)


@dataclass(frozen=True)
class _ResolvedGEContext:
    source_kind: Literal["none", "multiplier", "technical_coefficients"]
    point_multiplier: np.ndarray | None
    source_matrix: np.ndarray | None
    lower_multiplier: np.ndarray | None
    upper_multiplier: np.ndarray | None
    ge_model_ref: ArtifactRefModel | None
    ge_uncertainty_ref: GEUncertaintyBundleRef | None
    ge_entry_map: dict[str, tuple[int, int]]
    diagnostics: dict[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ResolvedDependenceContext:
    ref: DependenceStructureRef | None
    structure: DependenceStructure | None
    correlation_matrix: np.ndarray | None
    parameter_order: tuple[str, ...]
    strategy: str
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _ResolvedWelfareContext:
    welfare_measure: str
    model_class: str
    ge_multiplier_semantics: str
    labels: tuple[str, ...]
    base_response: np.ndarray
    weights: np.ndarray
    weights_ref: ArtifactRefModel | None
    social_weight_ref: ArtifactRefModel | None
    policy_ref: ArtifactRefModel | None
    baseline_ref: ArtifactRefModel | None
    pe_model_ref: ArtifactRefModel | None
    dependence_structure_ref: DependenceStructureRef | None
    dependence_context: _ResolvedDependenceContext
    pe_sensitivity: dict[str, dict[str, float]]
    ge_context: _ResolvedGEContext
    warnings: tuple[str, ...]
    diagnostics: dict[str, Any]


@dataclass(frozen=True)
class _EnvelopeCollection:
    envelopes: dict[str, UncertaintyEnvelope]
    refs: dict[str, UncertaintyEnvelopeRef]


@dataclass(frozen=True)
class _PropagationOutcome:
    credible_interval: tuple[float, float] | None
    method_used: WelfareMethod
    result_map: dict[str, Any]
    method_config_ref: ArtifactRefModel | None
    report_ref: ArtifactRefModel | None
    sample_bundle_ref: WelfareSampleBundleRef | None
    diagnostics: dict[str, Any]


class _WelfareNodeFailure(Exception):
    def __init__(self, error: NodeError) -> None:
        super().__init__(error.message)
        self.error = error


@dataclass(frozen=True)
class PropagateWelfareNode:
    """Propagate welfare under PE/GE uncertainty into a typed top-level bundle."""

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
                        level="info", message="No simulation_result_ref; skip welfare propagation"
                    )
                ],
            )

        try:
            sim_result = _load_model(ctx, sim_result_ref, SimulationResult)
            metrics = _load_model(ctx, sim_result.metrics_ref, Metrics)
        except _WELFARE_LOAD_ERRORS as exc:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="warn",
                        message=f"Unable to load simulation outputs for welfare: {exc}",
                    )
                ],
            )

        welfare_params = _load_welfare_params(state)
        numeric_metrics = _extract_numeric_metrics(metrics)

        try:
            collection = _collect_input_envelopes(ctx, state, welfare_params=welfare_params)
            if (
                not collection.envelopes
                and not _has_explicit_welfare_request(
                    welfare_params,
                    keys=_EXPLICIT_WELFARE_RESPONSE_KEYS | _EXPLICIT_GE_UNCERTAINTY_KEYS,
                )
            ):
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[
                        NodeEvent(
                            level="info",
                            code="welfare.inputs_missing",
                            message=(
                                "No welfare target or PE/GE uncertainty inputs supplied; "
                                "skip welfare propagation"
                            ),
                        )
                    ],
                )
            context = _resolve_welfare_context(
                ctx,
                welfare_params=welfare_params,
                numeric_metrics=numeric_metrics,
                response_size_hint=len(numeric_metrics),
            )
            simulation_fn, nominal_params, used_input_envelopes, pe_uncertainty_refs = (
                _build_simulation_fn(
                    ctx,
                    context=context,
                    available_envelopes=collection,
                )
            )
            if (
                not used_input_envelopes
                and context.ge_context.ge_uncertainty_ref is None
                and context.ge_context.lower_multiplier is None
                and context.ge_context.upper_multiplier is None
            ):
                return NodeOutcome(
                    status="skip",
                    state=state,
                    events=[
                        NodeEvent(
                            level="info",
                            message="No PE or GE uncertainty supplied; skip welfare propagation",
                        )
                    ],
                )
            point_outputs = simulation_fn(**nominal_params)
            point_estimate = float(point_outputs["welfare"])
            if not math.isfinite(point_estimate):
                raise _fail_error(
                    _ERROR_WELFARE_OUTPUT_NONFINITE,
                    "Nominal welfare output is non-finite",
                )
            propagation = _propagate_credible_interval(
                ctx,
                state,
                welfare_params=welfare_params,
                context=context,
                simulation_fn=simulation_fn,
                nominal_params=nominal_params,
                input_envelopes=used_input_envelopes,
            )
            robust_interval, robust_diagnostics = _build_robust_interval(
                context=context,
                nominal_params=nominal_params,
                input_envelopes=used_input_envelopes,
            )
            if not math.isfinite(robust_interval[0]) or not math.isfinite(robust_interval[1]):
                raise _fail_error(
                    _ERROR_WELFARE_OUTPUT_NONFINITE,
                    "Robust welfare interval contains non-finite values",
                )
            warnings, status = _resolve_bundle_status(
                context=context,
                used_input_envelopes=used_input_envelopes,
                dependence_applied=bool(propagation.diagnostics.get("dependence_applied", False)),
            )
            method_used = _resolve_bundle_method(
                propagation.method_used,
                credible_interval=propagation.credible_interval,
                robust_interval=robust_interval,
            )
            interval_semantics = _resolve_interval_semantics(
                credible_interval=propagation.credible_interval,
                robust_interval=robust_interval,
            )
            diagnostics = {
                **context.diagnostics,
                "credible_method": propagation.method_used.value,
                "input_envelope_count": len(used_input_envelopes),
                "pe_uncertainty_count": len(pe_uncertainty_refs),
                **propagation.diagnostics,
                "robust": robust_diagnostics,
            }
            if propagation.report_ref is not None:
                diagnostics["propagation_report_ref"] = str(propagation.report_ref.artifact_id)
            sensitivity_diagnostics_ref = _persist_sensitivity_diagnostics(
                ctx,
                simulation_fn=simulation_fn,
                nominal_params=nominal_params,
                input_envelopes=used_input_envelopes,
                robust_interval=robust_interval,
            )
            total_vector = _point_total_vector(context, nominal_params=nominal_params)
            subgroup_welfare = _resolve_subgroup_welfare(
                welfare_params=welfare_params,
                labels=context.labels,
                total_vector=total_vector,
            )
            channel_decomposition_ref = _maybe_build_channel_decomposition_ref(
                ctx,
                welfare_params=welfare_params,
                total_vector=total_vector,
            )
            equilibrium_multiplicity = _equilibrium_multiplicity_annotation(ctx, sim_result)
            bundle = WelfareBundle(
                welfare_measure=context.welfare_measure,
                model_class=context.model_class,
                ge_multiplier_semantics=context.ge_multiplier_semantics,
                policy_ref=context.policy_ref,
                baseline_ref=context.baseline_ref,
                pe_model_ref=context.pe_model_ref,
                ge_model_ref=context.ge_context.ge_model_ref,
                pe_uncertainty_refs=pe_uncertainty_refs,
                ge_uncertainty_ref=context.ge_context.ge_uncertainty_ref,
                dependence_structure_ref=context.dependence_structure_ref,
                social_weight_ref=context.social_weight_ref,
                welfare_weights_ref=context.weights_ref,
                channel_decomposition_ref=channel_decomposition_ref,
                point_estimate=point_estimate,
                credible_interval=propagation.credible_interval,
                robust_interval=robust_interval,
                interval_semantics=interval_semantics,
                channel_decomposition={
                    "pe": float(point_outputs["welfare_pe"]),
                    "ge": float(point_outputs["welfare_ge"]),
                },
                subgroup_welfare=subgroup_welfare,
                equilibrium_multiplicity=equilibrium_multiplicity,
                method_used=method_used,
                method_config_ref=propagation.method_config_ref,
                sample_bundle_ref=propagation.sample_bundle_ref,
                sensitivity_diagnostics_ref=sensitivity_diagnostics_ref,
                warnings=warnings,
                status=status,
                diagnostics=diagnostics,
                metadata={
                    "response_labels": list(context.labels),
                    "used_input_params": sorted(used_input_envelopes),
                    "source_social_weight_handle": _source_social_weight_handle(welfare_params),
                    "equilibrium_multiplicity_status": equilibrium_multiplicity.status,
                },
            )
            bundle_inputs = _bundle_inputs(
                sim_result_ref=sim_result_ref,
                metric_ref=sim_result.metrics_ref,
                pe_uncertainty_refs=pe_uncertainty_refs,
                ge_uncertainty_ref=context.ge_context.ge_uncertainty_ref,
                dependence_structure_ref=context.dependence_structure_ref,
                channel_decomposition_ref=channel_decomposition_ref,
                method_config_ref=propagation.method_config_ref,
                report_ref=propagation.report_ref,
                sample_bundle_ref=propagation.sample_bundle_ref,
                sensitivity_diagnostics_ref=sensitivity_diagnostics_ref,
            )
            bundle_ref = persist_welfare_bundle(ctx.store, bundle, inputs=bundle_inputs)
            updated_simulation_result = sim_result.model_copy(
                update={"welfare_bundle_ref": bundle_ref}
            )
            updated_simulation_result_payload = ctx.store.put_json(
                updated_simulation_result,
                PutOptions(
                    kind="foundry.simulation_result",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.2"),
                    inputs=[
                        InputRef(
                            artifact_id=str(sim_result_ref.artifact_id),
                            role="base_simulation_result",
                        ),
                        InputRef(
                            artifact_id=str(bundle_ref.artifact_id),
                            role="welfare_bundle",
                        ),
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
            updated_simulation_result_ref = SimulationResultRef(
                artifact_id=updated_simulation_result_payload.artifact_id
            )
        except _WelfareNodeFailure as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=exc.error,
                events=[
                    NodeEvent(
                        level="error",
                        code=exc.error.code,
                        message=exc.error.message,
                    )
                ],
            )

        new_state = branch_state(state, write_paths=("artifacts_index",)).state
        new_state.artifacts_index[ARTIFACT_SIMULATION_RESULT_REF] = updated_simulation_result_ref
        new_state.artifacts_index[ARTIFACT_WELFARE_BUNDLE_REF] = bundle_ref

        artifacts: list[ArtifactRef] = [updated_simulation_result_ref, bundle_ref]
        if channel_decomposition_ref is not None:
            artifacts.append(channel_decomposition_ref)
        if context.ge_context.ge_uncertainty_ref is not None:
            artifacts.append(context.ge_context.ge_uncertainty_ref)
        if propagation.method_config_ref is not None:
            artifacts.append(propagation.method_config_ref)
        if propagation.report_ref is not None:
            artifacts.append(propagation.report_ref)
        if propagation.sample_bundle_ref is not None:
            artifacts.append(propagation.sample_bundle_ref)
        if sensitivity_diagnostics_ref is not None:
            artifacts.append(sensitivity_diagnostics_ref)

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=artifacts,
            events=[
                NodeEvent(
                    level="info",
                    message=(
                        "Propagated welfare bundle "
                        f"(inputs={len(used_input_envelopes)}, status={status.value})"
                    ),
                )
            ],
        )


def _load_model(ctx: ExecutionContext, ref: ArtifactRef, model_cls):
    payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)


def _equilibrium_multiplicity_annotation(
    ctx: ExecutionContext,
    sim_result: SimulationResult,
) -> EquilibriumMultiplicityWelfareAnnotation:
    if sim_result.feedback_result_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    try:
        feedback = _load_model(ctx, sim_result.feedback_result_ref, FeedbackSolveResult)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            materiality_note="feedback_result_unavailable_for_multiplicity_annotation",
        )
    report_ref = feedback.multiplicity_report_ref
    if report_ref is None:
        return EquilibriumMultiplicityWelfareAnnotation(status="not_checked")
    generic_ref = ArtifactRefModel.model_validate(report_ref.model_dump(mode="python"))
    try:
        report = _load_model(ctx, report_ref, EquilibriumMultiplicityReport)
    except _WELFARE_LOAD_ERRORS:
        return EquilibriumMultiplicityWelfareAnnotation(
            status="unresolved",
            report_ref=generic_ref,
            selection_dependence=True,
            materiality_note="equilibrium_multiplicity_report_unavailable",
        )
    count = int(report.global_diagnostics.num_equilibria)
    unresolved = int(report.global_diagnostics.num_unresolved)
    status: Literal["unique", "multiple", "unresolved", "not_checked"]
    if count > 1:
        status = "multiple"
    elif unresolved > 0:
        status = "unresolved"
    elif count == 1:
        status = "unique"
    else:
        status = "unresolved"
    return EquilibriumMultiplicityWelfareAnnotation(
        status=status,
        report_ref=generic_ref,
        selection_dependence=status in {"multiple", "unresolved"},
        materiality_note=(
            f"equilibria={count}; unresolved_starts={unresolved}; "
            f"bifurcation_candidates={len(report.bifurcation_candidates)}"
        ),
        metadata={
            "num_equilibria": count,
            "num_unresolved": unresolved,
            "bifurcation_candidate_count": len(report.bifurcation_candidates),
        },
    )


def _load_welfare_params(state: ExperimentState) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    raw_config = state.params.get("welfare_config")
    if isinstance(raw_config, dict):
        resolved.update(raw_config)
    for key, value in state.params.items():
        if key.startswith("welfare_"):
            resolved[key[8:]] = value
    return resolved


def _has_explicit_welfare_request(
    welfare_params: Mapping[str, Any],
    *,
    keys: frozenset[str],
) -> bool:
    for key in keys:
        if welfare_params.get(key) is not None:
            return True
        prefixed_key = f"welfare_{key}"
        if welfare_params.get(prefixed_key) is not None:
            return True
    return False


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
    welfare_params: Mapping[str, Any],
) -> _EnvelopeCollection:
    envelopes: dict[str, UncertaintyEnvelope] = {}
    refs: dict[str, UncertaintyEnvelopeRef] = {}

    data_snapshot_ref = state.inputs.get(INPUT_DATA_SNAPSHOT_REF)
    if data_snapshot_ref is not None:
        snapshot = _load_model(ctx, data_snapshot_ref, DataSnapshot)
        if snapshot.uncertainty_envelope_ref is not None:
            env = load_uncertainty_envelope(ctx.store, snapshot.uncertainty_envelope_ref)
            name = env.metadata.get("param_name")
            key = str(name) if isinstance(name, str) and name.strip() else "data_snapshot"
            envelopes[key] = env
            refs[key] = snapshot.uncertainty_envelope_ref

    calibration_ref = state.inputs.get(INPUT_CALIBRATION_REPORT_REF)
    if calibration_ref is not None:
        report = _load_model(ctx, calibration_ref, CalibrationReport)
        if report.uncertainty_envelope_refs:
            for name, ref in report.uncertainty_envelope_refs.items():
                envelopes[str(name)] = load_uncertainty_envelope(ctx.store, ref)
                refs[str(name)] = ref
        elif report.uncertainty_envelopes:
            for name, env in report.uncertainty_envelopes.items():
                envelopes[str(name)] = env

    raw_input_envelopes = welfare_params.get("input_envelopes")
    if isinstance(raw_input_envelopes, dict):
        for name, value in raw_input_envelopes.items():
            if not isinstance(name, str) or not name.strip():
                continue
            if isinstance(value, dict) and {"artifact_id", "kind", "media_type"} <= set(value):
                ref = UncertaintyEnvelopeRef.model_validate(value)
                envelopes[name] = load_uncertainty_envelope(ctx.store, ref)
                refs[name] = ref
                continue
            try:
                envelopes[name] = UncertaintyEnvelope.model_validate(value)
            except _WELFARE_VALIDATION_ERRORS:
                logger.debug("Invalid inline welfare input envelope for %s", name, exc_info=True)

    return _EnvelopeCollection(envelopes=envelopes, refs=refs)


def _resolve_welfare_context(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
    response_size_hint: int,
) -> _ResolvedWelfareContext:
    labels, base_response = _resolve_base_response(
        welfare_params=welfare_params,
        numeric_metrics=numeric_metrics,
    )
    weights, weights_ref = _resolve_weights(
        ctx,
        welfare_params=welfare_params,
        labels=labels,
    )
    social_weight_ref = ensure_social_weight_manifest_artifact(
        ctx,
        welfare_params=welfare_params,
    )
    policy_ref = _coerce_artifact_ref(welfare_params.get("policy_ref"))
    baseline_ref = _coerce_artifact_ref(welfare_params.get("baseline_ref"))
    pe_model_ref = _coerce_artifact_ref(welfare_params.get("pe_model_ref"))
    dependence_context = _resolve_dependence_context(ctx, welfare_params)
    dependence_structure_ref = dependence_context.ref
    pe_sensitivity = _resolve_pe_sensitivity(
        welfare_params=welfare_params,
        labels=labels,
    )
    ge_multiplier_semantics = _resolve_ge_multiplier_semantics(welfare_params)
    model_class = str(welfare_params.get("model_class") or "linearized_ge_io")
    _validate_model_class(model_class, ge_multiplier_semantics)
    ge_context = _resolve_ge_context(
        ctx,
        welfare_params=welfare_params,
        size=len(labels),
        ge_multiplier_semantics=ge_multiplier_semantics,
    )
    if ge_context.point_multiplier is not None and ge_context.point_multiplier.shape != (
        len(labels),
        len(labels),
    ):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "GE multiplier dimensions do not match welfare response vector",
            details={
                "multiplier_shape": list(ge_context.point_multiplier.shape),
                "response_size": len(labels),
            },
        )
    warnings = list(ge_context.warnings)
    diagnostics = {
        "response_size": len(labels),
        "metric_labels": list(labels),
        "weights_norm": float(np.linalg.norm(weights)),
        "response_size_hint": response_size_hint,
        "dependence_structure": dependence_context.diagnostics,
        **ge_context.diagnostics,
    }
    return _ResolvedWelfareContext(
        welfare_measure=str(welfare_params.get("measure") or "net_social_welfare"),
        model_class=model_class,
        ge_multiplier_semantics=ge_multiplier_semantics,
        labels=labels,
        base_response=base_response,
        weights=weights,
        weights_ref=weights_ref,
        social_weight_ref=social_weight_ref,
        policy_ref=policy_ref,
        baseline_ref=baseline_ref,
        pe_model_ref=pe_model_ref,
        dependence_structure_ref=dependence_structure_ref,
        dependence_context=dependence_context,
        pe_sensitivity=pe_sensitivity,
        ge_context=ge_context,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _resolve_base_response(
    *,
    welfare_params: Mapping[str, Any],
    numeric_metrics: Mapping[str, float],
) -> tuple[tuple[str, ...], np.ndarray]:
    metric_order = _coerce_str_list(welfare_params.get("metric_order"))
    raw_response = welfare_params.get("pe_response")

    if isinstance(raw_response, dict):
        labels = metric_order or [str(key) for key in raw_response]
        try:
            vector = np.asarray([float(raw_response[label]) for label in labels], dtype=np.float64)
        except KeyError as exc:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_pe_response is missing a requested metric_order label",
                details={"missing_label": str(exc)},
            ) from exc
        return tuple(labels), vector

    if isinstance(raw_response, (list, tuple)):
        vector = np.asarray([float(value) for value in raw_response], dtype=np.float64)
        if metric_order is not None and len(metric_order) != vector.shape[0]:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_metric_order length must match welfare_pe_response length",
                details={"metric_order": len(metric_order), "pe_response": int(vector.shape[0])},
            )
        if metric_order is None:
            labels = tuple(f"component_{idx}" for idx in range(vector.shape[0]))
        else:
            labels = tuple(metric_order)
        return labels, vector

    if metric_order is not None:
        missing = [label for label in metric_order if label not in numeric_metrics]
        if missing:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "Requested welfare_metric_order labels are missing from simulation metrics",
                details={"missing_metrics": missing},
            )
        return tuple(metric_order), np.asarray(
            [float(numeric_metrics[label]) for label in metric_order],
            dtype=np.float64,
        )

    raw_weights = welfare_params.get("weights")
    if isinstance(raw_weights, dict):
        labels = [str(key) for key in raw_weights]
        missing = [label for label in labels if label not in numeric_metrics]
        if missing:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights keys must align with numeric simulation metrics when pe_response is omitted",
                details={"missing_metrics": missing},
            )
        return tuple(labels), np.asarray(
            [float(numeric_metrics[label]) for label in labels],
            dtype=np.float64,
        )

    for candidate in ("net_social_welfare", "welfare", "policy_value", "gdp_change"):
        if candidate in numeric_metrics:
            return (candidate,), np.asarray([float(numeric_metrics[candidate])], dtype=np.float64)

    if len(numeric_metrics) == 1:
        label, value = next(iter(numeric_metrics.items()))
        return (label,), np.asarray([float(value)], dtype=np.float64)

    raise _fail_error(
        _ERROR_WELFARE_DIMENSION_MISMATCH,
        "No welfare target could be resolved from metrics or welfare_pe_response",
        details={"available_metrics": sorted(numeric_metrics)},
    )


def _resolve_weights(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
) -> tuple[np.ndarray, ArtifactRefModel | None]:
    raw_weights = welfare_params.get("weights")
    if raw_weights is None:
        if len(labels) != 1:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights must be provided when aggregating more than one response component",
                details={"labels": list(labels)},
            )
        return np.asarray([1.0], dtype=np.float64), None

    if isinstance(raw_weights, dict):
        missing = [label for label in labels if label not in raw_weights]
        if missing:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights is missing one or more response labels",
                details={"missing_labels": missing},
            )
        vector = np.asarray([float(raw_weights[label]) for label in labels], dtype=np.float64)
    elif isinstance(raw_weights, (list, tuple)):
        vector = np.asarray([float(value) for value in raw_weights], dtype=np.float64)
        if vector.shape[0] != len(labels):
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_weights length must match response vector length",
                details={"weights": int(vector.shape[0]), "response": len(labels)},
            )
    else:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "welfare_weights must be a dict keyed by labels or a dense list",
        )
    if not np.all(np.isfinite(vector)):
        raise _fail_error(
            _ERROR_WELFARE_OUTPUT_NONFINITE,
            "welfare_weights must be finite",
        )

    weights_ref = _persist_json_payload(
        ctx,
        payload={"labels": list(labels), "weights": vector.tolist()},
        kind="ir.welfare_weights",
        schema_name="ir.welfare_weights",
    )
    return vector, weights_ref


def _source_social_weight_handle(welfare_params: Mapping[str, Any]) -> str | None:
    for key in (
        "welfare_social_weight_ref",
        "social_weight_ref",
    ):
        value = welfare_params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_dependence_context(
    ctx: ExecutionContext,
    welfare_params: Mapping[str, Any],
) -> _ResolvedDependenceContext:
    raw = welfare_params.get("dependence_structure_ref")
    if raw is None:
        return _ResolvedDependenceContext(
            ref=None,
            structure=None,
            correlation_matrix=None,
            parameter_order=(),
            strategy="independent",
            warnings=(),
            diagnostics={"present": False, "strategy": "independent"},
        )
    try:
        ref = DependenceStructureRef.model_validate(raw)
        structure = load_dependence_structure(ctx.store, ref)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Invalid welfare dependence_structure_ref",
            details={"error": str(exc)},
        ) from exc
    warnings = list(structure.warnings)
    if structure.blocking_reasons:
        warnings.extend(f"blocking:{item}" for item in structure.blocking_reasons)

    metadata = dict(structure.metadata)
    parameter_order = (
        _coerce_str_list(metadata.get("parameter_order"))
        or _coerce_str_list(metadata.get("parameter_names"))
        or _coerce_str_list(metadata.get("order"))
        or []
    )
    correlation_matrix = _coerce_dependence_matrix(
        metadata.get("correlation_matrix")
        or metadata.get("gaussian_copula_correlation")
        or metadata.get("gaussian_copula_corr")
    )
    covariance_matrix = _coerce_dependence_matrix(
        metadata.get("covariance_matrix") or metadata.get("gaussian_copula_covariance")
    )
    strategy = "descriptive_only"
    if correlation_matrix is None and covariance_matrix is not None:
        correlation_matrix = _correlation_from_covariance(covariance_matrix)
        strategy = "gaussian_copula_from_covariance"
    elif correlation_matrix is not None:
        strategy = "gaussian_copula"

    if correlation_matrix is not None:
        if not parameter_order or len(parameter_order) != correlation_matrix.shape[0]:
            warnings.append("dependence_parameter_order_mismatch")
            correlation_matrix = None
            strategy = "descriptive_only"
        else:
            correlation_matrix = _stabilize_correlation_matrix(correlation_matrix)

    diagnostics = {
        "present": True,
        "regime": structure.regime,
        "class_label": structure.class_label,
        "recommended_covariance": structure.recommended_covariance,
        "calibrated": bool(structure.calibrated),
        "source_method": structure.source_method,
        "strategy": strategy,
        "parameter_order": list(parameter_order),
        "warnings": list(warnings),
        "blocking_reasons": list(structure.blocking_reasons),
    }
    if correlation_matrix is not None:
        diagnostics["matrix_shape"] = list(correlation_matrix.shape)
    return _ResolvedDependenceContext(
        ref=ref,
        structure=structure,
        correlation_matrix=correlation_matrix,
        parameter_order=tuple(parameter_order),
        strategy=strategy,
        warnings=tuple(warnings),
        diagnostics=diagnostics,
    )


def _resolve_pe_sensitivity(
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
) -> dict[str, dict[str, float]]:
    raw = welfare_params.get("pe_sensitivity")
    resolved: dict[str, dict[str, float]] = {}
    if not isinstance(raw, dict):
        return {label: {label: 1.0} for label in labels}

    for label in labels:
        per_label = raw.get(label)
        if not isinstance(per_label, dict):
            continue
        label_map: dict[str, float] = {}
        for param_name, coef in per_label.items():
            if not isinstance(param_name, str) or not param_name.strip():
                continue
            try:
                label_map[param_name] = float(coef)
            except (TypeError, ValueError):
                continue
        if label_map:
            resolved[label] = label_map
    return resolved or {label: {label: 1.0} for label in labels}


def _resolve_ge_multiplier_semantics(welfare_params: Mapping[str, Any]) -> str:
    explicit = welfare_params.get("ge_multiplier_semantics")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    if welfare_params.get("ge_technical_coefficients") is not None:
        return "leontief_inverse"
    if welfare_params.get("ge_model_ref") is not None:
        return "leontief_inverse"
    return "reduced_form_ge_multiplier"


def _validate_model_class(model_class: str, ge_multiplier_semantics: str) -> None:
    if model_class == "linearized_ge_io" and ge_multiplier_semantics not in {
        "leontief_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_ge_io requires leontief or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )
    if model_class == "linearized_cge" and ge_multiplier_semantics not in {
        "jacobian_inverse",
        "reduced_form_ge_multiplier",
    }:
        raise _fail_error(
            _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
            "linearized_cge requires jacobian or reduced-form GE semantics",
            details={"ge_multiplier_semantics": ge_multiplier_semantics},
        )


def _resolve_ge_context(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    size: int,
    ge_multiplier_semantics: str,
) -> _ResolvedGEContext:
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {}
    ge_entry_map = _coerce_entry_map(welfare_params.get("ge_entry_map"))
    _validate_entry_map(ge_entry_map, size=size)

    bundle_ref = _coerce_ge_uncertainty_ref(welfare_params.get("ge_uncertainty_ref"))
    ge_bundle: GEUncertaintyBundle | None = None
    if bundle_ref is not None:
        try:
            ge_bundle = load_ge_uncertainty_bundle(ctx.store, bundle_ref)
        except _WELFARE_LOAD_ERRORS as exc:
            raise _fail_error(
                _ERROR_GE_UNCERTAINTY_REF_KIND,
                "Unable to load welfare GE uncertainty bundle",
                details={"error": str(exc)},
            ) from exc
        diagnostics["loaded_ge_uncertainty_representation"] = ge_bundle.representation.value
        if tuple(ge_bundle.multiplier_shape) != (size, size):
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "GE uncertainty bundle dimensions do not match welfare response size",
                details={
                    "multiplier_shape": list(ge_bundle.multiplier_shape),
                    "response_size": size,
                },
            )
        if not ge_entry_map and isinstance(ge_bundle.metadata.get("entry_map"), dict):
            ge_entry_map = _coerce_entry_map(ge_bundle.metadata["entry_map"])

    raw_ge_model_ref = _coerce_artifact_ref(welfare_params.get("ge_model_ref"))
    point_multiplier: np.ndarray | None = None
    source_matrix: np.ndarray | None = None
    source_kind: Literal["none", "multiplier", "technical_coefficients"] = "none"
    ge_model_ref = raw_ge_model_ref

    lower_multiplier = _coerce_matrix(welfare_params.get("ge_lower_matrix"))
    upper_multiplier = _coerce_matrix(welfare_params.get("ge_upper_matrix"))
    if lower_multiplier is not None or upper_multiplier is not None:
        _validate_matrix_interval(
            lower_multiplier,
            upper_multiplier,
            expected_size=size,
            field_name="welfare_ge_matrix_interval",
        )

    direct_multiplier = _coerce_matrix(welfare_params.get("ge_matrix"))
    direct_coefficients = _coerce_matrix(welfare_params.get("ge_technical_coefficients"))
    lower_coefficients = _coerce_matrix(welfare_params.get("ge_lower_technical_coefficients"))
    upper_coefficients = _coerce_matrix(welfare_params.get("ge_upper_technical_coefficients"))
    if lower_coefficients is not None or upper_coefficients is not None:
        _validate_matrix_interval(
            lower_coefficients,
            upper_coefficients,
            expected_size=size,
            field_name="welfare_ge_technical_coefficients_interval",
        )

    if direct_multiplier is not None:
        point_multiplier = _validate_square_matrix(
            direct_multiplier,
            expected_size=size,
            field_name="welfare_ge_matrix",
        )
        source_matrix = point_multiplier
        source_kind = "multiplier"
        if ge_model_ref is None:
            ge_model_ref = _persist_json_payload(
                ctx,
                payload={"matrix": point_multiplier.tolist()},
                kind="ir.welfare_ge_multiplier_matrix",
                schema_name="ir.welfare_ge_multiplier_matrix",
            )
    elif direct_coefficients is not None:
        source_matrix = _validate_square_matrix(
            direct_coefficients,
            expected_size=size,
            field_name="welfare_ge_technical_coefficients",
        )
        point_multiplier, condition_number = _invert_linear_operator(
            source_matrix,
            semantics=ge_multiplier_semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
        )
        diagnostics["ge_condition_number"] = condition_number
        source_kind = "technical_coefficients"
        if ge_model_ref is None:
            ge_model_ref = _persist_json_payload(
                ctx,
                payload={"technical_coefficients": source_matrix.tolist()},
                kind="ir.welfare_ge_technical_coefficients",
                schema_name="ir.welfare_ge_technical_coefficients",
            )
    elif raw_ge_model_ref is not None:
        point_multiplier, source_matrix, source_kind = _load_ge_model_from_ref(
            ctx,
            raw_ge_model_ref,
            semantics=ge_multiplier_semantics,
            size=size,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
            diagnostics=diagnostics,
        )
    elif ge_bundle is not None and ge_bundle.point_multiplier_ref is not None:
        point_multiplier = _load_matrix_artifact(
            ctx,
            ge_bundle.point_multiplier_ref,
            expected_size=size,
            field_name="point_multiplier_ref",
        )
        source_matrix = point_multiplier
        source_kind = "multiplier"
        if ge_model_ref is None:
            ge_model_ref = ge_bundle.point_multiplier_ref

    if ge_bundle is not None and ge_bundle.lower_multiplier_ref is not None:
        lower_multiplier = _load_matrix_artifact(
            ctx,
            ge_bundle.lower_multiplier_ref,
            expected_size=size,
            field_name="lower_multiplier_ref",
        )
        upper_multiplier = _load_matrix_artifact(
            ctx,
            ge_bundle.upper_multiplier_ref,
            expected_size=size,
            field_name="upper_multiplier_ref",
        )
        _validate_matrix_interval(
            lower_multiplier,
            upper_multiplier,
            expected_size=size,
            field_name="ge_uncertainty_bundle.multiplier_interval",
        )

    if lower_coefficients is not None and upper_coefficients is not None:
        derived_lower, derived_upper, vertex_meta = _derive_multiplier_interval_from_coefficients(
            lower_coefficients,
            upper_coefficients,
            semantics=ge_multiplier_semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
            max_varying_entries=int(
                welfare_params.get("robust_max_vertex_enumeration", _DEFAULT_MAX_VERTEX_ENUMERATION)
            ),
        )
        diagnostics["coefficient_interval_vertex_enumeration"] = vertex_meta
        if derived_lower is not None and derived_upper is not None:
            lower_multiplier = derived_lower
            upper_multiplier = derived_upper
        else:
            warnings.append("ge_coefficient_interval_not_materialized_to_multiplier_bounds")

    if point_multiplier is None and lower_multiplier is not None and upper_multiplier is not None:
        point_multiplier = 0.5 * (lower_multiplier + upper_multiplier)
        source_matrix = point_multiplier
        source_kind = "multiplier"

    if source_matrix is None and lower_coefficients is not None and upper_coefficients is not None:
        source_matrix = 0.5 * (lower_coefficients + upper_coefficients)
        point_multiplier, condition_number = _invert_linear_operator(
            source_matrix,
            semantics=ge_multiplier_semantics,
            condition_threshold=float(
                welfare_params.get("ge_condition_number_threshold", _DEFAULT_CONDITION_THRESHOLD)
            ),
        )
        diagnostics["ge_condition_number"] = condition_number
        source_kind = "technical_coefficients"

    if source_matrix is None and point_multiplier is None:
        return _ResolvedGEContext(
            source_kind="none",
            point_multiplier=None,
            source_matrix=None,
            lower_multiplier=None,
            upper_multiplier=None,
            ge_model_ref=None,
            ge_uncertainty_ref=None,
            ge_entry_map={},
            diagnostics=diagnostics,
            warnings=tuple(warnings),
        )

    if (
        lower_multiplier is None
        and upper_multiplier is None
        and source_kind == "multiplier"
        and ge_entry_map
    ):
        lower_multiplier = np.array(point_multiplier, copy=True)
        upper_multiplier = np.array(point_multiplier, copy=True)

    if (
        source_kind == "multiplier"
        and lower_multiplier is not None
        and upper_multiplier is not None
    ):
        for param_name, (row_idx, col_idx) in ge_entry_map.items():
            lower_multiplier[row_idx, col_idx] = lower_multiplier[row_idx, col_idx]
            upper_multiplier[row_idx, col_idx] = upper_multiplier[row_idx, col_idx]

    created_bundle_ref = bundle_ref
    if created_bundle_ref is None and (
        lower_multiplier is not None or upper_multiplier is not None
    ):
        point_multiplier_ref = _persist_json_payload(
            ctx,
            payload={"matrix": point_multiplier.tolist()},
            kind="ir.welfare_multiplier_matrix",
            schema_name="ir.welfare_multiplier_matrix",
        )
        lower_ref = _persist_json_payload(
            ctx,
            payload={"matrix": lower_multiplier.tolist()},
            kind="ir.welfare_multiplier_matrix",
            schema_name="ir.welfare_multiplier_matrix",
        )
        upper_ref = _persist_json_payload(
            ctx,
            payload={"matrix": upper_multiplier.tolist()},
            kind="ir.welfare_multiplier_matrix",
            schema_name="ir.welfare_multiplier_matrix",
        )
        created_bundle_ref = persist_ge_uncertainty_bundle(
            ctx.store,
            GEUncertaintyBundle(
                model_class=str(welfare_params.get("model_class") or "linearized_ge_io"),
                representation=(
                    GEUncertaintyRepresentation.COEFFICIENT_INTERVALS
                    if lower_coefficients is not None or upper_coefficients is not None
                    else GEUncertaintyRepresentation.MULTIPLIER_INTERVALS
                ),
                multiplier_shape=(size, size),
                point_multiplier_ref=ArtifactRefModel.model_validate(
                    point_multiplier_ref.model_dump()
                ),
                lower_multiplier_ref=ArtifactRefModel.model_validate(lower_ref.model_dump()),
                upper_multiplier_ref=ArtifactRefModel.model_validate(upper_ref.model_dump()),
                diagnostics=diagnostics,
                metadata={"entry_map": {key: list(value) for key, value in ge_entry_map.items()}},
            ),
        )

    if source_kind == "multiplier" and point_multiplier is not None:
        diagnostics["ge_point_multiplier_condition_number"] = float(
            np.linalg.cond(point_multiplier)
        )

    return _ResolvedGEContext(
        source_kind=source_kind,
        point_multiplier=point_multiplier,
        source_matrix=source_matrix,
        lower_multiplier=lower_multiplier,
        upper_multiplier=upper_multiplier,
        ge_model_ref=ge_model_ref,
        ge_uncertainty_ref=created_bundle_ref,
        ge_entry_map=ge_entry_map,
        diagnostics=diagnostics,
        warnings=tuple(warnings),
    )


def _build_simulation_fn(
    ctx: ExecutionContext,
    *,
    context: _ResolvedWelfareContext,
    available_envelopes: _EnvelopeCollection,
) -> tuple[
    Any, dict[str, float], dict[str, UncertaintyEnvelope], dict[str, UncertaintyEnvelopeRef]
]:
    nominal_params: dict[str, float] = {}
    used_envelopes: dict[str, UncertaintyEnvelope] = {}
    pe_refs: dict[str, UncertaintyEnvelopeRef] = {}

    for label in context.labels:
        for param_name in context.pe_sensitivity.get(label, {}):
            if param_name in available_envelopes.envelopes:
                used_envelopes[param_name] = available_envelopes.envelopes[param_name]
                nominal_params[param_name] = float(
                    available_envelopes.envelopes[param_name].point_estimate
                )
                if param_name in available_envelopes.refs:
                    pe_refs[param_name] = available_envelopes.refs[param_name]

    for param_name in context.ge_context.ge_entry_map:
        env = available_envelopes.envelopes.get(param_name)
        if env is None:
            continue
        used_envelopes[param_name] = env
        nominal_params[param_name] = float(env.point_estimate)

    for param_name, ref in list(pe_refs.items()):
        if param_name not in used_envelopes:
            pe_refs.pop(param_name)

    for param_name, env in used_envelopes.items():
        if (
            param_name not in pe_refs
            and param_name in available_envelopes.refs
            and param_name
            in {item for mapping in context.pe_sensitivity.values() for item in mapping}
        ):
            pe_refs[param_name] = available_envelopes.refs[param_name]
        elif param_name not in available_envelopes.refs and param_name in {
            item for mapping in context.pe_sensitivity.values() for item in mapping
        }:
            pe_refs[param_name] = persist_uncertainty_envelope(ctx.store, env)

    base_response = np.asarray(context.base_response, dtype=np.float64)
    weights = np.asarray(context.weights, dtype=np.float64)
    point_multiplier = (
        None
        if context.ge_context.point_multiplier is None
        else np.asarray(context.ge_context.point_multiplier, dtype=np.float64)
    )
    source_matrix = (
        None
        if context.ge_context.source_matrix is None
        else np.asarray(context.ge_context.source_matrix, dtype=np.float64)
    )
    sensitivity = context.pe_sensitivity
    ge_entry_map = context.ge_context.ge_entry_map

    def _fn(**params: Any) -> dict[str, Any]:
        response = np.array(base_response, copy=True)
        for idx, label in enumerate(context.labels):
            per_label = sensitivity.get(label, {})
            if not per_label:
                continue
            delta = 0.0
            for param_name, coef in per_label.items():
                env = used_envelopes.get(param_name)
                if env is None:
                    continue
                baseline = float(env.point_estimate)
                current = float(params.get(param_name, float(env.point_estimate)))
                denom = max(abs(float(env.point_estimate)), 1.0)
                delta += float(coef) * ((current - baseline) / denom)
            response[idx] = float(base_response[idx]) * (1.0 + delta)

        if (
            point_multiplier is None
            or source_matrix is None
            or context.ge_context.source_kind == "none"
        ):
            total = response
        elif context.ge_context.source_kind == "multiplier":
            current_multiplier = np.array(point_multiplier, copy=True)
            for param_name, (row_idx, col_idx) in ge_entry_map.items():
                env = used_envelopes.get(param_name)
                if env is None:
                    continue
                current_value = float(params.get(param_name, float(env.point_estimate)))
                current_multiplier[row_idx, col_idx] = current_value
            total = current_multiplier @ response
        else:
            current_coefficients = np.array(source_matrix, copy=True)
            for param_name, (row_idx, col_idx) in ge_entry_map.items():
                env = used_envelopes.get(param_name)
                if env is None:
                    continue
                current_value = float(params.get(param_name, float(env.point_estimate)))
                current_coefficients[row_idx, col_idx] = current_value
            identity = np.eye(current_coefficients.shape[0], dtype=np.float64)
            multiplier = np.linalg.inv(identity - current_coefficients)
            total = multiplier @ response

        welfare_pe = float(weights @ response)
        welfare_total = float(weights @ total)
        return {
            "welfare": welfare_total,
            "welfare_pe": welfare_pe,
            "welfare_ge": welfare_total - welfare_pe,
        }

    return _fn, nominal_params, used_envelopes, pe_refs


def _propagate_credible_interval(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    welfare_params: Mapping[str, Any],
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> _PropagationOutcome:
    config = _load_propagation_config(state)
    config_ref = _persist_json_payload(
        ctx,
        payload=config.model_dump(mode="json"),
        kind="foundry.welfare_method_config",
        schema_name="polisyos.foundry.WelfareMethodConfig",
    )
    requested_method = _resolve_requested_welfare_method(config, welfare_params)
    if not input_envelopes:
        report_ref = _persist_json_payload(
            ctx,
            payload={
                "schema_version": "1.0",
                "input_envelope_count": 0,
                "methods": [WelfareMethod.DETERMINISTIC.value],
                "requested_method": requested_method,
            },
            kind="foundry.welfare_propagation_report",
            schema_name="polisyos.foundry.WelfarePropagationReport",
        )
        return _PropagationOutcome(
            credible_interval=None,
            method_used=WelfareMethod.DETERMINISTIC,
            result_map={},
            method_config_ref=config_ref,
            report_ref=report_ref,
            sample_bundle_ref=None,
            diagnostics={"dependence_applied": False, "requested_method": requested_method},
        )

    if requested_method in {"interval_outer", "robust_set", "none", "deterministic"}:
        report_ref = _persist_json_payload(
            ctx,
            payload={
                "schema_version": "1.0",
                "input_envelope_count": len(input_envelopes),
                "methods": [WelfareMethod.INTERVAL_OUTER.value],
                "requested_method": requested_method,
                "reason": "credible_interval_skipped_by_requested_method",
            },
            kind="foundry.welfare_propagation_report",
            schema_name="polisyos.foundry.WelfarePropagationReport",
        )
        return _PropagationOutcome(
            credible_interval=None,
            method_used=WelfareMethod.INTERVAL_OUTER,
            result_map={},
            method_config_ref=config_ref,
            report_ref=report_ref,
            sample_bundle_ref=None,
            diagnostics={"dependence_applied": False, "requested_method": requested_method},
        )

    if requested_method in {"delta", "delta_method"}:
        return _propagate_delta_interval(
            ctx,
            config=config,
            config_ref=config_ref,
            context=context,
            simulation_fn=simulation_fn,
            nominal_params=nominal_params,
            input_envelopes=input_envelopes,
            requested_method=requested_method,
        )

    rng = np.random.default_rng(config.mc_seed)
    draws_welfare: list[float] = []
    draws_pe: list[float] = []
    draws_ge: list[float] = []
    param_names = sorted(input_envelopes)
    dependence_sampler = _build_dependence_sampler(
        context.dependence_context,
        param_names=param_names,
    )
    for _ in range(int(config.mc_n_samples)):
        draw_params = _sample_param_draw(
            rng,
            param_names=param_names,
            input_envelopes=input_envelopes,
            dependence_sampler=dependence_sampler,
        )
        outputs = simulation_fn(**draw_params)
        welfare = float(outputs.get("welfare", float("nan")))
        welfare_pe = float(outputs.get("welfare_pe", float("nan")))
        welfare_ge = float(outputs.get("welfare_ge", float("nan")))
        if not (math.isfinite(welfare) and math.isfinite(welfare_pe) and math.isfinite(welfare_ge)):
            continue
        draws_welfare.append(welfare)
        draws_pe.append(welfare_pe)
        draws_ge.append(welfare_ge)
    if len(draws_welfare) < int(config.mc_min_valid_samples):
        raise _fail_error(
            _ERROR_MONTE_CARLO_NOT_CONVERGED,
            "Welfare Monte Carlo propagation did not reach the minimum valid sample budget",
            details={
                "valid_samples": len(draws_welfare),
                "required": int(config.mc_min_valid_samples),
            },
        )
    alpha = max((1.0 - float(config.confidence_level)) / 2.0, 0.0)
    welfare_array = np.asarray(draws_welfare, dtype=np.float64)
    result_map = {
        "welfare": {
            "point_estimate": float(np.mean(welfare_array)),
            "draw_count": int(welfare_array.shape[0]),
        }
    }
    sample_bundle_ref = persist_welfare_sample_bundle(
        ctx.store,
        WelfareSampleBundle(
            welfare_draws=tuple(float(value) for value in draws_welfare),
            welfare_pe_draws=tuple(float(value) for value in draws_pe),
            welfare_ge_draws=tuple(float(value) for value in draws_ge),
            metadata={
                "requested_method": requested_method,
                "dependence_strategy": dependence_sampler["strategy"],
                "covered_params": dependence_sampler["covered_params"],
            },
        ),
    )
    report_ref = _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "input_envelope_count": len(input_envelopes),
            "methods": ["monte_carlo"],
            "requested_method": requested_method,
            "valid_draw_count": int(welfare_array.shape[0]),
            "draw_summary": {
                "welfare_mean": float(np.mean(welfare_array)),
                "welfare_std": float(np.std(welfare_array)),
                "welfare_pe_mean": float(np.mean(np.asarray(draws_pe, dtype=np.float64))),
                "welfare_ge_mean": float(np.mean(np.asarray(draws_ge, dtype=np.float64))),
            },
            "dependence_sampling": dependence_sampler,
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
    )
    return _PropagationOutcome(
        credible_interval=(
            float(np.quantile(welfare_array, alpha)),
            float(np.quantile(welfare_array, 1.0 - alpha)),
        ),
        method_used=WelfareMethod.MONTE_CARLO,
        result_map=result_map,
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=sample_bundle_ref,
        diagnostics={
            "dependence_applied": bool(dependence_sampler["applied"]),
            "dependence_sampling": dependence_sampler,
            "requested_method": requested_method,
        },
    )


def _resolve_requested_welfare_method(
    config: PropagationConfig,
    welfare_params: Mapping[str, Any],
) -> str:
    requested = welfare_params.get("credible_method")
    if not isinstance(requested, str) or not requested.strip():
        requested = welfare_params.get("method")
    if not isinstance(requested, str) or not requested.strip():
        requested = config.preferred_method
    text = str(requested or "auto").strip().lower()
    aliases = {
        "mc": "monte_carlo",
        "delta_method": "delta",
        "robust": "robust_set",
        "interval": "interval_outer",
    }
    return aliases.get(text, text)


def _propagate_delta_interval(
    ctx: ExecutionContext,
    *,
    config: PropagationConfig,
    config_ref: ArtifactRefModel,
    context: _ResolvedWelfareContext,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    requested_method: str,
) -> _PropagationOutcome:
    param_names = sorted(input_envelopes)
    gradient, base_value = _finite_difference_gradient(
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
    )
    covariance, dependence_applied, dependence_note = _build_parameter_covariance(
        context.dependence_context,
        param_names=param_names,
        input_envelopes=input_envelopes,
    )
    gradient_vector = np.asarray([gradient[name] for name in param_names], dtype=np.float64)
    variance = float(gradient_vector @ covariance @ gradient_vector) if param_names else 0.0
    variance = max(variance, 0.0)
    std = math.sqrt(variance)
    z_value = NormalDist().inv_cdf((1.0 + float(config.confidence_level)) / 2.0)
    credible_interval = (
        float(base_value - z_value * std),
        float(base_value + z_value * std),
    )
    report_ref = _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "input_envelope_count": len(input_envelopes),
            "methods": [WelfareMethod.DELTA.value],
            "requested_method": requested_method,
            "gradient": gradient,
            "covariance": covariance.tolist(),
            "delta_std": float(std),
            "dependence_sampling": dependence_note,
        },
        kind="foundry.welfare_propagation_report",
        schema_name="polisyos.foundry.WelfarePropagationReport",
    )
    return _PropagationOutcome(
        credible_interval=credible_interval,
        method_used=WelfareMethod.DELTA,
        result_map={
            "welfare": {
                "point_estimate": float(base_value),
                "gradient": gradient,
                "delta_std": float(std),
            }
        },
        method_config_ref=config_ref,
        report_ref=report_ref,
        sample_bundle_ref=None,
        diagnostics={
            "dependence_applied": dependence_applied,
            "dependence_sampling": dependence_note,
            "requested_method": requested_method,
            "delta_gradient": gradient,
            "delta_std": float(std),
        },
    )


def _build_dependence_sampler(
    dependence_context: _ResolvedDependenceContext,
    *,
    param_names: list[str],
) -> dict[str, Any]:
    if dependence_context.correlation_matrix is None or len(param_names) < 2:
        return {
            "applied": False,
            "strategy": dependence_context.strategy,
            "covered_params": [],
            "uncovered_params": list(param_names),
            "reason": "no_dependence_matrix",
        }
    order_index = {name: idx for idx, name in enumerate(dependence_context.parameter_order)}
    covered = [name for name in param_names if name in order_index]
    if len(covered) < 2:
        return {
            "applied": False,
            "strategy": dependence_context.strategy,
            "covered_params": covered,
            "uncovered_params": [name for name in param_names if name not in covered],
            "reason": "insufficient_parameter_overlap",
        }
    indices = [order_index[name] for name in covered]
    correlation = dependence_context.correlation_matrix[np.ix_(indices, indices)]
    correlation = _stabilize_correlation_matrix(correlation)
    return {
        "applied": True,
        "strategy": dependence_context.strategy,
        "covered_params": covered,
        "uncovered_params": [name for name in param_names if name not in covered],
        "correlation_matrix": correlation.tolist(),
    }


def _sample_param_draw(
    rng: np.random.Generator,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_sampler: Mapping[str, Any],
) -> dict[str, float]:
    draw_params: dict[str, float] = {}
    if bool(dependence_sampler.get("applied")):
        covered = [str(name) for name in dependence_sampler.get("covered_params", ())]
        correlation = np.asarray(dependence_sampler.get("correlation_matrix"), dtype=np.float64)
        latent = rng.multivariate_normal(
            mean=np.zeros(len(covered), dtype=np.float64),
            cov=correlation,
        )
        for name, latent_value in zip(covered, latent, strict=False):
            u = float(NormalDist().cdf(float(latent_value)))
            draw_params[name] = _quantile_from_envelope(u, input_envelopes[name])
    for name in param_names:
        if name in draw_params:
            continue
        draw_params[name] = _sample_from_envelope(rng, input_envelopes[name])
    return draw_params


def _quantile_from_envelope(u: float, env: UncertaintyEnvelope) -> float:
    bounded_u = min(max(float(u), 1e-9), 1.0 - 1e-9)
    point = float(env.point_estimate)
    lower = float(env.confidence_interval[0])
    upper = float(env.confidence_interval[1])
    if env.distribution_family == DistributionFamily.NORMAL:
        std = max(_extract_std(env), 1e-12)
        z_value = NormalDist().inv_cdf(bounded_u)
        return float(point + std * z_value)
    if env.distribution_family == DistributionFamily.UNIFORM:
        return float(lower + bounded_u * (upper - lower))
    mode = min(max(point, lower), upper)
    if upper <= lower:
        return point
    c = (mode - lower) / (upper - lower) if upper > lower else 0.5
    if bounded_u <= c and c > 0.0:
        return float(lower + math.sqrt(bounded_u * (upper - lower) * (mode - lower)))
    if c >= 1.0:
        return float(mode)
    return float(upper - math.sqrt((1.0 - bounded_u) * (upper - lower) * (upper - mode)))


def _build_parameter_covariance(
    dependence_context: _ResolvedDependenceContext,
    *,
    param_names: list[str],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[np.ndarray, bool, dict[str, Any]]:
    stds = np.asarray(
        [max(_extract_std(input_envelopes[name]), 1e-12) for name in param_names], dtype=np.float64
    )
    covariance = np.diag(stds**2)
    note: dict[str, Any] = {
        "strategy": "independent",
        "covered_params": [],
        "uncovered_params": list(param_names),
    }
    if dependence_context.correlation_matrix is None or len(param_names) < 2:
        return covariance, False, note

    order_index = {name: idx for idx, name in enumerate(dependence_context.parameter_order)}
    covered = [name for name in param_names if name in order_index]
    if len(covered) < 2:
        note["strategy"] = dependence_context.strategy
        note["covered_params"] = covered
        return covariance, False, note

    indices = [order_index[name] for name in covered]
    corr_sub = dependence_context.correlation_matrix[np.ix_(indices, indices)]
    corr_sub = _stabilize_correlation_matrix(corr_sub)
    local_indices = [param_names.index(name) for name in covered]
    for row_local, row_param in enumerate(local_indices):
        for col_local, col_param in enumerate(local_indices):
            covariance[row_param, col_param] = (
                corr_sub[row_local, col_local] * stds[row_param] * stds[col_param]
            )
    note = {
        "strategy": dependence_context.strategy,
        "covered_params": covered,
        "uncovered_params": [name for name in param_names if name not in covered],
        "correlation_matrix": corr_sub.tolist(),
    }
    return covariance, True, note


def _finite_difference_gradient(
    *,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[dict[str, float], float]:
    base_output = simulation_fn(**nominal_params)
    base_value = float(base_output["welfare"])
    gradient: dict[str, float] = {}
    for name, env in input_envelopes.items():
        step = _finite_difference_step(env)
        current = float(nominal_params.get(name, env.point_estimate))
        lower = float(env.confidence_interval[0])
        upper = float(env.confidence_interval[1])
        step_up = min(step, max(upper - current, 0.0))
        step_down = min(step, max(current - lower, 0.0))
        if step_up > 0.0 and step_down > 0.0:
            upper_params = dict(nominal_params)
            lower_params = dict(nominal_params)
            upper_params[name] = current + step_up
            lower_params[name] = current - step_down
            upper_value = float(simulation_fn(**upper_params)["welfare"])
            lower_value = float(simulation_fn(**lower_params)["welfare"])
            gradient[name] = float((upper_value - lower_value) / (step_up + step_down))
        elif step_up > 0.0:
            upper_params = dict(nominal_params)
            upper_params[name] = current + step_up
            upper_value = float(simulation_fn(**upper_params)["welfare"])
            gradient[name] = float((upper_value - base_value) / step_up)
        elif step_down > 0.0:
            lower_params = dict(nominal_params)
            lower_params[name] = current - step_down
            lower_value = float(simulation_fn(**lower_params)["welfare"])
            gradient[name] = float((base_value - lower_value) / step_down)
        else:
            gradient[name] = 0.0
    return gradient, base_value


def _finite_difference_step(env: UncertaintyEnvelope) -> float:
    point = abs(float(env.point_estimate))
    width = max(
        float(env.confidence_interval[1]) - float(env.confidence_interval[0]),
        0.0,
    )
    std = _extract_std(env)
    return max(std * 0.5, width / 20.0, max(point, 1.0) * 1e-4, 1e-6)


def _load_propagation_config(state: ExperimentState) -> PropagationConfig:
    raw = state.params.get("propagation_config")
    if isinstance(raw, dict):
        try:
            return PropagationConfig.model_validate(raw)
        except _WELFARE_VALIDATION_ERRORS:
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


def _build_robust_interval(
    *,
    context: _ResolvedWelfareContext,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
) -> tuple[tuple[float, float], dict[str, Any]]:
    response_lower = np.array(context.base_response, copy=True)
    response_upper = np.array(context.base_response, copy=True)
    for idx, label in enumerate(context.labels):
        per_label = context.pe_sensitivity.get(label, {})
        if not per_label:
            continue
        delta_lower = 0.0
        delta_upper = 0.0
        for param_name, coef in per_label.items():
            env = input_envelopes.get(param_name)
            if env is None:
                continue
            denom = max(abs(float(env.point_estimate)), 1.0)
            lo = (float(env.confidence_interval[0]) - float(env.point_estimate)) / denom
            hi = (float(env.confidence_interval[1]) - float(env.point_estimate)) / denom
            contrib = _mul_interval(float(coef), float(coef), lo, hi)
            delta_lower += contrib[0]
            delta_upper += contrib[1]
        scaled = _mul_interval(
            float(context.base_response[idx]),
            float(context.base_response[idx]),
            1.0 + delta_lower,
            1.0 + delta_upper,
        )
        response_lower[idx], response_upper[idx] = scaled

    if context.ge_context.point_multiplier is None:
        matrix_lower = np.eye(len(context.labels), dtype=np.float64)
        matrix_upper = np.eye(len(context.labels), dtype=np.float64)
    else:
        matrix_lower = (
            np.array(context.ge_context.lower_multiplier, copy=True)
            if context.ge_context.lower_multiplier is not None
            else np.array(context.ge_context.point_multiplier, copy=True)
        )
        matrix_upper = (
            np.array(context.ge_context.upper_multiplier, copy=True)
            if context.ge_context.upper_multiplier is not None
            else np.array(context.ge_context.point_multiplier, copy=True)
        )
        if context.ge_context.source_kind == "multiplier":
            for param_name, (row_idx, col_idx) in context.ge_context.ge_entry_map.items():
                env = input_envelopes.get(param_name)
                if env is None:
                    continue
                matrix_lower[row_idx, col_idx] = float(env.confidence_interval[0])
                matrix_upper[row_idx, col_idx] = float(env.confidence_interval[1])

    total_lower, total_upper = _matvec_interval(
        matrix_lower,
        matrix_upper,
        response_lower,
        response_upper,
    )
    robust_interval = _dot_interval(context.weights, total_lower, total_upper)
    return robust_interval, {
        "response_interval": [response_lower.tolist(), response_upper.tolist()],
        "matrix_bounded": bool(
            context.ge_context.lower_multiplier is not None
            or context.ge_context.upper_multiplier is not None
        ),
    }


def _resolve_bundle_status(
    *,
    context: _ResolvedWelfareContext,
    used_input_envelopes: Mapping[str, UncertaintyEnvelope],
    dependence_applied: bool,
) -> tuple[list[str], WelfareStatus]:
    warnings = list(context.warnings)
    status = WelfareStatus.OK

    if context.ge_context.point_multiplier is None:
        warnings.append("ge_operator_missing_pe_only")
        status = WelfareStatus.PARTIAL
    elif context.ge_context.ge_uncertainty_ref is None:
        warnings.append("ge_multiplier_treated_as_fixed")
        status = WelfareStatus.DEGRADED

    if len(used_input_envelopes) > 1 and context.dependence_structure_ref is None:
        warnings.append("dependence_assumed_independent")
        if status is WelfareStatus.OK:
            status = WelfareStatus.DEGRADED
    elif (
        len(used_input_envelopes) > 1
        and context.dependence_structure_ref is not None
        and not dependence_applied
    ):
        warnings.append("dependence_structure_present_but_not_applied")
        if status is WelfareStatus.OK:
            status = WelfareStatus.DEGRADED

    return warnings, status


def _resolve_bundle_method(
    propagated_method: WelfareMethod,
    *,
    credible_interval: tuple[float, float] | None,
    robust_interval: tuple[float, float] | None,
) -> WelfareMethod:
    if credible_interval is not None and robust_interval is not None:
        return (
            WelfareMethod.MIXED_NESTED
            if propagated_method is not WelfareMethod.DETERMINISTIC
            else WelfareMethod.INTERVAL_OUTER
        )
    if credible_interval is not None:
        return propagated_method
    if robust_interval is not None:
        return WelfareMethod.INTERVAL_OUTER
    return WelfareMethod.DETERMINISTIC


def _resolve_interval_semantics(
    *,
    credible_interval: tuple[float, float] | None,
    robust_interval: tuple[float, float] | None,
) -> WelfareIntervalSemantics:
    if credible_interval is not None and robust_interval is not None:
        return WelfareIntervalSemantics.MIXED_NESTED
    if credible_interval is not None:
        return WelfareIntervalSemantics.CREDIBLE
    if robust_interval is not None:
        return WelfareIntervalSemantics.ROBUST_OUTER
    return WelfareIntervalSemantics.NONE


def _resolve_subgroup_welfare(
    *,
    welfare_params: Mapping[str, Any],
    labels: tuple[str, ...],
    total_vector: np.ndarray,
) -> dict[str, float]:
    raw = welfare_params.get("subgroup_weights")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for name, weights_value in raw.items():
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(weights_value, dict):
            if any(label not in weights_value for label in labels):
                continue
            weights = np.asarray(
                [float(weights_value[label]) for label in labels], dtype=np.float64
            )
        elif isinstance(weights_value, (list, tuple)) and len(weights_value) == len(labels):
            weights = np.asarray([float(value) for value in weights_value], dtype=np.float64)
        else:
            continue
        out[name] = float(weights @ total_vector)
    return out


def _point_total_vector(
    context: _ResolvedWelfareContext,
    *,
    nominal_params: Mapping[str, float],
) -> np.ndarray:
    response = np.array(context.base_response, copy=True)
    for idx, label in enumerate(context.labels):
        per_label = context.pe_sensitivity.get(label, {})
        if not per_label:
            continue
        delta = 0.0
        for param_name, coef in per_label.items():
            if param_name not in nominal_params:
                continue
            baseline = float(nominal_params[param_name])
            denom = max(abs(baseline), 1.0)
            delta += float(coef) * ((float(nominal_params[param_name]) - baseline) / denom)
        response[idx] = float(context.base_response[idx]) * (1.0 + delta)
    if context.ge_context.point_multiplier is None:
        return response
    return np.asarray(context.ge_context.point_multiplier @ response, dtype=np.float64)


def _persist_sensitivity_diagnostics(
    ctx: ExecutionContext,
    *,
    simulation_fn: Any,
    nominal_params: Mapping[str, float],
    input_envelopes: Mapping[str, UncertaintyEnvelope],
    robust_interval: tuple[float, float],
) -> ArtifactRefModel | None:
    if not input_envelopes:
        return None
    gradient, _ = _finite_difference_gradient(
        simulation_fn=simulation_fn,
        nominal_params=nominal_params,
        input_envelopes=input_envelopes,
    )
    rows: list[dict[str, Any]] = []
    for name, env in input_envelopes.items():
        half_width = max(
            (float(env.confidence_interval[1]) - float(env.confidence_interval[0])) / 2.0,
            0.0,
        )
        std = max(_extract_std(env), 0.0)
        grad = float(gradient.get(name, 0.0))
        rows.append(
            {
                "parameter": name,
                "local_gradient": grad,
                "credible_scale": abs(grad) * std,
                "robust_scale": abs(grad) * half_width,
                "interval_half_width": half_width,
                "distribution_family": env.distribution_family.value,
            }
        )
    rows.sort(key=lambda item: (item["robust_scale"], item["credible_scale"]), reverse=True)
    return _persist_json_payload(
        ctx,
        payload={
            "schema_version": "1.0",
            "sensitivity_rows": rows,
            "robust_interval": [float(robust_interval[0]), float(robust_interval[1])],
        },
        kind="foundry.welfare_sensitivity_diagnostics",
        schema_name="polisyos.foundry.WelfareSensitivityDiagnostics",
    )


def _bundle_inputs(
    *,
    sim_result_ref: ArtifactRef,
    metric_ref: ArtifactRef,
    pe_uncertainty_refs: Mapping[str, UncertaintyEnvelopeRef],
    ge_uncertainty_ref: GEUncertaintyBundleRef | None,
    dependence_structure_ref: DependenceStructureRef | None,
    channel_decomposition_ref: ArtifactRefModel | None,
    method_config_ref: ArtifactRefModel | None,
    report_ref: ArtifactRefModel | None,
    sample_bundle_ref: WelfareSampleBundleRef | None,
    sensitivity_diagnostics_ref: ArtifactRefModel | None,
) -> list[InputRef]:
    inputs = [
        InputRef(artifact_id=str(sim_result_ref.artifact_id), role="simulation_result"),
        InputRef(artifact_id=str(metric_ref.artifact_id), role="metrics"),
    ]
    for name, ref in pe_uncertainty_refs.items():
        inputs.append(InputRef(artifact_id=str(ref.artifact_id), role=f"pe_uncertainty.{name}"))
    if ge_uncertainty_ref is not None:
        inputs.append(
            InputRef(artifact_id=str(ge_uncertainty_ref.artifact_id), role="ge_uncertainty")
        )
    if dependence_structure_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=str(dependence_structure_ref.artifact_id),
                role="dependence_structure",
            )
        )
    if channel_decomposition_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=str(channel_decomposition_ref.artifact_id),
                role="channel_decomposition",
            )
        )
    if method_config_ref is not None:
        inputs.append(
            InputRef(artifact_id=str(method_config_ref.artifact_id), role="method_config")
        )
    if report_ref is not None:
        inputs.append(InputRef(artifact_id=str(report_ref.artifact_id), role="propagation_report"))
    if sample_bundle_ref is not None:
        inputs.append(
            InputRef(artifact_id=str(sample_bundle_ref.artifact_id), role="sample_bundle")
        )
    if sensitivity_diagnostics_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=str(sensitivity_diagnostics_ref.artifact_id),
                role="sensitivity_diagnostics",
            )
        )
    return inputs


def _maybe_build_channel_decomposition_ref(
    ctx: ExecutionContext,
    *,
    welfare_params: Mapping[str, Any],
    total_vector: np.ndarray,
) -> ArtifactRefModel | None:
    config = _resolve_channel_decomposition_config(welfare_params)
    if config is None:
        return None

    baseline_microdata_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="baseline_microdata",
        ref_key="baseline_microdata_ref",
        kind="ir.baseline_microdata",
        schema_name="ir.baseline_microdata",
    )
    policy_basis_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="policy_basis",
        ref_key="policy_basis_ref",
        kind="ir.policy_basis",
        schema_name="ir.policy_basis",
    )
    mechanical_inputs_ref = _resolve_channel_artifact_ref(
        ctx,
        config,
        payload_key="mechanical_inputs",
        ref_key="mechanical_inputs_ref",
        kind="ir.mechanical_inputs",
        schema_name="ir.mechanical_inputs",
    )
    if baseline_microdata_ref is None or policy_basis_ref is None or mechanical_inputs_ref is None:
        missing: list[str] = []
        if baseline_microdata_ref is None:
            missing.append("baseline_microdata_ref")
        if policy_basis_ref is None:
            missing.append("policy_basis_ref")
        if mechanical_inputs_ref is None:
            missing.append("mechanical_inputs_ref")
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            "welfare channel decomposition requires baseline, policy basis, and mechanical inputs",
            details={"missing_fields": missing},
        )

    explicit_total_vector = _coerce_numeric_sequence(
        config.get("total_vector"),
        field_name="welfare_channel_decomposition.total_vector",
    )
    try:
        return build_channel_decomposition_ref(
            ctx.store,
            target_kind=str(
                config.get(
                    "target_kind",
                    ChannelDecompositionTargetKind.SOCIAL_WELFARE.value,
                )
            ),
            baseline_microdata_ref=baseline_microdata_ref,
            policy_basis_ref=policy_basis_ref,
            mechanical_inputs_ref=mechanical_inputs_ref,
            behavior_model_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="behavior_model",
                ref_key="behavior_model_ref",
                kind="ir.behavior_model",
                schema_name="ir.behavior_model",
            ),
            fiscal_state_model_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="fiscal_state_model",
                ref_key="fiscal_state_model_ref",
                kind="ir.fiscal_state_model",
                schema_name="ir.fiscal_state_model",
            ),
            instrument_set_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="instrument_set",
                ref_key="instrument_set_ref",
                kind="ir.instrument_set",
                schema_name="ir.instrument_set",
            ),
            proof_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="proof",
                ref_key="proof_ref",
                kind="ir.channel_decomposition_proof",
                schema_name="ir.channel_decomposition_proof",
            ),
            uncertainty_ref=_resolve_channel_artifact_ref(
                ctx,
                config,
                payload_key="uncertainty",
                ref_key="uncertainty_ref",
                kind="ir.channel_decomposition_uncertainty",
                schema_name="ir.channel_decomposition_uncertainty",
            ),
            total_vector=explicit_total_vector or total_vector.tolist(),
            block_on_failure=_coerce_bool(config.get("block_on_failure", True)),
        )
    except (TypeError, ValueError, ValidationError) as exc:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_BUILD_FAILED,
            "Unable to build welfare channel decomposition artifact",
            details={"error": str(exc)},
        ) from exc


def _resolve_channel_decomposition_config(
    welfare_params: Mapping[str, Any],
) -> dict[str, Any] | None:
    raw = welfare_params.get("channel_decomposition")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            "welfare_channel_decomposition must be a JSON object",
        )
    return dict(raw)


def _resolve_channel_artifact_ref(
    ctx: ExecutionContext,
    config: Mapping[str, Any],
    *,
    payload_key: str,
    ref_key: str,
    kind: str,
    schema_name: str,
) -> ArtifactRefModel | None:
    if payload_key in config and ref_key in config:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"Specify only one of {payload_key} or {ref_key}",
        )
    raw_value = config.get(ref_key, config.get(payload_key))
    if raw_value is None:
        return None
    if isinstance(raw_value, ArtifactRefModel):
        return raw_value
    if isinstance(raw_value, Mapping):
        if {"artifact_id", "kind", "media_type"} <= set(raw_value):
            try:
                return ArtifactRefModel.model_validate(raw_value)
            except ValidationError as exc:
                raise _fail_error(
                    _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
                    f"Invalid artifact ref for {ref_key}",
                    details={"error": str(exc)},
                ) from exc
        return _persist_json_payload(
            ctx,
            payload=raw_value,
            kind=kind,
            schema_name=schema_name,
        )
    raise _fail_error(
        _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
        f"{ref_key} must be an artifact ref or JSON object",
        details={"received_type": type(raw_value).__name__},
    )


def _coerce_artifact_ref(value: Any) -> ArtifactRefModel | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRefModel):
        return value
    if isinstance(value, dict):
        return ArtifactRefModel.model_validate(value)
    return None


def _coerce_ge_uncertainty_ref(value: Any) -> GEUncertaintyBundleRef | None:
    if value is None:
        return None
    try:
        return GEUncertaintyBundleRef.model_validate(value)
    except _WELFARE_VALIDATION_ERRORS as exc:
        raise _fail_error(
            _ERROR_GE_UNCERTAINTY_REF_KIND,
            "Invalid welfare ge_uncertainty_ref",
            details={"error": str(exc)},
        ) from exc


def _coerce_str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        return None
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            continue
        out.append(item)
    return out or None


def _coerce_numeric_sequence(value: Any, *, field_name: str) -> list[float] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must be a list of finite numbers",
        )
    try:
        numeric = [float(item) for item in value]
    except (TypeError, ValueError) as exc:
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must be a list of finite numbers",
            details={"error": str(exc)},
        ) from exc
    if not all(math.isfinite(item) for item in numeric):
        raise _fail_error(
            _ERROR_CHANNEL_DECOMPOSITION_CONFIG_INVALID,
            f"{field_name} must contain only finite numbers",
        )
    return numeric


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "ok", "pass"}:
            return True
        if normalized in {"false", "0", "no", "n", "fail"}:
            return False
    return bool(value)


def _coerce_matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2:
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            "Expected a 2D matrix payload",
        )
    return matrix


def _coerce_dependence_matrix(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Dependence structure matrix must be square",
        )
    if not np.all(np.isfinite(matrix)):
        raise _fail_error(
            _ERROR_DEPENDENCE_SPEC_INVALID,
            "Dependence structure matrix must be finite",
        )
    return matrix


def _correlation_from_covariance(covariance: np.ndarray) -> np.ndarray:
    scale = np.sqrt(np.clip(np.diag(covariance), a_min=1e-12, a_max=None))
    correlation = covariance / np.outer(scale, scale)
    return _stabilize_correlation_matrix(correlation)


def _stabilize_correlation_matrix(matrix: np.ndarray) -> np.ndarray:
    symmetric = 0.5 * (matrix + matrix.T)
    np.fill_diagonal(symmetric, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, a_min=1e-8, a_max=None)
    repaired = (eigenvectors * clipped) @ eigenvectors.T
    scale = np.sqrt(np.clip(np.diag(repaired), a_min=1e-12, a_max=None))
    correlation = repaired / np.outer(scale, scale)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    return correlation


def _coerce_entry_map(value: Any) -> dict[str, tuple[int, int]]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, tuple[int, int]] = {}
    for param_name, coords in value.items():
        if not isinstance(param_name, str) or not param_name.strip():
            continue
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            continue
        try:
            row_idx = int(coords[0])
            col_idx = int(coords[1])
        except (TypeError, ValueError):
            continue
        out[param_name] = (row_idx, col_idx)
    return out


def _validate_entry_map(entry_map: Mapping[str, tuple[int, int]], *, size: int) -> None:
    for param_name, (row_idx, col_idx) in entry_map.items():
        if row_idx < 0 or row_idx >= size or col_idx < 0 or col_idx >= size:
            raise _fail_error(
                _ERROR_WELFARE_DIMENSION_MISMATCH,
                "welfare_ge_entry_map coordinates must lie within the GE matrix",
                details={"param_name": param_name, "row": row_idx, "col": col_idx, "size": size},
            )


def _validate_square_matrix(
    matrix: np.ndarray,
    *,
    expected_size: int,
    field_name: str,
) -> np.ndarray:
    if matrix.shape != (expected_size, expected_size):
        raise _fail_error(
            _ERROR_WELFARE_DIMENSION_MISMATCH,
            f"{field_name} must be square and align with welfare response size",
            details={"shape": list(matrix.shape), "expected_size": expected_size},
        )
    return matrix


def _validate_matrix_interval(
    lower: np.ndarray | None,
    upper: np.ndarray | None,
    *,
    expected_size: int,
    field_name: str,
) -> None:
    if lower is None or upper is None:
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            f"{field_name} requires both lower and upper matrices",
        )
    _validate_square_matrix(lower, expected_size=expected_size, field_name=f"{field_name}.lower")
    _validate_square_matrix(upper, expected_size=expected_size, field_name=f"{field_name}.upper")
    if np.any(lower > upper):
        raise _fail_error(
            _ERROR_INTERVAL_SEMANTICS_INVALID,
            f"{field_name} must satisfy elementwise lower <= upper",
        )


def _invert_linear_operator(
    matrix: np.ndarray,
    *,
    semantics: str,
    condition_threshold: float,
) -> tuple[np.ndarray, float]:
    if semantics == "leontief_inverse":
        operator = np.eye(matrix.shape[0], dtype=np.float64) - matrix
    elif semantics == "jacobian_inverse":
        operator = np.asarray(matrix, dtype=np.float64)
    else:
        return np.asarray(matrix, dtype=np.float64), float(np.linalg.cond(matrix))

    try:
        condition_number = float(np.linalg.cond(operator))
    except np.linalg.LinAlgError as exc:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "Unable to compute GE operator condition number",
            details={"error": str(exc)},
        ) from exc
    if not math.isfinite(condition_number) or condition_number > condition_threshold:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "GE operator is singular or ill-conditioned",
            details={"condition_number": condition_number, "threshold": condition_threshold},
        )
    try:
        inverse = np.linalg.inv(operator)
    except np.linalg.LinAlgError as exc:
        raise _fail_error(
            _ERROR_GE_OPERATOR_SINGULAR,
            "GE operator inversion failed",
            details={"error": str(exc)},
        ) from exc
    return np.asarray(inverse, dtype=np.float64), condition_number


def _load_ge_model_from_ref(
    ctx: ExecutionContext,
    ref: ArtifactRefModel,
    *,
    semantics: str,
    size: int,
    condition_threshold: float,
    diagnostics: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, Literal["multiplier", "technical_coefficients"]]:
    payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    if isinstance(payload, dict):
        if "technical_coefficients" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["technical_coefficients"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.technical_coefficients",
            )
            multiplier, condition_number = _invert_linear_operator(
                matrix,
                semantics=semantics,
                condition_threshold=condition_threshold,
            )
            diagnostics["ge_condition_number"] = condition_number
            return multiplier, matrix, "technical_coefficients"
        if "matrix" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["matrix"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.matrix",
            )
            return matrix, matrix, "multiplier"
        if "leontief_inverse" in payload:
            matrix = _validate_square_matrix(
                np.asarray(payload["leontief_inverse"], dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.leontief_inverse",
            )
            return matrix, matrix, "multiplier"
        try:
            bundle = LeontiefIOBundle.model_validate(payload)
        except ValidationError:
            bundle = None
        if bundle is not None:
            coefficients = _validate_square_matrix(
                np.asarray(bundle.technical_coefficients, dtype=np.float64),
                expected_size=size,
                field_name="ge_model_ref.leontief_io_bundle",
            )
            multiplier, condition_number = _invert_linear_operator(
                coefficients,
                semantics=semantics,
                condition_threshold=condition_threshold,
            )
            diagnostics["ge_condition_number"] = condition_number
            return multiplier, coefficients, "technical_coefficients"
    raise _fail_error(
        _ERROR_WELFARE_MODEL_CLASS_MISMATCH,
        "Unsupported ge_model_ref payload for welfare propagation",
        details={"kind": ref.kind},
    )


def _load_matrix_artifact(
    ctx: ExecutionContext,
    ref: ArtifactRefModel,
    *,
    expected_size: int,
    field_name: str,
) -> np.ndarray:
    payload = from_canonical_bytes(ctx.store.get_bytes(ref.artifact_id))
    if isinstance(payload, dict):
        if "matrix" in payload:
            return _validate_square_matrix(
                np.asarray(payload["matrix"], dtype=np.float64),
                expected_size=expected_size,
                field_name=field_name,
            )
        if "leontief_inverse" in payload:
            return _validate_square_matrix(
                np.asarray(payload["leontief_inverse"], dtype=np.float64),
                expected_size=expected_size,
                field_name=field_name,
            )
    return _validate_square_matrix(
        np.asarray(payload, dtype=np.float64),
        expected_size=expected_size,
        field_name=field_name,
    )


def _derive_multiplier_interval_from_coefficients(
    lower_coefficients: np.ndarray,
    upper_coefficients: np.ndarray,
    *,
    semantics: str,
    condition_threshold: float,
    max_varying_entries: int,
) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    varying = list(zip(*np.where(np.abs(lower_coefficients - upper_coefficients) > 0.0)))
    if len(varying) > max_varying_entries:
        return None, None, {"varying_entries": len(varying), "status": "skipped"}

    lower_bound: np.ndarray | None = None
    upper_bound: np.ndarray | None = None
    for selector in itertools.product((0, 1), repeat=len(varying)):
        candidate = np.array(lower_coefficients, copy=True)
        for choice, (row_idx, col_idx) in zip(selector, varying, strict=False):
            candidate[row_idx, col_idx] = (
                upper_coefficients[row_idx, col_idx]
                if choice
                else lower_coefficients[row_idx, col_idx]
            )
        multiplier, _ = _invert_linear_operator(
            candidate,
            semantics=semantics,
            condition_threshold=condition_threshold,
        )
        if lower_bound is None:
            lower_bound = multiplier
            upper_bound = multiplier
            continue
        lower_bound = np.minimum(lower_bound, multiplier)
        upper_bound = np.maximum(upper_bound, multiplier)
    return (
        lower_bound,
        upper_bound,
        {
            "varying_entries": len(varying),
            "status": "ok",
            "corner_count": 2 ** len(varying),
        },
    )


def _persist_json_payload(
    ctx: ExecutionContext,
    *,
    payload: Mapping[str, Any],
    kind: str,
    schema_name: str,
) -> ArtifactRefModel:
    ref = ctx.store.put_json(
        dict(payload),
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref.model_dump())


def _sample_from_envelope(rng: np.random.Generator, env: UncertaintyEnvelope) -> float:
    point = float(env.point_estimate)
    lower, upper = float(env.confidence_interval[0]), float(env.confidence_interval[1])
    if env.distribution_family == DistributionFamily.NORMAL:
        std = _extract_std(env)
        return float(rng.normal(loc=point, scale=max(std, 1e-12)))
    if env.distribution_family == DistributionFamily.UNIFORM:
        return float(rng.uniform(lower, upper))
    if env.distribution_family == DistributionFamily.TRIANGULAR:
        if upper <= lower:
            return point
        mode = min(max(point, lower), upper)
        return float(rng.triangular(lower, mode, upper))
    return float(rng.normal(loc=point, scale=max((upper - lower) / 4.0, 1e-12)))


def _extract_std(env: UncertaintyEnvelope) -> float:
    lower, upper = float(env.confidence_interval[0]), float(env.confidence_interval[1])
    width = max(upper - lower, 0.0)
    if env.distribution_family == DistributionFamily.NORMAL and env.confidence_level is not None:
        z = NormalDist().inv_cdf((1.0 + float(env.confidence_level)) / 2.0)
        if z > 0.0:
            return width / (2.0 * z)
    return width / (2.0 * (3.0**0.5))


def _mul_interval(
    a_lower: float, a_upper: float, b_lower: float, b_upper: float
) -> tuple[float, float]:
    candidates = (
        a_lower * b_lower,
        a_lower * b_upper,
        a_upper * b_lower,
        a_upper * b_upper,
    )
    return min(candidates), max(candidates)


def _matvec_interval(
    matrix_lower: np.ndarray,
    matrix_upper: np.ndarray,
    vector_lower: np.ndarray,
    vector_upper: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = matrix_lower.shape
    out_lower = np.zeros(rows, dtype=np.float64)
    out_upper = np.zeros(rows, dtype=np.float64)
    for row_idx in range(rows):
        total_lower = 0.0
        total_upper = 0.0
        for col_idx in range(cols):
            item_lower, item_upper = _mul_interval(
                float(matrix_lower[row_idx, col_idx]),
                float(matrix_upper[row_idx, col_idx]),
                float(vector_lower[col_idx]),
                float(vector_upper[col_idx]),
            )
            total_lower += item_lower
            total_upper += item_upper
        out_lower[row_idx] = total_lower
        out_upper[row_idx] = total_upper
    return out_lower, out_upper


def _dot_interval(weights: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> tuple[float, float]:
    total_lower = 0.0
    total_upper = 0.0
    for weight, lo, hi in zip(weights, lower, upper, strict=True):
        contrib_lower, contrib_upper = _mul_interval(
            float(weight),
            float(weight),
            float(lo),
            float(hi),
        )
        total_lower += contrib_lower
        total_upper += contrib_upper
    return total_lower, total_upper


def _fail_error(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
) -> _WelfareNodeFailure:
    return _WelfareNodeFailure(NodeError(code=code, message=message, details=dict(details or {})))


__all__ = ["PropagateWelfareNode"]
