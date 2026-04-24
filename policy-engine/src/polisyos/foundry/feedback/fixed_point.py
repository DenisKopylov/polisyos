"""Hybrid fixed-point solver for feedback-consistent Foundry execution."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

from .config import PreparedFeedbackConfig, project_bounds
from .diagnostics import (
    SolveTraceRecord,
    converged,
    detect_divergence,
    detect_stagnation,
    detect_two_cycle,
    scaled_inf_norm,
)
from .jacobian import JacobianSummary, finite_difference_jacobian, summarize_jacobian


@dataclass(frozen=True)
class MapEvaluation:
    """Evaluation of the fixed-point map at one iterate."""

    map_value: np.ndarray
    diagnostics: dict[str, Any]
    budget_gap: float | None = None
    noise_sd: float | None = None


FeedbackMap = Callable[[np.ndarray], MapEvaluation | np.ndarray]


@dataclass(frozen=True)
class AlternativeSolution:
    """One converged alternative fixed point discovered by multi-start solve."""

    solution: np.ndarray
    residual_norm: float | None
    diagnostics: dict[str, Any]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolveOutcome:
    """Numeric solve outcome returned to the execute facade."""

    converged: bool
    status: str
    failure_reason: str | None
    solution: np.ndarray
    initial: np.ndarray
    trace: tuple[SolveTraceRecord, ...]
    final_residual_norm: float | None
    final_step_norm: float | None
    final_budget_gap: float | None
    final_diagnostics: dict[str, Any]
    jacobian: JacobianSummary | None
    alternative_solutions: tuple[AlternativeSolution, ...] = ()


@dataclass(frozen=True)
class _SingleStartOutcome:
    converged: bool
    status: str
    failure_reason: str | None
    start: np.ndarray
    solution: np.ndarray
    trace: tuple[SolveTraceRecord, ...]
    final_residual_norm: float | None
    final_step_norm: float | None
    final_budget_gap: float | None
    final_diagnostics: dict[str, Any]


def solve_fixed_point(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
) -> SolveOutcome:
    """Solve `x = T(x)` using homotopy, damped Picard, safeguarded Anderson, and Newton."""

    cfg = prepared.config.solver
    starts = [np.asarray(prepared.initial_values, dtype=float)]
    starts.extend(np.asarray(start, dtype=float) for start in cfg.multi_start_values)
    attempts = [
        _solve_single_start(
            prepared=prepared,
            evaluate_map=evaluate_map,
            start=project_bounds(prepared, start),
        )
        for start in starts
    ]

    converged_attempts = [attempt for attempt in attempts if attempt.converged]
    if converged_attempts:
        unique_attempts = _deduplicate_attempts(converged_attempts, prepared=prepared)
        chosen = min(
            unique_attempts,
            key=lambda attempt: (
                float(attempt.final_residual_norm or 0.0),
                scaled_inf_norm(attempt.start - prepared.initial_values, prepared=prepared),
            ),
        )
        jacobian_summary = None
        if cfg.compute_jacobian_diagnostics:
            jacobian_summary = _compute_jacobian_summary(
                evaluate_map=evaluate_map,
                x=chosen.solution,
                prepared=prepared,
            )
        alternatives = ()
        if cfg.store_alternative_fixed_points:
            alternatives = tuple(
                AlternativeSolution(
                    solution=attempt.solution.copy(),
                    residual_norm=attempt.final_residual_norm,
                    diagnostics=dict(attempt.final_diagnostics),
                    notes=(_start_distance_note(attempt, prepared=prepared),),
                )
                for attempt in unique_attempts
                if attempt is not chosen
            )
        final_diagnostics = dict(chosen.final_diagnostics)
        if len(unique_attempts) > 1:
            final_diagnostics["multiple_fixed_points"] = 1
        if jacobian_summary is not None:
            final_diagnostics["near_bifurcation"] = int(jacobian_summary.near_bifurcation)
        return SolveOutcome(
            converged=True,
            status="converged",
            failure_reason=None,
            solution=chosen.solution.copy(),
            initial=prepared.initial_values.copy(),
            trace=chosen.trace,
            final_residual_norm=chosen.final_residual_norm,
            final_step_norm=chosen.final_step_norm,
            final_budget_gap=chosen.final_budget_gap,
            final_diagnostics=final_diagnostics,
            jacobian=jacobian_summary,
            alternative_solutions=alternatives,
        )

    best_attempt = min(
        attempts,
        key=lambda attempt: (
            float("inf") if attempt.final_residual_norm is None else attempt.final_residual_norm
        ),
    )
    return SolveOutcome(
        converged=False,
        status=best_attempt.status,
        failure_reason=best_attempt.failure_reason,
        solution=best_attempt.solution.copy(),
        initial=prepared.initial_values.copy(),
        trace=best_attempt.trace,
        final_residual_norm=best_attempt.final_residual_norm,
        final_step_norm=best_attempt.final_step_norm,
        final_budget_gap=best_attempt.final_budget_gap,
        final_diagnostics=dict(best_attempt.final_diagnostics),
        jacobian=None,
        alternative_solutions=(),
    )


def _solve_single_start(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
    start: np.ndarray,
) -> _SingleStartOutcome:
    cfg = prepared.config.solver
    anchor = project_bounds(prepared, start)
    x_stage = project_bounds(prepared, start)
    trace: list[SolveTraceRecord] = []
    last_diagnostics: dict[str, Any] = {}
    final_residual_norm: float | None = None
    final_step_norm: float | None = None
    final_budget_gap: float | None = None

    for alpha in cfg.homotopy_grid:
        x = x_stage.copy()
        damping = float(cfg.damping_init)
        restarts = 0
        history_r: list[np.ndarray] = []
        stage_records_start = len(trace)

        for iteration in range(cfg.max_iter):
            current_eval = _evaluate_stage_map(
                evaluate_map,
                x,
                alpha=alpha,
                initial=anchor,
            )
            next_value = current_eval.map_value
            residual = next_value - x
            residual_norm = scaled_inf_norm(residual, prepared=prepared)
            last_diagnostics = dict(current_eval.diagnostics)
            final_residual_norm = residual_norm
            final_step_norm = scaled_inf_norm(next_value - x, prepared=prepared)
            final_budget_gap = current_eval.budget_gap

            budget_gap = current_eval.budget_gap if alpha == cfg.homotopy_grid[-1] else None
            if converged(
                x,
                next_value,
                residual,
                prepared=prepared,
                budget_gap=budget_gap,
            ):
                trace.append(
                    SolveTraceRecord(
                        stage_alpha=float(alpha),
                        iteration=iteration,
                        residual_norm=residual_norm,
                        step_norm=0.0,
                        damping=damping,
                        method="stop",
                        accepted=True,
                        iterate=x.copy(),
                        residual=residual.copy(),
                        diagnostics=_augment_diagnostics(current_eval),
                        notes=("converged",),
                    )
                )
                x_stage = project_bounds(prepared, next_value)
                break

            method = "picard"
            accepted = False
            candidate = project_bounds(prepared, x + damping * residual)
            candidate_eval: MapEvaluation | None = None

            if cfg.mode in {"anderson", "hybrid"} and iteration >= cfg.anderson_start:
                anderson_candidate = _anderson_candidate(x, residual, history_r)
                if anderson_candidate is not None:
                    method = "anderson"
                    trial = project_bounds(prepared, anderson_candidate)
                    trial_eval = _evaluate_stage_map(
                        evaluate_map,
                        trial,
                        alpha=alpha,
                        initial=anchor,
                    )
                    trial_residual = trial_eval.map_value - trial
                    if scaled_inf_norm(trial_residual, prepared=prepared) <= (
                        cfg.anderson_accept_ratio * residual_norm
                    ):
                        candidate = trial
                        candidate_eval = trial_eval
                        accepted = True
                    else:
                        method = "picard_fallback"

            if (
                not accepted
                and cfg.mode == "hybrid"
                and iteration >= cfg.newton_start
                and _is_stagnating(trace[stage_records_start:], prepared=prepared)
            ):
                method = "newton"
                newton_candidate = _newton_candidate(
                    evaluate_map=evaluate_map,
                    x=x,
                    alpha=alpha,
                    current_map=next_value,
                    prepared=prepared,
                    anchor=anchor,
                )
                candidate = project_bounds(prepared, newton_candidate)
                candidate_eval = _evaluate_stage_map(
                    evaluate_map,
                    candidate,
                    alpha=alpha,
                    initial=anchor,
                )

            if candidate_eval is None:
                candidate_eval = _evaluate_stage_map(
                    evaluate_map,
                    candidate,
                    alpha=alpha,
                    initial=anchor,
                )

            candidate_residual = candidate_eval.map_value - candidate
            candidate_norm = scaled_inf_norm(candidate_residual, prepared=prepared)
            step_norm = scaled_inf_norm(candidate - x, prepared=prepared)

            if candidate_norm < residual_norm:
                x = candidate
                accepted = True
                history_r.append(candidate_residual.copy())
                if len(history_r) > cfg.anderson_memory:
                    history_r.pop(0)
                last_diagnostics = dict(candidate_eval.diagnostics)
                final_residual_norm = candidate_norm
                final_step_norm = step_norm
                final_budget_gap = candidate_eval.budget_gap
            else:
                damping = max(float(cfg.damping_min), 0.5 * damping)
                restarts += 1
                history_r.clear()

            trace.append(
                SolveTraceRecord(
                    stage_alpha=float(alpha),
                    iteration=iteration,
                    residual_norm=residual_norm,
                    step_norm=step_norm,
                    damping=damping,
                    method=method,
                    accepted=accepted,
                    iterate=x.copy(),
                    residual=candidate_residual.copy() if accepted else residual.copy(),
                    diagnostics=_augment_diagnostics(candidate_eval if accepted else current_eval),
                    notes=tuple(_notes_for_record(restarts=restarts, accepted=accepted)),
                )
            )

            if restarts > cfg.max_restarts:
                status, reason, diag = _classify_failure(
                    trace[stage_records_start:],
                    prepared=prepared,
                    fallback="restarts_exhausted",
                )
                last_diagnostics.update(diag)
                return _SingleStartOutcome(
                    converged=False,
                    status=status,
                    failure_reason=reason,
                    start=start.copy(),
                    solution=x.copy(),
                    trace=tuple(trace),
                    final_residual_norm=final_residual_norm,
                    final_step_norm=final_step_norm,
                    final_budget_gap=final_budget_gap,
                    final_diagnostics=last_diagnostics,
                )
        else:
            status, reason, diag = _classify_failure(
                trace[stage_records_start:],
                prepared=prepared,
                fallback="max_iter_exceeded",
            )
            last_diagnostics.update(diag)
            return _SingleStartOutcome(
                converged=False,
                status=status,
                failure_reason=reason,
                start=start.copy(),
                solution=x.copy(),
                trace=tuple(trace),
                final_residual_norm=final_residual_norm,
                final_step_norm=final_step_norm,
                final_budget_gap=final_budget_gap,
                final_diagnostics=last_diagnostics,
            )

    return _SingleStartOutcome(
        converged=True,
        status="converged",
        failure_reason=None,
        start=start.copy(),
        solution=x_stage.copy(),
        trace=tuple(trace),
        final_residual_norm=final_residual_norm,
        final_step_norm=final_step_norm,
        final_budget_gap=final_budget_gap,
        final_diagnostics=last_diagnostics,
    )


def _evaluate_stage_map(
    evaluate_map: FeedbackMap,
    x: np.ndarray,
    *,
    alpha: float,
    initial: np.ndarray,
) -> MapEvaluation:
    raw = evaluate_map(np.asarray(x, dtype=float))
    if not isinstance(raw, MapEvaluation):
        raw = MapEvaluation(map_value=np.asarray(raw, dtype=float), diagnostics={})
    blended = np.asarray(initial, dtype=float) + alpha * (
        np.asarray(raw.map_value, dtype=float) - np.asarray(initial, dtype=float)
    )
    diagnostics = dict(raw.diagnostics)
    diagnostics["homotopy_alpha"] = float(alpha)
    return MapEvaluation(
        map_value=blended,
        diagnostics=diagnostics,
        budget_gap=raw.budget_gap,
        noise_sd=raw.noise_sd,
    )


def _anderson_candidate(
    x: np.ndarray,
    residual: np.ndarray,
    history_r: list[np.ndarray],
) -> np.ndarray | None:
    if len(history_r) < 2:
        return None
    try:
        differences = np.column_stack(
            [history_r[index + 1] - history_r[index] for index in range(len(history_r) - 1)]
        )
        gamma, *_ = np.linalg.lstsq(differences, residual - history_r[-1], rcond=None)
        return x + residual - differences @ gamma
    except np.linalg.LinAlgError:
        return None


def _newton_candidate(
    *,
    evaluate_map: FeedbackMap,
    x: np.ndarray,
    alpha: float,
    current_map: np.ndarray,
    prepared: PreparedFeedbackConfig,
    anchor: np.ndarray,
) -> np.ndarray:
    def stage_eval(point: np.ndarray) -> np.ndarray:
        return _evaluate_stage_map(
            evaluate_map,
            point,
            alpha=alpha,
            initial=anchor,
        ).map_value

    jacobian = finite_difference_jacobian(
        stage_eval,
        x,
        prepared=prepared,
        baseline_map=current_map,
    )
    residual = current_map - x
    system = jacobian - np.eye(jacobian.shape[0], dtype=float)
    try:
        step = np.linalg.solve(system, -residual)
    except np.linalg.LinAlgError:
        regularized = system.T @ system + 1.0e-6 * np.eye(system.shape[0], dtype=float)
        rhs = -system.T @ residual
        step = np.linalg.solve(regularized, rhs)

    norm = scaled_inf_norm(step, prepared=prepared)
    if norm > prepared.config.solver.trust_radius_init:
        step = step * (prepared.config.solver.trust_radius_init / max(norm, 1.0e-12))
    return x + step


def _compute_jacobian_summary(
    *,
    evaluate_map: FeedbackMap,
    x: np.ndarray,
    prepared: PreparedFeedbackConfig,
) -> JacobianSummary:
    point = np.asarray(x, dtype=float)
    baseline = evaluate_map(point)
    if not isinstance(baseline, MapEvaluation):
        baseline = MapEvaluation(map_value=np.asarray(baseline, dtype=float), diagnostics={})
    jacobian = finite_difference_jacobian(
        lambda candidate: _coerce_map_value(evaluate_map(np.asarray(candidate, dtype=float))),
        point,
        prepared=prepared,
        baseline_map=baseline.map_value,
    )
    return summarize_jacobian(jacobian)


def _coerce_map_value(result: MapEvaluation | np.ndarray) -> np.ndarray:
    if isinstance(result, MapEvaluation):
        return np.asarray(result.map_value, dtype=float)
    return np.asarray(result, dtype=float)


def _is_stagnating(
    records: list[SolveTraceRecord],
    *,
    prepared: PreparedFeedbackConfig,
) -> bool:
    return detect_stagnation(records, patience=prepared.config.solver.stagnation_patience)


def _notes_for_record(*, restarts: int, accepted: bool) -> list[str]:
    notes: list[str] = []
    if accepted:
        notes.append("accepted")
    if restarts:
        notes.append(f"restarts={restarts}")
    return notes


def _augment_diagnostics(evaluation: MapEvaluation) -> dict[str, Any]:
    diagnostics = dict(evaluation.diagnostics)
    if evaluation.budget_gap is not None:
        diagnostics["budget_gap"] = float(evaluation.budget_gap)
    if evaluation.noise_sd is not None:
        diagnostics["noise_sd"] = float(evaluation.noise_sd)
    return diagnostics


def _classify_failure(
    records: list[SolveTraceRecord],
    *,
    prepared: PreparedFeedbackConfig,
    fallback: str,
) -> tuple[str, str, dict[str, int]]:
    cfg = prepared.config.solver
    oscillating = detect_two_cycle(
        records,
        patience=cfg.oscillation_patience,
        tolerance=cfg.fixed_point_merge_tol,
    )
    diverging = detect_divergence(records, patience=cfg.divergence_patience)
    stagnating = detect_stagnation(records, patience=cfg.stagnation_patience)
    diagnostics = {
        "oscillation_detected": int(oscillating),
        "divergence_detected": int(diverging),
        "stagnation_detected": int(stagnating),
    }
    if oscillating:
        return (
            "oscillating",
            "Detected stable two-cycle / oscillation in feedback iterates",
            diagnostics,
        )
    if diverging:
        return "diverged", "Residual norms grew over the recent iterations", diagnostics
    if stagnating:
        return "stagnated", "Residual norms plateaued without satisfying tolerances", diagnostics
    if fallback == "restarts_exhausted":
        return (
            "restarts_exhausted",
            "Repeated non-improving steps exhausted solver restarts",
            diagnostics,
        )
    return (
        "max_iter_exceeded",
        "Solver reached max_iter before satisfying convergence tolerances",
        diagnostics,
    )


def _deduplicate_attempts(
    attempts: list[_SingleStartOutcome],
    *,
    prepared: PreparedFeedbackConfig,
) -> list[_SingleStartOutcome]:
    unique: list[_SingleStartOutcome] = []
    tolerance = prepared.config.solver.fixed_point_merge_tol
    for attempt in attempts:
        if any(
            scaled_inf_norm(attempt.solution - existing.solution, prepared=prepared) <= tolerance
            for existing in unique
        ):
            continue
        unique.append(attempt)
    return unique


def _start_distance_note(
    attempt: _SingleStartOutcome,
    *,
    prepared: PreparedFeedbackConfig,
) -> str:
    distance = scaled_inf_norm(attempt.start - prepared.initial_values, prepared=prepared)
    return f"start_distance={distance:.6g}"
