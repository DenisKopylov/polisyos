"""Structural strategic network-formation estimator for policy analysis."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import comb, log
from statistics import NormalDist
from typing import Any, ClassVar

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)

from .missingness import maybe_build_missingness_assessment
from .protocols import (
    IntervalEstimate,
    NetworkData,
    NetworkFormationCounterfactualSummary,
    NetworkFormationDiagnostic,
    NetworkFormationIdentifiedSet,
    NetworkFormationPredictiveCheck,
    NetworkFormationScenarioMoments,
    NetworkFormationUncertaintySummary,
    NetworkFormationValidationSummary,
    NetworkResult,
    StrategicNetworkFormationData,
)


@dataclass(frozen=True)
class _LogitFit:
    beta: np.ndarray
    covariance: np.ndarray
    std_errors: np.ndarray
    converged: bool
    log_likelihood: float
    iterations: int


def _strategic_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, StrategicNetworkFormationData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be StrategicNetworkFormationData or mapping")


def _binary_undirected_adjacency(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    binary = ((arr > 0.0) | (arr.T > 0.0)).astype(float)
    np.fill_diagonal(binary, 0.0)
    return binary


def _unordered_pairs(n_nodes: int) -> tuple[np.ndarray, np.ndarray]:
    return np.triu_indices(n_nodes, k=1)


def _density(adjacency: np.ndarray) -> float:
    graph = _binary_undirected_adjacency(adjacency)
    n_nodes = graph.shape[0]
    if n_nodes <= 1:
        return 0.0
    tri = _unordered_pairs(n_nodes)
    return float(np.mean(graph[tri])) if tri[0].size else 0.0


def _component_sizes(adjacency: np.ndarray) -> list[int]:
    graph = _binary_undirected_adjacency(adjacency)
    n_nodes = graph.shape[0]
    visited = np.zeros(n_nodes, dtype=bool)
    sizes: list[int] = []
    for start in range(n_nodes):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        size = 0
        while stack:
            node = stack.pop()
            size += 1
            neighbors = np.flatnonzero(graph[node] > 0.0)
            for neighbor in neighbors:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(int(neighbor))
        sizes.append(size)
    return sizes


def _clustering(adjacency: np.ndarray) -> float:
    graph = _binary_undirected_adjacency(adjacency)
    degree = np.sum(graph, axis=1)
    wedges = float(np.sum(degree * np.maximum(degree - 1.0, 0.0) / 2.0))
    if wedges <= 0.0:
        return 0.0
    triangles = float(np.trace(graph @ graph @ graph) / 6.0)
    return float(np.clip(3.0 * triangles / wedges, 0.0, 1.0))


def _network_moments(adjacency: np.ndarray) -> NetworkFormationScenarioMoments:
    graph = _binary_undirected_adjacency(adjacency)
    degree = np.sum(graph, axis=1)
    n_nodes = graph.shape[0]
    sizes = _component_sizes(graph) if n_nodes else []
    largest_component_share = float(max(sizes) / n_nodes) if sizes and n_nodes else 0.0
    if n_nodes <= 1:
        reachability_share = 0.0
    else:
        reachable_pairs = float(sum(size * (size - 1) for size in sizes))
        reachability_share = float(
            np.clip(reachable_pairs / float(n_nodes * (n_nodes - 1)), 0.0, 1.0)
        )
    return NetworkFormationScenarioMoments(
        density=_density(graph),
        mean_degree=float(np.mean(degree)) if degree.size else 0.0,
        clustering=_clustering(graph),
        reachability_share=reachability_share,
        largest_component_share=largest_component_share,
    )


def _support_from_matrix(matrix: np.ndarray | None) -> float:
    if matrix is None or matrix.size == 0:
        return 0.0
    return float(np.mean(np.std(matrix, axis=0) > 1.0e-8))


def _full_dyad_surface_available(
    data: StrategicNetworkFormationData, parameters: Mapping[str, float]
) -> bool:
    required = [
        int(key.split("_")[-1]) + 1
        for key in parameters
        if key.startswith("dyad_feature_") and key.split("_")[-1].isdigit()
    ]
    if not required:
        return True
    if data.dyad_features is None:
        return False
    return data.dyad_features.shape[2] >= max(required, default=0)


def _simulation_ready(data: StrategicNetworkFormationData, parameters: Mapping[str, float]) -> bool:
    if any(key.startswith("node_") for key in parameters) and data.node_features is None:
        return False
    return _full_dyad_surface_available(data, parameters)


def _design_diagnostics(design: np.ndarray) -> tuple[int | None, float | None]:
    if design.size == 0:
        return None, None
    try:
        rank = int(np.linalg.matrix_rank(design))
        condition = float(np.linalg.cond(design))
    except np.linalg.LinAlgError:
        return None, None
    if not np.isfinite(condition):
        return rank, None
    return rank, condition


def _sigmoid(values: np.ndarray | float) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.clip(arr, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-arr))


def _logit_clipped(probability: float) -> float:
    clipped = float(np.clip(probability, 1.0e-6, 1.0 - 1.0e-6))
    return log(clipped / (1.0 - clipped))


def _fit_logistic_ridge(
    design: np.ndarray,
    responses: np.ndarray,
    *,
    ridge: float,
    max_iter: int,
    tol: float = 1.0e-6,
) -> _LogitFit:
    n_obs, n_features = design.shape
    ridge = max(float(ridge), 1.0e-8)
    penalty = np.eye(n_features, dtype=float) * ridge
    penalty[0, 0] = 0.0

    if n_obs == 0:
        zeros = np.zeros(n_features, dtype=float)
        covariance = np.eye(n_features, dtype=float)
        return _LogitFit(
            beta=zeros,
            covariance=covariance,
            std_errors=np.sqrt(np.diag(covariance)),
            converged=False,
            log_likelihood=0.0,
            iterations=0,
        )

    if np.unique(responses).size < 2:
        beta = np.zeros(n_features, dtype=float)
        beta[0] = _logit_clipped(float(np.mean(responses)))
        information = design.T @ design + penalty + 1.0e-6 * np.eye(n_features, dtype=float)
        covariance = np.linalg.pinv(information)
        std_errors = np.sqrt(np.maximum(np.diag(covariance), 1.0e-8))
        probabilities = np.clip(_sigmoid(design @ beta), 1.0e-6, 1.0 - 1.0e-6)
        log_likelihood = float(
            np.sum(
                responses * np.log(probabilities) + (1.0 - responses) * np.log(1.0 - probabilities)
            )
        )
        return _LogitFit(
            beta=beta,
            covariance=covariance,
            std_errors=std_errors,
            converged=True,
            log_likelihood=log_likelihood,
            iterations=1,
        )

    beta = np.zeros(n_features, dtype=float)
    converged = False
    for iteration in range(1, max(max_iter, 1) + 1):
        linear = design @ beta
        probabilities = np.clip(_sigmoid(linear), 1.0e-6, 1.0 - 1.0e-6)
        weights = np.clip(probabilities * (1.0 - probabilities), 1.0e-6, None)
        working_response = linear + (responses - probabilities) / weights
        lhs = design.T @ (weights[:, None] * design) + penalty
        rhs = design.T @ (weights * working_response)
        try:
            updated = np.linalg.solve(lhs, rhs)
        except np.linalg.LinAlgError:
            updated = np.linalg.pinv(lhs) @ rhs
        updated = np.clip(updated, -12.0, 12.0)
        if float(np.max(np.abs(updated - beta))) < tol:
            beta = updated
            converged = True
            break
        beta = updated

    linear = design @ beta
    probabilities = np.clip(_sigmoid(linear), 1.0e-6, 1.0 - 1.0e-6)
    weights = np.clip(probabilities * (1.0 - probabilities), 1.0e-6, None)
    information = design.T @ (weights[:, None] * design) + penalty
    covariance = np.linalg.pinv(information)
    std_errors = np.sqrt(np.maximum(np.diag(covariance), 1.0e-8))
    log_likelihood = float(
        np.sum(responses * np.log(probabilities) + (1.0 - responses) * np.log(1.0 - probabilities))
        - 0.5 * ridge * np.sum(beta[1:] ** 2)
    )
    return _LogitFit(
        beta=beta,
        covariance=covariance,
        std_errors=std_errors,
        converged=converged,
        log_likelihood=log_likelihood,
        iterations=iteration,
    )


def _build_design_names(dyad_dim: int, node_dim: int) -> list[str]:
    names = ["intercept", "triadic_closure", "degree_penalty_feature"]
    names.extend(f"dyad_feature_{idx}" for idx in range(dyad_dim))
    names.extend(f"node_sum_{idx}" for idx in range(node_dim))
    names.extend(f"node_absdiff_{idx}" for idx in range(node_dim))
    return names


def _node_pair_terms(
    node_features: np.ndarray | None, i: int, j: int
) -> tuple[np.ndarray, np.ndarray]:
    if node_features is None:
        return np.zeros(0, dtype=float), np.zeros(0, dtype=float)
    left = np.asarray(node_features[i], dtype=float)
    right = np.asarray(node_features[j], dtype=float)
    return left + right, np.abs(left - right)


def _pair_design_row(
    graph: np.ndarray,
    *,
    data: StrategicNetworkFormationData,
    i: int,
    j: int,
    dyad_vector: np.ndarray | None,
) -> np.ndarray:
    degree = np.sum(graph, axis=1)
    common_neighbors = float(np.dot(graph[i], graph[j]))
    degree_penalty_feature = float(degree[i] + degree[j] - 2.0 * graph[i, j] + 1.0)
    pieces = [np.array([1.0, common_neighbors, degree_penalty_feature], dtype=float)]
    if dyad_vector is not None:
        pieces.append(np.asarray(dyad_vector, dtype=float))
    node_sum, node_absdiff = _node_pair_terms(data.node_features, i, j)
    if node_sum.size:
        pieces.append(node_sum)
        pieces.append(node_absdiff)
    return np.concatenate(pieces) if pieces else np.zeros(0, dtype=float)


def _build_cross_sectional_design(
    feature_graph: np.ndarray,
    data: StrategicNetworkFormationData,
    *,
    response_graph: np.ndarray | None = None,
    pair_mask: np.ndarray | None = None,
    dyad_features: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, list[str], int, float]:
    graph = _binary_undirected_adjacency(feature_graph)
    responses_graph = (
        graph if response_graph is None else _binary_undirected_adjacency(response_graph)
    )
    tri = _unordered_pairs(graph.shape[0])
    if pair_mask is None:
        pair_mask = np.ones(tri[0].shape[0], dtype=bool)
    else:
        pair_mask = np.asarray(pair_mask, dtype=bool)

    surface = None if dyad_features is None else np.asarray(dyad_features, dtype=float)
    dyad_dim = 0 if surface is None else int(surface.shape[2])
    node_dim = 0 if data.node_features is None else int(np.asarray(data.node_features).shape[1])
    names = _build_design_names(dyad_dim, node_dim)

    rows: list[np.ndarray] = []
    responses: list[float] = []
    dyad_rows: list[np.ndarray] = []
    for idx, (i, j) in enumerate(zip(tri[0], tri[1], strict=True)):
        if not pair_mask[idx]:
            continue
        dyad_vector = None if surface is None else surface[i, j, :]
        rows.append(_pair_design_row(graph, data=data, i=int(i), j=int(j), dyad_vector=dyad_vector))
        responses.append(float(responses_graph[i, j]))
        if dyad_vector is not None:
            dyad_rows.append(np.asarray(dyad_vector, dtype=float))

    design = np.vstack(rows) if rows else np.zeros((0, len(names)), dtype=float)
    response_array = np.asarray(responses, dtype=float)
    dyad_matrix = np.vstack(dyad_rows) if dyad_rows else np.zeros((0, dyad_dim), dtype=float)
    return design, response_array, names, dyad_dim, _support_from_matrix(dyad_matrix)


def _build_event_history_design(
    data: StrategicNetworkFormationData,
) -> tuple[np.ndarray, np.ndarray, list[str], int, float]:
    if data.formation_events:
        event_width = max(
            (
                len(event.dyad_covariates)
                for event in data.formation_events
                if event.dyad_covariates
            ),
            default=0,
        )
    else:
        event_width = 0
    surface_width = (
        0
        if data.dyad_features is None
        else int(np.asarray(data.dyad_features, dtype=float).shape[2])
    )
    dyad_dim = max(event_width, surface_width)
    node_dim = 0 if data.node_features is None else int(np.asarray(data.node_features).shape[1])
    names = _build_design_names(dyad_dim, node_dim)

    graph = (
        _binary_undirected_adjacency(np.asarray(data.initial_adjacency, dtype=float))
        if data.initial_adjacency is not None
        else np.zeros_like(np.asarray(data.adjacency, dtype=float), dtype=float)
    )
    surface = None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    rows: list[np.ndarray] = []
    responses: list[float] = []
    dyad_rows: list[np.ndarray] = []

    for event in data.formation_events:
        dyad_vector = np.zeros(dyad_dim, dtype=float)
        if event.dyad_covariates:
            covariates = np.asarray(event.dyad_covariates, dtype=float)
            dyad_vector[: covariates.shape[0]] = covariates
        elif surface is not None and dyad_dim > 0:
            dyad_vector[: surface.shape[2]] = surface[event.i, event.j, :]
        rows.append(
            _pair_design_row(
                graph,
                data=data,
                i=int(event.i),
                j=int(event.j),
                dyad_vector=dyad_vector if dyad_dim > 0 else None,
            )
        )
        responses.append(float(event.next_state))
        if dyad_dim > 0:
            dyad_rows.append(dyad_vector.copy())
        graph[event.i, event.j] = float(event.next_state)
        graph[event.j, event.i] = float(event.next_state)

    design = np.vstack(rows) if rows else np.zeros((0, len(names)), dtype=float)
    response_array = np.asarray(responses, dtype=float)
    dyad_matrix = np.vstack(dyad_rows) if dyad_rows else np.zeros((0, dyad_dim), dtype=float)
    return design, response_array, names, dyad_dim, _support_from_matrix(dyad_matrix)


def _structuralize_estimates(
    names: list[str],
    values: np.ndarray,
    std_errors: np.ndarray | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    estimates: dict[str, float] = {}
    errors: dict[str, float] = {}
    for idx, name in enumerate(names):
        value = float(values[idx])
        error = None if std_errors is None else float(std_errors[idx])
        if name == "degree_penalty_feature":
            estimates["degree_penalty"] = float(-value)
            if error is not None:
                errors["degree_penalty"] = abs(error)
            continue
        estimates[name] = value
        if error is not None:
            errors[name] = abs(error)
    return estimates, errors


def _parameter_keys(parameters: Mapping[str, float]) -> list[str]:
    return list(parameters.keys())


def _interval_from_samples(
    samples: np.ndarray,
    *,
    ci_level: float,
    estimate: float | None,
    method: str,
    units: str,
) -> IntervalEstimate:
    arr = np.asarray(samples, dtype=float)
    if arr.size == 0:
        point = 0.0 if estimate is None else float(estimate)
        return IntervalEstimate(
            estimate=point,
            std_error=0.0,
            ci_level=ci_level,
            ci_lower=point,
            ci_upper=point,
            p_value=1.0,
            units=units,
            method=method,
        )
    mean = float(np.mean(arr)) if estimate is None else float(estimate)
    std_error = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    alpha = max(1.0 - float(ci_level), 1.0e-6)
    ci_lower, ci_upper = np.quantile(arr, [alpha / 2.0, 1.0 - alpha / 2.0])
    p_value = 1.0
    if std_error > 1.0e-12:
        z_score = abs(mean) / std_error
        p_value = float(2.0 * (1.0 - NormalDist().cdf(z_score)))
    return IntervalEstimate(
        estimate=mean,
        std_error=std_error,
        ci_level=ci_level,
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
        p_value=p_value,
        units=units,
        method=method,
    )


def _uncertainty_summary_from_draws(
    *,
    parameters: Mapping[str, float],
    parameter_draws: list[dict[str, float]],
    ci_level: float,
    method: str,
    scenario_effects: dict[str, np.ndarray] | None = None,
    warnings: tuple[str, ...] = (),
) -> NetworkFormationUncertaintySummary:
    parameter_intervals = {
        key: _interval_from_samples(
            np.asarray([draw.get(key, parameters[key]) for draw in parameter_draws], dtype=float),
            ci_level=ci_level,
            estimate=parameters[key],
            method=method,
            units="structural-parameter units",
        )
        for key in _parameter_keys(parameters)
    }
    scenario_effect_intervals = {}
    if scenario_effects is not None:
        scenario_effect_intervals = {
            key: _interval_from_samples(
                np.asarray(values, dtype=float),
                ci_level=ci_level,
                estimate=float(np.mean(values)) if len(values) else 0.0,
                method=f"{method}+simulation",
                units="network-moment units",
            )
            for key, values in scenario_effects.items()
        }
    return NetworkFormationUncertaintySummary(
        method=method,
        draw_count=len(parameter_draws),
        parameter_intervals=parameter_intervals,
        scenario_effect_intervals=scenario_effect_intervals,
        warnings=warnings,
    )


def _raw_draws_from_normal(
    mean: np.ndarray,
    covariance: np.ndarray,
    *,
    draws: int,
    seed: int,
) -> np.ndarray:
    if draws <= 0:
        return np.zeros((0, mean.shape[0]), dtype=float)
    covariance = 0.5 * (covariance + covariance.T)
    eigvals, eigvecs = np.linalg.eigh(covariance)
    eigvals = np.clip(eigvals, 0.0, None)
    transform = eigvecs @ np.diag(np.sqrt(eigvals))
    rng = np.random.default_rng(seed)
    normals = rng.normal(size=(draws, mean.shape[0]))
    return mean[None, :] + normals @ transform.T


def _normal_parameter_draws(
    *,
    names: list[str],
    fit: _LogitFit,
    draws: int,
    seed: int,
) -> list[dict[str, float]]:
    raw_draws = _raw_draws_from_normal(fit.beta, fit.covariance, draws=draws, seed=seed)
    structured: list[dict[str, float]] = []
    for draw in raw_draws:
        estimates, _ = _structuralize_estimates(names, draw)
        structured.append(estimates)
    return structured


def _score_pair(
    graph: np.ndarray,
    *,
    data: StrategicNetworkFormationData,
    parameters: Mapping[str, float],
    i: int,
    j: int,
    dyad_features: np.ndarray | None,
) -> float:
    degree = np.sum(graph, axis=1)
    common_neighbors = float(np.dot(graph[i], graph[j]))
    degree_penalty_feature = float(degree[i] + degree[j] - 2.0 * graph[i, j] + 1.0)
    score = float(parameters.get("intercept", 0.0))
    score += float(parameters.get("triadic_closure", 0.0)) * common_neighbors
    score -= float(parameters.get("degree_penalty", 0.0)) * degree_penalty_feature

    if dyad_features is not None:
        for idx in range(dyad_features.shape[2]):
            score += float(parameters.get(f"dyad_feature_{idx}", 0.0)) * float(
                dyad_features[i, j, idx]
            )

    if data.node_features is not None:
        node_sum, node_absdiff = _node_pair_terms(np.asarray(data.node_features, dtype=float), i, j)
        for idx, value in enumerate(node_sum):
            score += float(parameters.get(f"node_sum_{idx}", 0.0)) * float(value)
        for idx, value in enumerate(node_absdiff):
            score += float(parameters.get(f"node_absdiff_{idx}", 0.0)) * float(value)
    return score


def _simulate_networks(
    *,
    data: StrategicNetworkFormationData,
    parameters: Mapping[str, float],
    dyad_features: np.ndarray | None,
    draws: int,
    burnin: int,
    interval: int,
    seed: int,
    initial_adjacency: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    base = data.adjacency if initial_adjacency is None else initial_adjacency
    graph = _binary_undirected_adjacency(np.asarray(base, dtype=float))
    n_nodes = graph.shape[0]
    if draws <= 0 or n_nodes <= 1:
        return np.zeros((0, n_nodes, n_nodes), dtype=float), graph

    tri = _unordered_pairs(n_nodes)
    n_pairs = tri[0].size
    rng = np.random.default_rng(seed)
    saved = np.zeros((draws, n_nodes, n_nodes), dtype=float)
    total_steps = max(burnin, 0) + max(interval, 1) * draws
    save_idx = 0

    for step in range(total_steps):
        pair_idx = int(rng.integers(0, n_pairs))
        i = int(tri[0][pair_idx])
        j = int(tri[1][pair_idx])
        probability = float(
            _sigmoid(
                _score_pair(
                    graph, data=data, parameters=parameters, i=i, j=j, dyad_features=dyad_features
                )
            )
        )
        new_state = 1.0 if rng.uniform() < probability else 0.0
        graph[i, j] = new_state
        graph[j, i] = new_state
        if step >= burnin and (step - burnin) % max(interval, 1) == 0 and save_idx < draws:
            saved[save_idx] = graph.copy()
            save_idx += 1

    return saved[:save_idx], graph


def _sufficient_statistics(
    adjacency: np.ndarray,
    *,
    data: StrategicNetworkFormationData,
    dyad_features: np.ndarray | None,
    parameter_names: list[str],
) -> dict[str, float]:
    graph = _binary_undirected_adjacency(adjacency)
    tri = _unordered_pairs(graph.shape[0])
    edges = graph[tri]
    stats: dict[str, float] = {"intercept": float(np.mean(edges)) if edges.size else 0.0}
    triangles = float(np.trace(graph @ graph @ graph) / 6.0)
    triangle_scale = float(comb(graph.shape[0], 3)) if graph.shape[0] >= 3 else 1.0
    stats["triadic_closure"] = float(triangles / triangle_scale) if triangle_scale > 0.0 else 0.0
    degree = np.sum(graph, axis=1)
    stats["degree_penalty"] = float(-0.5 * np.mean(degree**2)) if degree.size else 0.0

    if dyad_features is not None:
        for idx in range(dyad_features.shape[2]):
            stats[f"dyad_feature_{idx}"] = (
                float(np.mean(edges * dyad_features[tri[0], tri[1], idx])) if edges.size else 0.0
            )

    if data.node_features is not None and edges.size:
        node_features = np.asarray(data.node_features, dtype=float)
        for idx in range(node_features.shape[1]):
            node_sum = node_features[tri[0], idx] + node_features[tri[1], idx]
            node_absdiff = np.abs(node_features[tri[0], idx] - node_features[tri[1], idx])
            stats[f"node_sum_{idx}"] = float(np.mean(edges * node_sum))
            stats[f"node_absdiff_{idx}"] = float(np.mean(edges * node_absdiff))

    return {key: float(stats.get(key, 0.0)) for key in parameter_names}


def _effective_sample_size(series: np.ndarray) -> float:
    values = np.asarray(series, dtype=float)
    n_obs = values.shape[0]
    if n_obs <= 2:
        return float(n_obs)
    centered = values - float(np.mean(values))
    variance = float(np.var(centered))
    if variance <= 1.0e-12:
        return float(n_obs)
    tau = 1.0
    max_lag = min(n_obs - 1, 20)
    for lag in range(1, max_lag + 1):
        autocov = float(np.dot(centered[:-lag], centered[lag:]) / (n_obs - lag))
        rho = autocov / variance
        if rho <= 0.0:
            break
        tau += 2.0 * rho
    return float(max(1.0, n_obs / tau))


def _bootstrap_parameter_draws(
    *,
    data: StrategicNetworkFormationData,
    point_parameters: Mapping[str, float],
    draws: int,
    ridge: float,
    max_iter: int,
    burnin: int,
    interval: int,
    seed: int,
) -> list[dict[str, float]]:
    if draws <= 0 or not _simulation_ready(data, point_parameters):
        return []

    dyad_features = (
        None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    )
    simulated_graphs, _ = _simulate_networks(
        data=data,
        parameters=point_parameters,
        dyad_features=dyad_features,
        draws=draws,
        burnin=burnin,
        interval=interval,
        seed=seed,
    )
    parameter_draws: list[dict[str, float]] = []
    for index, graph in enumerate(simulated_graphs):
        design, responses, names, _, _ = _build_cross_sectional_design(
            graph,
            data,
            response_graph=graph,
            dyad_features=dyad_features,
        )
        fit = _fit_logistic_ridge(design, responses, ridge=ridge, max_iter=max_iter)
        estimates, _ = _structuralize_estimates(names, fit.beta, fit.std_errors)
        if estimates:
            parameter_draws.append(estimates)
        else:
            parameter_draws.append(dict(point_parameters))
        if index + 1 >= draws:
            break
    return parameter_draws


def _predictive_checks_from_graphs(
    observed_adjacency: np.ndarray,
    simulated_graphs: np.ndarray,
) -> tuple[tuple[NetworkFormationPredictiveCheck, ...], tuple[str, ...]]:
    if simulated_graphs.size == 0:
        return (), (
            "posterior predictive checks skipped because no simulated graphs were available",
        )

    observed = _network_moments(observed_adjacency).model_dump(mode="python")
    simulated_moments = [
        _network_moments(graph).model_dump(mode="python") for graph in simulated_graphs
    ]
    checks: list[NetworkFormationPredictiveCheck] = []
    for key in (
        "density",
        "mean_degree",
        "clustering",
        "reachability_share",
        "largest_component_share",
    ):
        values = np.asarray([moments[key] for moments in simulated_moments], dtype=float)
        q05, q95 = np.quantile(values, [0.05, 0.95])
        observed_value = float(observed[key])
        checks.append(
            NetworkFormationPredictiveCheck(
                statistic=key,
                observed=observed_value,
                simulated_mean=float(np.mean(values)),
                q05=float(q05),
                q95=float(q95),
                passed=bool(q05 <= observed_value <= q95),
            )
        )
    return tuple(checks), ()


def _heldout_log_loss(
    *,
    data: StrategicNetworkFormationData,
    adjacency: np.ndarray,
    ridge: float,
    max_iter: int,
    holdout_fraction: float,
    seed: int,
) -> tuple[float | None, tuple[str, ...]]:
    tri = _unordered_pairs(adjacency.shape[0])
    n_pairs = tri[0].size
    if n_pairs == 0:
        return None, ()

    if data.holdout_mask is not None:
        holdout_pairs = np.asarray(data.holdout_mask[tri], dtype=bool)
    else:
        fraction = float(np.clip(holdout_fraction, 0.0, 0.9))
        if fraction <= 0.0 or n_pairs < 4:
            return None, ()
        rng = np.random.default_rng(seed)
        holdout_pairs = np.zeros(n_pairs, dtype=bool)
        sample_size = max(1, int(round(fraction * n_pairs)))
        chosen = rng.choice(n_pairs, size=min(sample_size, n_pairs - 1), replace=False)
        holdout_pairs[chosen] = True

    if not np.any(holdout_pairs) or np.all(holdout_pairs):
        return None, (
            "held-out validation skipped because the holdout mask did not leave both train and test dyads",
        )

    train_graph = adjacency.copy()
    for i, j in zip(tri[0][holdout_pairs], tri[1][holdout_pairs], strict=True):
        train_graph[i, j] = 0.0
        train_graph[j, i] = 0.0

    dyad_features = (
        None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    )
    train_design, train_y, _, _, _ = _build_cross_sectional_design(
        train_graph,
        data,
        response_graph=train_graph,
        pair_mask=~holdout_pairs,
        dyad_features=dyad_features,
    )
    test_design, test_y, _, _, _ = _build_cross_sectional_design(
        train_graph,
        data,
        response_graph=adjacency,
        pair_mask=holdout_pairs,
        dyad_features=dyad_features,
    )
    fit = _fit_logistic_ridge(train_design, train_y, ridge=ridge, max_iter=max_iter)
    probabilities = np.clip(_sigmoid(test_design @ fit.beta), 1.0e-6, 1.0 - 1.0e-6)
    log_loss = -float(
        np.mean(test_y * np.log(probabilities) + (1.0 - test_y) * np.log(1.0 - probabilities))
    )
    return log_loss, ()


def _temporal_parameter_drift(
    *,
    data: StrategicNetworkFormationData,
    ridge: float,
    max_iter: int,
) -> tuple[float | None, tuple[str, ...]]:
    if data.adjacency_snapshots is None:
        return None, ()
    snapshots = np.asarray(data.adjacency_snapshots, dtype=float)
    first = _binary_undirected_adjacency(snapshots[0])
    last = _binary_undirected_adjacency(snapshots[-1])
    dyad_features = (
        None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    )

    first_design, first_y, names, _, _ = _build_cross_sectional_design(
        first,
        data,
        response_graph=first,
        dyad_features=dyad_features,
    )
    last_design, last_y, _, _, _ = _build_cross_sectional_design(
        last,
        data,
        response_graph=last,
        dyad_features=dyad_features,
    )
    first_fit = _fit_logistic_ridge(first_design, first_y, ridge=ridge, max_iter=max_iter)
    last_fit = _fit_logistic_ridge(last_design, last_y, ridge=ridge, max_iter=max_iter)
    first_params, _ = _structuralize_estimates(names, first_fit.beta, first_fit.std_errors)
    last_params, _ = _structuralize_estimates(names, last_fit.beta, last_fit.std_errors)
    keys = sorted(set(first_params) | set(last_params))
    first_vec = np.asarray([first_params.get(key, 0.0) for key in keys], dtype=float)
    last_vec = np.asarray([last_params.get(key, 0.0) for key in keys], dtype=float)
    drift = float(np.linalg.norm(last_vec - first_vec) / np.sqrt(max(len(keys), 1)))
    return drift, ()


def _counterfactual_summary(
    *,
    data: StrategicNetworkFormationData,
    parameter_draws: list[dict[str, float]],
    point_parameters: Mapping[str, float],
    ci_level: float,
    burnin: int,
    interval: int,
    draws: int,
    seed: int,
) -> tuple[NetworkFormationCounterfactualSummary | None, dict[str, np.ndarray] | None]:
    if data.policy_shock is None:
        return None, None
    if not _simulation_ready(data, point_parameters):
        return None, None

    baseline_features = (
        None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    )
    shocked_features = None
    warnings: list[str] = []
    if baseline_features is not None:
        shocked_features = baseline_features + np.asarray(data.policy_shock, dtype=float)
    else:
        shocked_features = None
        warnings.append("policy shock does not load on any estimated dyad-feature term")

    if not parameter_draws:
        parameter_draws = [dict(point_parameters)]
    draw_count = max(1, min(draws, len(parameter_draws)))
    selected_draws = parameter_draws[:draw_count]

    baseline_moments: list[dict[str, float]] = []
    counterfactual_moments: list[dict[str, float]] = []
    for index, parameters in enumerate(selected_draws):
        baseline_graphs, _ = _simulate_networks(
            data=data,
            parameters=parameters,
            dyad_features=baseline_features,
            draws=1,
            burnin=burnin,
            interval=interval,
            seed=seed + 101 * (index + 1),
            initial_adjacency=data.adjacency,
        )
        counterfactual_graphs, _ = _simulate_networks(
            data=data,
            parameters=parameters,
            dyad_features=shocked_features,
            draws=1,
            burnin=burnin,
            interval=interval,
            seed=seed + 101 * (index + 1) + 13,
            initial_adjacency=data.adjacency,
        )
        if baseline_graphs.size == 0 or counterfactual_graphs.size == 0:
            continue
        baseline_moments.append(_network_moments(baseline_graphs[-1]).model_dump(mode="python"))
        counterfactual_moments.append(
            _network_moments(counterfactual_graphs[-1]).model_dump(mode="python")
        )

    if not baseline_moments or not counterfactual_moments:
        return None, None

    keys = ("density", "mean_degree", "clustering", "reachability_share", "largest_component_share")
    effects = {
        key: np.asarray(
            [
                counterfactual_moments[idx][key] - baseline_moments[idx][key]
                for idx in range(len(baseline_moments))
            ],
            dtype=float,
        )
        for key in keys
    }

    baseline_summary = NetworkFormationScenarioMoments(
        **{key: float(np.mean([moments[key] for moments in baseline_moments])) for key in keys}
    )
    counterfactual_summary = NetworkFormationScenarioMoments(
        **{
            key: float(np.mean([moments[key] for moments in counterfactual_moments]))
            for key in keys
        }
    )
    effect_intervals = {
        key: _interval_from_samples(
            values,
            ci_level=ci_level,
            estimate=float(np.mean(values)),
            method="counterfactual_simulation",
            units="network-moment units",
        )
        for key, values in effects.items()
    }
    scenario_name = str(data.metadata.get("policy_shock_name", "policy_shock"))
    summary = NetworkFormationCounterfactualSummary(
        scenario_name=scenario_name,
        baseline=baseline_summary,
        counterfactual=counterfactual_summary,
        effects=effect_intervals,
        simulation_draws=len(baseline_moments),
        warnings=tuple(warnings),
    )
    return summary, effects


def _degeneracy_risk(adjacency: np.ndarray) -> str:
    density = _density(adjacency)
    clustering = _clustering(adjacency)
    if density < 0.05 or density > 0.95:
        return "high"
    if density < 0.10 or density > 0.85 or clustering > 0.80:
        return "moderate"
    return "low"


def _fallback_identified_set(
    *,
    adjacency: np.ndarray,
    grid_size: int,
    threshold_buffer: float,
) -> NetworkFormationIdentifiedSet:
    graph = _binary_undirected_adjacency(adjacency)
    tri = _unordered_pairs(graph.shape[0])
    degree = np.sum(graph, axis=1)
    tri_grid = np.linspace(-0.5, 1.5, max(grid_size, 3))
    degree_grid = np.linspace(0.0, 1.5, max(grid_size, 3))
    feasible: list[tuple[float, float]] = []

    for triadic in tri_grid:
        for degree_penalty in degree_grid:
            violation = 0.0
            for i, j in zip(tri[0], tri[1], strict=True):
                common_neighbors = float(np.dot(graph[i], graph[j]))
                degree_feature = float(degree[i] + degree[j] - 2.0 * graph[i, j] + 1.0)
                utility = triadic * common_neighbors - degree_penalty * degree_feature
                if graph[i, j] > 0.0 and utility < -threshold_buffer:
                    violation += float(-utility - threshold_buffer)
                if graph[i, j] == 0.0 and utility > threshold_buffer:
                    violation += float(utility - threshold_buffer)
            if tri[0].size == 0 or violation / max(tri[0].size, 1) <= threshold_buffer:
                feasible.append((float(triadic), float(degree_penalty)))

    if feasible:
        tri_values = [item[0] for item in feasible]
        degree_values = [item[1] for item in feasible]
        parameter_bounds = {
            "triadic_closure": (float(min(tri_values)), float(max(tri_values))),
            "degree_penalty": (float(min(degree_values)), float(max(degree_values))),
        }
    else:
        parameter_bounds = {
            "triadic_closure": (float(tri_grid[0]), float(tri_grid[-1])),
            "degree_penalty": (float(degree_grid[0]), float(degree_grid[-1])),
        }
    feasible_share = float(len(feasible) / float(len(tri_grid) * len(degree_grid)))
    return NetworkFormationIdentifiedSet(
        parameter_bounds=parameter_bounds,
        grid_size=int(grid_size),
        feasible_share=feasible_share,
        violation_threshold=float(threshold_buffer),
    )


def _validation_summary(
    *,
    data: StrategicNetworkFormationData,
    adjacency: np.ndarray,
    predictive_graphs: np.ndarray,
    ridge: float,
    max_iter: int,
    holdout_fraction: float,
    heldout_log_loss_warn: float,
    temporal_drift_warn: float,
    seed: int,
) -> NetworkFormationValidationSummary:
    predictive_checks, predictive_warnings = _predictive_checks_from_graphs(
        adjacency, predictive_graphs
    )
    heldout_log_loss, holdout_warnings = _heldout_log_loss(
        data=data,
        adjacency=adjacency,
        ridge=ridge,
        max_iter=max_iter,
        holdout_fraction=holdout_fraction,
        seed=seed + 701,
    )
    temporal_drift, temporal_warnings = _temporal_parameter_drift(
        data=data,
        ridge=ridge,
        max_iter=max_iter,
    )
    warnings = list(predictive_warnings) + list(holdout_warnings) + list(temporal_warnings)
    overall_passed = all(check.passed for check in predictive_checks) if predictive_checks else True
    if heldout_log_loss is not None and heldout_log_loss > heldout_log_loss_warn:
        overall_passed = False
        warnings.append("held-out dyad log loss exceeded the configured warning threshold")
    if temporal_drift is not None and temporal_drift > temporal_drift_warn:
        overall_passed = False
        warnings.append("temporal parameter drift exceeded the configured warning threshold")
    return NetworkFormationValidationSummary(
        posterior_predictive_checks=predictive_checks,
        heldout_log_loss=heldout_log_loss,
        temporal_parameter_drift=temporal_drift,
        overall_passed=overall_passed,
        warnings=tuple(warnings),
    )


def _stationary_structural_fit(
    *,
    data: StrategicNetworkFormationData,
    adjacency: np.ndarray,
    ridge: float,
    max_iter: int,
    sa_iterations: int,
    sa_batch_draws: int,
    sa_learning_rate: float,
    sa_tolerance: float,
    burnin: int,
    interval: int,
    seed: int,
) -> tuple[
    dict[str, float],
    dict[str, float],
    dict[str, float],
    bool,
    bool,
    np.ndarray,
    list[str],
    _LogitFit,
]:
    dyad_features = (
        None if data.dyad_features is None else np.asarray(data.dyad_features, dtype=float)
    )
    design, responses, names, _, _ = _build_cross_sectional_design(
        adjacency,
        data,
        response_graph=adjacency,
        dyad_features=dyad_features,
    )
    warm_start_fit = _fit_logistic_ridge(design, responses, ridge=ridge, max_iter=max_iter)
    warm_start_parameters, warm_start_errors = _structuralize_estimates(
        names, warm_start_fit.beta, warm_start_fit.std_errors
    )
    parameter_order = _parameter_keys(warm_start_parameters)
    observed_stats = _sufficient_statistics(
        adjacency,
        data=data,
        dyad_features=dyad_features,
        parameter_names=parameter_order,
    )

    theta = dict(warm_start_parameters)
    trace_rmse: list[float] = []
    chain_state = adjacency.copy()
    predictive_graphs = np.zeros((0, adjacency.shape[0], adjacency.shape[1]), dtype=float)
    converged = False
    for iteration in range(max(sa_iterations, 1)):
        predictive_graphs, chain_state = _simulate_networks(
            data=data,
            parameters=theta,
            dyad_features=dyad_features,
            draws=max(sa_batch_draws, 1),
            burnin=burnin if iteration == 0 else max(interval, 1),
            interval=interval,
            seed=seed + 37 * (iteration + 1),
            initial_adjacency=chain_state,
        )
        if predictive_graphs.size == 0:
            break
        simulated_stats = [
            _sufficient_statistics(
                graph,
                data=data,
                dyad_features=dyad_features,
                parameter_names=parameter_order,
            )
            for graph in predictive_graphs
        ]
        averaged = {
            key: float(np.mean([stats[key] for stats in simulated_stats]))
            for key in parameter_order
        }
        diff = {key: float(observed_stats[key] - averaged[key]) for key in parameter_order}
        rmse = float(np.sqrt(np.mean([value * value for value in diff.values()]))) if diff else 0.0
        trace_rmse.append(rmse)
        learning_rate = float(sa_learning_rate / np.sqrt(iteration + 1.0))
        for key, value in diff.items():
            theta[key] = float(np.clip(theta.get(key, 0.0) + learning_rate * value, -6.0, 6.0))
        if rmse <= sa_tolerance:
            converged = True
            break

    standard_errors = {
        key: warm_start_errors.get(key, 1.0 / np.sqrt(max(design.shape[0], 1))) for key in theta
    }
    density_trace = np.asarray([_density(graph) for graph in predictive_graphs], dtype=float)
    fit_statistics = {
        "warm_start_log_likelihood": float(warm_start_fit.log_likelihood),
        "warm_start_iterations": float(warm_start_fit.iterations),
        "moment_rmse": float(trace_rmse[-1]) if trace_rmse else 0.0,
        "stochastic_approximation_steps": float(len(trace_rmse)),
        "density_simulation_ess": _effective_sample_size(density_trace)
        if density_trace.size
        else 0.0,
    }
    return (
        theta,
        standard_errors,
        fit_statistics,
        converged,
        True,
        predictive_graphs,
        names,
        warm_start_fit,
    )


@foundry_method(
    namespace="network.formation",
    version="1.0.0",
    tags={"network", "strategic-formation", "game-theory"},
)
class StrategicNetworkFormationEstimator:
    """Structural strategic-formation estimator with diagnostics and fallbacks."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="strategic_formation",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency",
                    SlotType.MATRIX,
                    Unit("network", "weight"),
                    shape=("n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=frozenset(
            {
                SlotSpec(
                    "result",
                    SlotType.SCALAR,
                    Unit("network", "json"),
                    contract_id=NetworkResult.contract_id,
                )
            }
        ),
        parameters=(
            ParameterSpec(name="prefer_event_history", default=True),
            ParameterSpec(name="cross_sectional_mode", default="auto"),
            ParameterSpec(name="ridge", default=0.5),
            ParameterSpec(name="max_iter", default=200),
            ParameterSpec(name="condition_number_warn", default=1.0e4),
            ParameterSpec(name="condition_number_block", default=1.0e8),
            ParameterSpec(name="fallback_grid_size", default=31),
            ParameterSpec(name="fallback_threshold_buffer", default=0.05),
            ParameterSpec(name="sa_iterations", default=10),
            ParameterSpec(name="sa_batch_draws", default=6),
            ParameterSpec(name="sa_learning_rate", default=0.75),
            ParameterSpec(name="sa_tolerance", default=0.02),
            ParameterSpec(name="mcmc_burnin", default=80),
            ParameterSpec(name="mcmc_interval", default=8),
            ParameterSpec(name="predictive_draws", default=20),
            ParameterSpec(name="bootstrap_draws", default=12),
            ParameterSpec(name="counterfactual_draws", default=20),
            ParameterSpec(name="ci_level", default=0.95),
            ParameterSpec(name="holdout_fraction", default=0.15),
            ParameterSpec(name="heldout_log_loss_warn", default=0.75),
            ParameterSpec(name="temporal_drift_warn", default=0.5),
            ParameterSpec(name="missingness", default=None),
            ParameterSpec(name="missingness_assessment", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N3,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Strategic network-formation estimator with event-history MLE, stationary structural refinement, partial-identification fallback, uncertainty, validation, and policy counterfactual simulation.",
        tags=frozenset({"network", "strategic-formation"}),
        when_to_use="Use for policy-facing strategic formation problems when you have network snapshots, dyad shifters, or formation/severance event logs.",
        citations=(
            "Jackson, M. & Wolinsky, A. (1996). A strategic model of social and economic networks. Journal of Economic Theory, 71(1), 44-74.",
            "Bala, V. & Goyal, S. (2000). A noncooperative model of network formation. Econometrica, 68(5), 1181-1229.",
            "Mele, A. (2017). A structural model of dense network formation. Econometrica, 85(3), 825-850.",
        ),
        when_not_to_use="Use descriptive graph estimators when no structural interpretation, dyadic support, or policy counterfactual is required.",
        output_interpretation="Returns a typed formation diagnostic with the selected estimation route, uncertainty intervals, validation checks, and optional counterfactual summaries.",
    )

    @staticmethod
    def materialize_input(
        bound_inputs: Mapping[str, Any], fallback_state: Any
    ) -> StrategicNetworkFormationData:
        payload = _strategic_payload(fallback_state)
        payload.update(bound_inputs)
        return StrategicNetworkFormationData.model_validate(payload)

    @staticmethod
    def pure_step(
        state: StrategicNetworkFormationData | Mapping[str, Any], params: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = (
            state
            if isinstance(state, StrategicNetworkFormationData)
            else StrategicNetworkFormationData.model_validate(state)
        )
        adjacency = _binary_undirected_adjacency(np.asarray(data.adjacency, dtype=float))
        density = _density(adjacency)
        clustering = _clustering(adjacency)
        n_nodes = adjacency.shape[0]
        observed_dyads = comb(n_nodes, 2) if n_nodes >= 2 else 0
        event_history_available = len(data.formation_events) > 0
        prefer_event_history = bool(params.get("prefer_event_history", True))
        cross_sectional_mode = str(params.get("cross_sectional_mode", "auto"))
        ridge = max(float(params.get("ridge", 0.5)), 1.0e-8)
        max_iter = max(int(params.get("max_iter", 200)), 1)
        condition_warn = max(float(params.get("condition_number_warn", 1.0e4)), 1.0)
        condition_block = max(float(params.get("condition_number_block", 1.0e8)), condition_warn)
        fallback_grid_size = max(int(params.get("fallback_grid_size", 31)), 3)
        fallback_threshold_buffer = max(float(params.get("fallback_threshold_buffer", 0.05)), 0.0)
        sa_iterations = max(int(params.get("sa_iterations", 10)), 1)
        sa_batch_draws = max(int(params.get("sa_batch_draws", 6)), 1)
        sa_learning_rate = float(params.get("sa_learning_rate", 0.75))
        sa_tolerance = max(float(params.get("sa_tolerance", 0.02)), 1.0e-6)
        burnin = max(int(params.get("mcmc_burnin", 80)), 0)
        interval = max(int(params.get("mcmc_interval", 8)), 1)
        predictive_draws = max(int(params.get("predictive_draws", 20)), 0)
        bootstrap_draws = max(int(params.get("bootstrap_draws", 12)), 0)
        counterfactual_draws = max(int(params.get("counterfactual_draws", 20)), 0)
        ci_level = float(np.clip(float(params.get("ci_level", 0.95)), 0.5, 0.999))
        holdout_fraction = float(np.clip(float(params.get("holdout_fraction", 0.15)), 0.0, 0.9))
        heldout_log_loss_warn = float(params.get("heldout_log_loss_warn", 0.75))
        temporal_drift_warn = float(params.get("temporal_drift_warn", 0.5))
        seed = int(params.get("__seed__", 0))

        parameter_estimates: dict[str, float] = {}
        standard_errors: dict[str, float] = {}
        fit_statistics: dict[str, float] = {}
        warnings: list[str] = []
        identified_set = None
        uncertainty_summary = None
        validation_summary = NetworkFormationValidationSummary(overall_passed=True, warnings=())
        counterfactual_summary = None
        warm_start_used = False
        fit_converged = False
        strategy_used = "blocked"
        model_class = "blocked"
        identification_status = "blocked"
        design_rank = None
        design_condition_number = None
        dyad_feature_dimension = 0
        dyad_feature_support = 0.0
        policy_counterfactual_ready = False
        fallback_reason = None

        if prefer_event_history and event_history_available:
            design, responses, names, dyad_feature_dimension, dyad_feature_support = (
                _build_event_history_design(data)
            )
            design_rank, design_condition_number = _design_diagnostics(design)
            fit = _fit_logistic_ridge(design, responses, ridge=ridge, max_iter=max_iter)
            parameter_estimates, standard_errors = _structuralize_estimates(
                names, fit.beta, fit.std_errors
            )
            fit_statistics = {
                "log_likelihood": float(fit.log_likelihood),
                "iterations": float(fit.iterations),
                "event_rate": float(np.mean(responses)) if responses.size else 0.0,
            }
            predictive_graphs = np.zeros((0, n_nodes, n_nodes), dtype=float)
            if _simulation_ready(data, parameter_estimates) and predictive_draws > 0:
                predictive_graphs, _ = _simulate_networks(
                    data=data,
                    parameters=parameter_estimates,
                    dyad_features=None
                    if data.dyad_features is None
                    else np.asarray(data.dyad_features, dtype=float),
                    draws=predictive_draws,
                    burnin=burnin,
                    interval=interval,
                    seed=seed + 211,
                    initial_adjacency=data.initial_adjacency
                    if data.initial_adjacency is not None
                    else data.adjacency,
                )
            validation_summary = _validation_summary(
                data=data,
                adjacency=adjacency,
                predictive_graphs=predictive_graphs,
                ridge=ridge,
                max_iter=max_iter,
                holdout_fraction=holdout_fraction,
                heldout_log_loss_warn=heldout_log_loss_warn,
                temporal_drift_warn=temporal_drift_warn,
                seed=seed,
            )
            parameter_draws = _normal_parameter_draws(
                names=names,
                fit=fit,
                draws=max(max(bootstrap_draws, predictive_draws), 8),
                seed=seed + 307,
            )
            counterfactual_summary, scenario_effects = _counterfactual_summary(
                data=data,
                parameter_draws=parameter_draws,
                point_parameters=parameter_estimates,
                ci_level=ci_level,
                burnin=burnin,
                interval=interval,
                draws=max(counterfactual_draws, 1),
                seed=seed + 401,
            )
            uncertainty_summary = _uncertainty_summary_from_draws(
                parameters=parameter_estimates,
                parameter_draws=parameter_draws,
                ci_level=ci_level,
                method="asymptotic_normal",
                scenario_effects=scenario_effects,
            )
            fit_converged = bool(fit.converged)
            strategy_used = "event_history_mle"
            model_class = "strategic_event_history_logit"
            identification_status = "point_identified"
            if dyad_feature_support <= 0.0 or (
                design_condition_number is not None and design_condition_number > condition_warn
            ):
                identification_status = "weakly_identified"
            warnings.extend(validation_summary.warnings)
            if design_condition_number is not None and design_condition_number > condition_warn:
                warnings.append(
                    "event-history design is ill-conditioned; interpret point estimates cautiously"
                )
            policy_counterfactual_ready = counterfactual_summary is not None
        else:
            design, responses, names, dyad_feature_dimension, dyad_feature_support = (
                _build_cross_sectional_design(
                    adjacency,
                    data,
                    response_graph=adjacency,
                    dyad_features=None
                    if data.dyad_features is None
                    else np.asarray(data.dyad_features, dtype=float),
                )
            )
            design_rank, design_condition_number = _design_diagnostics(design)
            if dyad_feature_support <= 0.0 or (
                design_condition_number is not None and design_condition_number > condition_block
            ):
                identified_set = _fallback_identified_set(
                    adjacency=adjacency,
                    grid_size=fallback_grid_size,
                    threshold_buffer=fallback_threshold_buffer,
                )
                strategy_used = "moment_inequality_fallback"
                model_class = "moment_inequality_pairwise_stability"
                identification_status = "partially_identified"
                fit_converged = False
                fallback_reason = "insufficient_dyad_covariate_support"
                fit_statistics = {"grid_feasible_share": float(identified_set.feasible_share)}
                warnings.append(
                    "dyad support is too weak for structural point estimation; returning an identified set"
                )
            else:
                use_pseudo_only = cross_sectional_mode in {"pseudo", "stationary_pseudolikelihood"}
                if use_pseudo_only:
                    fit = _fit_logistic_ridge(design, responses, ridge=ridge, max_iter=max_iter)
                    parameter_estimates, standard_errors = _structuralize_estimates(
                        names, fit.beta, fit.std_errors
                    )
                    fit_statistics = {
                        "log_likelihood": float(fit.log_likelihood),
                        "iterations": float(fit.iterations),
                        "edge_rate": float(np.mean(responses)) if responses.size else 0.0,
                    }
                    parameter_draws = _normal_parameter_draws(
                        names=names,
                        fit=fit,
                        draws=max(max(bootstrap_draws, predictive_draws), 8),
                        seed=seed + 521,
                    )
                    predictive_graphs = np.zeros((0, n_nodes, n_nodes), dtype=float)
                    if _simulation_ready(data, parameter_estimates) and predictive_draws > 0:
                        predictive_graphs, _ = _simulate_networks(
                            data=data,
                            parameters=parameter_estimates,
                            dyad_features=None
                            if data.dyad_features is None
                            else np.asarray(data.dyad_features, dtype=float),
                            draws=predictive_draws,
                            burnin=burnin,
                            interval=interval,
                            seed=seed + 613,
                            initial_adjacency=adjacency,
                        )
                    validation_summary = _validation_summary(
                        data=data,
                        adjacency=adjacency,
                        predictive_graphs=predictive_graphs,
                        ridge=ridge,
                        max_iter=max_iter,
                        holdout_fraction=holdout_fraction,
                        heldout_log_loss_warn=heldout_log_loss_warn,
                        temporal_drift_warn=temporal_drift_warn,
                        seed=seed,
                    )
                    counterfactual_summary, scenario_effects = _counterfactual_summary(
                        data=data,
                        parameter_draws=parameter_draws,
                        point_parameters=parameter_estimates,
                        ci_level=ci_level,
                        burnin=burnin,
                        interval=interval,
                        draws=max(counterfactual_draws, 1),
                        seed=seed + 701,
                    )
                    uncertainty_summary = _uncertainty_summary_from_draws(
                        parameters=parameter_estimates,
                        parameter_draws=parameter_draws,
                        ci_level=ci_level,
                        method="asymptotic_normal",
                        scenario_effects=scenario_effects,
                        warnings=(
                            "cross-sectional route used pseudolikelihood without structural refinement",
                        ),
                    )
                    fit_converged = bool(fit.converged)
                    strategy_used = "stationary_pseudolikelihood"
                    model_class = "stationary_pseudolikelihood"
                    identification_status = "weakly_identified"
                    warnings.append("cross-sectional route uses a pseudolikelihood approximation")
                    warnings.extend(validation_summary.warnings)
                    policy_counterfactual_ready = counterfactual_summary is not None
                else:
                    (
                        parameter_estimates,
                        standard_errors,
                        fit_statistics,
                        fit_converged,
                        warm_start_used,
                        predictive_graphs,
                        raw_names,
                        warm_start_fit,
                    ) = _stationary_structural_fit(
                        data=data,
                        adjacency=adjacency,
                        ridge=ridge,
                        max_iter=max_iter,
                        sa_iterations=sa_iterations,
                        sa_batch_draws=sa_batch_draws,
                        sa_learning_rate=sa_learning_rate,
                        sa_tolerance=sa_tolerance,
                        burnin=burnin,
                        interval=interval,
                        seed=seed,
                    )
                    validation_summary = _validation_summary(
                        data=data,
                        adjacency=adjacency,
                        predictive_graphs=predictive_graphs,
                        ridge=ridge,
                        max_iter=max_iter,
                        holdout_fraction=holdout_fraction,
                        heldout_log_loss_warn=heldout_log_loss_warn,
                        temporal_drift_warn=temporal_drift_warn,
                        seed=seed,
                    )
                    bootstrap_parameters = _bootstrap_parameter_draws(
                        data=data,
                        point_parameters=parameter_estimates,
                        draws=max(bootstrap_draws, 4),
                        ridge=ridge,
                        max_iter=max_iter,
                        burnin=max(interval, 4),
                        interval=interval,
                        seed=seed + 809,
                    )
                    if not bootstrap_parameters:
                        bootstrap_parameters = _normal_parameter_draws(
                            names=raw_names,
                            fit=warm_start_fit,
                            draws=max(bootstrap_draws, 4),
                            seed=seed + 877,
                        )
                    counterfactual_summary, scenario_effects = _counterfactual_summary(
                        data=data,
                        parameter_draws=bootstrap_parameters,
                        point_parameters=parameter_estimates,
                        ci_level=ci_level,
                        burnin=burnin,
                        interval=interval,
                        draws=max(counterfactual_draws, 1),
                        seed=seed + 941,
                    )
                    uncertainty_summary = _uncertainty_summary_from_draws(
                        parameters=parameter_estimates,
                        parameter_draws=bootstrap_parameters,
                        ci_level=ci_level,
                        method="bootstrap_refit",
                        scenario_effects=scenario_effects,
                    )
                    strategy_used = "stationary_mcmc_mle"
                    model_class = "stationary_structural_network_formation"
                    identification_status = "point_identified"
                    if (
                        design_condition_number is not None
                        and design_condition_number > condition_warn
                    ):
                        identification_status = "weakly_identified"
                        warnings.append(
                            "cross-sectional design is ill-conditioned; structural route remains weakly identified"
                        )
                    warnings.extend(validation_summary.warnings)
                    policy_counterfactual_ready = counterfactual_summary is not None

        missingness_assessment = maybe_build_missingness_assessment(
            NetworkData(
                adjacency=adjacency,
                node_features=data.node_features,
                node_ids=data.node_ids,
                metadata=data.metadata,
            ),
            params,
        )
        diagnostic = NetworkFormationDiagnostic(
            model_class=model_class,
            strategy_used=strategy_used,
            identification_status=identification_status,
            assumptions=(
                "network is undirected and links are formed under bilateral strategic incentives",
                "included dyad shifters span the policy-relevant support for the selected route",
            ),
            warnings=tuple(warnings),
            density=density,
            clustering=clustering,
            event_history_available=event_history_available,
            event_history_used=bool(strategy_used == "event_history_mle"),
            observed_events=len(data.formation_events),
            observed_dyads=observed_dyads,
            dyad_feature_dimension=dyad_feature_dimension,
            dyad_feature_support=dyad_feature_support,
            node_heterogeneity_present=data.node_features is not None,
            design_rank=design_rank,
            design_condition_number=design_condition_number,
            degeneracy_risk=_degeneracy_risk(adjacency),
            fit_converged=fit_converged,
            policy_counterfactual_ready=policy_counterfactual_ready,
            parameter_estimates=parameter_estimates,
            standard_errors=standard_errors,
            fit_statistics=fit_statistics,
            identified_set=identified_set,
            uncertainty_summary=uncertainty_summary,
            validation_summary=validation_summary,
            counterfactual_summary=counterfactual_summary,
            warm_start_used=warm_start_used,
            fallback_reason=fallback_reason,
        )
        metrics = {
            "density": density,
            "clustering": clustering,
            "observed_dyads": float(observed_dyads),
        }
        if diagnostic.counterfactual_summary is not None:
            density_effect = diagnostic.counterfactual_summary.effects.get("density")
            metrics["counterfactual_density_effect"] = (
                float(density_effect.estimate) if density_effect else 0.0
            )
        return {
            "result": NetworkResult(
                method_name="strategic_formation",
                metrics=metrics,
                formation_diagnostic=diagnostic,
                missingness_assessment=missingness_assessment,
                metadata={
                    "preferred_route": "event_history"
                    if prefer_event_history
                    else "cross_sectional",
                    "baseline_moments": _network_moments(adjacency).model_dump(mode="python"),
                },
            )
        }


__all__ = ["StrategicNetworkFormationEstimator"]
