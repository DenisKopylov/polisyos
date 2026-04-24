"""Circuit 3: Discovery — Tübingen cause-effect pairs benchmark.

Evaluates pairwise causal direction identification on synthetic bivariate
data generated from Additive Noise Models (ANMs), mirroring the evaluation
protocol of the Tübingen cause-effect pairs dataset (Mooij et al. 2016).

DGPs
----
50 synthetic bivariate pairs:
  - 20 linear ANM   : Y = a*X + ε  (X→Y)
  - 15 cubic ANM    : Y = X³/3 + ε  (X→Y)
  - 10 sin ANM      : Y = sin(X) + ε  (X→Y)
  - 5  reverse pairs: true direction is Y→X (uniform over ANM types)

Algorithm
---------
Residual independence test (pure numpy HSIC approximation):
  - Fit Y ~ X (linear), compute ε = Y − β̂X
  - Fit X ~ Y (linear), compute η = X − γ̂Y
  - Score = HSIC(X, η) − HSIC(Y, ε)  (positive → prefer X→Y)
Breaks: use |corr(X², ε)| vs |corr(Y², η)| as a nonlinearity tiebreaker.

Metrics
-------
Direction accuracy (fraction of pairs with correct inferred direction)

Bar
---
Accuracy ≥ 0.65  (top-quartile reference on Tübingen pairs)

Usage
-----
    python benchmarks/discovery/tuebingen_benchmark.py
    python benchmarks/discovery/tuebingen_benchmark.py --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.kernel_ridge import KernelRidge
from sklearn.model_selection import KFold

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
# HSIC approximation (O(n²) kernel statistic)
# ---------------------------------------------------------------------------


def _rbf_kernel(x: np.ndarray, sigma: float) -> np.ndarray:
    """Radial basis function (Gaussian) kernel matrix."""
    diff = x[:, None] - x[None, :]
    return np.exp(-0.5 * (diff / sigma) ** 2)


def _hsic(x: np.ndarray, y: np.ndarray) -> float:
    """Empirical HSIC with median-heuristic bandwidth (O(n²))."""
    n = len(x)
    if n < 4:
        return 0.0
    # Median heuristic for bandwidth
    diff_x = np.abs(x[:, None] - x[None, :])
    diff_y = np.abs(y[:, None] - y[None, :])
    sigma_x = float(np.median(diff_x[diff_x > 0])) + 1e-6
    sigma_y = float(np.median(diff_y[diff_y > 0])) + 1e-6

    Kx = _rbf_kernel(x, sigma_x)
    Ky = _rbf_kernel(y, sigma_y)

    # Centre kernel matrices: Kc = H @ K @ H  where H = I − (1/n) 11ᵀ
    H = np.eye(n) - 1.0 / n
    Kxc = H @ Kx @ H
    Kyc = H @ Ky @ H

    return float(np.trace(Kxc @ Kyc)) / (n * n)


# ---------------------------------------------------------------------------
# ANM direction test
# ---------------------------------------------------------------------------


def _median_gamma(x: np.ndarray) -> float:
    pairwise = np.abs(x[:, None] - x[None, :])
    non_zero = pairwise[pairwise > 0]
    sigma = float(np.median(non_zero)) if non_zero.size else 1.0
    sigma = max(sigma, 1e-3)
    return 1.0 / (2.0 * sigma * sigma)


def _kernel_ridge_residuals(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = x.reshape(-1, 1)
    y = y.reshape(-1)
    gamma = _median_gamma(x.reshape(-1))
    cv = KFold(n_splits=3, shuffle=False)
    alpha_grid = (1e-3, 1e-2, 1e-1, 1.0)

    best_alpha = alpha_grid[0]
    best_mse = float("inf")
    for alpha in alpha_grid:
        fold_mse: list[float] = []
        for train_idx, test_idx in cv.split(x):
            model = KernelRidge(kernel="rbf", alpha=alpha, gamma=gamma)
            model.fit(x[train_idx], y[train_idx])
            pred = model.predict(x[test_idx])
            fold_mse.append(float(np.mean((y[test_idx] - pred) ** 2)))
        mean_mse = float(np.mean(fold_mse))
        if mean_mse < best_mse - 1e-12:
            best_mse = mean_mse
            best_alpha = alpha

    model = KernelRidge(kernel="rbf", alpha=best_alpha, gamma=gamma)
    model.fit(x, y)
    pred = model.predict(x)
    return y - pred


def _nonlinearity_tiebreak(x: np.ndarray, residual: np.ndarray) -> float:
    centered_x = x - x.mean()
    centered_r = residual - residual.mean()
    num = float(np.sum((centered_x**2) * centered_r))
    den = math.sqrt(float(np.sum(centered_x**4)) * float(np.sum(centered_r**2)) + 1e-12)
    return abs(num / den) if den > 0 else 0.0


def _anm_direction_score(x: np.ndarray, y: np.ndarray) -> float:
    """Score > 0 → prefer X→Y;  score < 0 → prefer Y→X.

    Uses HSIC of the residual from fitting in each direction:
      forward  : ε = y − β*x,  test HSIC(x, ε)
      backward : η = x − γ*y,  test HSIC(y, η)
    Score = HSIC(y, η) − HSIC(x, ε)   (smaller residual-HSIC = true causal dir)
    """
    # Normalise for numerical stability
    x = (x - x.mean()) / (x.std() + 1e-8)
    y = (y - y.mean()) / (y.std() + 1e-8)

    # Forward residual: fit y ~ x with nonlinear ANM regression
    eps = _kernel_ridge_residuals(x, y)

    # Backward residual: fit x ~ y with the same regression family
    eta = _kernel_ridge_residuals(y, x)

    hsic_fwd = _hsic(x, eps)  # should be small if X→Y is true
    hsic_bwd = _hsic(y, eta)  # should be small if Y→X is true

    score = hsic_bwd - hsic_fwd  # positive → prefer X→Y
    if abs(score) < 1e-4:
        # Only break near-ties using higher-order residual dependence.
        return _nonlinearity_tiebreak(y, eta) - _nonlinearity_tiebreak(x, eps)
    return score


# ---------------------------------------------------------------------------
# Synthetic pair DGPs
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class BivariatePair:
    pair_id: str
    true_direction: str  # "X→Y" or "Y→X"
    dgp_type: str  # "linear", "cubic", "sin"


def _make_pairs() -> list[BivariatePair]:
    pairs: list[BivariatePair] = []
    # 20 linear X→Y
    for i in range(20):
        pairs.append(BivariatePair(f"linear_{i:02d}", "X→Y", "linear"))
    # 15 cubic X→Y
    for i in range(15):
        pairs.append(BivariatePair(f"cubic_{i:02d}", "X→Y", "cubic"))
    # 10 sin X→Y
    for i in range(10):
        pairs.append(BivariatePair(f"sin_{i:02d}", "X→Y", "sin"))
    # 5 reverse (Y→X, linear)
    for i in range(5):
        pairs.append(BivariatePair(f"reverse_{i:02d}", "Y→X", "linear"))
    return pairs


def _simulate_pair(pair: BivariatePair, n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Simulate (X, Y) from the specified ANM DGP."""
    rng = np.random.default_rng(seed)
    noise_scale = 0.5

    if pair.true_direction == "X→Y":
        X = rng.standard_normal(n)
        eps = rng.normal(0, noise_scale, n)
        if pair.dgp_type == "linear":
            coef = rng.uniform(0.5, 1.5)
            Y = coef * X + eps
        elif pair.dgp_type == "cubic":
            Y = X**3 / 3.0 + eps
        else:  # sin
            Y = np.sin(X) + eps
        return X, Y

    # Y→X: swap roles
    Y = rng.standard_normal(n)
    eta = rng.normal(0, noise_scale, n)
    coef = rng.uniform(0.5, 1.5)
    X = coef * Y + eta
    return X, Y


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class TuebingenResult:
    n_pairs: int
    n_correct: int
    accuracy: float
    n_per_type: dict[str, int]
    n_correct_per_type: dict[str, int]


# ---------------------------------------------------------------------------
# BenchmarkCase builder
# ---------------------------------------------------------------------------


def _tuebingen_case(
    pairs: list[BivariatePair],
    *,
    n_obs: int,
    seed: int,
    accuracy_threshold: float,
) -> BenchmarkCase:
    def runner() -> TuebingenResult:
        def _eval_pair(args: tuple[int, BivariatePair]) -> tuple[BivariatePair, bool]:
            i, pair = args
            X, Y = _simulate_pair(pair, n_obs, seed + i)
            score = _anm_direction_score(X, Y)
            pred = "X→Y" if score > 0 else "Y→X"
            return pair, pred == pair.true_direction

        # Evaluate pairs in parallel — each pair is independent, each uses its own RNG.
        # KernelRidge + HSIC both release the GIL during LAPACK/numpy ops.
        n_workers = min(8, len(pairs))
        with ThreadPoolExecutor(max_workers=n_workers) as ex:
            pair_results = list(ex.map(_eval_pair, enumerate(pairs)))

        n_correct = 0
        n_per_type: dict[str, int] = {}
        n_correct_per_type: dict[str, int] = {}
        for pair, correct in pair_results:
            n_per_type[pair.dgp_type] = n_per_type.get(pair.dgp_type, 0) + 1
            if correct:
                n_correct += 1
                n_correct_per_type[pair.dgp_type] = n_correct_per_type.get(pair.dgp_type, 0) + 1

        accuracy = n_correct / len(pairs) if pairs else 0.0
        return TuebingenResult(
            n_pairs=len(pairs),
            n_correct=n_correct,
            accuracy=accuracy,
            n_per_type=n_per_type,
            n_correct_per_type=n_correct_per_type,
        )

    def checker(r: TuebingenResult) -> bool:
        if r.accuracy < accuracy_threshold:
            raise AssertionError(
                f"Direction accuracy={r.accuracy:.3f} < {accuracy_threshold}"
                f" (correct={r.n_correct}/{r.n_pairs})"
            )
        return True

    return BenchmarkCase(
        name="tuebingen::anm_50_pairs",
        circuit=CIRCUIT,
        runner=runner,
        checker=checker,
        tags=("tuebingen", "anm"),
        timeout_s=180.0,
    )


# ---------------------------------------------------------------------------
# Harness builder
# ---------------------------------------------------------------------------


def build_tuebingen_harness(
    *,
    n_obs: int = 500,
    seed: int = 42,
    accuracy_threshold: float = 0.65,
) -> BenchmarkHarness:
    harness = BenchmarkHarness()
    pairs = _make_pairs()
    harness.register(
        _tuebingen_case(pairs, n_obs=n_obs, seed=seed, accuracy_threshold=accuracy_threshold)
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
        suite_id="discovery_tuebingen",
        mode=mode,
        preflight=preflight,
        sub_circuit="tuebingen",
        benchmark_family="discovery_tuebingen",
        proof_class="supplementary_benchmark",
        literature_anchor="Mooij et al. 2016 Tuebingen cause-effect pairs",
        baseline_snapshot_ref="phase15-discovery-tuebingen-v2",
        regression_guard={"rule": "no_regression_from_locked_snapshot", "expected_all_pass": True},
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Circuit 3 — Tübingen ANM direction benchmark")
    parser.add_argument("--n-obs", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--accuracy-threshold", type=float, default=0.65)
    parser.add_argument("--mode", choices=("smoke", "acceptance"))
    parser.add_argument("--json", metavar="FILE")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    mode = resolve_mode(args.mode).value
    preflight = build_preflight(mode=mode, data_source="synthetic_anm_pairs")
    print_preflight(preflight)

    harness = build_tuebingen_harness(
        n_obs=args.n_obs,
        seed=args.seed,
        accuracy_threshold=args.accuracy_threshold,
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
