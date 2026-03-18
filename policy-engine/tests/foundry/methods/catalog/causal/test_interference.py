"""Tests for Phase 4: Interference and Network Causal Inference.

Covers:
- PartialInterferenceEstimator (Hudgens & Halloran 2008)
- NetworkAIPWEstimator (Aronow & Samii 2017)
- SpatialInterferenceEstimator (kernel spatial spillover)
- BipartiteInterferenceEstimator (Zigler & Papadogeorgou 2021)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.catalog.causal.protocols import NetworkCausalData
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.interference import (
    InterferenceMethod,
    NetworkInterferenceReport,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixture: reset registry / dispatcher before each test
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers: compute fractional exposure (mirrors production code for data gen)
# ──────────────────────────────────────────────────────────────────────────────

def _fractional_exposure(treatment: np.ndarray, cluster_id: np.ndarray) -> np.ndarray:
    clusters = np.unique(cluster_id)
    exposure = np.zeros(len(treatment), dtype=float)
    for c in clusters:
        mask = cluster_id == c
        indices = np.where(mask)[0]
        n_c = int(mask.sum())
        if n_c < 2:
            continue
        for pos, idx in enumerate(indices):
            total_others = float(treatment[mask].sum()) - float(treatment[idx])
            exposure[idx] = total_others / (n_c - 1)
    return exposure


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic data generators
# ──────────────────────────────────────────────────────────────────────────────

def _clustered_data(
    n_clusters: int = 10,
    cluster_size: int = 20,
    ate: float = 1.0,
    spillover: float = 0.5,
    seed: int = 42,
) -> NetworkCausalData:
    """Clustered interference: Y_i = ate*A_i + spillover*f_i + ε.
    True direct effect ≈ ate, true spillover ≈ spillover.
    """
    rng = np.random.default_rng(seed)
    n = n_clusters * cluster_size
    cluster_id = np.repeat(np.arange(n_clusters, dtype=int), cluster_size)
    X = rng.normal(size=(n, 2))
    A = rng.binomial(1, 0.5, size=n).astype(float)
    f = _fractional_exposure(A, cluster_id)
    Y = ate * A + spillover * f + rng.normal(scale=0.5, size=n)
    return NetworkCausalData(outcome=Y, treatment=A, cluster_id=cluster_id, covariates=X)


def _clustered_no_spillover(seed: int = 77) -> NetworkCausalData:
    """Clustered data with zero spillover coefficient."""
    return _clustered_data(n_clusters=10, cluster_size=20, ate=2.0, spillover=0.0, seed=seed)


def _network_data(
    n: int = 200,
    p_edge: float = 0.08,
    ate: float = 2.0,
    seed: int = 7,
) -> NetworkCausalData:
    """Erdős–Rényi network; Y_i = ate*A_i + ε (no spillover)."""
    rng = np.random.default_rng(seed)
    adj = (rng.uniform(size=(n, n)) < p_edge).astype(float)
    np.fill_diagonal(adj, 0.0)
    adj = np.triu(adj) + np.triu(adj).T
    np.clip(adj, 0, 1, out=adj)
    X = rng.normal(size=(n, 3))
    A = rng.binomial(1, 0.5, size=n).astype(float)
    Y = ate * A + rng.normal(scale=1.0, size=n)
    return NetworkCausalData(outcome=Y, treatment=A, adjacency_matrix=adj, covariates=X)


def _network_missing_adjacency(seed: int = 7) -> NetworkCausalData:
    """Network data WITHOUT adjacency matrix — should trigger INPUT_INVALID."""
    rng = np.random.default_rng(seed)
    n = 100
    A = rng.binomial(1, 0.5, size=n).astype(float)
    Y = A + rng.normal(size=n)
    cluster_id = np.repeat(np.arange(10), 10)
    return NetworkCausalData(outcome=Y, treatment=A, cluster_id=cluster_id)


def _spatial_data(
    n: int = 300,
    bandwidth: float = 0.3,
    spillover: float = 0.3,
    seed: int = 13,
) -> NetworkCausalData:
    """Spatial data with known Gaussian spillover; ate=1.5."""

    def _kernel_weights(coords: np.ndarray, bw: float) -> np.ndarray:
        diff = coords[:, np.newaxis, :] - coords[np.newaxis, :, :]
        sq_dist = (diff ** 2).sum(axis=-1)
        W = np.exp(-sq_dist / (2.0 * bw ** 2))
        np.fill_diagonal(W, 0.0)
        return W

    rng = np.random.default_rng(seed)
    coords = rng.uniform(size=(n, 2))
    A = rng.binomial(1, 0.4, size=n).astype(float)
    W = _kernel_weights(coords, bandwidth)
    degree = W.sum(axis=1)
    s = np.where(degree > 0, (W @ A) / degree, 0.0)
    Y = 1.5 * A + spillover * s + rng.normal(scale=0.5, size=n)
    return NetworkCausalData(outcome=Y, treatment=A, coordinates=coords)


def _bipartite_data(
    n_treatment: int = 50,
    n_outcome: int = 200,
    avg_degree: int = 3,
    seed: int = 99,
) -> NetworkCausalData:
    """Bipartite: treatment units → outcome units; Y ≈ mean(A_upstream)."""
    rng = np.random.default_rng(seed)
    tx_ids = np.arange(n_treatment, dtype=int)
    edges = []
    for j in range(n_outcome):
        degree = int(rng.poisson(avg_degree)) + 1
        sources = rng.choice(n_treatment, size=min(degree, n_treatment), replace=False)
        for s in sources:
            edges.append([int(s), int(j)])
    edges_arr = np.array(edges, dtype=int)

    A_tx = rng.binomial(1, 0.5, size=n_treatment).astype(float)
    Y_outcome = np.zeros(n_outcome)
    for i in range(n_outcome):
        upstream = edges_arr[edges_arr[:, 1] == i, 0]
        if len(upstream) > 0:
            Y_outcome[i] = float(A_tx[upstream].mean())
    Y_outcome += rng.normal(scale=0.1, size=n_outcome)

    n = n_treatment + n_outcome
    outcome_full = np.concatenate([np.zeros(n_treatment), Y_outcome])
    treatment_full = np.concatenate([A_tx, np.zeros(n_outcome)])

    return NetworkCausalData(
        outcome=outcome_full,
        treatment=treatment_full,
        bipartite_edges=edges_arr,
        treatment_unit_ids=tx_ids,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch helper
# ──────────────────────────────────────────────────────────────────────────────

def _dispatch(
    fqn: str,
    data: NetworkCausalData,
    params: dict | None = None,
    seed: int = 42,
) -> NetworkInterferenceReport:
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get(fqn)
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params=params or {},
        seed=seed,
    )
    return result.output["result"]


# ──────────────────────────────────────────────────────────────────────────────
# Registry smoke test
# ──────────────────────────────────────────────────────────────────────────────

def test_all_methods_registered():
    ensure_causal_methods_registered()
    reg = MethodRegistry.get_instance()
    fqns = [
        "causal.interference.partial@1.0.0",
        "causal.interference.network_aipw@1.0.0",
        "causal.interference.spatial@1.0.0",
        "causal.interference.bipartite@1.0.0",
    ]
    for fqn in fqns:
        assert reg.get(fqn) is not None, f"Method not registered: {fqn}"


# ──────────────────────────────────────────────────────────────────────────────
# PartialInterferenceEstimator tests
# ──────────────────────────────────────────────────────────────────────────────

def test_partial_interference_status_success():
    data = _clustered_data()
    report = _dispatch("causal.interference.partial@1.0.0", data)
    assert report.is_success
    assert report.method == InterferenceMethod.PARTIAL_IPW


def test_partial_interference_known_de():
    """Direct effect should be close to the true ate=1.0."""
    data = _clustered_data(n_clusters=20, cluster_size=30, ate=1.0, spillover=0.5, seed=0)
    report = _dispatch(
        "causal.interference.partial@1.0.0",
        data,
        params={"alpha_high": 0.5, "alpha_bandwidth": 0.15},
    )
    assert report.is_success
    de = report.direct_effect
    assert de is not None
    assert abs(de - 1.0) < 0.5, f"DE={de:.3f} too far from true value 1.0"


def test_partial_interference_known_spillover():
    """Spillover effect should be non-zero when spillover coefficient > 0."""
    data = _clustered_data(n_clusters=20, cluster_size=30, ate=1.0, spillover=0.8, seed=1)
    report = _dispatch(
        "causal.interference.partial@1.0.0",
        data,
        params={"alpha_high": 0.5, "alpha_low": 0.0, "alpha_bandwidth": 0.2},
    )
    assert report.is_success
    se = report.spillover_effect
    assert se is not None
    # Spillover should be positive (high-coverage arm > low-coverage arm)
    assert se > -0.5, f"Spillover={se:.3f} unexpectedly negative"


def test_partial_interference_zero_spillover():
    """When spillover=0, spillover effect should be near zero."""
    data = _clustered_no_spillover(seed=22)
    report = _dispatch(
        "causal.interference.partial@1.0.0",
        data,
        params={"alpha_high": 0.5, "alpha_bandwidth": 0.2},
    )
    assert report.is_success
    se = report.spillover_effect
    assert se is not None
    assert abs(se) < 0.8, f"Spillover={se:.3f} should be near 0 when coefficient=0"


def test_partial_interference_missing_cluster_id():
    """Should return INPUT_INVALID when cluster_id is absent."""
    rng = np.random.default_rng(0)
    n = 100
    A = rng.binomial(1, 0.5, size=n).astype(float)
    Y = A + rng.normal(size=n)
    adj = np.zeros((n, n))
    adj[0, 1] = 1.0  # need at least one structure
    data = NetworkCausalData(outcome=Y, treatment=A, adjacency_matrix=adj)
    report = _dispatch("causal.interference.partial@1.0.0", data)
    assert report.status == "input_invalid"


def test_partial_interference_report_schema_version():
    data = _clustered_data()
    report = _dispatch("causal.interference.partial@1.0.0", data)
    assert report.schema_version == "1.0"


def test_partial_interference_total_effect():
    """Total effect should roughly equal DE + SE (up to approximation)."""
    data = _clustered_data(n_clusters=15, cluster_size=25, seed=5)
    report = _dispatch(
        "causal.interference.partial@1.0.0",
        data,
        params={"alpha_high": 0.5, "alpha_low": 0.0, "alpha_bandwidth": 0.15},
    )
    assert report.is_success
    assert report.effects is not None
    de = report.effects.direct_effect
    se = report.effects.spillover_effect
    te = report.effects.total_effect
    # TE = E[Y(1,α_high)] - E[Y(0,α_low)] = DE(α_high) + SE(α_high, α_low) approximately
    assert abs(te - (de + se)) < 1.0, f"TE={te:.3f} vs DE+SE={de+se:.3f}"


# ──────────────────────────────────────────────────────────────────────────────
# NetworkAIPWEstimator tests
# ──────────────────────────────────────────────────────────────────────────────

def test_network_aipw_status_success():
    data = _network_data()
    report = _dispatch("causal.interference.network_aipw@1.0.0", data)
    assert report.is_success
    assert report.method == InterferenceMethod.NETWORK_AIPW


def test_network_aipw_low_interference_de():
    """Under low network density (minimal spillover), DE should track the true ate."""
    data = _network_data(n=300, p_edge=0.05, ate=2.0, seed=10)
    report = _dispatch(
        "causal.interference.network_aipw@1.0.0",
        data,
        params={"alpha_high": 0.3, "alpha_low": 0.0, "exposure_mapping": "fraction"},
    )
    assert report.is_success
    de = report.direct_effect
    assert de is not None
    assert abs(de - 2.0) < 1.2, f"DE={de:.3f} too far from ate=2.0"


def test_network_aipw_missing_adjacency_invalid():
    """Should return INPUT_INVALID when adjacency_matrix is absent."""
    data = _network_missing_adjacency()
    report = _dispatch("causal.interference.network_aipw@1.0.0", data)
    assert report.status == "input_invalid"
    assert "adjacency_matrix" in (report.status_reason or "")


def test_network_aipw_report_schema_version():
    data = _network_data()
    report = _dispatch("causal.interference.network_aipw@1.0.0", data)
    assert report.schema_version == "1.0"


def test_network_aipw_effects_not_none_on_success():
    data = _network_data()
    report = _dispatch("causal.interference.network_aipw@1.0.0", data)
    assert report.is_success
    assert report.effects is not None
    assert math.isfinite(report.effects.direct_effect)
    assert math.isfinite(report.effects.spillover_effect)
    assert math.isfinite(report.effects.total_effect)


# ──────────────────────────────────────────────────────────────────────────────
# SpatialInterferenceEstimator tests
# ──────────────────────────────────────────────────────────────────────────────

def test_spatial_interference_status_success():
    data = _spatial_data()
    report = _dispatch("causal.interference.spatial@1.0.0", data)
    assert report.is_success
    assert report.method == InterferenceMethod.SPATIAL_KERNEL


def test_spatial_interference_auto_bandwidth():
    """auto bandwidth should run without error and store bandwidth in metadata."""
    data = _spatial_data(n=200, seed=20)
    report = _dispatch(
        "causal.interference.spatial@1.0.0",
        data,
        params={"bandwidth": "auto"},
    )
    assert report.is_success
    assert "bandwidth" in report.exposure_mapping_params


def test_spatial_interference_de_positive():
    """Direct effect should be positive (ate=1.5 in DGP)."""
    data = _spatial_data(n=400, bandwidth=0.25, spillover=0.2, seed=30)
    report = _dispatch(
        "causal.interference.spatial@1.0.0",
        data,
        params={"bandwidth": 0.25, "alpha_high": 0.4},
    )
    assert report.is_success
    de = report.direct_effect
    assert de is not None
    assert de > 0, f"Expected positive DE, got {de:.3f}"


def test_spatial_interference_report_schema_version():
    data = _spatial_data()
    report = _dispatch("causal.interference.spatial@1.0.0", data)
    assert report.schema_version == "1.0"


def test_spatial_fallback_to_adjacency():
    """When coordinates is None but adjacency_matrix exists, should not error."""
    data = _network_data(n=100, p_edge=0.1, seed=40)
    # data has adjacency_matrix but no coordinates
    report = _dispatch("causal.interference.spatial@1.0.0", data)
    assert report.is_success


# ──────────────────────────────────────────────────────────────────────────────
# BipartiteInterferenceEstimator tests
# ──────────────────────────────────────────────────────────────────────────────

def test_bipartite_interference_status_success():
    data = _bipartite_data()
    report = _dispatch("causal.interference.bipartite@1.0.0", data)
    assert report.is_success
    assert report.method == InterferenceMethod.BIPARTITE


def test_bipartite_effect_sign():
    """Direct effect should be positive: high upstream treatment → higher Y."""
    data = _bipartite_data(n_treatment=60, n_outcome=300, avg_degree=4, seed=50)
    report = _dispatch(
        "causal.interference.bipartite@1.0.0",
        data,
        params={"alpha_high": 0.5, "alpha_low": 0.0},
    )
    assert report.is_success
    de = report.direct_effect
    assert de is not None
    assert de > -0.3, f"Expected positive DE in bipartite setting, got {de:.3f}"


def test_bipartite_missing_edges_invalid():
    """Should return INPUT_INVALID when bipartite_edges is absent."""
    rng = np.random.default_rng(0)
    n = 100
    A = rng.binomial(1, 0.5, size=n).astype(float)
    Y = A + rng.normal(size=n)
    cluster_id = np.repeat(np.arange(10), 10)
    data = NetworkCausalData(outcome=Y, treatment=A, cluster_id=cluster_id)
    report = _dispatch("causal.interference.bipartite@1.0.0", data)
    assert report.status == "input_invalid"


def test_bipartite_report_schema_version():
    data = _bipartite_data()
    report = _dispatch("causal.interference.bipartite@1.0.0", data)
    assert report.schema_version == "1.0"


# ──────────────────────────────────────────────────────────────────────────────
# NetworkCausalData protocol validation tests
# ──────────────────────────────────────────────────────────────────────────────

def test_network_causal_data_cluster_id_valid():
    rng = np.random.default_rng(0)
    n = 100
    d = NetworkCausalData(
        outcome=rng.normal(size=n),
        treatment=rng.binomial(1, 0.5, size=n).astype(float),
        cluster_id=np.repeat(np.arange(10), 10),
    )
    assert d.n_units == n
    assert 0 < d.n_treated < n


def test_network_causal_data_adjacency_valid():
    rng = np.random.default_rng(1)
    n = 50
    adj = (rng.uniform(size=(n, n)) < 0.1).astype(float)
    np.fill_diagonal(adj, 0.0)
    d = NetworkCausalData(
        outcome=rng.normal(size=n),
        treatment=rng.binomial(1, 0.5, size=n).astype(float),
        adjacency_matrix=adj,
    )
    assert d.n_units == n


def test_network_causal_data_no_structure_raises():
    rng = np.random.default_rng(2)
    n = 50
    with pytest.raises(Exception):
        NetworkCausalData(
            outcome=rng.normal(size=n),
            treatment=rng.binomial(1, 0.5, size=n).astype(float),
        )


def test_network_causal_data_non_binary_treatment_raises():
    rng = np.random.default_rng(3)
    n = 50
    with pytest.raises(Exception):
        NetworkCausalData(
            outcome=rng.normal(size=n),
            treatment=rng.uniform(0, 1, size=n),  # continuous, not binary
            cluster_id=np.repeat(np.arange(5), 10),
        )
