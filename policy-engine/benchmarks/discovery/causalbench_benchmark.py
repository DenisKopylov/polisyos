"""Circuit 3: Discovery — CausalBench-style perturbational benchmark.

Evaluates edge recovery from large-scale perturbational (interventional) data,
mirroring the evaluation protocol of CausalBench (Chevalley et al. 2023) for
single-cell genetic perturbation screens.

DGPs
----
Synthetic linear-Gaussian DAGs (8-node, ~12 edges) with:
  - Observational samples (n_obs control cells)
  - Interventional samples per gene (n_int cells with do(X_i = c) per node)

Algorithm
---------
Marginal intervention detection: compare each variable's distribution in
perturbed vs control samples using Welch's t-test.
Score per directed pair (i→j): −log₁₀(p-value) of t-test for X_j in
perturbation of X_i vs control.

Metrics
-------
AUROC on directed edge recovery

Bar
---
AUROC ≥ 0.70

Usage
-----
    python benchmarks/discovery/causalbench_benchmark.py
    python benchmarks/discovery/causalbench_benchmark.py --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
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
# Metric helpers
# ---------------------------------------------------------------------------


def _norm_sf(z: float) -> float:
    """Upper-tail survival of standard normal (Abramowitz & Stegun)."""
    z = abs(z)
    t = 1.0 / (1.0 + 0.2316419 * z)
    poly = t * (
        0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    return poly * math.exp(-0.5 * z * z)


def _welch_t_pvalue(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sided Welch t-test p-value between groups a and b."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 1.0
    ma, mb = a.mean(), b.mean()
    va = a.var(ddof=1) / na
    vb = b.var(ddof=1) / nb
    denom = math.sqrt(va + vb + 1e-12)
    t_stat = abs(ma - mb) / denom
    # Welch-Satterthwaite degrees of freedom
    df = ((va + vb) ** 2) / (va**2 / max(na - 1, 1) + vb**2 / max(nb - 1, 1))
    # Approximate t-distribution p-value via normal for large df
    if df > 100:
        return 2.0 * _norm_sf(t_stat)
    # For smaller df, use a rough approximation (conservative)
    # t_p ≈ 2 * norm_sf(t * sqrt(df/(df+t^2)))  — not great, acceptable
    adjusted_z = t_stat * math.sqrt(df / (df + t_stat**2 + 1e-6))
    return min(1.0, 2.0 * _norm_sf(adjusted_z))


def _compute_auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    n_pos = int(labels.sum())
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores)
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
    u = float(np.sum(ranks[labels == 1])) - n_pos * (n_pos + 1) / 2.0
    return u / (n_pos * n_neg)


# ---------------------------------------------------------------------------
# 8-node DAG DGP
# ---------------------------------------------------------------------------

# Fixed 8-node DAG topology: sparse Erdős–Rényi-like with ~12 edges
# Nodes: 0..7, topologically sorted.  True adj[i,j]=1 means i→j.
_N8 = 8
_TRUE_EDGES_8: list[tuple[int, int]] = [
    (0, 1),
    (0, 2),
    (0, 3),
    (1, 3),
    (1, 4),
    (2, 4),
    (2, 5),
    (3, 6),
    (4, 6),
    (4, 7),
    (5, 7),
    (6, 7),
]


def _build_true_adj8() -> np.ndarray:
    adj = np.zeros((_N8, _N8), dtype=int)
    for i, j in _TRUE_EDGES_8:
        adj[i, j] = 1
    return adj


def _simulate_perturbational(
    n_obs: int,
    n_int: int,
    seed: int,
) -> tuple[np.ndarray, list[np.ndarray], np.ndarray]:
    """Simulate observational + per-node interventional data.

    Returns
    -------
    control_data  : (n_obs, n) observational samples
    pert_data     : list of (n_int, n) arrays, one per node (do(X_i = 2))
    true_adj      : (n, n) ground-truth adjacency
    """
    rng = np.random.default_rng(seed)
    n = _N8
    true_adj = _build_true_adj8()

    # Random positive linear coefficients
    coef = np.zeros((n, n))
    for i, j in _TRUE_EDGES_8:
        coef[j, i] = rng.uniform(0.5, 1.0)  # X_j receives from X_i

    def _sample(
        n_samples: int, intervened_node: int | None = None, intervention_val: float = 2.0
    ) -> np.ndarray:
        data = np.zeros((n_samples, n))
        eps = rng.standard_normal((n_samples, n))
        for node in range(n):  # already in topological order 0..7
            if intervened_node is not None and node == intervened_node:
                data[:, node] = intervention_val
            else:
                parents = [p for p in range(n) if coef[node, p] != 0]
                x_node = eps[:, node].copy()
                for p in parents:
                    x_node += coef[node, p] * data[:, p]
                data[:, node] = x_node
        return data

    control = _sample(n_obs)
    interventions = [_sample(n_int, intervened_node=i) for i in range(n)]

    return control, interventions, true_adj


# ---------------------------------------------------------------------------
# Perturbational edge detection
# ---------------------------------------------------------------------------


def _detect_edges_perturbational(
    control: np.ndarray,
    interventions: list[np.ndarray],
) -> np.ndarray:
    """Score matrix: score[i,j] = −log10(p-value) for i→j.

    Large score means more evidence for edge i→j (perturbation of i
    significantly changes the distribution of j).
    """
    n = control.shape[1]
    scores = np.zeros((n, n))
    for i, pert in enumerate(interventions):
        for j in range(n):
            if i == j:
                continue
            p = _welch_t_pvalue(pert[:, j], control[:, j])
            scores[i, j] = -math.log10(max(p, 1e-12))
    return scores


# ---------------------------------------------------------------------------
# Result type + BenchmarkCase
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CausalBenchResult:
    auroc: float
    n_true_edges: int
    n_possible_edges: int
    seed: int


def _causalbench_case(
    *,
    n_obs: int,
    n_int: int,
    seed: int,
    auroc_threshold: float,
) -> BenchmarkCase:
    def runner() -> CausalBenchResult:
        control, ints, true_adj = _simulate_perturbational(n_obs, n_int, seed)
        scores = _detect_edges_perturbational(control, ints)

        n = _N8
        mask = np.ones(n * n, dtype=bool)
        mask[np.arange(n) * n + np.arange(n)] = False  # exclude diagonal

        auroc = _compute_auroc(scores.flatten()[mask], true_adj.flatten()[mask])
        return CausalBenchResult(
            auroc=auroc,
            n_true_edges=int(true_adj.sum()),
            n_possible_edges=int(mask.sum()),
            seed=seed,
        )

    def checker(r: CausalBenchResult) -> bool:
        if r.auroc < auroc_threshold:
            raise AssertionError(f"CausalBench AUROC={r.auroc:.3f} < {auroc_threshold}")
        return True

    return BenchmarkCase(
        name=f"causalbench::8node_seed{seed}",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("causalbench", "perturbational"),
        timeout_s=60.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_causalbench_harness(
    *,
    n_obs: int = 300,
    n_int: int = 200,
    seeds: list[int] | None = None,
    auroc_threshold: float = 0.70,
) -> BenchmarkHarness:
    harness = BenchmarkHarness()
    if seeds is None:
        seeds = [42, 7, 99]
    for seed in seeds:
        harness.register(
            _causalbench_case(
                n_obs=n_obs,
                n_int=n_int,
                seed=seed,
                auroc_threshold=auroc_threshold,
            )
        )
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
        suite_id="discovery_causalbench",
        mode=mode,
        preflight=preflight,
        sub_circuit="causalbench",
        benchmark_family="discovery_causalbench",
        proof_class="supplementary_benchmark",
        literature_anchor="CausalBench perturbational single-cell benchmark",
        baseline_snapshot_ref="phase15-discovery-causalbench-v1",
        regression_guard={"rule": "no_regression_from_locked_snapshot", "expected_all_pass": True},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 3 — CausalBench perturbational benchmark")
    parser.add_argument("--n-obs", type=int, default=300)
    parser.add_argument("--n-int", type=int, default=200)
    parser.add_argument("--seed", type=int, nargs="+", default=[42, 7, 99])
    parser.add_argument("--auroc-threshold", type=float, default=0.70)
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="synthetic_perturbational_ground_truth")
    print_preflight(preflight)

    harness = build_causalbench_harness(
        n_obs=args.n_obs,
        n_int=args.n_int,
        seeds=args.seed,
        auroc_threshold=args.auroc_threshold,
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
