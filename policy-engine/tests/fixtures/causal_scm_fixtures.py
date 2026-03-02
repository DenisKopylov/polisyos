"""Canonical SCM test fixtures (ADR-0095).

Seven synthetic causal structures with analytical or near-analytical ground-truth
ATE values, used across phases 2-15 for SL-5 fixture coverage.

Each fixture function returns ``(GraphCausalData, ground_truth_ate: float)``.
"""
from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal.protocols import GraphCausalData


# ---------------------------------------------------------------------------
# FORK: Z -> X, Z -> Y  (confounded, ATE_true = 0.0)
# ---------------------------------------------------------------------------

def fork_fixture(n: int = 6000, seed: int = 41) -> tuple[GraphCausalData, float]:
    """Fork / common cause. X and Y are spuriously correlated via Z."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.8 * z + rng.normal(0.0, 0.2, size=n)
    y = 1.2 * z + rng.normal(0.0, 0.2, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; }",
        graph_ref="cas:graph:fork",
        covariates=["Z"],
    )
    return data, 0.0


# ---------------------------------------------------------------------------
# CHAIN: X -> M -> Y  (mediation, ATE ≈ 0.91)
# ---------------------------------------------------------------------------

def chain_fixture(n: int = 6000, seed: int = 42) -> tuple[GraphCausalData, float]:
    """Chain / mediation. Total effect = β_XM × β_MY."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    m = 0.7 * x + rng.normal(0.0, 0.2, size=n)
    y = 1.3 * m + rng.normal(0.0, 0.2, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, m]),
        column_names=["X", "Y", "M"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> M; M -> Y; }",
        graph_ref="cas:graph:chain",
    )
    return data, 0.91


# ---------------------------------------------------------------------------
# COLLIDER: X -> Z, Y -> Z  (conditioning on Z opens spurious path)
# ---------------------------------------------------------------------------

def collider_fixture(n: int = 6000, seed: int = 43) -> tuple[GraphCausalData, float]:
    """Collider. X and Y are independent; conditioning on Z creates bias."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = rng.normal(size=n)
    z = 0.6 * x + 0.4 * y + rng.normal(0.0, 0.2, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> Z; Y -> Z; }",
        graph_ref="cas:graph:collider",
    )
    return data, 0.0


# ---------------------------------------------------------------------------
# INSTRUMENTAL_VARIABLE: Z -> X, X -> Y, U -> X, U -> Y
# ---------------------------------------------------------------------------

def instrumental_variable_fixture(n: int = 6000, seed: int = 44) -> tuple[GraphCausalData, float]:
    """IV setup with unmeasured confounder U. ATE = 1.2."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    u = rng.normal(size=n)
    x = 0.9 * z + 0.5 * u + rng.normal(0.0, 0.3, size=n)
    beta_xy = 1.2
    y = beta_xy * x + 0.8 * u + rng.normal(0.0, 0.3, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, z, u]),
        column_names=["X", "Y", "Z", "U"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; X -> Y; U -> X; U -> Y; }",
        graph_ref="cas:graph:iv",
        covariates=["Z"],
    )
    return data, beta_xy


# ---------------------------------------------------------------------------
# BACKDOOR_WITH_TRANSPORT: Z -> X, Z -> Y, X -> Y, S -> Z
# ---------------------------------------------------------------------------

def backdoor_with_transport_fixture(n: int = 6000, seed: int = 45) -> tuple[GraphCausalData, float]:
    """Backdoor identification with S-node for transport analysis. ATE = 1.2."""
    rng = np.random.default_rng(seed)
    s = rng.choice([0.0, 1.0], size=n)
    z = 0.3 * s + rng.normal(size=n)
    beta_xy = 1.2
    x = 0.9 * z + rng.normal(0.0, 0.3, size=n)
    y = beta_xy * x + 1.1 * z + rng.normal(0.0, 0.3, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, z, s]),
        column_names=["X", "Y", "Z", "S"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; S -> Z; }",
        graph_ref="cas:graph:backdoor_transport",
        covariates=["Z"],
    )
    return data, beta_xy


# ---------------------------------------------------------------------------
# FRONT_DOOR: X -> M -> Y, U -> X, U -> Y
# ---------------------------------------------------------------------------

def front_door_fixture(n: int = 6000, seed: int = 46) -> tuple[GraphCausalData, float]:
    """Front-door criterion. Unmeasured U confounds X-Y. ATE ≈ 0.91."""
    rng = np.random.default_rng(seed)
    u = rng.normal(size=n)
    x = 0.5 * u + rng.normal(0.0, 0.3, size=n)
    m = 0.7 * x + rng.normal(0.0, 0.2, size=n)
    y = 1.3 * m + 0.4 * u + rng.normal(0.0, 0.2, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, m, u]),
        column_names=["X", "Y", "M", "U"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> M; M -> Y; U -> X; U -> Y; }",
        graph_ref="cas:graph:front_door",
    )
    return data, 0.91


# ---------------------------------------------------------------------------
# DIAMOND: X -> A, X -> B, A -> Y, B -> Y  (multiple mediators, ATE ≈ 0.86)
# ---------------------------------------------------------------------------

def diamond_fixture(n: int = 6000, seed: int = 47) -> tuple[GraphCausalData, float]:
    """Diamond graph with two parallel mediators. ATE ≈ 0.86."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    a = 0.7 * x + rng.normal(0.0, 0.2, size=n)
    b = 0.5 * x + rng.normal(0.0, 0.2, size=n)
    y = 0.8 * a + 0.6 * b + rng.normal(0.0, 0.2, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, a, b]),
        column_names=["X", "Y", "A", "B"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { X -> A; X -> B; A -> Y; B -> Y; }",
        graph_ref="cas:graph:diamond",
    )
    return data, 0.86


# ---------------------------------------------------------------------------
# Linear confounding (bonus: commonly used for DoWhy tests)
# ---------------------------------------------------------------------------

def linear_confounding_fixture(n: int = 6000, seed: int = 48) -> tuple[GraphCausalData, float]:
    """Classic confounded treatment with direct effect. ATE = 1.2."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    x = 0.9 * z + rng.normal(0.0, 0.3, size=n)
    beta_xy = 1.2
    y = beta_xy * x + 1.1 * z + rng.normal(0.0, 0.3, size=n)
    data = GraphCausalData(
        data=np.column_stack([x, y, z]),
        column_names=["X", "Y", "Z"],
        treatment="X",
        outcome="Y",
        graph_dot="digraph { Z -> X; Z -> Y; X -> Y; }",
        graph_ref="cas:graph:linear_confounding",
        covariates=["Z"],
    )
    return data, beta_xy


# ---------------------------------------------------------------------------
# Registry of all canonical fixtures
# ---------------------------------------------------------------------------

ALL_FIXTURES = {
    "FORK": fork_fixture,
    "CHAIN": chain_fixture,
    "COLLIDER": collider_fixture,
    "INSTRUMENTAL_VARIABLE": instrumental_variable_fixture,
    "BACKDOOR_WITH_TRANSPORT": backdoor_with_transport_fixture,
    "FRONT_DOOR": front_door_fixture,
    "DIAMOND": diamond_fixture,
}


__all__ = [
    "ALL_FIXTURES",
    "fork_fixture",
    "chain_fixture",
    "collider_fixture",
    "instrumental_variable_fixture",
    "backdoor_with_transport_fixture",
    "front_door_fixture",
    "diamond_fixture",
    "linear_confounding_fixture",
]
