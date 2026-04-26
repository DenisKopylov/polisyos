"""Multiplicity exploration built on top of the local fixed-point solver."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from polisyos.core.contracts.foundry import (
    BasinEstimate,
    BifurcationCandidate,
    EquilibriumCandidate,
    EquilibriumCandidateJacobian,
    EquilibriumMultiplicityReport,
    UnresolvedEquilibriumStart,
)

from .basin import (
    BasinCluster,
    estimate_basin_shares,
    finite_start_bounds,
    latin_hypercube_starts,
)
from .config import (
    PreparedFeedbackConfig,
    prepare_feedback_config,
    project_bounds,
    snapshot_from_vector,
)
from .continuation import (
    ContinuationPoint,
    build_nearest_neighbor_branches,
    pseudo_arclength_predictor,
)
from .diagnostics import scaled_inf_norm
from .fixed_point import FeedbackMap, SolveOutcome, solve_fixed_point
from .jacobian import JacobianSummary
from .reporting import (
    build_multiplicity_report,
    build_search_protocol,
    summarize_search_diagnostics,
)


@dataclass
class _Cluster:
    equilibrium_id: str
    branch_id: str
    representative: SolveOutcome
    members: list[SolveOutcome] = field(default_factory=list)

    @property
    def solution(self) -> np.ndarray:
        return self.representative.solution


@dataclass(frozen=True)
class MultiplicityExplorer:
    """Orchestrate multi-start fixed-point exploration for one prepared config."""

    prepared: PreparedFeedbackConfig
    evaluate_map: FeedbackMap
    model_id: str = "feedback_fixed_point"
    parameter_hash: str | None = None
    runtime_refs: tuple[str, ...] = ()
    git_sha: str = "unknown"
    continuation_map_factory: Callable[[float], FeedbackMap] | None = None

    def run(self, *, base_outcome: SolveOutcome | None = None) -> EquilibriumMultiplicityReport:
        """Run the configured exploration and return a structured report."""

        return discover_equilibria(
            prepared=self.prepared,
            evaluate_map=self.evaluate_map,
            base_outcome=base_outcome,
            model_id=self.model_id,
            parameter_hash=self.parameter_hash,
            runtime_refs=self.runtime_refs,
            git_sha=self.git_sha,
            continuation_map_factory=self.continuation_map_factory,
        )


def discover_equilibria(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
    base_outcome: SolveOutcome | None = None,
    model_id: str = "feedback_fixed_point",
    parameter_hash: str | None = None,
    runtime_refs: Iterable[str] = (),
    git_sha: str = "unknown",
    continuation_map_factory: Callable[[float], FeedbackMap] | None = None,
) -> EquilibriumMultiplicityReport:
    """Run a bounded multi-start search and return a structured multiplicity report.

    This first-phase explorer deliberately treats `solve_fixed_point()` as the
    local solver. It adds deterministic start generation, clustering, local
    stability labels, bifurcation flags, and optional basin-share reruns.
    """

    cfg = prepared.config.solver
    if (
        cfg.multiplicity_mode == "continuation"
        and cfg.continuation_grid
        and continuation_map_factory is not None
    ):
        return _discover_equilibria_continuation(
            prepared=prepared,
            evaluate_map=evaluate_map,
            continuation_map_factory=continuation_map_factory,
            base_outcome=base_outcome,
            model_id=model_id,
            parameter_hash=parameter_hash,
            runtime_refs=runtime_refs,
            git_sha=git_sha,
        )

    starts = _build_discovery_starts(prepared)
    if base_outcome is not None and starts:
        starts = starts[1:]
    outcomes = [
        _solve_from_start(prepared=prepared, evaluate_map=evaluate_map, start=start)
        for start in starts
    ]

    if base_outcome is not None:
        outcomes.insert(0, base_outcome)

    clusters = _cluster_outcomes(
        [outcome for outcome in outcomes if outcome.converged],
        prepared=prepared,
    )
    unresolved = [
        _unresolved_start(prepared, outcome)
        for outcome in outcomes
        if not outcome.converged
    ]

    basin_estimates: list[BasinEstimate] = []
    basin_hits: dict[str, int] = {cluster.equilibrium_id: 0 for cluster in clusters}
    if cfg.basin_draws > 0 and clusters:
        basin_estimates, basin_hits, basin_unresolved = _estimate_basins(
            prepared=prepared,
            evaluate_map=evaluate_map,
            clusters=clusters,
        )
        unresolved.extend(basin_unresolved)

    candidates: list[EquilibriumCandidate] = []
    bifurcation_candidates: list[BifurcationCandidate] = []
    for cluster in clusters:
        summary = cluster.representative.jacobian
        jacobian = _candidate_jacobian(summary)
        stability = _classify_stability(
            summary,
            spectral_radius_warn_tol=cfg.spectral_radius_warn_tol,
        )
        basin = next(
            (
                estimate
                for estimate in basin_estimates
                if estimate.equilibrium_id == cluster.equilibrium_id
            ),
            None,
        )
        candidate = EquilibriumCandidate(
            equilibrium_id=cluster.equilibrium_id,
            state=snapshot_from_vector(
                prepared,
                cluster.solution,
                notes=["multiplicity_cluster_representative"],
            ),
            residual_norm=(
                None
                if cluster.representative.final_residual_norm is None
                else float(cluster.representative.final_residual_norm)
            ),
            step_norm=(
                None
                if cluster.representative.final_step_norm is None
                else float(cluster.representative.final_step_norm)
            ),
            jacobian=jacobian,
            local_stability=stability,
            branch_id=cluster.branch_id,
            basin_share_hat=None if basin is None else basin.share_hat,
            basin_ci_95=None if basin is None else basin.ci_95,
            discovered_from_starts=max(1, len(cluster.members) + basin_hits[cluster.equilibrium_id]),
            diagnostics=dict(cluster.representative.final_diagnostics),
            notes=_candidate_notes(summary),
        )
        candidates.append(candidate)
        bifurcation_candidates.extend(
            _bifurcation_candidates(
                equilibrium_id=cluster.equilibrium_id,
                summary=summary,
                lambda_value=_report_lambda(prepared),
            )
        )

    branch_lambda = _report_lambda(prepared) or 0.0
    branches = build_nearest_neighbor_branches(
        [
            (
                branch_lambda,
                [(cluster.equilibrium_id, cluster.solution) for cluster in clusters],
            )
        ],
        merge_tol=prepared.config.solver.fixed_point_merge_tol,
    )

    diagnostics = summarize_search_diagnostics(
        outcomes,
        num_equilibria=len(clusters),
        num_unresolved=len(unresolved),
    )
    protocol = build_search_protocol(
        mode=_report_mode(prepared),
        start_domain=_start_domain_payload(prepared),
        n_attempts=len(outcomes),
        continuation_parameter=cfg.continuation_parameter,
        continuation_grid=list(cfg.continuation_grid),
        merge_tol=cfg.fixed_point_merge_tol,
        residual_tol=cfg.atol,
        basin_draws=cfg.basin_draws,
    )
    return build_multiplicity_report(
        model_id=model_id,
        parameter_hash=parameter_hash,
        search_protocol=protocol,
        equilibria=candidates,
        branches=branches,
        bifurcation_candidates=bifurcation_candidates,
        basin_estimates=basin_estimates,
        unresolved_starts=unresolved,
        global_diagnostics=diagnostics,
        runtime_refs=runtime_refs,
        git_sha=git_sha,
        random_seed=cfg.basin_seed,
        notes=[
            "multiplicity_mode:baseline"
            if cfg.multiplicity_mode == "off"
            else f"multiplicity_mode:{cfg.multiplicity_mode}",
            "continuation_engine:map_factory_required"
            if cfg.multiplicity_mode == "continuation"
            else "continuation_engine:not_requested",
        ],
    )


def _discover_equilibria_continuation(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
    continuation_map_factory: Callable[[float], FeedbackMap],
    base_outcome: SolveOutcome | None,
    model_id: str,
    parameter_hash: str | None,
    runtime_refs: Iterable[str],
    git_sha: str,
) -> EquilibriumMultiplicityReport:
    cfg = prepared.config.solver
    lambda_values = [float(value) for value in cfg.continuation_grid]
    all_outcomes: list[SolveOutcome] = []
    all_unresolved: list[UnresolvedEquilibriumStart] = []
    rounds: list[tuple[float, list[_Cluster]]] = []
    next_equilibrium_index = 1

    for lambda_index, lambda_value in enumerate(lambda_values):
        starts = _continuation_starts(prepared, rounds, next_lambda=lambda_value)
        lambda_map = continuation_map_factory(lambda_value)
        outcomes = [
            _solve_from_start(prepared=prepared, evaluate_map=lambda_map, start=start)
            for start in starts
        ]
        if lambda_index == 0 and base_outcome is not None and lambda_map is evaluate_map:
            outcomes.insert(0, base_outcome)

        clusters = _cluster_outcomes(
            [outcome for outcome in outcomes if outcome.converged],
            prepared=prepared,
        )
        for cluster in clusters:
            cluster.equilibrium_id = f"eq_{next_equilibrium_index:03d}"
            next_equilibrium_index += 1

        all_outcomes.extend(outcomes)
        all_unresolved.extend(
            _unresolved_start(prepared, outcome)
            for outcome in outcomes
            if not outcome.converged
        )
        rounds.append((lambda_value, clusters))

    points_by_lambda = [
        (
            lambda_value,
            [(cluster.equilibrium_id, cluster.solution) for cluster in clusters],
        )
        for lambda_value, clusters in rounds
    ]
    branches = build_nearest_neighbor_branches(
        points_by_lambda,
        merge_tol=float("inf"),
    )
    branch_lookup = {
        point.equilibrium_id: branch.branch_id
        for branch in branches
        for point in branch.points
    }

    basin_estimates: list[BasinEstimate] = []
    basin_hits: dict[str, int] = {
        cluster.equilibrium_id: 0 for _, clusters in rounds for cluster in clusters
    }
    if cfg.basin_draws > 0 and rounds and rounds[0][1]:
        first_lambda, first_clusters = rounds[0]
        basin_estimates, first_hits, basin_unresolved = _estimate_basins(
            prepared=prepared,
            evaluate_map=continuation_map_factory(first_lambda),
            clusters=first_clusters,
        )
        basin_hits.update(first_hits)
        all_unresolved.extend(basin_unresolved)

    candidates: list[EquilibriumCandidate] = []
    bifurcation_candidates: list[BifurcationCandidate] = []
    for lambda_value, clusters in rounds:
        for cluster in clusters:
            summary = cluster.representative.jacobian
            basin = next(
                (
                    estimate
                    for estimate in basin_estimates
                    if estimate.equilibrium_id == cluster.equilibrium_id
                ),
                None,
            )
            candidates.append(
                EquilibriumCandidate(
                    equilibrium_id=cluster.equilibrium_id,
                    state=snapshot_from_vector(
                        prepared,
                        cluster.solution,
                        notes=["multiplicity_cluster_representative"],
                    ),
                    residual_norm=(
                        None
                        if cluster.representative.final_residual_norm is None
                        else float(cluster.representative.final_residual_norm)
                    ),
                    step_norm=(
                        None
                        if cluster.representative.final_step_norm is None
                        else float(cluster.representative.final_step_norm)
                    ),
                    jacobian=_candidate_jacobian(summary),
                    local_stability=_classify_stability(
                        summary,
                        spectral_radius_warn_tol=cfg.spectral_radius_warn_tol,
                    ),
                    branch_id=branch_lookup.get(cluster.equilibrium_id),
                    basin_share_hat=None if basin is None else basin.share_hat,
                    basin_ci_95=None if basin is None else basin.ci_95,
                    discovered_from_starts=max(
                        1,
                        len(cluster.members) + basin_hits[cluster.equilibrium_id],
                    ),
                    diagnostics={
                        **dict(cluster.representative.final_diagnostics),
                        "continuation_lambda": lambda_value,
                    },
                    notes=_candidate_notes(summary),
                )
            )
            bifurcation_candidates.extend(
                _bifurcation_candidates(
                    equilibrium_id=cluster.equilibrium_id,
                    summary=summary,
                    lambda_value=lambda_value,
                )
            )

    diagnostics = summarize_search_diagnostics(
        all_outcomes,
        num_equilibria=len(candidates),
        num_unresolved=len(all_unresolved),
    )
    protocol = build_search_protocol(
        mode="continuation",
        start_domain=_start_domain_payload(prepared),
        n_attempts=len(all_outcomes),
        continuation_parameter=cfg.continuation_parameter,
        continuation_grid=lambda_values,
        merge_tol=cfg.fixed_point_merge_tol,
        residual_tol=cfg.atol,
        basin_draws=cfg.basin_draws,
    )
    return build_multiplicity_report(
        model_id=model_id,
        parameter_hash=parameter_hash,
        search_protocol=protocol,
        equilibria=candidates,
        branches=branches,
        bifurcation_candidates=bifurcation_candidates,
        basin_estimates=basin_estimates,
        unresolved_starts=all_unresolved,
        global_diagnostics=diagnostics,
        runtime_refs=runtime_refs,
        git_sha=git_sha,
        random_seed=cfg.basin_seed,
        notes=[
            "multiplicity_mode:continuation",
            "continuation_engine:pseudo_arclength_predictor",
        ],
    )


def _build_discovery_starts(prepared: PreparedFeedbackConfig) -> list[np.ndarray]:
    cfg = prepared.config.solver
    starts: list[np.ndarray] = [project_bounds(prepared, prepared.initial_values)]
    starts.extend(project_bounds(prepared, np.asarray(start, dtype=float)) for start in cfg.multi_start_values)

    remaining = max(0, cfg.multiplicity_max_attempts - len(starts))
    draw_count = min(int(cfg.multiplicity_sobol_draws), remaining)
    if draw_count:
        starts.extend(_latin_hypercube_starts(prepared, draw_count))

    unique: list[np.ndarray] = []
    for start in starts:
        if len(unique) >= cfg.multiplicity_max_attempts:
            break
        if any(
            scaled_inf_norm(start - existing, prepared=prepared) <= cfg.fixed_point_merge_tol
            for existing in unique
        ):
            continue
        unique.append(start)
    return unique or [project_bounds(prepared, prepared.initial_values)]


def _continuation_starts(
    prepared: PreparedFeedbackConfig,
    rounds: list[tuple[float, list[_Cluster]]],
    *,
    next_lambda: float,
) -> list[np.ndarray]:
    starts: list[np.ndarray] = []
    if len(rounds) >= 2:
        starts.extend(
            _predictor_starts(
                previous_round=rounds[-2],
                current_round=rounds[-1],
                next_lambda=next_lambda,
            )
        )
    if rounds:
        starts.extend(cluster.solution for cluster in rounds[-1][1])
    starts.extend(_build_discovery_starts(prepared))
    return _deduplicate_starts(prepared, starts)


def _predictor_starts(
    *,
    previous_round: tuple[float, list[_Cluster]],
    current_round: tuple[float, list[_Cluster]],
    next_lambda: float,
) -> list[np.ndarray]:
    previous_lambda, previous_clusters = previous_round
    current_lambda, current_clusters = current_round
    starts: list[np.ndarray] = []
    for current in current_clusters:
        previous = _nearest_cluster(current.solution, previous_clusters)
        if previous is None:
            continue
        starts.append(
            pseudo_arclength_predictor(
                ContinuationPoint(
                    lambda_value=previous_lambda,
                    equilibrium_id=previous.equilibrium_id,
                    solution=previous.solution,
                ),
                ContinuationPoint(
                    lambda_value=current_lambda,
                    equilibrium_id=current.equilibrium_id,
                    solution=current.solution,
                ),
                next_lambda=next_lambda,
            )
        )
    return starts


def _nearest_cluster(solution: np.ndarray, clusters: list[_Cluster]) -> _Cluster | None:
    if not clusters:
        return None
    return min(
        clusters,
        key=lambda cluster: float(np.max(np.abs(solution - cluster.solution))),
    )


def _deduplicate_starts(
    prepared: PreparedFeedbackConfig,
    starts: Iterable[np.ndarray],
) -> list[np.ndarray]:
    unique: list[np.ndarray] = []
    for start in starts:
        candidate = project_bounds(prepared, np.asarray(start, dtype=float))
        if len(unique) >= prepared.config.solver.multiplicity_max_attempts:
            break
        if any(
            scaled_inf_norm(candidate - existing, prepared=prepared)
            <= prepared.config.solver.fixed_point_merge_tol
            for existing in unique
        ):
            continue
        unique.append(candidate)
    return unique or [project_bounds(prepared, prepared.initial_values)]


def _latin_hypercube_starts(
    prepared: PreparedFeedbackConfig,
    count: int,
) -> list[np.ndarray]:
    return latin_hypercube_starts(
        prepared,
        count,
        seed=prepared.config.solver.basin_seed,
    )


def _finite_start_bounds(prepared: PreparedFeedbackConfig) -> tuple[np.ndarray, np.ndarray]:
    return finite_start_bounds(prepared)


def _solve_from_start(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
    start: np.ndarray,
) -> SolveOutcome:
    solver = prepared.config.solver.model_copy(update={"multi_start_values": []})
    config = prepared.config.model_copy(update={"solver": solver})
    start_prepared = prepare_feedback_config(
        config,
        initial_state=snapshot_from_vector(prepared, project_bounds(prepared, start)),
    )
    return solve_fixed_point(prepared=start_prepared, evaluate_map=evaluate_map)


def _cluster_outcomes(
    outcomes: list[SolveOutcome],
    *,
    prepared: PreparedFeedbackConfig,
) -> list[_Cluster]:
    clusters: list[_Cluster] = []
    for outcome in outcomes:
        match = next(
            (
                cluster
                for cluster in clusters
                if scaled_inf_norm(outcome.solution - cluster.solution, prepared=prepared)
                <= prepared.config.solver.fixed_point_merge_tol
            ),
            None,
        )
        if match is None:
            index = len(clusters) + 1
            clusters.append(
                _Cluster(
                    equilibrium_id=f"eq_{index:03d}",
                    branch_id=f"br_{index:03d}",
                    representative=outcome,
                    members=[outcome],
                )
            )
            continue
        match.members.append(outcome)
        if _residual_value(outcome) < _residual_value(match.representative):
            match.representative = outcome
    return clusters


def _estimate_basins(
    *,
    prepared: PreparedFeedbackConfig,
    evaluate_map: FeedbackMap,
    clusters: list[_Cluster],
) -> tuple[list[BasinEstimate], dict[str, int], list[UnresolvedEquilibriumStart]]:
    draws = int(prepared.config.solver.basin_draws)
    starts = _latin_hypercube_starts(prepared, draws)
    unresolved: list[UnresolvedEquilibriumStart] = []
    basin_clusters = [
        BasinCluster(equilibrium_id=cluster.equilibrium_id, solution=cluster.solution)
        for cluster in clusters
    ]

    def solve_start(start: np.ndarray) -> tuple[bool, str, np.ndarray, float | None]:
        outcome = _solve_from_start(prepared=prepared, evaluate_map=evaluate_map, start=start)
        return (
            bool(outcome.converged),
            outcome.status,
            np.asarray(outcome.solution, dtype=float),
            None if outcome.final_residual_norm is None else float(outcome.final_residual_norm),
        )

    estimates, hits, assignments = estimate_basin_shares(
        prepared=prepared,
        clusters=basin_clusters,
        starts=starts,
        solve_start=solve_start,
    )
    for assignment in assignments:
        if assignment.status == "assigned":
            continue
        unresolved.append(
            UnresolvedEquilibriumStart(
                start_state=snapshot_from_vector(
                    prepared,
                    assignment.start,
                    notes=["multiplicity_start", "basin_draw"],
                ),
                status=assignment.status,
                failure_reason=None,
                residual_norm=assignment.residual_norm,
                diagnostics={},
                notes=["basin_unassigned"]
                if assignment.status == "unassigned"
                else ["basin_draw"],
            )
        )
    return estimates, hits, unresolved


def _assign_cluster(
    *,
    prepared: PreparedFeedbackConfig,
    outcome: SolveOutcome,
    clusters: list[_Cluster],
) -> _Cluster | None:
    distances = [
        (
            scaled_inf_norm(outcome.solution - cluster.solution, prepared=prepared),
            cluster,
        )
        for cluster in clusters
    ]
    if not distances:
        return None
    distance, cluster = min(distances, key=lambda item: item[0])
    if distance <= prepared.config.solver.fixed_point_merge_tol:
        return cluster
    return None


def _candidate_jacobian(summary: JacobianSummary | None) -> EquilibriumCandidateJacobian | None:
    if summary is None:
        return None
    return EquilibriumCandidateJacobian(
        spectral_radius=summary.spectral_radius,
        operator_norm_inf=summary.operator_norm_inf,
        condition_number=summary.condition_number,
        smallest_singular_value_i_minus_j=summary.smallest_singular_value_i_minus_j,
        near_fold=summary.near_fold,
        near_flip=summary.near_flip,
        near_loss_of_stability=summary.near_loss_of_stability,
        near_bifurcation=summary.near_bifurcation,
    )


def _classify_stability(
    summary: JacobianSummary | None,
    *,
    spectral_radius_warn_tol: float,
) -> str:
    if summary is None or summary.spectral_radius is None:
        return "unknown"
    radius = float(summary.spectral_radius)
    if radius < 1.0 - spectral_radius_warn_tol:
        return "attractive"
    if radius > 1.0 + spectral_radius_warn_tol:
        return "unstable"
    return "neutral_or_near_bifurcation"


def _candidate_notes(summary: JacobianSummary | None) -> list[str]:
    if summary is None:
        return []
    return list(summary.notes)


def _bifurcation_candidates(
    *,
    equilibrium_id: str,
    summary: JacobianSummary | None,
    lambda_value: float | None,
) -> list[BifurcationCandidate]:
    if summary is None:
        return []
    candidates: list[BifurcationCandidate] = []
    if summary.near_fold:
        candidates.append(
            BifurcationCandidate(
                kind="fold",
                lambda_value=lambda_value,
                equilibrium_id=equilibrium_id,
                confidence="medium",
                diagnostics={
                    "smallest_singular_value_i_minus_j": summary.smallest_singular_value_i_minus_j
                },
            )
        )
    if summary.near_flip:
        candidates.append(
            BifurcationCandidate(
                kind="flip",
                lambda_value=lambda_value,
                equilibrium_id=equilibrium_id,
                confidence="low",
                diagnostics={"spectral_radius": summary.spectral_radius},
            )
        )
    if summary.near_loss_of_stability:
        candidates.append(
            BifurcationCandidate(
                kind="loss_of_stability",
                lambda_value=lambda_value,
                equilibrium_id=equilibrium_id,
                confidence="low",
                diagnostics={"spectral_radius": summary.spectral_radius},
            )
        )
    return candidates


def _unresolved_start(
    prepared: PreparedFeedbackConfig,
    outcome: SolveOutcome,
    *,
    notes: list[str] | None = None,
) -> UnresolvedEquilibriumStart:
    return UnresolvedEquilibriumStart(
        start_state=snapshot_from_vector(prepared, outcome.initial, notes=["multiplicity_start"]),
        status=outcome.status,
        failure_reason=outcome.failure_reason,
        residual_norm=(
            None if outcome.final_residual_norm is None else float(outcome.final_residual_norm)
        ),
        diagnostics=dict(outcome.final_diagnostics),
        notes=list(notes or []),
    )


def _report_mode(prepared: PreparedFeedbackConfig) -> str:
    mode = prepared.config.solver.multiplicity_mode
    if mode == "off":
        return "baseline"
    return mode


def _report_lambda(prepared: PreparedFeedbackConfig) -> float | None:
    grid = prepared.config.solver.continuation_grid
    return float(grid[0]) if grid else None


def _start_domain_payload(prepared: PreparedFeedbackConfig) -> dict[str, Any]:
    lower, upper = _finite_start_bounds(prepared)
    return {
        variable_id: [float(lower[index]), float(upper[index])]
        for index, variable_id in enumerate(prepared.variable_ids)
    }


def _residual_value(outcome: SolveOutcome) -> float:
    if outcome.final_residual_norm is None:
        return float("inf")
    return float(outcome.final_residual_norm)
