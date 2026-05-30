"""Causal-frontier small-area estimation with boundary-constrained graph smoothing."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
from polisyos.foundry.methods.catalog._phase1_artifacts import resolve_artifact_store
from polisyos.foundry.methods.catalog.dependence.protocols import DependenceGraphSpec
from polisyos.foundry.methods.catalog.survey.protocols import SAEResult
from polisyos.ir.analytics.dependence_structure import (
    dependence_structure_from_graph_diagnostic,
    persist_dependence_structure,
)
from polisyos.ir.artifacts.io import put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel

_FLOAT_EPS = 1e-12


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("result", "json"),
                contract_id=SAEResult.contract_id,
            )
        }
    )


def _persist_quality_certificate(
    artifact_store: Any | None,
    quality_certificate: dict[str, Any],
) -> ArtifactRefModel | None:
    if artifact_store is None:
        return None
    ref = put_json_artifact(
        artifact_store,
        quality_certificate,
        kind="ir.sae_quality_certificate",
        schema_name="ir.sae_quality_certificate",
        schema_version="1.0",
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ArtifactRefModel.model_validate(ref)


def _validate_small_area_inputs(
    y_direct: np.ndarray,
    x_covariates: np.ndarray,
    sampling_var: np.ndarray,
    policy_indicator: np.ndarray,
) -> None:
    if y_direct.ndim != 1:
        raise ValueError("y_direct must be a 1D vector")
    if x_covariates.ndim != 2:
        raise ValueError("X must be a 2D matrix")
    if sampling_var.ndim != 1:
        raise ValueError("sampling_var must be a 1D vector")
    if policy_indicator.ndim != 1:
        raise ValueError("policy_indicator must be a 1D vector")
    n_areas = y_direct.shape[0]
    if (
        x_covariates.shape[0] != n_areas
        or sampling_var.shape[0] != n_areas
        or policy_indicator.shape[0] != n_areas
    ):
        raise ValueError("y_direct, X, sampling_var, and policy_indicator must align on n_areas")
    if n_areas < 3:
        raise ValueError("causal-frontier SAE requires at least 3 areas")
    if x_covariates.shape[1] < 1:
        raise ValueError("X must contain at least one covariate")
    if (
        not np.all(np.isfinite(y_direct))
        or not np.all(np.isfinite(x_covariates))
        or not np.all(np.isfinite(sampling_var))
    ):
        raise ValueError("y_direct, X, and sampling_var must be finite")
    if not np.all(np.isfinite(policy_indicator)):
        raise ValueError("policy_indicator must be finite")
    if np.any(sampling_var <= 0.0):
        raise ValueError("sampling_var must be strictly positive")
    if np.linalg.matrix_rank(x_covariates) < x_covariates.shape[1]:
        raise ValueError("X must have full column rank")


def _safe_solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(matrix, rhs)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(matrix) @ rhs


def _coerce_optional_vector(
    raw_value: Any,
    *,
    name: str,
    expected_length: int,
) -> np.ndarray | None:
    if raw_value is None:
        return None
    vector = np.asarray(raw_value, dtype=float).reshape(-1)
    if vector.shape[0] != expected_length:
        raise ValueError(f"{name} must have length {expected_length}")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must be finite")
    return vector


def _coerce_graph(
    state: Mapping[str, Any],
    params: Mapping[str, Any],
    *,
    n_areas: int,
) -> DependenceGraphSpec:
    requested_graph_id = params.get("graph_id")
    raw_graph = state.get("graph")
    if raw_graph is not None:
        return _normalize_graph(raw_graph, graph_id=requested_graph_id, n_areas=n_areas)

    raw_graphs = state.get("candidate_graphs")
    if raw_graphs is not None:
        if not isinstance(raw_graphs, Sequence):
            raise TypeError("candidate_graphs must be a sequence of graph specifications")
        normalized = [_normalize_graph(item, graph_id=None, n_areas=n_areas) for item in raw_graphs]
        if not normalized:
            raise ValueError("candidate_graphs must contain at least one graph")
        if isinstance(requested_graph_id, str) and requested_graph_id.strip():
            target = requested_graph_id.strip().lower()
            for graph in normalized:
                if graph.graph_id.lower() == target:
                    return graph
            raise ValueError(f"graph_id={requested_graph_id!r} was not found in candidate_graphs")
        return normalized[0]

    for key in ("W", "adjacency"):
        if key in state:
            return _normalize_graph(
                state[key],
                graph_id=requested_graph_id or "causal_frontier_graph",
                n_areas=n_areas,
            )
    raise KeyError("missing required graph input: provide graph, candidate_graphs, W, or adjacency")


def _normalize_graph(
    raw_graph: Any,
    *,
    graph_id: Any,
    n_areas: int,
) -> DependenceGraphSpec:
    if isinstance(raw_graph, DependenceGraphSpec):
        graph = raw_graph
    elif isinstance(raw_graph, Mapping):
        graph = DependenceGraphSpec.model_validate(raw_graph)
    else:
        graph = DependenceGraphSpec(
            graph_id=str(graph_id or "causal_frontier_graph"),
            family="CAR",
            W=np.asarray(raw_graph, dtype=float),
            metadata={},
        )
    if graph.W.shape != (n_areas, n_areas):
        raise ValueError(f"graph {graph.graph_id!r} must have shape {(n_areas, n_areas)}")
    return graph


def _area_index_lookup(area_ids: Sequence[str] | None) -> dict[str, int]:
    if area_ids is None:
        return {}
    return {str(area_id): idx for idx, area_id in enumerate(area_ids)}


def _coerce_frontier_mask(
    raw_mask: Any,
    *,
    n_areas: int,
    area_ids: Sequence[str] | None = None,
) -> np.ndarray:
    if raw_mask is None:
        raise KeyError(
            "missing required frontier specification: provide frontier_mask or frontier_edges"
        )

    try:
        matrix = np.asarray(raw_mask, dtype=float)
    except (TypeError, ValueError):
        matrix = None
    if matrix is not None and matrix.ndim == 2 and matrix.shape == (n_areas, n_areas):
        mask = matrix > 0.0
        mask = np.logical_or(mask, mask.T)
        np.fill_diagonal(mask, False)
        return mask

    if not isinstance(raw_mask, Sequence):
        raise TypeError("frontier_edges must be a sequence of edge specifications")

    area_lookup = _area_index_lookup(area_ids)
    mask = np.zeros((n_areas, n_areas), dtype=bool)
    for edge in raw_mask:
        src, dst, is_frontier = _parse_frontier_edge(edge)
        if not is_frontier:
            continue
        src_idx = _resolve_area_index(src, area_lookup=area_lookup, n_areas=n_areas)
        dst_idx = _resolve_area_index(dst, area_lookup=area_lookup, n_areas=n_areas)
        if src_idx == dst_idx:
            continue
        mask[src_idx, dst_idx] = True
        mask[dst_idx, src_idx] = True
    return mask


def _parse_frontier_edge(edge: Any) -> tuple[Any, Any, bool]:
    if isinstance(edge, Mapping):
        src = edge.get("src_area_id", edge.get("src", edge.get("source")))
        dst = edge.get("dst_area_id", edge.get("dst", edge.get("target")))
        frontier_flag = edge.get("frontier_flag", edge.get("is_frontier", True))
        return src, dst, bool(frontier_flag)
    if isinstance(edge, Sequence) and not isinstance(edge, (str, bytes)):
        if len(edge) == 2:
            return edge[0], edge[1], True
        if len(edge) >= 3:
            return edge[0], edge[1], bool(edge[2])
    raise TypeError(
        "frontier edge must be a mapping or a tuple/list like (src, dst[, frontier_flag])"
    )


def _resolve_area_index(
    raw_index: Any,
    *,
    area_lookup: Mapping[str, int],
    n_areas: int,
) -> int:
    if isinstance(raw_index, (int, np.integer)):
        index = int(raw_index)
    else:
        key = str(raw_index)
        if key not in area_lookup:
            raise ValueError(f"unknown area id in frontier edges: {raw_index!r}")
        index = area_lookup[key]
    if index < 0 or index >= n_areas:
        raise ValueError(f"frontier edge index {index} is out of bounds for n_areas={n_areas}")
    return index


def _symmetrize_weights(raw_weights: Any, *, n_areas: int) -> np.ndarray:
    weights = np.asarray(raw_weights, dtype=float)
    if weights.shape != (n_areas, n_areas):
        raise ValueError(f"graph weights must have shape {(n_areas, n_areas)}")
    if not np.all(np.isfinite(weights)):
        raise ValueError("graph weights must be finite")
    if np.any(weights < 0.0):
        raise ValueError("graph weights must be non-negative")
    weights = 0.5 * (weights + weights.T)
    np.fill_diagonal(weights, 0.0)
    return weights


def _connected_components(weights: np.ndarray) -> tuple[np.ndarray, tuple[np.ndarray, ...]]:
    n_areas = weights.shape[0]
    adjacency = weights > 0.0
    component_ids = np.full(n_areas, -1, dtype=int)
    components: list[np.ndarray] = []
    next_component = 0
    for start in range(n_areas):
        if component_ids[start] != -1:
            continue
        stack = [start]
        nodes: list[int] = []
        component_ids[start] = next_component
        while stack:
            current = stack.pop()
            nodes.append(current)
            neighbors = np.nonzero(adjacency[current])[0]
            for neighbor in neighbors:
                if component_ids[neighbor] == -1:
                    component_ids[neighbor] = next_component
                    stack.append(int(neighbor))
        components.append(np.asarray(sorted(nodes), dtype=int))
        next_component += 1
    return component_ids, tuple(components)


def _component_sum_penalty(
    components: Sequence[np.ndarray],
    *,
    n_areas: int,
) -> np.ndarray:
    penalty = np.zeros((n_areas, n_areas), dtype=float)
    for component in components:
        penalty[np.ix_(component, component)] += 1.0
    return penalty


def _laplacian(weights: np.ndarray) -> np.ndarray:
    return np.diag(np.sum(weights, axis=1)) - weights


def _fit_frontier_smoother(
    *,
    y_direct: np.ndarray,
    x_covariates: np.ndarray,
    sampling_var: np.ndarray,
    policy_indicator: np.ndarray,
    spillover_exposure: np.ndarray | None,
    weights: np.ndarray,
    lambda_spatial: float,
    component_ridge: float,
) -> dict[str, Any]:
    n_areas = y_direct.shape[0]
    precision_diag = 1.0 / np.maximum(sampling_var, _FLOAT_EPS)
    precision_y = np.diag(precision_diag)
    components_ids, components = _connected_components(weights)
    component_penalty = _component_sum_penalty(components, n_areas=n_areas)
    laplacian = _laplacian(weights)

    design_columns = [x_covariates, policy_indicator.reshape(-1, 1)]
    coefficient_names = [f"beta_{idx}" for idx in range(x_covariates.shape[1])] + ["tau"]
    if spillover_exposure is not None:
        design_columns.append(spillover_exposure.reshape(-1, 1))
        coefficient_names.append("spillover_gamma")
    design_matrix = np.column_stack(design_columns)
    weighted_design = design_matrix.T * precision_diag

    coefficient_block = weighted_design @ design_matrix
    smoothing_block = precision_y + lambda_spatial * laplacian + component_ridge * component_penalty
    system = np.block(
        [
            [coefficient_block, weighted_design],
            [weighted_design.T, smoothing_block],
        ]
    )
    rhs = np.concatenate([weighted_design @ y_direct, precision_diag * y_direct], axis=0)
    solution = _safe_solve(system, rhs)

    n_coefficients = design_matrix.shape[1]
    coefficients = solution[:n_coefficients]
    smooth_field = solution[n_coefficients:]
    regression_mean = design_matrix @ coefficients
    theta = regression_mean + smooth_field
    residual = y_direct - theta

    covariance = np.linalg.pinv(system)
    map_operator = np.hstack([design_matrix, np.eye(n_areas, dtype=float)])
    theta_covariance = map_operator @ covariance @ map_operator.T
    mse = np.clip(np.diag(theta_covariance), 0.0, None)
    component_sizes = [int(component.shape[0]) for component in components]

    return {
        "theta": theta,
        "mse": mse,
        "theta_sd": np.sqrt(np.maximum(mse, 0.0)),
        "coefficients": coefficients,
        "coefficient_names": coefficient_names,
        "beta": coefficients[: x_covariates.shape[1]],
        "tau": float(coefficients[x_covariates.shape[1]]),
        "spillover_gamma": (float(coefficients[-1]) if spillover_exposure is not None else None),
        "smooth_field": smooth_field,
        "regression_mean": regression_mean,
        "residual": residual,
        "components": components,
        "component_ids": components_ids,
        "component_sizes": component_sizes,
        "borrow_strength_neighbors": np.sum(weights > 0.0, axis=1).astype(int),
        "laplacian_trace": float(np.trace(laplacian)),
        "condition_number": float(np.linalg.cond(system)),
        "objective": float(
            0.5 * np.sum(precision_diag * residual**2)
            + 0.5 * lambda_spatial * smooth_field @ laplacian @ smooth_field
            + 0.5 * component_ridge * smooth_field @ component_penalty @ smooth_field
        ),
    }


def _weighted_residualize(
    vector: np.ndarray,
    x_covariates: np.ndarray,
    sampling_var: np.ndarray,
) -> np.ndarray:
    precision_diag = 1.0 / np.maximum(sampling_var, _FLOAT_EPS)
    weighted_x = x_covariates.T * precision_diag
    beta = _safe_solve(weighted_x @ x_covariates, weighted_x @ vector)
    return vector - x_covariates @ beta


def _projection_leakage_index(
    *,
    policy_indicator: np.ndarray,
    x_covariates: np.ndarray,
    sampling_var: np.ndarray,
    unrestricted_field: np.ndarray,
) -> float:
    z_perp = _weighted_residualize(policy_indicator, x_covariates, sampling_var)
    weight = 1.0 / np.maximum(sampling_var, _FLOAT_EPS)
    denominator = float(np.sum(weight * unrestricted_field**2))
    if denominator <= _FLOAT_EPS:
        return 0.0
    z_norm = float(np.sum(weight * z_perp**2))
    if z_norm <= _FLOAT_EPS:
        return 0.0
    projection_scale = float(np.sum(weight * z_perp * unrestricted_field) / z_norm)
    projected = projection_scale * z_perp
    numerator = float(np.sum(weight * projected**2))
    return float(np.clip(numerator / denominator, 0.0, 1.0))


def _boundary_leakage_ratio(
    unrestricted_tau: float,
    constrained_tau: float,
    *,
    eps: float,
) -> float:
    unrestricted_abs = abs(float(unrestricted_tau))
    constrained_abs = abs(float(constrained_tau))
    if unrestricted_abs <= eps and constrained_abs <= eps:
        return 0.0
    return float(max(0.0, 1.0 - unrestricted_abs / max(constrained_abs, eps)))


def _alert_level(
    blr: float,
    *,
    green_threshold: float,
    red_threshold: float,
) -> str:
    if blr < green_threshold:
        return "green"
    if blr < red_threshold:
        return "amber"
    return "red"


def _upper_edge_count(mask: np.ndarray) -> int:
    return int(np.count_nonzero(np.triu(mask, k=1)))


@foundry_method(
    namespace="survey.estimation",
    version="1.0.0",
    tags={"survey", "small-area", "causal-frontier", "fay-herriot", "graph"},
)
class CausalFrontierFayHerriotEstimator:
    """Boundary-constrained small-area estimator that avoids smoothing across causal frontiers."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="causal_frontier_fay_herriot",
        namespace="",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "y_direct", SlotType.VECTOR, Unit("estimate", "value"), shape=("n_areas",)
                ),
                SlotSpec(
                    "X",
                    SlotType.MATRIX,
                    Unit("covariate", "value"),
                    shape=("n_areas", "n_covariates"),
                ),
                SlotSpec(
                    "sampling_var", SlotType.VECTOR, Unit("variance", "value"), shape=("n_areas",)
                ),
                SlotSpec(
                    "policy_indicator", SlotType.VECTOR, Unit("policy", "value"), shape=("n_areas",)
                ),
                SlotSpec("graph", SlotType.SCALAR, Unit("graph", "json")),
                SlotSpec("frontier_mask", SlotType.SCALAR, Unit("graph", "json")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="graph_id", default=None),
            ParameterSpec(name="lambda_spatial", default=1.0),
            ParameterSpec(name="component_ridge", default=1e-6),
            ParameterSpec(name="contrast_eps", default=1e-8),
            ParameterSpec(name="green_threshold", default=0.05),
            ParameterSpec(name="red_threshold", default=0.15),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Penalized causal-frontier Fay-Herriot smoother that cuts graph edges crossing declared policy frontiers and diagnoses boundary leakage against an unrestricted baseline.",
        tags=frozenset(
            {
                "survey",
                "small-area",
                "causal-frontier",
                "fay-herriot",
                "boundary-leakage",
            }
        ),
        citations=(
            "Fay, R.E. & Herriot, R.A. (1979). Estimates of Income for Small Places. JASA.",
        ),
        equations={
            "constrained_objective": (
                "argmin_{beta,tau,u} 0.5*(y-Xbeta-tau z-u)' D^{-1}(y-Xbeta-tau z-u) "
                "+ 0.5*lambda*u' L* u"
            ),
            "boundary_leakage_ratio": "BLR = max(0, 1 - |tau_unc| / (|tau_cut| + eps))",
        },
        determinism_tier=DeterminismTier.LIBRARY_DETERMINISTIC,
        required_deps=("numpy",),
        when_to_use="Areal small-area estimation when smoothing must not cross declared causal or policy frontiers and leakage diagnostics should compare unrestricted versus constrained borrowing strength.",
        typical_min_obs=5,
        output_interpretation="The constrained estimates borrow strength only within frontier-respecting connected components; BLR/PLI indicate whether unrestricted smoothing was absorbing the policy contrast.",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        y_direct = np.asarray(state["y_direct"], dtype=float)
        x_covariates = np.asarray(state["X"], dtype=float)
        sampling_var = np.asarray(state["sampling_var"], dtype=float)
        policy_indicator = np.asarray(state["policy_indicator"], dtype=float)
        _validate_small_area_inputs(y_direct, x_covariates, sampling_var, policy_indicator)

        n_areas = y_direct.shape[0]
        area_ids_raw = state.get("area_ids")
        area_ids = tuple(str(item) for item in area_ids_raw) if area_ids_raw is not None else None
        graph = _coerce_graph(state, params, n_areas=n_areas)
        full_weights = _symmetrize_weights(graph.W, n_areas=n_areas)
        raw_frontier = state.get("frontier_mask", state.get("frontier_edges"))
        frontier_mask = _coerce_frontier_mask(raw_frontier, n_areas=n_areas, area_ids=area_ids)
        cut_weights = full_weights * (~frontier_mask)
        spillover_exposure = _coerce_optional_vector(
            state.get("spillover_exposure"),
            name="spillover_exposure",
            expected_length=n_areas,
        )

        lambda_spatial = float(params.get("lambda_spatial", 1.0))
        component_ridge = float(params.get("component_ridge", 1e-6))
        contrast_eps = float(params.get("contrast_eps", 1e-8))
        green_threshold = float(params.get("green_threshold", 0.05))
        red_threshold = float(params.get("red_threshold", 0.15))
        if lambda_spatial < 0.0:
            raise ValueError("lambda_spatial must be non-negative")
        if component_ridge < 0.0:
            raise ValueError("component_ridge must be non-negative")
        if not 0.0 <= green_threshold <= red_threshold:
            raise ValueError(
                "green_threshold must be <= red_threshold and both must be non-negative"
            )

        unrestricted_fit = _fit_frontier_smoother(
            y_direct=y_direct,
            x_covariates=x_covariates,
            sampling_var=sampling_var,
            policy_indicator=policy_indicator,
            spillover_exposure=spillover_exposure,
            weights=full_weights,
            lambda_spatial=lambda_spatial,
            component_ridge=component_ridge,
        )
        constrained_fit = _fit_frontier_smoother(
            y_direct=y_direct,
            x_covariates=x_covariates,
            sampling_var=sampling_var,
            policy_indicator=policy_indicator,
            spillover_exposure=spillover_exposure,
            weights=cut_weights,
            lambda_spatial=lambda_spatial,
            component_ridge=component_ridge,
        )

        frontier_edges_total = _upper_edge_count(frontier_mask)
        frontier_edges_active = _upper_edge_count(frontier_mask & (full_weights > 0.0))
        cut_component_ids = constrained_fit["component_ids"]
        cut_component_sizes = constrained_fit["component_sizes"]
        singletons_after_cut = int(sum(size == 1 for size in cut_component_sizes))
        variance_inflation_ratio = float(
            np.mean(constrained_fit["mse"]) / max(np.mean(unrestricted_fit["mse"]), _FLOAT_EPS)
        )
        blr = _boundary_leakage_ratio(
            unrestricted_fit["tau"],
            constrained_fit["tau"],
            eps=contrast_eps,
        )
        pli = _projection_leakage_index(
            policy_indicator=policy_indicator,
            x_covariates=x_covariates,
            sampling_var=sampling_var,
            unrestricted_field=np.asarray(unrestricted_fit["smooth_field"], dtype=float),
        )
        alert_level = _alert_level(
            blr,
            green_threshold=green_threshold,
            red_threshold=red_threshold,
        )

        diagnostics = {
            "blr": blr,
            "pli": pli,
            "variance_inflation_ratio": variance_inflation_ratio,
            "singletons_after_cut": singletons_after_cut,
            "frontier_edges_total": frontier_edges_total,
            "frontier_edges_active": frontier_edges_active,
            "component_sizes": cut_component_sizes,
            "component_count": len(cut_component_sizes),
            "alert_level": alert_level,
            "calibration_quantiles": {
                "green_threshold": green_threshold,
                "red_threshold": red_threshold,
            },
            "tau_unrestricted": float(unrestricted_fit["tau"]),
            "tau_constrained": float(constrained_fit["tau"]),
            "spillover_term_included": spillover_exposure is not None,
            "graph_id": graph.graph_id,
            "graph_family": graph.family,
            "decision": "identified",
            "identifiable": True,
            "class_label": "graph_local",
            "strength": "strong" if frontier_edges_active > 0 else "weak",
            "selected_graph_id": graph.graph_id,
            "fallback_reason": None,
            "information_condition_number": float(constrained_fit["condition_number"]),
        }
        quality_certificate = {
            "estimator": "survey.estimation.causal_frontier_fay_herriot",
            "assumptions": {
                "declared_frontier_respected": True,
                "nuisance_borrowing_crosses_frontier": False,
                "spillover_term_included": spillover_exposure is not None,
            },
            "frontier": {
                "graph_id": graph.graph_id,
                "frontier_edges_total": frontier_edges_total,
                "frontier_edges_active": frontier_edges_active,
                "component_sizes": cut_component_sizes,
            },
            "diagnostics": diagnostics,
        }

        artifact_store = resolve_artifact_store(
            state if isinstance(state, Mapping) else None, params
        )
        dependence_structure = dependence_structure_from_graph_diagnostic(
            diagnostics,
            regime="areal",
            source_method="survey.estimation.causal_frontier_fay_herriot",
        )
        dependence_ref = (
            persist_dependence_structure(artifact_store, dependence_structure)
            if artifact_store is not None
            else None
        )
        quality_certificate_ref = _persist_quality_certificate(
            artifact_store,
            quality_certificate,
        )

        statistics = {
            "selected_model": "causal_frontier_constrained",
            "n_areas": n_areas,
            "estimates": np.asarray(constrained_fit["theta"], dtype=float).tolist(),
            "theta_sd": np.asarray(constrained_fit["theta_sd"], dtype=float).tolist(),
            "mse": np.asarray(constrained_fit["mse"], dtype=float).tolist(),
            "beta": np.asarray(constrained_fit["beta"], dtype=float).tolist(),
            "tau": float(constrained_fit["tau"]),
            "spillover_gamma": constrained_fit["spillover_gamma"],
            "component_ids": cut_component_ids.astype(int).tolist(),
            "borrow_strength_neighbors": np.asarray(
                constrained_fit["borrow_strength_neighbors"],
                dtype=int,
            ).tolist(),
            "variance_components": {
                "lambda_spatial": lambda_spatial,
                "component_ridge": component_ridge,
                "laplacian_trace": float(constrained_fit["laplacian_trace"]),
                "selected_graph_id": graph.graph_id,
            },
            "diagnostics": diagnostics,
            "baseline_unrestricted": {
                "estimates": np.asarray(unrestricted_fit["theta"], dtype=float).tolist(),
                "mse": np.asarray(unrestricted_fit["mse"], dtype=float).tolist(),
                "tau": float(unrestricted_fit["tau"]),
                "spillover_gamma": unrestricted_fit["spillover_gamma"],
                "borrow_strength_neighbors": np.asarray(
                    unrestricted_fit["borrow_strength_neighbors"],
                    dtype=int,
                ).tolist(),
            },
            "graph": {
                "graph_id": graph.graph_id,
                "family": graph.family,
                "n_areas": n_areas,
            },
        }
        if area_ids is not None:
            statistics["area_ids"] = list(area_ids)

        return {
            "result": SAEResult(
                method_name="survey.estimation.causal_frontier_fay_herriot",
                statistics=statistics,
                dependence_ref=dependence_ref,
                quality_certificate_ref=quality_certificate_ref,
                metadata={
                    "diagnostics": diagnostics,
                    "quality_certificate": quality_certificate,
                },
            )
        }


__all__ = ["CausalFrontierFayHerriotEstimator"]
