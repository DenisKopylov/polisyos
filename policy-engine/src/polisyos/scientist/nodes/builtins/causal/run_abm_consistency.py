"""Public causal run abm consistency module API."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from statistics import mean, pstdev, stdev
from typing import Any

from pydantic import BaseModel, ValidationError

from polisyos.core.artifacts import (
    ArtifactStore,
    input_ref_from_artifact_ref,
    profile_bound_ref,
)
from polisyos.core.artifacts import (
    ensure_ir_artifact_store as _ensure_ir_artifact_store,
)
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    PhaseTransition,
    ToleranceMethod,
    persist_abm_alignment_report,
)
from polisyos.ir.analytics.abstraction import (
    ContinuousApproximateAbstractionConfig,
    FiniteStateAbstractionMap,
    load_finite_state_abstraction_map,
    persist_abstraction_certificate,
    persist_finite_state_abstraction_map,
    verify_continuous_approximate_abstraction,
    verify_finite_state_exact_abstraction,
)
from polisyos.ir.analytics.causal import load_causal_effect_report
from polisyos.ir.analytics.causal_graph import persist_causal_graph_model
from polisyos.ir.analytics.structural_causal_model import (
    StructuralCausalModelSpec,
    load_structural_causal_model_spec,
)
from polisyos.ir.registry.refs import (
    CausalGraphModelRef,
    FiniteStateAbstractionMapRef,
    StructuralCausalModelSpecRef,
)
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
    ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
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

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_abm_consistency@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run ABM Consistency Check",
    description=(
        "Compare SCM macro effects against ABM macro aggregates with adaptive "
        "tolerance and phase-transition detection."
    ),
    tags=["builtin", "causal", "abm"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.abm_macro_micro_mappings",
        "params.abm_run_stats",
        "params.scm_effects",
        "params.abm_bridge_config",
        "params.finite_state_micro_scm",
        "params.finite_state_micro_scm_ref",
        "params.finite_state_macro_scm",
        "params.finite_state_macro_scm_ref",
        "params.finite_state_abstraction_map",
        "params.finite_state_abstraction_map_ref",
        "params.continuous_micro_scm",
        "params.continuous_micro_scm_ref",
        "params.continuous_macro_scm",
        "params.continuous_macro_scm_ref",
        "params.continuous_abstraction_map",
        "params.continuous_abstraction_map_ref",
        "params.continuous_abstraction_bound_config",
        "params.abstraction_preserved_queries",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_ABM_ALIGNMENT_REPORT_REF}",
        f"artifacts_index.{ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF}",
        f"artifacts_index.{ARTIFACT_ABSTRACTION_CERTIFICATE_REF}",
        "params.abm_alignment_overall_consistent",
        "params.abm_alignment_warnings",
        "params.abstraction_preservation_type",
    ],
    produces=[
        ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
        ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF,
        ARTIFACT_ABSTRACTION_CERTIFICATE_REF,
    ],
)

_ABM_CONSISTENCY_VALIDATION_ERRORS = (TypeError, ValueError, ValidationError)
_ABM_CONSISTENCY_RUNTIME_ERRORS = (
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    ValidationError,
)
_UNSET = object()


@dataclass(frozen=True)
class _BridgeConfig:
    min_runs: int = 3
    sigma_multiplier: float = 2.0
    tolerance_floor: float = 0.02
    phase_min_points: int = 4
    phase_jump_sigma_mult: float = 3.0
    phase_jump_abs_floor: float = 0.25
    wide_tolerance_ratio: float = 0.8
    wide_tolerance_floor: float = 0.2

    @classmethod
    def from_payload(cls, payload: Any) -> _BridgeConfig:
        if not isinstance(payload, Mapping):
            return cls()

        def _int_value(key: str, default: int, lower: int) -> int:
            raw = payload.get(key)
            try:
                parsed = int(raw)
            except _ABM_CONSISTENCY_VALIDATION_ERRORS:
                return default
            return max(lower, parsed)

        def _float_value(key: str, default: float, lower: float) -> float:
            raw = payload.get(key)
            try:
                parsed = float(raw)
            except _ABM_CONSISTENCY_VALIDATION_ERRORS:
                return default
            if not math.isfinite(parsed):
                return default
            return max(lower, parsed)

        return cls(
            min_runs=_int_value("min_runs", cls.min_runs, 1),
            sigma_multiplier=_float_value("sigma_multiplier", cls.sigma_multiplier, 0.0),
            tolerance_floor=_float_value("tolerance_floor", cls.tolerance_floor, 0.0),
            phase_min_points=_int_value("phase_min_points", cls.phase_min_points, 3),
            phase_jump_sigma_mult=_float_value(
                "phase_jump_sigma_mult",
                cls.phase_jump_sigma_mult,
                0.0,
            ),
            phase_jump_abs_floor=_float_value(
                "phase_jump_abs_floor",
                cls.phase_jump_abs_floor,
                0.0,
            ),
            wide_tolerance_ratio=_float_value(
                "wide_tolerance_ratio",
                cls.wide_tolerance_ratio,
                0.0,
            ),
            wide_tolerance_floor=_float_value(
                "wide_tolerance_floor",
                cls.wide_tolerance_floor,
                0.0,
            ),
        )


@dataclass(frozen=True)
class _StructuralSCMInput:
    spec: StructuralCausalModelSpec
    selected_ref: StructuralCausalModelSpecRef | None


@dataclass(frozen=True)
class _ExactAbstractionInputs:
    micro_scm: StructuralCausalModelSpec
    macro_scm: StructuralCausalModelSpec
    abstraction_map: FiniteStateAbstractionMap
    abstraction_map_ref: FiniteStateAbstractionMapRef | None
    micro_scm_ref: StructuralCausalModelSpecRef | None
    macro_scm_ref: StructuralCausalModelSpecRef | None


@dataclass(frozen=True)
class _ContinuousAbstractionInputs:
    micro_scm: StructuralCausalModelSpec
    macro_scm: StructuralCausalModelSpec
    abstraction_map: FiniteStateAbstractionMap
    abstraction_map_ref: FiniteStateAbstractionMapRef | None
    bound_config: ContinuousApproximateAbstractionConfig
    micro_scm_ref: StructuralCausalModelSpecRef | None
    macro_scm_ref: StructuralCausalModelSpecRef | None


def _parse_mappings(raw: Any) -> list[MacroMicroMapping]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("params.abm_macro_micro_mappings must be a list")
    mappings = [MacroMicroMapping.model_validate(item) for item in raw]
    duplicates = {
        item.macro_variable
        for item in mappings
        if sum(1 for probe in mappings if probe.macro_variable == item.macro_variable) > 1
    }
    if duplicates:
        raise ValueError(
            "abm_macro_micro_mappings contain duplicate macro_variable entries: "
            + ", ".join(sorted(duplicates))
        )
    return mappings


def _parse_scm_effects(raw: Any) -> dict[str, float]:
    if not isinstance(raw, Mapping):
        return {}
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        name = str(key).strip()
        if not name:
            continue
        try:
            numeric = float(value)
        except _ABM_CONSISTENCY_VALIDATION_ERRORS:
            continue
        if math.isfinite(numeric):
            parsed[name] = numeric
    return parsed


def _extract_effects(stats_entry: Any) -> list[float]:
    if not isinstance(stats_entry, Mapping):
        return []
    raw = stats_entry.get("effects")
    if not isinstance(raw, list):
        return []
    effects: list[float] = []
    for item in raw:
        try:
            numeric = float(item)
        except _ABM_CONSISTENCY_VALIDATION_ERRORS:
            continue
        if math.isfinite(numeric):
            effects.append(numeric)
    return effects


def _extract_response_curve(stats_entry: Any) -> list[tuple[float, float]]:
    if not isinstance(stats_entry, Mapping):
        return []
    raw = stats_entry.get("response_curve")
    if not isinstance(raw, list):
        return []

    points: list[tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        intervention = item.get("intervention")
        effect = item.get("effect")
        try:
            x = float(intervention)
            y = float(effect)
        except _ABM_CONSISTENCY_VALIDATION_ERRORS:
            continue
        if math.isfinite(x) and math.isfinite(y):
            points.append((x, y))
    points.sort(key=lambda item: item[0])
    return points


def _detect_phase_transition(
    *,
    variable: str,
    response_curve: list[tuple[float, float]],
    cfg: _BridgeConfig,
) -> PhaseTransition | None:
    if len(response_curve) < cfg.phase_min_points:
        return None

    slopes: list[float] = []
    for idx in range(len(response_curve) - 1):
        x0, y0 = response_curve[idx]
        x1, y1 = response_curve[idx + 1]
        dx = x1 - x0
        if abs(dx) <= 1e-12:
            continue
        slopes.append((y1 - y0) / dx)

    if len(slopes) < 2:
        return None

    threshold = max(
        cfg.phase_jump_abs_floor,
        cfg.phase_jump_sigma_mult * pstdev(slopes),
    )
    for idx in range(len(slopes) - 1):
        jump = abs(slopes[idx + 1] - slopes[idx])
        if jump > threshold:
            threshold_value = response_curve[idx + 1][0]
            return PhaseTransition(
                variable=variable,
                threshold_value=float(threshold_value),
                pre_regime=f"slope={slopes[idx]:.6g}",
                post_regime=f"slope={slopes[idx + 1]:.6g}",
                jump_value=float(jump),
            )
    return None


def _load_single_fallback_effect(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> float | None:
    report_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
    if report_ref is None:
        return None
    try:
        report = load_causal_effect_report(_ensure_ir_artifact_store(ctx.store), report_ref)
    except _ABM_CONSISTENCY_RUNTIME_ERRORS:
        return None
    if report.point_estimate is None:
        return None
    point = float(report.point_estimate)
    if not math.isfinite(point):
        return None
    return point


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _coerce_structural_scm_ref(value: Any) -> StructuralCausalModelSpecRef | None:
    if value is None:
        return None
    if isinstance(value, StructuralCausalModelSpecRef):
        return value
    if isinstance(value, str):
        return StructuralCausalModelSpecRef.model_validate({"artifact_id": value})
    return StructuralCausalModelSpecRef.model_validate(value)


def _coerce_abstraction_map_ref(value: Any) -> FiniteStateAbstractionMapRef | None:
    if value is None:
        return None
    if isinstance(value, FiniteStateAbstractionMapRef):
        return value
    if isinstance(value, str):
        return FiniteStateAbstractionMapRef.model_validate({"artifact_id": value})
    return FiniteStateAbstractionMapRef.model_validate(value)


def _load_selected_typed_input[TModel: BaseModel, TRef: BaseModel](
    store: ArtifactStore,
    *,
    inline_payload: Any,
    raw_ref: Any,
    model_type: type[TModel],
    coerce_ref: Callable[[Any], TRef | None],
    load_ref: Callable[[ArtifactStore, TRef], TModel],
) -> tuple[TModel, TRef | None] | None:
    """Admit one inline/ref pair and bind both selectors to the same typed content.

    An absent pair remains absent. A supplied inline value is validated even when
    a ref is also supplied; a supplied ref is profile-bound and loaded even when
    an inline value is also supplied. When both are present, their normalized
    typed payloads must match before the CAS value and selected ref are returned.
    """
    inline_supplied = inline_payload is not _UNSET
    ref_supplied = raw_ref is not _UNSET
    inline_value = None
    if inline_supplied:
        inline_value = (
            inline_payload
            if isinstance(inline_payload, model_type)
            else model_type.model_validate(inline_payload)
        )

    if not ref_supplied:
        return (inline_value, None) if inline_value is not None else None

    typed_ref = coerce_ref(raw_ref)
    if typed_ref is None:
        raise ValueError("selected_artifact_ref_is_explicitly_null")
    selected_ref = profile_bound_ref(store, typed_ref)
    referenced_value = load_ref(store, selected_ref)
    if inline_value is not None and (
        inline_value.model_dump(mode="json") != referenced_value.model_dump(mode="json")
    ):
        raise ValueError("inline_payload_ref_content_mismatch")
    return referenced_value, selected_ref


def _load_structural_scm_value(
    ctx: ExecutionContext,
    state: ExperimentState,
    *,
    payload_key: str,
    ref_key: str,
    artifact_fallback_key: str | None = None,
) -> _StructuralSCMInput | None:
    store = _ensure_ir_artifact_store(ctx.store)
    selected = _load_selected_typed_input(
        store,
        inline_payload=state.params.get(payload_key, _UNSET),
        raw_ref=state.params.get(ref_key, _UNSET),
        model_type=StructuralCausalModelSpec,
        coerce_ref=_coerce_structural_scm_ref,
        load_ref=load_structural_causal_model_spec,
    )
    if selected is not None:
        spec, selected_ref = selected
        return _StructuralSCMInput(spec=spec, selected_ref=selected_ref)

    if artifact_fallback_key is not None:
        artifact_ref = state.artifacts_index.get(artifact_fallback_key)
        if artifact_ref is not None:
            fallback = _load_selected_typed_input(
                store,
                inline_payload=_UNSET,
                raw_ref=StructuralCausalModelSpecRef.model_validate(
                    artifact_ref.model_dump(mode="json")
                ),
                model_type=StructuralCausalModelSpec,
                coerce_ref=_coerce_structural_scm_ref,
                load_ref=load_structural_causal_model_spec,
            )
            if fallback is not None:
                spec, selected_ref = fallback
                return _StructuralSCMInput(spec=spec, selected_ref=selected_ref)
    return None


def _load_exact_abstraction_inputs(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> _ExactAbstractionInputs | None:
    any_requested = any(
        key in state.params
        for key in (
            "finite_state_micro_scm",
            "finite_state_micro_scm_ref",
            "finite_state_macro_scm",
            "finite_state_macro_scm_ref",
            "finite_state_abstraction_map",
            "finite_state_abstraction_map_ref",
        )
    )
    if not any_requested:
        return None

    micro_input = _load_structural_scm_value(
        ctx,
        state,
        payload_key="finite_state_micro_scm",
        ref_key="finite_state_micro_scm_ref",
    )
    macro_input = _load_structural_scm_value(
        ctx,
        state,
        payload_key="finite_state_macro_scm",
        ref_key="finite_state_macro_scm_ref",
        artifact_fallback_key=ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
    )
    if micro_input is None or macro_input is None:
        raise ValueError(
            "Exact abstraction verification requires both finite_state_micro_scm and finite_state_macro_scm"
        )

    store = _ensure_ir_artifact_store(ctx.store)
    selected_map = _load_selected_typed_input(
        store,
        inline_payload=state.params.get("finite_state_abstraction_map", _UNSET),
        raw_ref=state.params.get("finite_state_abstraction_map_ref", _UNSET),
        model_type=FiniteStateAbstractionMap,
        coerce_ref=_coerce_abstraction_map_ref,
        load_ref=load_finite_state_abstraction_map,
    )
    if selected_map is None:
        raise ValueError(
            "Exact abstraction verification requires finite_state_abstraction_map or finite_state_abstraction_map_ref"
        )
    abstraction_map, map_ref = selected_map
    return _ExactAbstractionInputs(
        micro_scm=micro_input.spec,
        macro_scm=macro_input.spec,
        abstraction_map=abstraction_map,
        abstraction_map_ref=map_ref,
        micro_scm_ref=micro_input.selected_ref,
        macro_scm_ref=macro_input.selected_ref,
    )


def _load_continuous_abstraction_inputs(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> _ContinuousAbstractionInputs | None:
    any_requested = any(
        key in state.params
        for key in (
            "continuous_micro_scm",
            "continuous_micro_scm_ref",
            "continuous_macro_scm",
            "continuous_macro_scm_ref",
            "continuous_abstraction_map",
            "continuous_abstraction_map_ref",
            "continuous_abstraction_bound_config",
        )
    )
    if not any_requested:
        return None

    micro_input = _load_structural_scm_value(
        ctx,
        state,
        payload_key="continuous_micro_scm",
        ref_key="continuous_micro_scm_ref",
    )
    macro_input = _load_structural_scm_value(
        ctx,
        state,
        payload_key="continuous_macro_scm",
        ref_key="continuous_macro_scm_ref",
        artifact_fallback_key=ARTIFACT_STRUCTURAL_CAUSAL_MODEL_SPEC_REF,
    )
    if micro_input is None or macro_input is None:
        raise ValueError(
            "Continuous abstraction verification requires both continuous_micro_scm "
            "and continuous_macro_scm"
        )

    store = _ensure_ir_artifact_store(ctx.store)
    selected_map = _load_selected_typed_input(
        store,
        inline_payload=state.params.get("continuous_abstraction_map", _UNSET),
        raw_ref=state.params.get("continuous_abstraction_map_ref", _UNSET),
        model_type=FiniteStateAbstractionMap,
        coerce_ref=_coerce_abstraction_map_ref,
        load_ref=load_finite_state_abstraction_map,
    )
    if selected_map is None:
        raise ValueError(
            "Continuous abstraction verification requires continuous_abstraction_map "
            "or continuous_abstraction_map_ref"
        )
    abstraction_map, map_ref = selected_map

    raw_bound_config = state.params.get("continuous_abstraction_bound_config")
    if raw_bound_config is None:
        raise ValueError(
            "Continuous abstraction verification requires continuous_abstraction_bound_config"
        )
    bound_config = (
        raw_bound_config
        if isinstance(raw_bound_config, ContinuousApproximateAbstractionConfig)
        else ContinuousApproximateAbstractionConfig.model_validate(raw_bound_config)
    )
    return _ContinuousAbstractionInputs(
        micro_scm=micro_input.spec,
        macro_scm=macro_input.spec,
        abstraction_map=abstraction_map,
        abstraction_map_ref=map_ref,
        bound_config=bound_config,
        micro_scm_ref=micro_input.selected_ref,
        macro_scm_ref=macro_input.selected_ref,
    )


@dataclass(frozen=True)
class RunABMConsistencyCheckNode:
    """Compare SCM effects against ABM aggregates and abstraction evidence.

    Produces alignment diagnostics, optional finite-state abstraction artifacts,
    and an abstraction certificate so governance can judge whether ABM and SCM
    outputs remain mutually consistent.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_ABM_ALIGNMENT_REPORT_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        try:
            mappings = _parse_mappings(state.params.get("abm_macro_micro_mappings"))
        except _ABM_CONSISTENCY_VALIDATION_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid params.abm_macro_micro_mappings payload: {exc}",
                ),
            )

        if not mappings:
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message=("No params.abm_macro_micro_mappings; skip ABM consistency check."),
                    )
                ],
            )

        cfg = _BridgeConfig.from_payload(state.params.get("abm_bridge_config"))
        scm_effects = _parse_scm_effects(state.params.get("scm_effects"))
        fallback_effect = _load_single_fallback_effect(ctx, state) if len(mappings) == 1 else None
        run_stats = state.params.get("abm_run_stats")
        run_stats_map: Mapping[str, Any] = run_stats if isinstance(run_stats, Mapping) else {}

        alignment_results: dict[str, AlignmentResult] = {}
        phase_transitions: list[PhaseTransition] = []
        warnings: list[str] = []
        events: list[NodeEvent] = []
        abstraction_map_ref: FiniteStateAbstractionMapRef | None = None
        abstraction_certificate_ref = None
        micro_graph_ref: CausalGraphModelRef | None = None
        macro_graph_ref: CausalGraphModelRef | None = None
        abstraction_preservation_type: str | None = None

        exact_inputs: _ExactAbstractionInputs | None = None
        continuous_inputs: _ContinuousAbstractionInputs | None = None
        try:
            exact_inputs = _load_exact_abstraction_inputs(ctx, state)
            continuous_inputs = _load_continuous_abstraction_inputs(ctx, state)
        except _ABM_CONSISTENCY_RUNTIME_ERRORS as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid abstraction payload: {exc}",
                ),
            )

        if exact_inputs is not None and continuous_inputs is not None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=(
                        "Provide either finite-state exact abstraction inputs or continuous "
                        "approximate abstraction inputs, not both"
                    ),
                ),
            )

        if exact_inputs is None and continuous_inputs is None:
            _append_warning(warnings, "heuristic_aggregation_without_abstraction_certificate")
        else:
            store = _ensure_ir_artifact_store(ctx.store)
            micro_scm_ref = (
                continuous_inputs.micro_scm_ref
                if continuous_inputs is not None
                else exact_inputs.micro_scm_ref
            )
            macro_scm_ref = (
                continuous_inputs.macro_scm_ref
                if continuous_inputs is not None
                else exact_inputs.macro_scm_ref
            )
            micro_graph_inputs = (
                [
                    input_ref_from_artifact_ref(
                        ArtifactRef.model_validate(micro_scm_ref.model_dump(mode="json")),
                        role="micro_structural_causal_model_spec",
                    )
                ]
                if micro_scm_ref is not None
                else None
            )
            macro_graph_inputs = (
                [
                    input_ref_from_artifact_ref(
                        ArtifactRef.model_validate(macro_scm_ref.model_dump(mode="json")),
                        role="macro_structural_causal_model_spec",
                    )
                ]
                if macro_scm_ref is not None
                else None
            )
            micro_graph_ref = profile_bound_ref(
                store,
                persist_causal_graph_model(
                    store,
                    (
                        continuous_inputs.micro_scm.graph
                        if continuous_inputs is not None
                        else exact_inputs.micro_scm.graph
                    ),
                    inputs=micro_graph_inputs,
                ),
            )
            macro_graph_ref = profile_bound_ref(
                store,
                persist_causal_graph_model(
                    store,
                    (
                        continuous_inputs.macro_scm.graph
                        if continuous_inputs is not None
                        else exact_inputs.macro_scm.graph
                    ),
                    inputs=macro_graph_inputs,
                ),
            )
            selected_map = (
                continuous_inputs.abstraction_map
                if continuous_inputs is not None
                else exact_inputs.abstraction_map
            )
            abstraction_map_ref = (
                continuous_inputs.abstraction_map_ref
                if continuous_inputs is not None
                else exact_inputs.abstraction_map_ref
            )
            if abstraction_map_ref is None:
                abstraction_map_ref = persist_finite_state_abstraction_map(
                    store,
                    selected_map,
                    inputs=[
                        input_ref_from_artifact_ref(
                            ArtifactRef.model_validate(micro_graph_ref.model_dump(mode="json")),
                            role="micro_graph",
                        ),
                        input_ref_from_artifact_ref(
                            ArtifactRef.model_validate(macro_graph_ref.model_dump(mode="json")),
                            role="macro_graph",
                        ),
                    ],
                )
            abstraction_map_ref = profile_bound_ref(store, abstraction_map_ref)
            preserved_queries = state.params.get("abstraction_preserved_queries")
            normalized_preserved_queries = (
                tuple(str(item) for item in preserved_queries)
                if isinstance(preserved_queries, (tuple, list))
                else None
            )
            if continuous_inputs is not None:
                certificate = verify_continuous_approximate_abstraction(
                    continuous_inputs.micro_scm,
                    continuous_inputs.macro_scm,
                    continuous_inputs.abstraction_map,
                    bound_config=continuous_inputs.bound_config,
                    micro_graph_ref=micro_graph_ref,
                    macro_graph_ref=macro_graph_ref,
                    abstraction_map_ref=abstraction_map_ref,
                    preserved_queries=normalized_preserved_queries,
                )
            else:
                certificate = verify_finite_state_exact_abstraction(
                    exact_inputs.micro_scm,
                    exact_inputs.macro_scm,
                    exact_inputs.abstraction_map,
                    micro_graph_ref=micro_graph_ref,
                    macro_graph_ref=macro_graph_ref,
                    abstraction_map_ref=abstraction_map_ref,
                    preserved_queries=normalized_preserved_queries,
                )
            abstraction_certificate_ref = profile_bound_ref(
                store,
                persist_abstraction_certificate(
                    store,
                    certificate,
                    inputs=[
                        input_ref_from_artifact_ref(
                            ArtifactRef.model_validate(micro_graph_ref.model_dump(mode="json")),
                            role="micro_graph",
                        ),
                        input_ref_from_artifact_ref(
                            ArtifactRef.model_validate(macro_graph_ref.model_dump(mode="json")),
                            role="macro_graph",
                        ),
                        input_ref_from_artifact_ref(
                            ArtifactRef.model_validate(abstraction_map_ref.model_dump(mode="json")),
                            role="abstraction_map",
                        ),
                    ],
                ),
            )
            abstraction_preservation_type = certificate.preservation_type.value
            if abstraction_preservation_type == "exact":
                events.append(
                    NodeEvent(
                        level="info",
                        message="Exact finite-state abstraction certificate verified.",
                    )
                )
            elif abstraction_preservation_type in {"approximate", "policy_value_only"}:
                events.append(
                    NodeEvent(
                        level="info",
                        message=(
                            "Continuous approximate abstraction certificate verified."
                            if continuous_inputs is not None
                            else "Approximate abstraction certificate verified."
                        ),
                    )
                )
            else:
                _append_warning(warnings, "invalid_abstraction_certificate")
                events.append(
                    NodeEvent(
                        level="warn",
                        message=(
                            "Exact finite-state abstraction inputs were provided but did not verify; "
                            "continuing with heuristic aggregation."
                        ),
                    )
                )

        for mapping in mappings:
            variable = mapping.macro_variable
            variable_prefix = f"{variable}: "
            scm_effect = scm_effects.get(variable)
            if scm_effect is None and fallback_effect is not None:
                scm_effect = fallback_effect

            stats_entry = run_stats_map.get(variable)
            effects = _extract_effects(stats_entry)
            n_runs = len(effects)
            abm_effect = float(mean(effects)) if effects else None
            response_curve = _extract_response_curve(stats_entry)

            transition = _detect_phase_transition(
                variable=variable,
                response_curve=response_curve,
                cfg=cfg,
            )
            if transition is not None:
                phase_transitions.append(transition)

            tolerance_used: float | None = None
            delta: float | None = None

            if transition is not None:
                status = AlignmentStatus.NON_LINEAR_DIVERGENCE
            elif n_runs == 0:
                status = AlignmentStatus.INSUFFICIENT_RUNS
                _append_warning(warnings, variable_prefix + "insufficient_abm_runs")
            elif scm_effect is None:
                status = AlignmentStatus.INCONSISTENT
                _append_warning(warnings, variable_prefix + "missing_scm_effect")
            else:
                needs_adaptive = mapping.tolerance_method is ToleranceMethod.ADAPTIVE
                if mapping.tolerance_method is ToleranceMethod.FIXED and mapping.tolerance is None:
                    needs_adaptive = True
                    _append_warning(
                        warnings,
                        variable_prefix + "fixed_tolerance_missing_fallback_adaptive",
                    )

                if needs_adaptive:
                    if n_runs < cfg.min_runs:
                        status = AlignmentStatus.INSUFFICIENT_RUNS
                        _append_warning(warnings, variable_prefix + "insufficient_abm_runs")
                    else:
                        sample_std = stdev(effects) if n_runs > 1 else 0.0
                        tolerance_used = max(cfg.sigma_multiplier * sample_std, cfg.tolerance_floor)
                        delta = abs(float(scm_effect) - float(abm_effect))
                        status = (
                            AlignmentStatus.CONSISTENT
                            if delta < tolerance_used
                            else AlignmentStatus.INCONSISTENT
                        )
                else:
                    tolerance_used = float(mapping.tolerance)
                    delta = abs(float(scm_effect) - float(abm_effect))
                    status = (
                        AlignmentStatus.CONSISTENT
                        if delta < tolerance_used
                        else AlignmentStatus.INCONSISTENT
                    )

                if status is AlignmentStatus.CONSISTENT and tolerance_used is not None:
                    wide_threshold = max(
                        cfg.wide_tolerance_floor,
                        cfg.wide_tolerance_ratio * abs(float(scm_effect)),
                    )
                    if tolerance_used >= wide_threshold:
                        message = variable_prefix + "wide_tolerance_consistent_warning"
                        _append_warning(warnings, message)
                        events.append(
                            NodeEvent(
                                level="warn",
                                message=(
                                    f"ABM alignment for '{variable}' is consistent but uses "
                                    "wide tolerance; treat as advisory signal."
                                ),
                            )
                        )

            alignment_results[variable] = AlignmentResult(
                scm_effect=scm_effect,
                abm_effect=abm_effect,
                status=status,
                tolerance_used=tolerance_used,
                delta=delta,
                n_runs=n_runs,
                metadata={
                    "aggregation_function": mapping.aggregation_function.value,
                    "tolerance_method": mapping.tolerance_method.value,
                },
            )

        overall_consistent = bool(alignment_results) and all(
            item.status is AlignmentStatus.CONSISTENT for item in alignment_results.values()
        )

        report = ABMAlignmentReport(
            mappings=mappings,
            alignment_results=alignment_results,
            overall_consistent=overall_consistent,
            phase_transitions=phase_transitions,
            warnings=warnings,
        )

        input_refs: list[InputRef] = []
        causal_ref = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        if causal_ref is not None:
            input_refs.append(InputRef(artifact_id=causal_ref.artifact_id, role="causal_report"))
        if micro_graph_ref is not None:
            input_refs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(micro_graph_ref.model_dump(mode="json")),
                    role="micro_graph",
                )
            )
        if macro_graph_ref is not None:
            input_refs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(macro_graph_ref.model_dump(mode="json")),
                    role="macro_graph",
                )
            )
        if abstraction_map_ref is not None:
            input_refs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(abstraction_map_ref.model_dump(mode="json")),
                    role="abstraction_map",
                )
            )
        if abstraction_certificate_ref is not None:
            input_refs.append(
                input_ref_from_artifact_ref(
                    ArtifactRef.model_validate(abstraction_certificate_ref.model_dump(mode="json")),
                    role="abstraction_certificate",
                )
            )

        report_ref = persist_abm_alignment_report(
            _ensure_ir_artifact_store(ctx.store), report, inputs=input_refs
        )

        new_state = branch_state(state, write_paths=_SPEC.state_writes).state
        new_state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF] = report_ref
        if abstraction_map_ref is not None:
            new_state.artifacts_index[ARTIFACT_FINITE_STATE_ABSTRACTION_MAP_REF] = (
                abstraction_map_ref
            )
        if abstraction_certificate_ref is not None:
            new_state.artifacts_index[ARTIFACT_ABSTRACTION_CERTIFICATE_REF] = (
                abstraction_certificate_ref
            )
        new_state.params["abm_alignment_overall_consistent"] = overall_consistent
        new_state.params["abm_alignment_warnings"] = list(warnings)
        if abstraction_preservation_type is not None:
            new_state.params["abstraction_preservation_type"] = abstraction_preservation_type

        events.append(
            NodeEvent(
                level="info",
                message=(
                    "ABM consistency check completed: "
                    f"mappings={len(mappings)}, "
                    f"overall_consistent={overall_consistent}"
                ),
            )
        )

        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[report_ref],
            events=events,
        )


__all__ = ["RunABMConsistencyCheckNode"]
