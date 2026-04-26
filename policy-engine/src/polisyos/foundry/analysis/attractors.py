"""Attractor-analysis helpers for reduced simulation trajectories."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.foundry import (
    AttractorAnalysisProvenance,
    AttractorAnalysisResult,
    AttractorAnalysisResultRef,
    AttractorBasinEstimate,
    AttractorCertificate,
    AttractorObservableSummary,
    AttractorParameterPoint,
    AttractorStability,
    AttractorStateProjection,
    AttractorStateRepresentation,
    AttractorSummary,
    AttractorUncertainty,
    AttractorUncertaintySummary,
    BasinMap,
    BasinMapRef,
    BasinMapSample,
    ContinuationBranch,
    ContinuationBranchRef,
    ExecPlanRef,
    FeedbackJacobianDiagnostics,
    FeedbackResultRef,
    FeedbackSolveResult,
    SimulationResult,
    SimulationResultRef,
)
from polisyos.ir.analytics.phase4_dynamics import build_abm_result_from_simulation
from polisyos.ir.refs import ABMResultRef

if TYPE_CHECKING:
    from polisyos.core.artifacts.store import FileSystemCAS


AttractorKind = Literal[
    "fixed_point",
    "limit_cycle",
    "chaotic",
    "torus",
    "invariant_set",
    "divergent",
]
ExistenceStatus = Literal[
    "candidate",
    "numerically_confirmed",
    "analytically_confirmed",
    "rejected",
    "unknown",
]


@dataclass(frozen=True)
class TerminalRegime:
    """Classification of the terminal segment of one reduced trajectory."""

    kind: AttractorKind
    existence_status: ExistenceStatus
    residual_norm: float
    bounded: bool
    equilibrium: tuple[float, ...] | None = None
    period: int | None = None
    largest_lyapunov_exponent: float | None = None
    notes: tuple[str, ...] = ()


def classify_terminal_regime(
    trajectory: Sequence[Sequence[float]] | np.ndarray,
    *,
    tolerance: float = 1.0e-6,
    rtol: float = 1.0e-5,
    window: int = 32,
    max_period: int = 12,
    divergence_bound: float = 1.0e12,
    largest_lyapunov_exponent: float | None = None,
    chaos_threshold: float = 1.0e-3,
) -> TerminalRegime:
    """Classify a reduced trajectory using fixed, periodic, and chaos diagnostics."""

    _validate_positive_controls(
        tolerance=tolerance,
        rtol=rtol,
        window=window,
        max_period=max_period,
        divergence_bound=divergence_bound,
    )
    array = _as_2d_trajectory(trajectory)
    if not np.all(np.isfinite(array)):
        return TerminalRegime(
            kind="divergent",
            existence_status="rejected",
            residual_norm=float("inf"),
            bounded=False,
            largest_lyapunov_exponent=largest_lyapunov_exponent,
            notes=("non_finite_trajectory",),
        )

    max_abs = float(np.max(np.abs(array)))
    bounded = max_abs <= divergence_bound
    if not bounded:
        return TerminalRegime(
            kind="divergent",
            existence_status="rejected",
            residual_norm=max_abs,
            bounded=False,
            largest_lyapunov_exponent=largest_lyapunov_exponent,
            notes=("divergence_bound_exceeded",),
        )

    tail = array[-min(window, array.shape[0]) :]
    effective_tol = _effective_tolerance(tail, tolerance=tolerance, rtol=rtol)
    fixed_residual = _fixed_residual(tail)
    if fixed_residual <= effective_tol:
        equilibrium = tuple(float(value) for value in np.mean(tail, axis=0))
        return TerminalRegime(
            kind="fixed_point",
            existence_status="numerically_confirmed",
            residual_norm=fixed_residual,
            bounded=True,
            equilibrium=equilibrium,
            largest_lyapunov_exponent=largest_lyapunov_exponent,
            notes=("terminal_window_converged",),
        )

    cycle_period, cycle_residual = _detect_cycle_period(
        tail,
        tolerance=effective_tol,
        max_period=max_period,
    )
    if cycle_period is not None:
        return TerminalRegime(
            kind="limit_cycle",
            existence_status="numerically_confirmed",
            residual_norm=cycle_residual,
            bounded=True,
            period=cycle_period,
            largest_lyapunov_exponent=largest_lyapunov_exponent,
            notes=("finite_period_recurrence_detected",),
        )

    if (
        largest_lyapunov_exponent is not None
        and largest_lyapunov_exponent > chaos_threshold
    ):
        return TerminalRegime(
            kind="chaotic",
            existence_status="numerically_confirmed",
            residual_norm=fixed_residual,
            bounded=True,
            largest_lyapunov_exponent=largest_lyapunov_exponent,
            notes=("positive_largest_lyapunov_exponent", "chaos_is_diagnostic_not_proof"),
        )

    return TerminalRegime(
        kind="invariant_set",
        existence_status="candidate",
        residual_norm=fixed_residual,
        bounded=True,
        largest_lyapunov_exponent=largest_lyapunov_exponent,
        notes=("bounded_terminal_regime_without_fixed_or_finite_period_certificate",),
    )


def finite_difference_map_jacobian(
    step_map: Callable[..., np.ndarray],
    x: Sequence[float] | np.ndarray,
    *,
    theta: Any = None,
    eps: float = 1.0e-6,
) -> np.ndarray:
    """Estimate a discrete map Jacobian with scale-aware forward differences."""

    if eps <= 0.0:
        raise ValueError("eps must be positive")
    point = np.asarray(x, dtype=float)
    if point.ndim != 1:
        raise ValueError("x must be one-dimensional")
    base = _call_step_map(step_map, point, theta=theta)
    jacobian = np.zeros((base.shape[0], point.shape[0]), dtype=float)
    for index in range(point.shape[0]):
        step = np.zeros_like(point)
        h = eps * max(1.0, abs(float(point[index])))
        step[index] = h
        perturbed = _call_step_map(step_map, point + step, theta=theta)
        jacobian[:, index] = (perturbed - base) / h
    return jacobian


def largest_lyapunov_exponent(
    step_map: Callable[..., np.ndarray],
    x0: Sequence[float] | np.ndarray,
    *,
    theta: Any = None,
    n_steps: int,
    renorm_every: int = 10,
    eps: float = 1.0e-6,
    seed: int = 0,
    jacobian_map: Callable[..., np.ndarray] | None = None,
) -> float:
    """Estimate the largest Lyapunov exponent with Benettin-style renormalization."""

    if n_steps < 1:
        raise ValueError("n_steps must be positive")
    if renorm_every < 1:
        raise ValueError("renorm_every must be positive")
    point = np.asarray(x0, dtype=float)
    if point.ndim != 1:
        raise ValueError("x0 must be one-dimensional")

    rng = np.random.default_rng(seed)
    direction = rng.normal(size=point.shape[0])
    direction_norm = float(np.linalg.norm(direction))
    if direction_norm <= 0.0:
        direction = np.ones(point.shape[0], dtype=float)
        direction_norm = float(np.linalg.norm(direction))
    direction = direction / direction_norm

    log_sum = 0.0
    consumed_steps = 0
    steps_since_renorm = 0
    x = point.copy()
    for _ in range(n_steps):
        jacobian = (
            _call_jacobian_map(jacobian_map, x, theta=theta)
            if jacobian_map is not None
            else finite_difference_map_jacobian(step_map, x, theta=theta, eps=eps)
        )
        direction = jacobian @ direction
        steps_since_renorm += 1
        x = _call_step_map(step_map, x, theta=theta)
        if steps_since_renorm >= renorm_every:
            log_sum += _renormalize_log_norm(direction)
            direction = _safe_unit(direction)
            consumed_steps += steps_since_renorm
            steps_since_renorm = 0

    if steps_since_renorm:
        log_sum += _renormalize_log_norm(direction)
        consumed_steps += steps_since_renorm

    return float(log_sum / max(consumed_steps, 1))


def build_attractor_analysis_result(
    trajectory: Sequence[Sequence[float]] | np.ndarray,
    variable_ids: Sequence[str],
    *,
    analysis_id: str | None = None,
    parameter_point: AttractorParameterPoint | Mapping[str, float] | None = None,
    model_ref: ArtifactRef | None = None,
    simulation_result_ref: SimulationResultRef | None = None,
    exec_plan_ref: ExecPlanRef | None = None,
    feedback_result_ref: FeedbackResultRef | None = None,
    tolerance: float = 1.0e-6,
    rtol: float = 1.0e-5,
    window: int = 32,
    max_period: int = 12,
    seeds_used: int | None = None,
    stochastic_model: bool = False,
    largest_lyapunov: float | None = None,
    notes: Sequence[str] = (),
) -> AttractorAnalysisResult:
    """Build an `AttractorAnalysisResult` from one reduced observable trajectory."""

    array = _as_2d_trajectory(trajectory)
    variables = _resolve_variable_ids(variable_ids, array.shape[1])
    regime = classify_terminal_regime(
        array,
        tolerance=tolerance,
        rtol=rtol,
        window=window,
        max_period=max_period,
        largest_lyapunov_exponent=largest_lyapunov,
    )
    result_id = analysis_id or _analysis_id(array, variables, _coerce_parameter_point(parameter_point))
    return AttractorAnalysisResult(
        analysis_id=result_id,
        model_ref=model_ref,
        simulation_result_ref=simulation_result_ref,
        exec_plan_ref=exec_plan_ref,
        feedback_result_ref=feedback_result_ref,
        state_projection=AttractorStateProjection(
            variables=variables,
            reduced_dimension=len(variables),
            quotient_notes=["reduced_observable_state"],
        ),
        parameter_point=_coerce_parameter_point(parameter_point),
        attractors=[
            _regime_to_attractor(
                regime,
                trajectory=array,
                variable_ids=variables,
                tolerance=tolerance,
                seeds_used=seeds_used,
            )
        ],
        uncertainty_summary=AttractorUncertaintySummary(
            stochastic_model=stochastic_model,
            seed_ensemble_size=seeds_used,
            unresolved_items=[] if regime.kind != "invariant_set" else ["possible_hidden_attractor"],
        ),
        provenance=AttractorAnalysisProvenance(
            toolchain=["polisyos.foundry.analysis.attractors"],
            derived_from=_derived_from_refs(
                model_ref=model_ref,
                simulation_result_ref=simulation_result_ref,
                exec_plan_ref=exec_plan_ref,
                feedback_result_ref=feedback_result_ref,
            ),
        ),
        notes=list(notes),
    )


def build_attractor_ensemble_analysis_result(
    trajectories: Sequence[Sequence[Sequence[float]]] | Sequence[np.ndarray],
    variable_ids: Sequence[str],
    *,
    initial_states: Sequence[Mapping[str, float]] | None = None,
    seeds: Sequence[int] | None = None,
    analysis_id: str | None = None,
    basin_id: str | None = None,
    parameter_point: AttractorParameterPoint | Mapping[str, float] | None = None,
    model_ref: ArtifactRef | None = None,
    simulation_result_ref: SimulationResultRef | None = None,
    exec_plan_ref: ExecPlanRef | None = None,
    feedback_result_ref: FeedbackResultRef | None = None,
    tolerance: float = 1.0e-6,
    rtol: float = 1.0e-5,
    window: int = 32,
    max_period: int = 12,
    stochastic_model: bool = False,
    notes: Sequence[str] = (),
) -> tuple[AttractorAnalysisResult, BasinMap]:
    """Build attractor and basin-map artifacts from a multi-start trajectory ensemble."""

    arrays = [_as_2d_trajectory(trajectory) for trajectory in trajectories]
    if not arrays:
        raise ValueError("trajectories must contain at least one trajectory")
    variables = _resolve_variable_ids(variable_ids, arrays[0].shape[1])
    for array in arrays:
        if array.shape[1] != len(variables):
            raise ValueError("all trajectories must have width matching variable_ids")

    seed_values = list(seeds or ())
    if seed_values and len(seed_values) != len(arrays):
        raise ValueError("seeds length must match trajectories length")
    supplied_initial_states = list(initial_states or ())
    if supplied_initial_states and len(supplied_initial_states) != len(arrays):
        raise ValueError("initial_states length must match trajectories length")

    parameter = _coerce_parameter_point(parameter_point)
    result_id = analysis_id or _ensemble_analysis_id(arrays, variables, parameter)
    basin_map_id = basin_id or _sidecar_id("basin", result_id)

    clusters: dict[str, dict[str, Any]] = {}
    basin_samples: list[BasinMapSample] = []
    for index, array in enumerate(arrays):
        regime = classify_terminal_regime(
            array,
            tolerance=tolerance,
            rtol=rtol,
            window=window,
            max_period=max_period,
        )
        key = _cluster_key(regime, array, tolerance=tolerance, variable_ids=variables)
        cluster = clusters.setdefault(
            key,
            {
                "regime": regime,
                "trajectory": array,
                "sample_indices": [],
            },
        )
        cluster["sample_indices"].append(index)
        basin_samples.append(
            BasinMapSample(
                sample_id=f"S{index + 1}",
                initial_state=_initial_state_for_sample(
                    array,
                    variables,
                    supplied=(
                        supplied_initial_states[index]
                        if supplied_initial_states
                        else None
                    ),
                ),
                attractor_id="",
                seed=seed_values[index] if seed_values else None,
                terminal_residual_norm=regime.residual_norm,
                confidence=1.0 if regime.kind != "invariant_set" else 0.5,
                notes=list(regime.notes),
            )
        )

    attractors: list[AttractorSummary] = []
    basin_measure_estimates: dict[str, float] = {}
    sample_to_attractor: dict[int, str] = {}
    for cluster_index, cluster in enumerate(clusters.values(), start=1):
        attractor_id = f"A{cluster_index}"
        sample_indices = list(cluster["sample_indices"])
        measure = float(len(sample_indices) / len(arrays))
        representative = _regime_to_attractor(
            cluster["regime"],
            trajectory=cluster["trajectory"],
            variable_ids=variables,
            tolerance=tolerance,
            seeds_used=len(set(seed_values)) if seed_values else None,
        )
        basin = representative.basin.model_copy(
            update={
                "estimation_method": "multi_start_ensemble",
                "basin_measure_estimate": measure,
            }
        )
        attractors.append(
            representative.model_copy(
                update={
                    "attractor_id": attractor_id,
                    "basin": basin,
                    "notes": [*representative.notes, f"samples={len(sample_indices)}"],
                }
            )
        )
        basin_measure_estimates[attractor_id] = measure
        for sample_index in sample_indices:
            sample_to_attractor[sample_index] = attractor_id

    basin_samples = [
        sample.model_copy(update={"attractor_id": sample_to_attractor[index]})
        for index, sample in enumerate(basin_samples)
    ]
    state_projection = AttractorStateProjection(
        variables=variables,
        reduced_dimension=len(variables),
        quotient_notes=["reduced_observable_state", "multi_start_ensemble"],
    )
    basin_map = BasinMap(
        basin_id=basin_map_id,
        analysis_id=result_id,
        state_projection=state_projection,
        sampling_method="multi_start_ensemble",
        samples=basin_samples,
        basin_measure_estimates=basin_measure_estimates,
    )
    result = AttractorAnalysisResult(
        analysis_id=result_id,
        model_ref=model_ref,
        simulation_result_ref=simulation_result_ref,
        exec_plan_ref=exec_plan_ref,
        feedback_result_ref=feedback_result_ref,
        state_projection=state_projection,
        parameter_point=parameter,
        attractors=attractors,
        uncertainty_summary=AttractorUncertaintySummary(
            stochastic_model=stochastic_model or bool(seed_values),
            seed_ensemble_size=len(set(seed_values)) if seed_values else None,
            unresolved_items=(
                ["possible_hidden_attractor"]
                if any(attractor.kind == "invariant_set" for attractor in attractors)
                else []
            ),
        ),
        provenance=AttractorAnalysisProvenance(
            toolchain=[
                "polisyos.foundry.analysis.attractors",
                "multi_start_ensemble",
            ],
            derived_from=_derived_from_refs(
                model_ref=model_ref,
                simulation_result_ref=simulation_result_ref,
                exec_plan_ref=exec_plan_ref,
                feedback_result_ref=feedback_result_ref,
            ),
        ),
        notes=[*notes, "basin_map_available"],
    )
    return result, basin_map


def build_feedback_attractor_analysis_result(
    feedback_result: FeedbackSolveResult,
    *,
    analysis_id: str | None = None,
    feedback_result_ref: FeedbackResultRef | None = None,
    jacobian_diagnostics: FeedbackJacobianDiagnostics | None = None,
    model_ref: ArtifactRef | None = None,
    simulation_result_ref: SimulationResultRef | None = None,
    exec_plan_ref: ExecPlanRef | None = None,
) -> AttractorAnalysisResult:
    """Convert a fixed-point feedback solve into the general attractor contract."""

    variables = list(feedback_result.final_state.variable_ids)
    final_attractor = _fixed_point_attractor_from_state(
        "A1",
        values=feedback_result.final_state.values,
        variable_ids=variables,
        residual_norm=_optional_float(feedback_result.final_diagnostics.get("residual_norm")),
        jacobian_diagnostics=jacobian_diagnostics,
        confirmed=feedback_result.converged,
        notes=["source:feedback_result"],
    )
    alternatives = [
        _fixed_point_attractor_from_state(
            f"A{index + 2}",
            values=candidate.state.values,
            variable_ids=variables,
            residual_norm=candidate.residual_norm,
            jacobian_diagnostics=None,
            confirmed=True,
            notes=["source:feedback_result_alternative", *candidate.notes],
        )
        for index, candidate in enumerate(feedback_result.alternative_fixed_points)
    ]
    result_id = analysis_id or _feedback_analysis_id(feedback_result)
    return AttractorAnalysisResult(
        analysis_id=result_id,
        model_ref=model_ref,
        simulation_result_ref=simulation_result_ref,
        exec_plan_ref=exec_plan_ref,
        feedback_result_ref=feedback_result_ref,
        state_projection=AttractorStateProjection(
            variables=variables,
            reduced_dimension=len(variables),
            quotient_notes=["feedback_state_projection"],
        ),
        attractors=[final_attractor, *alternatives],
        uncertainty_summary=AttractorUncertaintySummary(
            unresolved_items=[] if feedback_result.converged else ["feedback_solve_not_converged"],
        ),
        provenance=AttractorAnalysisProvenance(
            toolchain=["polisyos.foundry.feedback", "polisyos.foundry.analysis.attractors"],
            derived_from=_derived_from_refs(
                model_ref=model_ref,
                simulation_result_ref=simulation_result_ref,
                exec_plan_ref=exec_plan_ref,
                feedback_result_ref=feedback_result_ref,
            ),
        ),
        notes=["lifted_from_feedback_fixed_point"],
    )


def persist_attractor_analysis_result(
    store: FileSystemCAS,
    result: AttractorAnalysisResult,
    *,
    extra_inputs: Sequence[ArtifactRef | InputRef] = (),
) -> AttractorAnalysisResultRef:
    """Persist an attractor-analysis result as a Foundry CAS artifact."""

    ref = store.put_json(
        result,
        PutOptions(
            kind="foundry.attractor_analysis_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.AttractorAnalysisResult", version="1.0"),
            inputs=[
                *_result_input_refs(result),
                *_coerce_input_refs(extra_inputs, role_prefix="extra"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return AttractorAnalysisResultRef(artifact_id=ref.artifact_id)


def attach_abm_bifurcation_report_ref(
    store: FileSystemCAS,
    *,
    simulation_result_ref: SimulationResultRef,
    attractor_analysis_ref: AttractorAnalysisResultRef,
) -> ABMResultRef:
    """Persist an exact Phase-4 ``ABMResult`` with bifurcation report populated."""

    simulation_result = SimulationResult.model_validate(
        from_canonical_bytes(store.get_bytes(simulation_result_ref.artifact_id))
    )
    analysis = load_attractor_analysis_result(store, attractor_analysis_ref)
    abm_result = build_abm_result_from_simulation(
        simulation_result,
        attractor_analysis_ref=attractor_analysis_ref,
        bifurcation_count=len(analysis.bifurcations),
        attractor_count=len(analysis.attractors),
    )
    ref = store.put_json(
        abm_result,
        PutOptions(
            kind="ir.abm_result",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.ABMResult", version="1.0"),
            inputs=[
                InputRef(
                    artifact_id=simulation_result_ref.artifact_id,
                    role="artifact.simulation_result_ref",
                ),
                InputRef(
                    artifact_id=attractor_analysis_ref.artifact_id,
                    role="artifact.attractor_analysis_result_ref",
                ),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ABMResultRef.model_validate(
        {
            "artifact_id": ref.artifact_id,
            "kind": "ir.abm_result",
            "media_type": "application/json",
        }
    )


def load_attractor_analysis_result(
    store: FileSystemCAS,
    ref: AttractorAnalysisResultRef,
) -> AttractorAnalysisResult:
    """Load an attractor-analysis result from CAS."""

    return AttractorAnalysisResult.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_basin_map(
    store: FileSystemCAS,
    basin_map: BasinMap,
    *,
    extra_inputs: Sequence[ArtifactRef | InputRef] = (),
) -> BasinMapRef:
    """Persist a basin-map sidecar as a Foundry CAS artifact."""

    ref = store.put_json(
        basin_map,
        PutOptions(
            kind="foundry.basin_map",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.BasinMap", version="1.0"),
            inputs=_coerce_input_refs(extra_inputs, role_prefix="extra"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return BasinMapRef(artifact_id=ref.artifact_id)


def load_basin_map(store: FileSystemCAS, ref: BasinMapRef) -> BasinMap:
    """Load a basin-map sidecar from CAS."""

    return BasinMap.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def persist_continuation_branch(
    store: FileSystemCAS,
    branch: ContinuationBranch,
    *,
    extra_inputs: Sequence[ArtifactRef | InputRef] = (),
) -> ContinuationBranchRef:
    """Persist a continuation branch sidecar as a Foundry CAS artifact."""

    ref = store.put_json(
        branch,
        PutOptions(
            kind="foundry.continuation_branch",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.ContinuationBranch", version="1.0"),
            inputs=_coerce_input_refs(extra_inputs, role_prefix="extra"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ContinuationBranchRef(artifact_id=ref.artifact_id)


def load_continuation_branch(
    store: FileSystemCAS,
    ref: ContinuationBranchRef,
) -> ContinuationBranch:
    """Load a continuation branch sidecar from CAS."""

    return ContinuationBranch.model_validate(from_canonical_bytes(store.get_bytes(ref.artifact_id)))


def _validate_positive_controls(
    *,
    tolerance: float,
    rtol: float,
    window: int,
    max_period: int,
    divergence_bound: float,
) -> None:
    if tolerance < 0.0:
        raise ValueError("tolerance must be non-negative")
    if rtol < 0.0:
        raise ValueError("rtol must be non-negative")
    if window < 2:
        raise ValueError("window must be at least 2")
    if max_period < 2:
        raise ValueError("max_period must be at least 2")
    if divergence_bound <= 0.0:
        raise ValueError("divergence_bound must be positive")


def _as_2d_trajectory(trajectory: Sequence[Sequence[float]] | np.ndarray) -> np.ndarray:
    array = np.asarray(trajectory, dtype=float)
    if array.ndim == 1:
        array = array.reshape((-1, 1))
    if array.ndim != 2:
        raise ValueError("trajectory must be one- or two-dimensional")
    if array.shape[0] < 2:
        raise ValueError("trajectory must contain at least two time steps")
    return array


def _resolve_variable_ids(variable_ids: Sequence[str], width: int) -> list[str]:
    variables = list(variable_ids)
    if not variables:
        variables = [f"x{index}" for index in range(width)]
    if len(variables) != width:
        raise ValueError("variable_ids length must match trajectory width")
    return variables


def _effective_tolerance(tail: np.ndarray, *, tolerance: float, rtol: float) -> float:
    scale = max(1.0, float(np.max(np.abs(tail))))
    return float(tolerance + rtol * scale)


def _row_inf_norm(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.asarray([], dtype=float)
    return np.max(np.abs(values), axis=1)


def _fixed_residual(tail: np.ndarray) -> float:
    center = np.mean(tail, axis=0)
    diameter = float(np.max(_row_inf_norm(tail - center)))
    step_diffs = np.diff(tail, axis=0)
    step_residual = 0.0 if step_diffs.size == 0 else float(np.max(_row_inf_norm(step_diffs)))
    return max(diameter, step_residual)


def _detect_cycle_period(
    tail: np.ndarray,
    *,
    tolerance: float,
    max_period: int,
) -> tuple[int | None, float]:
    best_period: int | None = None
    best_residual = float("inf")
    max_candidate = min(max_period, max(2, tail.shape[0] // 2))
    for period in range(2, max_candidate + 1):
        if tail.shape[0] < period * 2:
            continue
        residuals = _row_inf_norm(tail[period:] - tail[:-period])
        residual = float(np.max(residuals))
        amplitude = float(np.max(_row_inf_norm(tail[-period:] - np.mean(tail[-period:], axis=0))))
        if residual < best_residual:
            best_period = period
            best_residual = residual
        if residual <= tolerance and amplitude > tolerance:
            return period, residual
    return None, best_residual if best_period is not None else float("inf")


def _call_step_map(step_map: Callable[..., np.ndarray], x: np.ndarray, *, theta: Any) -> np.ndarray:
    raw = step_map(x) if theta is None else step_map(x, theta)
    value = np.asarray(raw, dtype=float)
    if value.ndim != 1:
        raise ValueError("step_map must return a one-dimensional state")
    return value


def _call_jacobian_map(
    jacobian_map: Callable[..., np.ndarray],
    x: np.ndarray,
    *,
    theta: Any,
) -> np.ndarray:
    raw = jacobian_map(x) if theta is None else jacobian_map(x, theta)
    value = np.asarray(raw, dtype=float)
    if value.ndim != 2:
        raise ValueError("jacobian_map must return a two-dimensional matrix")
    return value


def _renormalize_log_norm(direction: np.ndarray) -> float:
    norm = float(np.linalg.norm(direction))
    return float(np.log(max(norm, 1.0e-300)))


def _safe_unit(direction: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(direction))
    if norm <= 0.0 or not np.isfinite(norm):
        return np.ones(direction.shape[0], dtype=float) / np.sqrt(float(direction.shape[0]))
    return direction / norm


def _coerce_parameter_point(
    parameter_point: AttractorParameterPoint | Mapping[str, float] | None,
) -> AttractorParameterPoint:
    if parameter_point is None:
        return AttractorParameterPoint()
    if isinstance(parameter_point, AttractorParameterPoint):
        return parameter_point
    items = list(parameter_point.items())
    return AttractorParameterPoint(
        names=[str(key) for key, _value in items],
        values=[float(value) for _key, value in items],
    )


def _analysis_id(
    trajectory: np.ndarray,
    variable_ids: Sequence[str],
    parameter_point: AttractorParameterPoint,
) -> str:
    digest = sha256()
    digest.update(np.ascontiguousarray(trajectory, dtype=float).tobytes())
    for variable_id in variable_ids:
        digest.update(variable_id.encode("utf-8"))
        digest.update(b"\0")
    for name, value in zip(parameter_point.names, parameter_point.values, strict=True):
        digest.update(name.encode("utf-8"))
        digest.update(repr(float(value)).encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _feedback_analysis_id(feedback_result: FeedbackSolveResult) -> str:
    digest = sha256()
    digest.update(repr(feedback_result.model_dump(mode="json")).encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def _ensemble_analysis_id(
    trajectories: Sequence[np.ndarray],
    variable_ids: Sequence[str],
    parameter_point: AttractorParameterPoint,
) -> str:
    digest = sha256()
    for trajectory in trajectories:
        digest.update(str(tuple(trajectory.shape)).encode("utf-8"))
        digest.update(np.ascontiguousarray(trajectory, dtype=float).tobytes())
        digest.update(b"\0")
    for variable_id in variable_ids:
        digest.update(variable_id.encode("utf-8"))
        digest.update(b"\0")
    for name, value in zip(parameter_point.names, parameter_point.values, strict=True):
        digest.update(name.encode("utf-8"))
        digest.update(repr(float(value)).encode("utf-8"))
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _sidecar_id(prefix: str, analysis_id: str) -> str:
    digest = sha256(f"{prefix}:{analysis_id}".encode()).hexdigest()
    return f"sha256:{digest}"


def _cluster_key(
    regime: TerminalRegime,
    trajectory: np.ndarray,
    *,
    tolerance: float,
    variable_ids: Sequence[str],
) -> str:
    if regime.equilibrium is not None:
        return repr((regime.kind, _quantized(regime.equilibrium, tolerance=tolerance)))
    if regime.period is not None:
        orbit = trajectory[-regime.period :]
        return repr(
            (
                regime.kind,
                regime.period,
                _quantized(orbit.reshape(-1), tolerance=tolerance),
            )
        )
    tail = trajectory[-min(32, trajectory.shape[0]) :]
    summary = [
        *_quantized(np.mean(tail, axis=0), tolerance=tolerance),
        *_quantized(np.min(tail, axis=0), tolerance=tolerance),
        *_quantized(np.max(tail, axis=0), tolerance=tolerance),
    ]
    return repr((regime.kind, tuple(variable_ids), tuple(summary)))


def _quantized(values: Sequence[float] | np.ndarray, *, tolerance: float) -> tuple[float, ...]:
    scale = max(float(tolerance), 1.0e-12)
    return tuple(float(round(float(value) / scale) * scale) for value in values)


def _initial_state_for_sample(
    trajectory: np.ndarray,
    variable_ids: Sequence[str],
    *,
    supplied: Mapping[str, float] | None,
) -> dict[str, float]:
    if supplied is not None:
        return {str(key): float(value) for key, value in supplied.items()}
    return {
        variable: float(value)
        for variable, value in zip(variable_ids, trajectory[0], strict=True)
    }


def _regime_to_attractor(
    regime: TerminalRegime,
    *,
    trajectory: np.ndarray,
    variable_ids: Sequence[str],
    tolerance: float,
    seeds_used: int | None,
) -> AttractorSummary:
    return AttractorSummary(
        attractor_id="A1",
        kind=regime.kind,
        existence_status=regime.existence_status,
        state_representation=_state_representation_for_regime(
            regime,
            trajectory=trajectory,
            variable_ids=variable_ids,
        ),
        stability=_stability_for_regime(regime),
        certificate=_certificate_for_regime(regime),
        basin=AttractorBasinEstimate(estimation_method="single_trajectory"),
        observables=AttractorObservableSummary(
            period=None if regime.period is None else float(regime.period),
            max_amplitude=_max_amplitude(trajectory),
            terminal_residual_norm=regime.residual_norm,
        ),
        uncertainty=AttractorUncertainty(
            seeds_used=seeds_used,
            numerical_tolerance=tolerance,
            finite_time_horizon=int(trajectory.shape[0]),
        ),
        notes=list(regime.notes),
    )


def _state_representation_for_regime(
    regime: TerminalRegime,
    *,
    trajectory: np.ndarray,
    variable_ids: Sequence[str],
) -> AttractorStateRepresentation:
    if regime.equilibrium is not None:
        return AttractorStateRepresentation(
            equilibrium=dict(zip(variable_ids, regime.equilibrium, strict=True))
        )
    if regime.period is not None:
        orbit = trajectory[-regime.period :]
        return AttractorStateRepresentation(
            orbit_points=[
                {variable: float(value) for variable, value in zip(variable_ids, row, strict=True)}
                for row in orbit
            ],
            summary={"period_steps": regime.period},
        )
    tail = trajectory[-min(32, trajectory.shape[0]) :]
    return AttractorStateRepresentation(
        summary={
            "terminal_mean": {
                variable: float(value)
                for variable, value in zip(variable_ids, np.mean(tail, axis=0), strict=True)
            },
            "terminal_min": {
                variable: float(value)
                for variable, value in zip(variable_ids, np.min(tail, axis=0), strict=True)
            },
            "terminal_max": {
                variable: float(value)
                for variable, value in zip(variable_ids, np.max(tail, axis=0), strict=True)
            },
        }
    )


def _stability_for_regime(regime: TerminalRegime) -> AttractorStability:
    local_class: Literal[
        "asymptotically_stable",
        "orbitally_stable",
        "neutral",
        "unstable",
        "mixed",
        "unknown",
    ] = "unknown"
    if regime.kind == "chaotic":
        local_class = "mixed"
    elif regime.kind == "divergent":
        local_class = "unstable"
    elif regime.kind == "limit_cycle":
        local_class = "orbitally_stable"
    elif regime.kind == "fixed_point" and regime.largest_lyapunov_exponent is not None:
        local_class = "asymptotically_stable" if regime.largest_lyapunov_exponent < 0.0 else "neutral"
    return AttractorStability(
        local_class=local_class,
        largest_lyapunov_exponent=regime.largest_lyapunov_exponent,
    )


def _certificate_for_regime(regime: TerminalRegime) -> AttractorCertificate:
    if regime.kind == "divergent":
        return AttractorCertificate(
            type="trajectory_diagnostic",
            status="failed",
            evidence_strength=0.0,
            notes=["divergent_regime_is_not_an_attractor"],
        )
    strength = {
        "fixed_point": 0.7,
        "limit_cycle": 0.65,
        "chaotic": 0.55,
        "torus": 0.4,
        "invariant_set": 0.35,
    }.get(regime.kind, 0.3)
    notes = ["finite_time_numerical_evidence"]
    if regime.kind == "chaotic":
        notes.append("positive_lyapunov_is_not_asymptotic_stability_certificate")
    return AttractorCertificate(
        type="trajectory_diagnostic",
        status="numerically_supported",
        evidence_strength=strength,
        notes=notes,
    )


def _max_amplitude(trajectory: np.ndarray) -> float:
    tail = trajectory[-min(32, trajectory.shape[0]) :]
    centered = tail - np.mean(tail, axis=0)
    return float(np.max(_row_inf_norm(centered)))


def _fixed_point_attractor_from_state(
    attractor_id: str,
    *,
    values: Sequence[float],
    variable_ids: Sequence[str],
    residual_norm: float | None,
    jacobian_diagnostics: FeedbackJacobianDiagnostics | None,
    confirmed: bool,
    notes: Sequence[str],
) -> AttractorSummary:
    spectral_radius = None if jacobian_diagnostics is None else jacobian_diagnostics.spectral_radius
    local_class = _local_class_from_spectral_radius(spectral_radius)
    return AttractorSummary(
        attractor_id=attractor_id,
        kind="fixed_point",
        existence_status="numerically_confirmed" if confirmed else "candidate",
        state_representation=AttractorStateRepresentation(
            equilibrium={
                variable: float(value)
                for variable, value in zip(variable_ids, values, strict=True)
            }
        ),
        stability=AttractorStability(
            local_class=local_class,
            spectral_radius=spectral_radius,
            diagnostics=(
                {}
                if jacobian_diagnostics is None
                else jacobian_diagnostics.model_dump(mode="json", exclude_none=True)
            ),
        ),
        certificate=AttractorCertificate(
            type="feedback_fixed_point_solver",
            status="numerically_supported" if confirmed else "not_attempted",
            evidence_strength=0.75 if confirmed else 0.25,
        ),
        observables=AttractorObservableSummary(terminal_residual_norm=residual_norm),
        notes=list(notes),
    )


def _local_class_from_spectral_radius(
    spectral_radius: float | None,
) -> Literal[
    "asymptotically_stable",
    "orbitally_stable",
    "neutral",
    "unstable",
    "mixed",
    "unknown",
]:
    if spectral_radius is None:
        return "unknown"
    if spectral_radius < 0.98:
        return "asymptotically_stable"
    if spectral_radius <= 1.02:
        return "neutral"
    return "unstable"


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _derived_from_refs(
    *,
    model_ref: ArtifactRef | None,
    simulation_result_ref: SimulationResultRef | None,
    exec_plan_ref: ExecPlanRef | None,
    feedback_result_ref: FeedbackResultRef | None,
) -> list[str]:
    refs = [model_ref, simulation_result_ref, exec_plan_ref, feedback_result_ref]
    return [f"{ref.kind}:{ref.artifact_id}" for ref in refs if ref is not None]


def _result_input_refs(result: AttractorAnalysisResult) -> list[InputRef]:
    refs: list[tuple[str, ArtifactRef | None]] = [
        ("model_ref", result.model_ref),
        ("simulation_result_ref", result.simulation_result_ref),
        ("exec_plan_ref", result.exec_plan_ref),
        ("feedback_result_ref", result.feedback_result_ref),
    ]
    return [
        InputRef(artifact_id=ref.artifact_id, role=role)
        for role, ref in refs
        if ref is not None
    ]


def _coerce_input_refs(
    inputs: Sequence[ArtifactRef | InputRef],
    *,
    role_prefix: str,
) -> list[InputRef]:
    coerced: list[InputRef] = []
    for index, ref in enumerate(inputs):
        if isinstance(ref, InputRef):
            coerced.append(ref)
        else:
            coerced.append(
                InputRef(
                    artifact_id=ref.artifact_id,
                    role=f"{role_prefix}:{ref.kind}:{index}",
                )
            )
    return coerced


__all__ = [
    "AttractorKind",
    "ExistenceStatus",
    "TerminalRegime",
    "build_attractor_analysis_result",
    "build_attractor_ensemble_analysis_result",
    "build_feedback_attractor_analysis_result",
    "attach_abm_bifurcation_report_ref",
    "classify_terminal_regime",
    "finite_difference_map_jacobian",
    "largest_lyapunov_exponent",
    "load_attractor_analysis_result",
    "load_basin_map",
    "load_continuation_branch",
    "persist_attractor_analysis_result",
    "persist_basin_map",
    "persist_continuation_branch",
]
