"""Covariate-assisted SBM stratification for design-stage causal workflows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import numpy as np
from pydantic import ValidationError

try:  # pragma: no cover - preferred in full scientific environments.
    from scipy.special import logsumexp
except ImportError:  # pragma: no cover - keeps catalog reflection importable.

    def logsumexp(
        values: np.ndarray,
        *,
        axis: int | None = None,
        keepdims: bool = False,
    ) -> np.ndarray:
        arr = np.asarray(values, dtype=float)
        max_values = np.max(arr, axis=axis, keepdims=True)
        stable = np.exp(arr - max_values)
        result = np.log(np.sum(stable, axis=axis, keepdims=True)) + max_values
        if keepdims:
            return result
        return np.squeeze(result, axis=axis)


try:  # pragma: no cover - preferred in full scientific environments.
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
except ImportError:  # pragma: no cover - keeps catalog reflection importable.
    KMeans = None  # type: ignore[assignment]
    adjusted_rand_score = None  # type: ignore[assignment]
    normalized_mutual_info_score = None  # type: ignore[assignment]

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

from .embedding_fidelity import maybe_compute_embedding_fidelity_certificate
from .generative_protocols import EdgeListNetworkData, SBMStratificationResult
from .protocols import NetworkData


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("network", "json"),
                contract_id=SBMStratificationResult.contract_id,
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


def _standardize(features: np.ndarray) -> np.ndarray:
    arr = np.asarray(features, dtype=float)
    mean = np.mean(arr, axis=0, keepdims=True)
    std = np.std(arr, axis=0, keepdims=True)
    std[std < 1e-8] = 1.0
    return (arr - mean) / std


def _regularized_embedding(
    adjacency: np.ndarray,
    *,
    n_blocks: int,
    node_features: np.ndarray | None,
    covariate_scale: float,
) -> np.ndarray:
    adj = _symmetrize(adjacency)
    deg = np.sum(adj, axis=1)
    tau = float(np.mean(deg)) if np.any(deg > 0.0) else 1.0
    d_reg = deg + tau + 1e-8
    normalized = adj / np.sqrt(np.outer(d_reg, d_reg))
    _, eigvecs = np.linalg.eigh(normalized)
    base = eigvecs[:, -n_blocks:]
    row_norm = np.linalg.norm(base, axis=1, keepdims=True)
    row_norm[row_norm == 0.0] = 1.0
    embedding = base / row_norm
    if node_features is not None and covariate_scale > 0.0:
        embedding = np.hstack([embedding, covariate_scale * _standardize(node_features)])
    return embedding


def _kmeans_labels(embedding: np.ndarray, *, n_blocks: int, seed: int) -> np.ndarray:
    if n_blocks <= 1:
        return np.zeros(embedding.shape[0], dtype=int)
    if KMeans is None:
        raise ImportError("scikit-learn is required for SBM KMeans initialization")
    model = KMeans(n_clusters=n_blocks, random_state=seed, n_init=10)
    return model.fit_predict(embedding).astype(int)


def _reindex_labels(labels: np.ndarray) -> np.ndarray:
    unique = sorted(int(value) for value in np.unique(labels))
    mapping = {label: idx for idx, label in enumerate(unique)}
    return np.asarray([mapping[int(label)] for label in labels], dtype=int)


def _ensure_nonempty_blocks(labels: np.ndarray, scores: np.ndarray) -> np.ndarray:
    updated = np.asarray(labels, dtype=int).copy()
    n_blocks = scores.shape[1]
    for block in range(n_blocks):
        if np.any(updated == block):
            continue
        largest = int(np.argmax(np.bincount(updated, minlength=n_blocks)))
        candidates = np.where(updated == largest)[0]
        if candidates.size == 0:
            continue
        donor = int(candidates[np.argmax(scores[candidates, block])])
        updated[donor] = block
    return _reindex_labels(updated)


def _estimate_block_connectivity(adjacency: np.ndarray, labels: np.ndarray) -> np.ndarray:
    adj = np.asarray(adjacency, dtype=float)
    labels = _reindex_labels(labels)
    n_blocks = int(np.max(labels)) + 1
    block = np.zeros((n_blocks, n_blocks), dtype=float)
    eps = 1e-6
    for a in range(n_blocks):
        mask_a = labels == a
        n_a = int(mask_a.sum())
        for b in range(n_blocks):
            mask_b = labels == b
            n_b = int(mask_b.sum())
            if n_a == 0 or n_b == 0:
                block[a, b] = eps
                continue
            mass = float(np.sum(adj[np.ix_(mask_a, mask_b)]))
            denom = float(n_a * max(n_a - 1, 1)) if a == b else float(n_a * n_b)
            block[a, b] = np.clip(mass / max(denom, 1.0), eps, 1.0 - eps)
    return block


def _estimate_degree_correction(adjacency: np.ndarray, labels: np.ndarray) -> np.ndarray:
    deg = np.sum(np.asarray(adjacency, dtype=float), axis=1)
    theta = np.ones_like(deg, dtype=float)
    for block in np.unique(labels):
        mask = labels == block
        mean_deg = float(np.mean(deg[mask])) if np.any(mask) else 1.0
        mean_deg = max(mean_deg, 1e-6)
        theta[mask] = deg[mask] / mean_deg
    return theta


def _assignment_scores(adjacency: np.ndarray, labels: np.ndarray) -> np.ndarray:
    adj = np.asarray(adjacency, dtype=float)
    labels = _reindex_labels(labels)
    block = _estimate_block_connectivity(adj, labels)
    block_sizes = np.bincount(labels, minlength=block.shape[0]).astype(float)
    degree = np.sum(adj, axis=1)
    mean_degree = float(np.mean(degree)) if np.any(degree > 0.0) else 1.0
    edge_counts = np.zeros((adj.shape[0], block.shape[0]), dtype=float)
    for block_id in range(block.shape[0]):
        mask = labels == block_id
        if np.any(mask):
            edge_counts[:, block_id] = np.sum(adj[:, mask], axis=1)
    scores = np.zeros_like(edge_counts)
    for block_id in range(block.shape[0]):
        prior = np.log((block_sizes[block_id] + 1e-6) / max(np.sum(block_sizes), 1.0))
        expected_degree = np.sum(block_sizes * block[block_id])
        scores[:, block_id] = (
            prior
            + np.sum(edge_counts * np.log(block[block_id][None, :]), axis=1)
            - (degree / max(mean_degree, 1e-6)) * expected_degree
        )
    return scores


def _refine_labels(adjacency: np.ndarray, labels: np.ndarray, *, max_iter: int) -> np.ndarray:
    current = _reindex_labels(labels)
    for _ in range(max_iter):
        scores = _assignment_scores(adjacency, current)
        updated = np.argmax(scores, axis=1).astype(int)
        updated = _ensure_nonempty_blocks(updated, scores)
        if np.array_equal(updated, current):
            return current
        current = updated
    return current


def _perturb_adjacency(adjacency: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    adj = _symmetrize(adjacency)
    tri = np.triu_indices_from(adj, k=1)
    observed = adj[tri] > 0.0
    density = float(np.mean(observed)) if observed.size else 0.0
    add_prob = min(0.10, max(0.01, density * 0.40))
    probs = np.where(observed, 0.90, add_prob)
    boot_upper = (rng.uniform(size=observed.shape[0]) < probs).astype(float)
    boot = np.zeros_like(adj, dtype=float)
    boot[tri] = boot_upper
    boot += boot.T
    return boot


def _bootstrap_stability(
    adjacency: np.ndarray,
    *,
    base_labels: np.ndarray,
    n_blocks: int,
    node_features: np.ndarray | None,
    covariate_scale: float,
    n_bootstrap: int,
    seed: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    rng = np.random.default_rng(seed)
    base_co = (base_labels[:, None] == base_labels[None, :]).astype(float)
    co_clustering = np.zeros_like(base_co, dtype=float)
    ari_scores: list[float] = []
    nmi_scores: list[float] = []
    for _ in range(max(n_bootstrap, 1)):
        boot_adj = _perturb_adjacency(adjacency, rng)
        embedding = _regularized_embedding(
            boot_adj,
            n_blocks=n_blocks,
            node_features=node_features,
            covariate_scale=covariate_scale,
        )
        labels = _refine_labels(
            boot_adj,
            _kmeans_labels(embedding, n_blocks=n_blocks, seed=int(rng.integers(0, 1_000_000))),
            max_iter=4,
        )
        co_clustering += (labels[:, None] == labels[None, :]).astype(float)
        if adjusted_rand_score is None or normalized_mutual_info_score is None:
            raise ImportError("scikit-learn is required for SBM bootstrap diagnostics")
        ari_scores.append(float(adjusted_rand_score(base_labels, labels)))
        nmi_scores.append(float(normalized_mutual_info_score(base_labels, labels)))
    co_clustering /= max(n_bootstrap, 1)
    node_stability = 1.0 - np.mean(np.abs(co_clustering - base_co), axis=1)
    return co_clustering, {
        "bootstrap_mean_ari": float(np.mean(ari_scores)),
        "bootstrap_mean_nmi": float(np.mean(nmi_scores)),
        "node_stability": node_stability,
        "overall_stability": float(np.mean(node_stability)),
    }


def _merge_unstable_blocks(
    labels: np.ndarray,
    embedding: np.ndarray,
    node_stability: np.ndarray,
    *,
    min_block_size: int,
    min_block_stability: float,
) -> tuple[np.ndarray, tuple[dict[str, int | float], ...]]:
    current = _reindex_labels(labels)
    history: list[dict[str, int | float]] = []
    while True:
        unique = np.unique(current)
        if unique.size <= 1:
            break
        counts = np.bincount(current, minlength=int(np.max(current)) + 1)
        centroids = np.vstack([np.mean(embedding[current == block], axis=0) for block in unique])
        block_stability = {
            int(block): float(np.mean(node_stability[current == block])) for block in unique
        }
        candidates = [
            int(block)
            for block in unique
            if counts[int(block)] < min_block_size
            or block_stability[int(block)] < min_block_stability
        ]
        if not candidates:
            break
        block = min(candidates, key=lambda item: (counts[item], block_stability[item]))
        centroid_idx = int(np.where(unique == block)[0][0])
        distances = np.linalg.norm(centroids - centroids[centroid_idx], axis=1)
        distances[centroid_idx] = np.inf
        target = int(unique[int(np.argmin(distances))])
        current[current == block] = target
        history.append(
            {
                "from_block": int(block),
                "to_block": int(target),
                "source_size": int(counts[block]),
                "source_stability": float(block_stability[block]),
            }
        )
        current = _reindex_labels(current)
    return current, tuple(history)


def _responsibilities(adjacency: np.ndarray, labels: np.ndarray) -> np.ndarray:
    scores = _assignment_scores(adjacency, labels)
    normalized = scores - logsumexp(scores, axis=1, keepdims=True)
    return np.exp(normalized)


def _optional_treatment(
    params: Mapping[str, Any],
    metadata: Mapping[str, Any],
    n_units: int,
) -> np.ndarray | None:
    raw = params.get("treatment", metadata.get("treatment"))
    if raw is None:
        return None
    treatment = np.asarray(raw, dtype=float)
    if treatment.ndim != 1 or treatment.shape[0] != n_units:
        return None
    if not np.isin(treatment, [0.0, 1.0]).all():
        return None
    return treatment


def _positivity_report(
    labels: np.ndarray,
    treatment: np.ndarray | None,
    *,
    min_treated: int,
    min_control: int,
) -> dict[str, Any]:
    if treatment is None:
        return {"status": "not_evaluated", "positivity_passed": None, "blocks": []}
    reports: list[dict[str, Any]] = []
    positivity_passed = True
    for block in np.unique(labels):
        mask = labels == block
        n_units = int(mask.sum())
        n_treated = int(np.sum(treatment[mask]))
        n_control = n_units - n_treated
        block_passed = n_treated >= min_treated and n_control >= min_control
        positivity_passed &= block_passed
        reports.append(
            {
                "block_id": int(block),
                "n_units": n_units,
                "n_treated": n_treated,
                "n_control": n_control,
                "treated_share": float(n_treated / max(n_units, 1)),
                "positivity_passed": block_passed,
            }
        )
    return {
        "status": "evaluated",
        "positivity_passed": positivity_passed,
        "min_treated": int(min_treated),
        "min_control": int(min_control),
        "blocks": reports,
    }


@foundry_method(
    namespace="network.community",
    version="1.0.0",
    tags={"network", "community-detection", "sbm", "causal-stratification"},
)
class SBMStratificationEstimator:
    """Fit a covariate-assisted SBM stratifier for pre-treatment causal design."""

    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy", "scikit-learn", "scipy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="sbm_stratification",
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
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="n_blocks", default=3),
            ParameterSpec(name="covariate_scale", default=0.5),
            ParameterSpec(name="refine_iter", default=5),
            ParameterSpec(name="bootstrap_samples", default=8),
            ParameterSpec(name="min_block_size", default=5),
            ParameterSpec(name="min_block_stability", default=0.60),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description=(
            "Covariate-assisted spectral stratification with an approximate "
            "degree-corrected SBM refinement and bootstrap stability summary."
        ),
        tags=frozenset({"network", "sbm", "causal-stratification", "community-detection"}),
        when_to_use=(
            "Build stable pre-treatment network strata that can be bridged into "
            "cluster-aware interference estimators or design diagnostics."
        ),
        when_not_to_use=(
            "Post-treatment graphs, outcome-informed clustering, or settings "
            "where the graph is too small to support multiple blocks."
        ),
        citations=(
            "Karrer, B. & Newman, M.E.J. (2011). Stochastic blockmodels and community structure in networks.",
            "Binkiewicz, N., Vogelstein, J. & Rohe, K. (2017). Covariate-assisted spectral clustering.",
            "Abbe, E. (2018). Community detection and stochastic block models.",
        ),
        output_interpretation=(
            "labels defines the design-stage block assignment; co_clustering and "
            "stability quantify assignment uncertainty before downstream causal use."
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
        payload = data.model_dump(mode="python")
        adjacency = _symmetrize(np.asarray(data.adjacency, dtype=float))
        node_features = (
            np.asarray(data.node_features, dtype=float) if data.node_features is not None else None
        )
        n_units = adjacency.shape[0]
        requested_blocks = int(params.get("n_blocks", 3))
        n_blocks = max(1, min(requested_blocks, n_units))
        covariate_scale = max(0.0, float(params.get("covariate_scale", 0.5)))
        refine_iter = max(1, int(params.get("refine_iter", 5)))
        bootstrap_samples = max(1, int(params.get("bootstrap_samples", 8)))
        min_block_size = max(1, int(params.get("min_block_size", 5)))
        min_block_stability = float(params.get("min_block_stability", 0.60))
        seed = int(params.get("__seed__", 0))

        embedding = _regularized_embedding(
            adjacency,
            n_blocks=n_blocks,
            node_features=node_features,
            covariate_scale=covariate_scale,
        )
        labels = _kmeans_labels(embedding, n_blocks=n_blocks, seed=seed)
        labels = _refine_labels(adjacency, labels, max_iter=refine_iter)

        co_clustering, stability = _bootstrap_stability(
            adjacency,
            base_labels=labels,
            n_blocks=max(1, len(np.unique(labels))),
            node_features=node_features,
            covariate_scale=covariate_scale,
            n_bootstrap=bootstrap_samples,
            seed=seed + 17,
        )
        labels, merge_history = _merge_unstable_blocks(
            labels,
            embedding,
            np.asarray(stability["node_stability"], dtype=float),
            min_block_size=min_block_size,
            min_block_stability=min_block_stability,
        )
        block_connectivity = _estimate_block_connectivity(adjacency, labels)
        degree_correction = _estimate_degree_correction(adjacency, labels)
        responsibilities = _responsibilities(adjacency, labels)
        treatment = _optional_treatment(params, data.metadata, n_units)
        positivity_report = _positivity_report(
            labels,
            treatment,
            min_treated=max(1, int(params.get("min_treated_per_block", 1))),
            min_control=max(1, int(params.get("min_control_per_block", 1))),
        )
        embedding_fidelity_certificate = maybe_compute_embedding_fidelity_certificate(
            payload,
            params=params,
            embedding=embedding,
            embedding_family="sbm",
        )

        result = SBMStratificationResult(
            method_name="sbm_stratification",
            labels=labels,
            responsibilities=responsibilities,
            co_clustering=co_clustering,
            block_connectivity=block_connectivity,
            degree_correction=degree_correction,
            stability={
                **{
                    key: (value.tolist() if isinstance(value, np.ndarray) else value)
                    for key, value in stability.items()
                },
                "bootstrap_samples": bootstrap_samples,
                "effective_blocks": len(np.unique(labels)),
            },
            positivity_report=positivity_report,
            metadata={
                "fit_type": "covariate_assisted_dcsbm_approx",
                "requested_blocks": int(requested_blocks),
                "effective_blocks": len(np.unique(labels)),
                "used_covariates": bool(node_features is not None and covariate_scale > 0.0),
                "covariate_scale": covariate_scale,
                "merge_history": list(merge_history),
                "node_ids": list(data.node_ids) if data.node_ids is not None else None,
                "embedding_fidelity_certificate": embedding_fidelity_certificate,
            },
        )
        return {"result": result}


__all__ = ["SBMStratificationEstimator"]
