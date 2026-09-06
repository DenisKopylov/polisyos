"""ERGM-inspired null models and diffusion anomaly tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar

import numpy as np
from pydantic import ValidationError

try:  # pragma: no cover - preferred in full scientific environments.
    from sklearn.linear_model import LogisticRegression
except ImportError:  # pragma: no cover - keeps catalog reflection importable.
    LogisticRegression = None  # type: ignore[assignment]

from polisyos.core.observability import DeterminismTier
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

from .generative_protocols import DiffusionNullResult, EdgeListNetworkData, ERGMResult
from .protocols import NetworkData


def _result_slot(contract_id: str) -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("network", "json"),
                contract_id=contract_id,
            )
        }
    )


def _symmetrize(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    return 0.5 * (arr + arr.T)


def _network_payload(state: Any) -> NetworkData:
    if isinstance(state, NetworkData):
        return state
    if isinstance(state, EdgeListNetworkData):
        return state.to_network_data()
    if isinstance(state, Mapping):
        nested = state.get("network_data")
        if isinstance(nested, NetworkData):
            return nested
        if isinstance(nested, EdgeListNetworkData):
            return nested.to_network_data()
        if isinstance(nested, Mapping):
            state = nested
        try:
            if "edge_index" in state:
                return EdgeListNetworkData.model_validate(dict(state)).to_network_data()
            return NetworkData.model_validate(dict(state))
        except ValidationError as exc:
            raise TypeError("state must be NetworkData-compatible") from exc
    raise TypeError("state must be NetworkData, EdgeListNetworkData, or mapping")


def _edgewise_shared_partners(adjacency: np.ndarray) -> np.ndarray:
    binary = (np.asarray(adjacency, dtype=float) > 0.0).astype(float)
    return binary @ binary


def _cosine_similarity(features: np.ndarray) -> np.ndarray:
    arr = np.asarray(features, dtype=float)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    normalized = arr / norms
    cosine = normalized @ normalized.T
    return 0.5 * (1.0 + cosine)


def _resolve_group_labels(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    n_units: int,
) -> np.ndarray | None:
    raw = params.get(
        "group_labels", metadata.get("ergm_group_labels", metadata.get("group_labels"))
    )
    if raw is None:
        return None
    groups = np.asarray(raw)
    if groups.ndim != 1 or groups.shape[0] != n_units:
        return None
    return groups


def _resolve_dyad_covariate(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    n_units: int,
) -> np.ndarray | None:
    raw = params.get("dyad_covariate", metadata.get("dyad_covariate_matrix"))
    if raw is None:
        return None
    matrix = np.asarray(raw, dtype=float)
    if matrix.shape != (n_units, n_units):
        return None
    return _symmetrize(matrix)


def _quantiles(values: np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"q25": 0.0, "q50": 0.0, "q75": 0.0}
    q25, q50, q75 = np.quantile(arr, [0.25, 0.50, 0.75])
    return {"q25": float(q25), "q50": float(q50), "q75": float(q75)}


def _edgewise_shared_partner_quantiles(adjacency: np.ndarray) -> dict[str, float]:
    adj = (np.asarray(adjacency, dtype=float) > 0.0).astype(float)
    tri = np.triu_indices_from(adj, k=1)
    edge_mask = adj[tri] > 0.0
    if not np.any(edge_mask):
        return {"q25": 0.0, "q50": 0.0, "q75": 0.0}
    esp = _edgewise_shared_partners(adj)[tri][edge_mask]
    return _quantiles(esp)


def _envelope(values: np.ndarray) -> dict[str, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"q05": 0.0, "q50": 0.0, "q95": 0.0}
    q05, q50, q95 = np.quantile(arr, [0.05, 0.50, 0.95])
    return {"q05": float(q05), "q50": float(q50), "q95": float(q95)}


def _diffusion_metric(
    adjacency: np.ndarray,
    node_states: np.ndarray,
    *,
    diffusion_rate: float,
    decay: float,
    n_steps: int,
) -> float:
    adj = np.asarray(adjacency, dtype=float)
    row_sums = np.sum(adj, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    normalized = adj / row_sums
    current = np.asarray(node_states, dtype=float)
    for _ in range(max(n_steps, 1)):
        current = np.clip(
            (1.0 - decay) * current + diffusion_rate * (normalized @ current), 0.0, 1.0
        )
    return float(np.mean(current))


def _two_sided_p_value(observed: float, simulated: np.ndarray) -> float:
    sims = np.asarray(simulated, dtype=float)
    center = float(np.mean(sims))
    obs_distance = abs(observed - center)
    sim_distance = np.abs(sims - center)
    return float((1.0 + np.sum(sim_distance >= obs_distance)) / (len(sims) + 1.0))


@dataclass(frozen=True)
class _ERGMFitArtifacts:
    result: ERGMResult
    probability_matrix: np.ndarray
    simulated_graphs: np.ndarray


def fit_ergm_null_model(state: Any, params: Mapping[str, Any]) -> _ERGMFitArtifacts:
    """Fit a sparse ERGM-inspired null-lite model and simulate null graphs."""
    data = _network_payload(state)
    adjacency = _symmetrize(np.asarray(data.adjacency, dtype=float))
    binary = (adjacency > 0.0).astype(float)
    n_units = adjacency.shape[0]
    tri = np.triu_indices_from(binary, k=1)
    y = binary[tri].astype(int)
    degree = np.sum(binary, axis=1)
    common = _edgewise_shared_partners(binary)
    degree_decay = max(1e-6, float(params.get("degree_decay", 0.35)))
    triangle_decay = max(1e-6, float(params.get("triangle_decay", 0.40)))
    ridge_penalty = max(1e-6, float(params.get("ridge_penalty", 1.0)))
    n_simulations = max(1, int(params.get("n_simulations", 32)))
    save_graphs = max(0, int(params.get("save_graphs", min(4, n_simulations))))
    seed = int(params.get("__seed__", 0))

    feature_names = ["gwdegree", "gwesp"]
    gwdegree = (1.0 - np.exp(-degree_decay * degree[tri[0]])) + (
        1.0 - np.exp(-degree_decay * degree[tri[1]])
    )
    gwesp = 1.0 - np.exp(-triangle_decay * common[tri])
    features = [gwdegree, gwesp]

    group_labels = _resolve_group_labels(params, data.metadata, n_units)
    if group_labels is not None:
        feature_names.append("nodemix")
        features.append((group_labels[tri[0]] == group_labels[tri[1]]).astype(float))

    dyad_covariate = _resolve_dyad_covariate(params, data.metadata, n_units)
    if dyad_covariate is not None:
        feature_names.append("edgecov")
        features.append(np.asarray(dyad_covariate[tri], dtype=float))
    elif data.node_features is not None:
        feature_names.append("edgecov")
        similarity = _cosine_similarity(np.asarray(data.node_features, dtype=float))
        features.append(similarity[tri])

    X = np.column_stack(features) if features else np.zeros((len(y), 0), dtype=float)

    if np.unique(y).size == 1:
        baseline = float(y[0])
        p = np.full((n_units, n_units), baseline, dtype=float)
        np.fill_diagonal(p, 0.0)
        simulated = np.repeat(p[None, :, :], n_simulations, axis=0)
        coefficients = {"intercept": float(np.log((baseline + 1e-6) / (1.0 - baseline + 1e-6)))}
    else:
        if LogisticRegression is None:
            raise ImportError("scikit-learn is required for ERGM logistic fitting")
        model = LogisticRegression(
            C=1.0 / ridge_penalty,
            solver="lbfgs",
            max_iter=2000,
            random_state=seed,
        )
        model.fit(X, y)
        probabilities = model.predict_proba(X)[:, 1]
        p = np.zeros((n_units, n_units), dtype=float)
        p[tri] = probabilities
        p += p.T
        np.fill_diagonal(p, 0.0)
        rng = np.random.default_rng(seed + 31)
        simulated = np.zeros((n_simulations, n_units, n_units), dtype=float)
        for sim_idx in range(n_simulations):
            draws = (rng.uniform(size=probabilities.shape[0]) < probabilities).astype(float)
            graph = np.zeros((n_units, n_units), dtype=float)
            graph[tri] = draws
            graph += graph.T
            simulated[sim_idx] = graph
        coefficients = {"intercept": float(model.intercept_[0])}
        coefficients.update(
            {
                name: float(weight)
                for name, weight in zip(feature_names, model.coef_[0], strict=True)
            }
        )

    if np.unique(y).size == 1:
        rng = np.random.default_rng(seed + 31)
        simulated = np.zeros((n_simulations, n_units, n_units), dtype=float)
        for sim_idx in range(n_simulations):
            draws = (rng.uniform(size=y.shape[0]) < float(np.mean(y))).astype(float)
            graph = np.zeros((n_units, n_units), dtype=float)
            graph[tri] = draws
            graph += graph.T
            simulated[sim_idx] = graph

    observed_density = float(np.mean(binary[tri])) if y.size else 0.0
    sim_density = (
        np.mean(simulated[:, tri[0], tri[1]], axis=1) if y.size else np.zeros(n_simulations)
    )
    observed_degree = _quantiles(degree)
    observed_esp = _edgewise_shared_partner_quantiles(binary)
    sim_degree_q25 = np.asarray(
        [_quantiles(np.sum(graph, axis=1))["q25"] for graph in simulated], dtype=float
    )
    sim_degree_q50 = np.asarray(
        [_quantiles(np.sum(graph, axis=1))["q50"] for graph in simulated], dtype=float
    )
    sim_degree_q75 = np.asarray(
        [_quantiles(np.sum(graph, axis=1))["q75"] for graph in simulated], dtype=float
    )
    sim_esp_q25 = np.asarray(
        [_edgewise_shared_partner_quantiles(graph)["q25"] for graph in simulated], dtype=float
    )
    sim_esp_q50 = np.asarray(
        [_edgewise_shared_partner_quantiles(graph)["q50"] for graph in simulated], dtype=float
    )
    sim_esp_q75 = np.asarray(
        [_edgewise_shared_partner_quantiles(graph)["q75"] for graph in simulated], dtype=float
    )
    density_envelope = _envelope(sim_density)
    degree_envelope = {
        "q25": _envelope(sim_degree_q25),
        "q50": _envelope(sim_degree_q50),
        "q75": _envelope(sim_degree_q75),
    }
    esp_envelope = {
        "q25": _envelope(sim_esp_q25),
        "q50": _envelope(sim_esp_q50),
        "q75": _envelope(sim_esp_q75),
    }
    observed_in_envelope = (
        density_envelope["q05"] <= observed_density <= density_envelope["q95"]
        and degree_envelope["q25"]["q05"] <= observed_degree["q25"] <= degree_envelope["q25"]["q95"]
        and degree_envelope["q50"]["q05"] <= observed_degree["q50"] <= degree_envelope["q50"]["q95"]
        and degree_envelope["q75"]["q05"] <= observed_degree["q75"] <= degree_envelope["q75"]["q95"]
    )
    extreme_density_share = float(np.mean((sim_density < 0.02) | (sim_density > 0.98)))
    degeneracy_alarm = bool(
        extreme_density_share > 0.20
        or np.mean(sim_density) < 0.03
        or np.mean(sim_density) > 0.97
        or not observed_in_envelope
    )

    result = ERGMResult(
        method_name="ergm_null",
        fit_status="null_lite",
        coefficients=coefficients,
        diagnostics={
            "backend": "penalized_mple_null_lite",
            "feature_names": feature_names,
            "observed_edge_density": observed_density,
            "simulated_edge_density_mean": float(np.mean(sim_density)),
            "extreme_density_share": extreme_density_share,
            "observed_degree_quantiles": observed_degree,
            "observed_esp_quantiles": observed_esp,
            "observed_in_envelope": observed_in_envelope,
        },
        gof_checks={
            "edge_density": density_envelope,
            "degree_quantiles": degree_envelope,
            "esp_quantiles": esp_envelope,
        },
        null_envelope={
            "edge_density": density_envelope,
            "degree_quantiles": degree_envelope,
            "esp_quantiles": esp_envelope,
        },
        simulated_graphs=simulated[:save_graphs] if save_graphs > 0 else None,
        degeneracy_alarm=degeneracy_alarm,
        metadata={
            "n_simulations": n_simulations,
            "saved_graphs": save_graphs,
            "group_labels_used": bool(group_labels is not None),
            "edgecov_used": "edgecov" in feature_names,
        },
    )
    return _ERGMFitArtifacts(result=result, probability_matrix=p, simulated_graphs=simulated)


@foundry_method(
    namespace="network.generative",
    version="0.1.0",
    tags={"network", "ergm", "null-model"},
)
class ERGMNullModelEstimator:
    """Fit an ERGM-inspired null-lite model and simulate a structural null ensemble."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="ergm_null",
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
        output_slots=_result_slot(ERGMResult.contract_id),
        parameters=(
            ParameterSpec(name="degree_decay", default=0.35),
            ParameterSpec(name="triangle_decay", default=0.40),
            ParameterSpec(name="ridge_penalty", default=1.0),
            ParameterSpec(name="n_simulations", default=32),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Sparse ERGM-inspired null-lite model using penalized MPLE-style dyad "
            "features and simulated graph diagnostics."
        ),
        tags=frozenset({"network", "ergm", "null-model", "diagnostics"}),
        when_to_use=(
            "Construct a structural null ensemble that preserves degree dispersion, "
            "closure, and optional pre-treatment mixing patterns before diffusion tests."
        ),
        when_not_to_use=(
            "Weighted dynamic ERGMs, online low-latency scoring, or cases requiring "
            "full MCMLE bridge sampling semantics."
        ),
        citations=(
            "Hunter, D.R. (2007). Curved exponential family models for social networks.",
            "Hummel, R.M., Hunter, D.R. & Handcock, M.S. (2012). Improving simulation-based algorithms for fitting ERGMs.",
        ),
        output_interpretation=(
            "coefficients summarize the null-lite fit; degeneracy_alarm warns when the "
            "simulated ensemble drifts toward near-empty/near-complete graphs or fails GOF checks."
        ),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state).model_dump(mode="python")
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"result": fit_ergm_null_model(state, params).result}


@foundry_method(
    namespace="network.generative",
    version="0.1.0",
    tags={"network", "ergm", "diffusion", "null-model"},
)
class DiffusionNullTestEstimator:
    """Compare observed diffusion against a structural ERGM-style null ensemble."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="diffusion_null_test",
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
                SlotSpec(
                    "node_states", SlotType.VECTOR, Unit("state", "value"), shape=("n_nodes",)
                ),
            }
        ),
        output_slots=_result_slot(DiffusionNullResult.contract_id),
        parameters=(
            ParameterSpec(name="n_simulations", default=32),
            ParameterSpec(name="diffusion_rate", default=0.3),
            ParameterSpec(name="decay", default=0.05),
            ParameterSpec(name="n_steps", default=10),
        ),
        fidelity=FidelityLevel.MEDIUM,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Runs DeGroot-style diffusion on the observed graph and on an ERGM-style "
            "null ensemble to quantify whether diffusion is structurally anomalous."
        ),
        tags=frozenset({"network", "diffusion", "null-model", "diagnostics"}),
        when_to_use=(
            "Assess whether the observed diffusion speed or terminal state is unusual "
            "relative to a structurally plausible null graph ensemble."
        ),
        when_not_to_use="Node states are unavailable or the graph is post-treatment.",
        citations=(
            "DeGroot, M. (1974). Reaching a consensus.",
            "Hunter, D.R. (2007). Curved exponential family models for social networks.",
        ),
        output_interpretation=(
            "Small p_value or large |z_score| indicates observed diffusion is atypical "
            "relative to the fitted structural null ensemble."
        ),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state).model_dump(mode="python")
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = _network_payload(state)
        if data.node_states is None:
            raise ValueError("node_states are required for DiffusionNullTestEstimator")
        fit = fit_ergm_null_model(data, params)
        node_states = np.asarray(data.node_states, dtype=float)
        diffusion_rate = float(params.get("diffusion_rate", 0.3))
        decay = float(params.get("decay", 0.05))
        n_steps = max(1, int(params.get("n_steps", 10)))
        observed_metric = _diffusion_metric(
            np.asarray(data.adjacency, dtype=float),
            node_states,
            diffusion_rate=diffusion_rate,
            decay=decay,
            n_steps=n_steps,
        )
        simulated_metrics = np.asarray(
            [
                _diffusion_metric(
                    graph,
                    node_states,
                    diffusion_rate=diffusion_rate,
                    decay=decay,
                    n_steps=n_steps,
                )
                for graph in fit.simulated_graphs
            ],
            dtype=float,
        )
        null_mean = float(np.mean(simulated_metrics))
        null_std = float(np.std(simulated_metrics))
        z_score = None if null_std < 1e-10 else float((observed_metric - null_mean) / null_std)
        result = DiffusionNullResult(
            method_name="diffusion_null_test",
            observed_metric=observed_metric,
            null_mean=null_mean,
            null_std=null_std,
            z_score=z_score,
            p_value=_two_sided_p_value(observed_metric, simulated_metrics),
            envelope=_envelope(simulated_metrics),
            simulated_metrics=simulated_metrics,
            metadata={
                "null_fit_status": fit.result.fit_status,
                "degeneracy_alarm": fit.result.degeneracy_alarm,
                "n_steps": n_steps,
                "diffusion_rate": diffusion_rate,
                "decay": decay,
            },
        )
        return {"result": result}


__all__ = [
    "DiffusionNullTestEstimator",
    "ERGMNullModelEstimator",
    "fit_ergm_null_model",
]
