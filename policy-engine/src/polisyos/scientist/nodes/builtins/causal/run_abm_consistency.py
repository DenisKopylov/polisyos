from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import mean, pstdev, stdev
from typing import Any

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.abm_bridge import (
    ABMAlignmentReport,
    AlignmentResult,
    AlignmentStatus,
    MacroMicroMapping,
    PhaseTransition,
    ToleranceMethod,
    persist_abm_alignment_report,
)
from polisyos.ir.analytics.causal import load_causal_effect_report
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ABM_ALIGNMENT_REPORT_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
)

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
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_ABM_ALIGNMENT_REPORT_REF}",
        "params.abm_alignment_overall_consistent",
        "params.abm_alignment_warnings",
    ],
    produces=[ARTIFACT_ABM_ALIGNMENT_REPORT_REF],
)


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
    def from_payload(cls, payload: Any) -> "_BridgeConfig":
        if not isinstance(payload, Mapping):
            return cls()

        def _int_value(key: str, default: int, lower: int) -> int:
            raw = payload.get(key)
            try:
                parsed = int(raw)
            except Exception:
                return default
            return max(lower, parsed)

        def _float_value(key: str, default: float, lower: float) -> float:
            raw = payload.get(key)
            try:
                parsed = float(raw)
            except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
        report = load_causal_effect_report(ctx.store, report_ref)
    except Exception:
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


@dataclass(frozen=True)
class RunABMConsistencyCheckNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        if ARTIFACT_ABM_ALIGNMENT_REPORT_REF in state.artifacts_index:
            return NodeOutcome(status="ok", state=state)

        try:
            mappings = _parse_mappings(state.params.get("abm_macro_micro_mappings"))
        except Exception as exc:
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
                        message=(
                            "No params.abm_macro_micro_mappings; "
                            "skip ABM consistency check."
                        ),
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
                        message = (
                            variable_prefix
                            + "wide_tolerance_consistent_warning"
                        )
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

        report_ref = persist_abm_alignment_report(ctx.store, report, inputs=input_refs)

        new_state = state.model_copy(deep=True)
        new_state.artifacts_index[ARTIFACT_ABM_ALIGNMENT_REPORT_REF] = report_ref
        new_state.params["abm_alignment_overall_consistent"] = overall_consistent
        new_state.params["abm_alignment_warnings"] = list(warnings)

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
