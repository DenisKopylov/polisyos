"""Monte Carlo coverage validation for CI calibration.

Generates K synthetic datasets with known ground truth ATE, runs each
estimator, and computes empirical coverage = fraction of times the 95%
CI contains the true ATE.

Three DGP regimes:
  1. Good overlap   — strong signal, balanced propensity
  2. Moderate overlap — mild positivity issues
  3. Poor overlap    — near-violations, heavy-tailed weights

Target: all estimators ≥ 0.90 empirical coverage at nominal 0.95.

Parameters are tuned for MacBook Air M2 16GB (K=50, n=300, folds=2,
bootstrap_draws=30).

Usage
-----
    python benchmarks/estimation/coverage_monte_carlo.py
    python benchmarks/estimation/coverage_monte_carlo.py --k 100 --n-obs 500
    python benchmarks/estimation/coverage_monte_carlo.py --json report.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


# ---------------------------------------------------------------------------
# DGP definitions
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DGPSpec:
    name: str
    regime: str  # "good" | "moderate" | "poor"
    true_ate: float
    propensity_strength: float  # controls overlap: higher = worse

    def generate(self, n: int, seed: int) -> dict[str, np.ndarray]:
        rng = np.random.default_rng(seed)
        p = 5
        X = rng.standard_normal((n, p))

        # Propensity: logistic(strength * X[:,0])
        logit_e = self.propensity_strength * X[:, 0]
        e = 1.0 / (1.0 + np.exp(-logit_e))
        e = np.clip(e, 0.005, 0.995)
        T = rng.binomial(1, e, size=n).astype(float)

        # Outcome: Y = f(X) + tau * T + noise
        f_x = 0.5 * X[:, 0] + 0.3 * X[:, 1] - 0.2 * X[:, 2]
        noise = rng.standard_normal(n) * 1.0
        Y = f_x + self.true_ate * T + noise

        return {"X": X, "T": T, "Y": Y, "true_ate": np.float64(self.true_ate)}


_DGPS: tuple[DGPSpec, ...] = (
    DGPSpec(name="good_overlap", regime="good", true_ate=1.0, propensity_strength=0.3),
    DGPSpec(name="moderate_overlap", regime="moderate", true_ate=1.0, propensity_strength=1.2),
    DGPSpec(name="poor_overlap", regime="poor", true_ate=1.0, propensity_strength=2.5),
)


# ---------------------------------------------------------------------------
# Estimator runners
# ---------------------------------------------------------------------------


def _run_aipw(data: dict[str, np.ndarray], seed: int) -> dict[str, float]:
    from polisyos.foundry.methods.catalog.causal.treatment_effects import AIPWEstimator

    result = AIPWEstimator.pure_step(
        {"X": data["X"], "treatment": data["T"], "outcome": data["Y"]},
        {
            "crossfit_folds": 2,
            "n_repeats": 1,
            "bootstrap_draws": 30,
            "propensity_clipping": 0.01,
            "random_seed": seed,
            "nuisance_model_family": "fast",
        },
    )
    report = result.get("report") or result.get("result", {})
    ate = _extract_float(report, "point_estimate", "ate")
    ci_lo = _extract_float(report, "ci_lower")
    ci_hi = _extract_float(report, "ci_upper")
    return {"ate": ate, "ci_lower": ci_lo, "ci_upper": ci_hi}


def _run_tmle(data: dict[str, np.ndarray], seed: int) -> dict[str, float]:
    from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator

    result = TMLEEstimator.pure_step(
        {"X": data["X"], "treatment": data["T"], "outcome": data["Y"]},
        {
            "crossfit_folds": 2,
            "n_repeats": 1,
            "bootstrap_draws": 30,
            "propensity_clipping": 0.01,
            "random_seed": seed,
            "nuisance_model_family": "fast",
        },
    )
    report = result.get("report") or result.get("result", {})
    ate = _extract_float(report, "point_estimate", "ate")
    ci_lo = _extract_float(report, "ci_lower")
    ci_hi = _extract_float(report, "ci_upper")
    return {"ate": ate, "ci_lower": ci_lo, "ci_upper": ci_hi}


def _extract_float(obj: Any, *keys: str) -> float:
    """Try multiple attribute/key names, return nan on failure."""
    for k in keys:
        val = getattr(obj, k, None) if not isinstance(obj, dict) else obj.get(k)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return float("nan")


_ESTIMATORS: dict[str, Any] = {
    "aipw": _run_aipw,
    "tmle": _run_tmle,
}


# ---------------------------------------------------------------------------
# Monte Carlo loop
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class CoverageResult:
    estimator: str
    regime: str
    dgp_name: str
    n_runs: int
    n_covered: int
    mean_width: float
    mean_bias: float

    @property
    def coverage(self) -> float:
        return self.n_covered / max(self.n_runs, 1)


def run_coverage_monte_carlo(
    k: int = 50,
    n_obs: int = 300,
    base_seed: int = 2026,
) -> list[CoverageResult]:
    """Run Monte Carlo coverage validation across all DGPs and estimators."""
    results: list[CoverageResult] = []

    for dgp in _DGPS:
        for est_name, est_fn in _ESTIMATORS.items():
            n_covered = 0
            widths: list[float] = []
            biases: list[float] = []
            n_valid = 0

            for i in range(k):
                seed = base_seed + i * 1000 + hash(dgp.name) % 10000
                data = dgp.generate(n_obs, seed)
                try:
                    out = est_fn(data, seed + 1)
                    ate = out["ate"]
                    ci_lo = out["ci_lower"]
                    ci_hi = out["ci_upper"]

                    if not (np.isfinite(ate) and np.isfinite(ci_lo) and np.isfinite(ci_hi)):
                        continue

                    n_valid += 1
                    biases.append(ate - dgp.true_ate)
                    widths.append(ci_hi - ci_lo)
                    if ci_lo <= dgp.true_ate <= ci_hi:
                        n_covered += 1
                except Exception:
                    continue

            results.append(
                CoverageResult(
                    estimator=est_name,
                    regime=dgp.regime,
                    dgp_name=dgp.name,
                    n_runs=n_valid,
                    n_covered=n_covered,
                    mean_width=float(np.mean(widths)) if widths else float("nan"),
                    mean_bias=float(np.mean(biases)) if biases else float("nan"),
                )
            )

    return results


def print_coverage_report(results: list[CoverageResult]) -> None:
    """Print a formatted coverage report."""
    print("\n" + "=" * 75)
    print("Monte Carlo Coverage Validation Report")
    print("=" * 75)
    print(
        f"{'Estimator':<10} {'Regime':<12} {'DGP':<20} "
        f"{'Coverage':<10} {'Width':<10} {'Bias':<10} {'Runs':<6}"
    )
    print("-" * 75)

    all_pass = True
    for r in results:
        cov = r.coverage
        status = "OK" if cov >= 0.90 else "FAIL"
        if cov < 0.90:
            all_pass = False
        print(
            f"{r.estimator:<10} {r.regime:<12} {r.dgp_name:<20} "
            f"{cov:<10.3f} {r.mean_width:<10.3f} {r.mean_bias:<+10.4f} "
            f"{r.n_runs:<6} {status}"
        )

    print("-" * 75)
    print(
        f"Overall: {'PASS' if all_pass else 'NEEDS WORK'} "
        f"(target: all estimators >= 0.90 at nominal 0.95)"
    )
    print("=" * 75)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Monte Carlo CI coverage validation")
    parser.add_argument("--k", type=int, default=50, help="Number of MC replications")
    parser.add_argument("--n-obs", type=int, default=300, help="Observations per dataset")
    parser.add_argument("--seed", type=int, default=2026, help="Base random seed")
    parser.add_argument("--json", type=str, default=None, help="Save JSON report to path")
    args = parser.parse_args()

    t0 = time.perf_counter()
    results = run_coverage_monte_carlo(k=args.k, n_obs=args.n_obs, base_seed=args.seed)
    elapsed = time.perf_counter() - t0

    print_coverage_report(results)
    print(f"\nCompleted in {elapsed:.1f}s")

    if args.json:
        report = {
            "params": {"k": args.k, "n_obs": args.n_obs, "seed": args.seed},
            "elapsed_s": round(elapsed, 2),
            "results": [dataclasses.asdict(r) for r in results],
        }
        Path(args.json).write_text(json.dumps(report, indent=2, default=str))
        print(f"JSON report saved to {args.json}")


if __name__ == "__main__":
    main()
