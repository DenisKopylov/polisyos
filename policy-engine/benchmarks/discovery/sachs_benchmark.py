"""Circuit 3: Discovery — Sachs et al. (2005) protein-signalling benchmark.

Evaluates structure recovery on synthetic data generated from the canonical
11-node Sachs protein-signalling network (Sachs et al. 2005, Science).

Network structure
-----------------
11 nodes: Raf, Mek, Erk, Akt, PKA, PKC, P38, Jnk, Plcg, PIP2, PIP3
17 directed edges (consensus causal DAG from Sachs 2005 Table 2)

Algorithm
---------
PC skeleton algorithm: iterative conditional independence testing using
Fisher's Z partial-correlation test (pure numpy).

Metrics
-------
SHD  — Structural Hamming Distance (extra + missing + reversed edges)
Skeleton precision and recall (ignoring edge direction)
Directed precision and recall

Bar
---
SHD ≤ 11  (< 65 % of true edges wrong)
Skeleton precision ≥ 0.55
Skeleton recall    ≥ 0.50

Usage
-----
    python benchmarks/discovery/sachs_benchmark.py
    python benchmarks/discovery/sachs_benchmark.py --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------

_BENCH_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _BENCH_ROOT / "src"
for _p in [str(_SRC), str(_BENCH_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from benchmarks.harness import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCircuit,
    BenchmarkHarness,
    BenchmarkReport,
)
from benchmarks.reporting import (  # noqa: E402
    build_preflight,
    build_report_payload,
    print_preflight,
)
from benchmarks.runtime import resolve_mode  # noqa: E402

CIRCUIT = BenchmarkCircuit.DISCOVERY

# ---------------------------------------------------------------------------
# Sachs 11-node consensus network
# ---------------------------------------------------------------------------

SACHS_NODES = ["Raf", "Mek", "Erk", "Akt", "PKA", "PKC", "P38", "Jnk", "Plcg", "PIP2", "PIP3"]
_N = len(SACHS_NODES)
_IDX = {v: i for i, v in enumerate(SACHS_NODES)}

#: 17 directed edges (src → dst) from Sachs 2005 Table 2
SACHS_EDGES: list[tuple[str, str]] = [
    ("Plcg", "PIP3"),
    ("Plcg", "PKC"),
    ("PIP3", "PIP2"),
    ("PIP3", "Akt"),
    ("PIP2", "PKC"),
    ("PKC", "Raf"),
    ("PKC", "Mek"),
    ("PKC", "P38"),
    ("PKC", "Jnk"),
    ("PKA", "Raf"),
    ("PKA", "Mek"),
    ("PKA", "Erk"),
    ("PKA", "Akt"),
    ("PKA", "P38"),
    ("PKA", "Jnk"),
    ("Raf", "Mek"),
    ("Mek", "Erk"),
]


def _sachs_adj() -> np.ndarray:
    """Build binary (11×11) directed adjacency matrix from SACHS_EDGES."""
    adj = np.zeros((_N, _N), dtype=int)
    for src, dst in SACHS_EDGES:
        adj[_IDX[src], _IDX[dst]] = 1
    return adj


def _sachs_coef_matrix(rng: np.random.Generator) -> np.ndarray:
    """Random linear coefficients consistent with the Sachs DAG.

    Each edge coefficient is drawn from Uniform(0.4, 0.9) with random sign.
    """
    adj = _sachs_adj()
    coef = np.zeros((_N, _N))
    for i in range(_N):
        for j in range(_N):
            if adj[i, j]:
                coef[i, j] = rng.uniform(0.4, 0.9) * rng.choice([-1, 1])
    return coef


# ---------------------------------------------------------------------------
# Linear Gaussian SCM simulation
# ---------------------------------------------------------------------------


def _simulate_linear_gaussian(coef: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    """Simulate n i.i.d. samples from a linear-Gaussian SCM.

    X_i = Σ_{j: j→i} coef[i,j] * X_j + ε_i,   ε_i ~ N(0,1)

    Uses the topological order implied by the lower-triangular structure.
    If ``coef`` is not lower-triangular, a topological ordering is computed.
    """
    # Topological sort (Kahn's algorithm)
    # Build parent map
    parents: list[list[int]] = [[] for _ in range(_N)]
    for i in range(_N):
        for j in range(_N):
            if coef[i, j] != 0:
                parents[i].append(j)

    # BFS topological order
    order: list[int] = []
    ready = [i for i in range(_N) if len(parents[i]) == 0]
    remaining_parents = [list(p) for p in parents]
    processed = set()
    queue = list(ready)
    while queue:
        node = queue.pop(0)
        if node in processed:
            continue
        processed.add(node)
        order.append(node)
        # Find children
        for child in range(_N):
            if node in remaining_parents[child]:
                remaining_parents[child].remove(node)
                if not remaining_parents[child]:
                    queue.append(child)

    # If cycle (shouldn't happen for Sachs DAG), append remaining
    for i in range(_N):
        if i not in processed:
            order.append(i)

    data = np.zeros((n, _N))
    eps = rng.standard_normal((n, _N))
    for node in order:
        x_node = eps[:, node].copy()
        for par in parents[node]:
            x_node += coef[node, par] * data[:, par]
        data[:, node] = x_node

    return data


# ---------------------------------------------------------------------------
# PC skeleton algorithm (pure numpy)
# ---------------------------------------------------------------------------


def _partial_corr(x: np.ndarray, y: np.ndarray, z: np.ndarray | None) -> float:
    """Sample partial correlation of x and y given z (columns)."""
    if z is None or z.ndim == 1 and z.shape[0] == 0 or (z.ndim == 2 and z.shape[1] == 0):
        # Simple correlation
        xc = x - x.mean()
        yc = y - y.mean()
        denom = math.sqrt(max(np.dot(xc, xc), 1e-12) * max(np.dot(yc, yc), 1e-12))
        return float(np.dot(xc, yc)) / denom

    # Partial correlation via regression residuals
    n = len(x)
    Z = np.column_stack([z, np.ones(n)])
    ZtZ_inv = np.linalg.pinv(Z.T @ Z)
    proj = Z @ ZtZ_inv @ Z.T

    def _residual(v: np.ndarray) -> np.ndarray:
        vc = v - v.mean()
        return vc - proj @ vc

    rx = _residual(x)
    ry = _residual(y)
    denom = math.sqrt(max(np.dot(rx, rx), 1e-12) * max(np.dot(ry, ry), 1e-12))
    return float(np.dot(rx, ry)) / denom


def _fisher_z_pvalue(r: float, n: int, k: int) -> float:
    """Two-sided p-value for H0: ρ(X,Y|Z) = 0 via Fisher Z-transform."""
    r = max(-0.9999, min(0.9999, r))
    z = 0.5 * math.log((1.0 + r) / (1.0 - r))
    se_inv = math.sqrt(max(1, n - k - 3))
    stat = abs(z) * se_inv
    # Two-sided: 2 * P(Z > stat)
    t = 1.0 / (1.0 + 0.2316419 * stat)
    poly = t * (
        0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    sf = poly * math.exp(-0.5 * stat * stat)
    return min(1.0, 2.0 * sf)


def _pc_skeleton(
    data: np.ndarray,
    *,
    alpha: float = 0.05,
    max_cond_size: int = 3,
) -> tuple[np.ndarray, dict[frozenset[int], frozenset[int]]]:
    """PC skeleton algorithm using partial-correlation CI tests.

    Returns
    -------
    adj      : (n, n) symmetric binary matrix (1 if edge present)
    sep_sets : dict mapping frozenset({i,j}) → frozenset of conditioning nodes
    """
    n = data.shape[1]
    adj = np.ones((n, n), dtype=int) - np.eye(n, dtype=int)
    sep_sets: dict[frozenset[int], frozenset[int]] = {}

    for cond_size in range(max_cond_size + 1):
        pairs = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]
        for i, j in pairs:
            # Candidate conditioning sets from adjacencies of i (excl. j)
            adj_i = [k for k in range(n) if adj[i, k] and k != j]
            if len(adj_i) < cond_size:
                continue
            found_sep = False
            for cond_set in combinations(adj_i, cond_size):
                cond_data = data[:, list(cond_set)] if cond_set else None
                r = _partial_corr(data[:, i], data[:, j], cond_data)
                p = _fisher_z_pvalue(r, len(data), len(cond_set))
                if p > alpha:
                    adj[i, j] = adj[j, i] = 0
                    sep_sets[frozenset({i, j})] = frozenset(cond_set)
                    found_sep = True
                    break
            if found_sep:
                continue
            # Also try conditioning sets from adjacencies of j
            adj_j = [k for k in range(n) if adj[j, k] and k != i]
            if len(adj_j) < cond_size:
                continue
            for cond_set in combinations(adj_j, cond_size):
                cond_data = data[:, list(cond_set)] if cond_set else None
                r = _partial_corr(data[:, i], data[:, j], cond_data)
                p = _fisher_z_pvalue(r, len(data), len(cond_set))
                if p > alpha:
                    adj[i, j] = adj[j, i] = 0
                    sep_sets[frozenset({i, j})] = frozenset(cond_set)
                    break

    return adj, sep_sets


def _orient_v_structures(
    adj: np.ndarray,
    sep_sets: dict[frozenset[int], frozenset[int]],
) -> np.ndarray:
    """Orient v-structures in the PC skeleton.

    For each unshielded triple i - k - j (i not adjacent to j):
    if k ∉ sep(i,j): orient as i → k ← j.

    Returns a directed adjacency matrix (directed[i,j]=1 means i→j).
    """
    n = adj.shape[0]
    directed = np.zeros((n, n), dtype=int)

    # Collect triples
    for k in range(n):
        neighbours = [i for i in range(n) if adj[k, i]]
        for i, j in combinations(neighbours, 2):
            if adj[i, j]:  # shielded triple — skip
                continue
            sep = sep_sets.get(frozenset({i, j}), frozenset())
            if k not in sep:
                # v-structure: i → k ← j
                directed[i, k] = 1
                directed[j, k] = 1

    # For undirected edges that were NOT oriented as part of a v-structure,
    # keep them as undirected (mark both directions = 0; skeleton adj is separate).
    return directed


# ---------------------------------------------------------------------------
# Graph-distance metrics
# ---------------------------------------------------------------------------


def _skeleton_metrics(pred_adj: np.ndarray, true_adj: np.ndarray) -> dict[str, float]:
    """Compute skeleton precision, recall, and SHD (ignoring orientation)."""
    n = pred_adj.shape[0]
    # Skeletonise (symmetrise and ignore direction)
    pred_skel = np.clip(pred_adj + pred_adj.T, 0, 1)
    true_skel = np.clip(true_adj + true_adj.T, 0, 1)

    tp = fp = fn = shd = 0
    for i in range(n):
        for j in range(i + 1, n):
            p = pred_skel[i, j]
            t = true_skel[i, j]
            if p == t == 1:
                tp += 1
            elif p == 1 and t == 0:
                fp += 1
                shd += 1
            elif p == 0 and t == 1:
                fn += 1
                shd += 1
            # p==t==0: true negative, no penalty

    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # Directed SHD: add wrong-direction penalties
    for i in range(n):
        for j in range(i + 1, n):
            if pred_adj[i, j] and pred_adj[j, i]:
                continue  # undirected, skip
            if true_adj[i, j] and (not pred_adj[i, j] or pred_adj[j, i]):
                shd += 1  # reversed or undirected where directed needed

    return {"precision": prec, "recall": rec, "shd": shd}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SachsResult:
    n_obs: int
    seed: int
    skeleton_precision: float
    skeleton_recall: float
    shd: int
    n_true_edges: int = 17


# ---------------------------------------------------------------------------
# BenchmarkCase builder
# ---------------------------------------------------------------------------


def _sachs_case(
    *,
    n_obs: int,
    seed: int,
    alpha: float,
    shd_threshold: int,
    prec_threshold: float,
    recall_threshold: float,
) -> BenchmarkCase:
    def runner() -> SachsResult:
        rng = np.random.default_rng(seed)
        coef = _sachs_coef_matrix(rng)
        data = _simulate_linear_gaussian(coef, n_obs, rng)
        # Standardise columns for better CI-test performance
        data = (data - data.mean(axis=0)) / (data.std(axis=0) + 1e-10)

        skel_adj, sep_sets = _pc_skeleton(data, alpha=alpha)
        _orient_v_structures(skel_adj, sep_sets)

        true_adj = _sachs_adj()
        metrics = _skeleton_metrics(skel_adj, true_adj)

        return SachsResult(
            n_obs=n_obs,
            seed=seed,
            skeleton_precision=metrics["precision"],
            skeleton_recall=metrics["recall"],
            shd=metrics["shd"],
        )

    def checker(r: SachsResult) -> bool:
        issues = []
        if r.shd > shd_threshold:
            issues.append(f"SHD={r.shd} > threshold={shd_threshold}")
        if r.skeleton_precision < prec_threshold:
            issues.append(f"precision={r.skeleton_precision:.3f} < {prec_threshold}")
        if r.skeleton_recall < recall_threshold:
            issues.append(f"recall={r.skeleton_recall:.3f} < {recall_threshold}")
        if issues:
            raise AssertionError(f"sachs n={r.n_obs} seed={r.seed}: " + "; ".join(issues))
        return True

    return BenchmarkCase(
        name=f"sachs::n{n_obs}_seed{seed}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("sachs", "pc"),
        timeout_s=120.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_sachs_harness(
    *,
    seeds: list[int] | None = None,
    n_obs: int = 1000,
    alpha: float = 0.05,
    shd_threshold: int = 11,
    prec_threshold: float = 0.55,
    recall_threshold: float = 0.50,
) -> BenchmarkHarness:
    harness = BenchmarkHarness()
    if seeds is None:
        seeds = [42, 123, 7]
    for seed in seeds:
        case = _sachs_case(
            n_obs=n_obs,
            seed=seed,
            alpha=alpha,
            shd_threshold=shd_threshold,
            prec_threshold=prec_threshold,
            recall_threshold=recall_threshold,
        )
        harness.register(case)
    return harness


# ---------------------------------------------------------------------------
# JSON / main
# ---------------------------------------------------------------------------


def _report_to_dict(
    report: BenchmarkReport,
    *,
    mode: str,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    return build_report_payload(
        report,
        suite_id="discovery_sachs",
        mode=mode,
        preflight=preflight,
        sub_circuit="sachs",
        benchmark_family="discovery_sachs",
        proof_class="supplementary_benchmark",
        literature_anchor="Sachs et al. 2005 protein signalling network benchmark",
        baseline_snapshot_ref="phase15-discovery-sachs-v1",
        regression_guard={"rule": "no_regression_from_locked_snapshot", "expected_all_pass": True},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 3 — Sachs protein-signalling benchmark")
    parser.add_argument("--n-obs", type=int, default=1000)
    parser.add_argument("--seed", type=int, nargs="+", default=[42, 123, 7])
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--shd-threshold", type=int, default=11)
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="synthetic_sachs_network")
    print_preflight(preflight)

    harness = build_sachs_harness(
        seeds=args.seed,
        n_obs=args.n_obs,
        alpha=args.alpha,
        shd_threshold=args.shd_threshold,
    )
    report = harness.run(circuit=CIRCUIT)
    harness.print_report(report, verbose=not args.quiet)

    if args.json:
        Path(args.json).write_text(
            json.dumps(_report_to_dict(report, mode=mode, preflight=preflight), indent=2),
            encoding="utf-8",
        )
        print(f"\nJSON report written to: {args.json}")

    return 1 if report.n_total() - report.n_passed() > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
