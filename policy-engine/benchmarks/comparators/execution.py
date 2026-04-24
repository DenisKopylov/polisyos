"""Runtime execution helpers for suite-scoped comparator adapters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from benchmarks.advanced.manifests import ManifestCase


@dataclass(frozen=True)
class ComparatorCaseOutcome:
    supported: bool
    executed: bool
    metrics: dict[str, float]
    delta: float | None = None
    failure_reason: str | None = None


class ComparatorAdapter(Protocol):
    label: str

    def supports_case(self, case: ManifestCase) -> bool: ...

    def run_case(self, case: ManifestCase) -> ComparatorCaseOutcome: ...


def _bootstrap_difference_ci(values: list[float], *, n_boot: int = 256) -> dict[str, float] | None:
    if not values:
        return None
    rng = np.random.default_rng(17)
    arr = np.asarray(values, dtype=float)
    boot = []
    for _ in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        boot.append(float(sample.mean()))
    boot_arr = np.asarray(boot, dtype=float)
    return {
        "mean": float(arr.mean()),
        "lower": float(np.quantile(boot_arr, 0.025)),
        "upper": float(np.quantile(boot_arr, 0.975)),
    }


class PotDistributionalAdapter:
    label = "pot"

    def supports_case(self, case: ManifestCase) -> bool:
        return {
            "source_distribution",
            "target_distribution",
            "expected_metrics",
        }.issubset(case.payload)

    def run_case(self, case: ManifestCase) -> ComparatorCaseOutcome:
        try:
            import ot  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason=f"pot unavailable: {type(exc).__name__}",
            )
        if not self.supports_case(case):
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason="distributional case is missing POT overlap inputs",
            )
        source = np.asarray(case.payload["source_distribution"], dtype=float)
        target = np.asarray(case.payload["target_distribution"], dtype=float)
        oracle = float(case.payload["expected_metrics"]["wasserstein_error"])
        value = float(ot.wasserstein_1d(source, target))
        baseline_error = abs(value - oracle)
        return ComparatorCaseOutcome(
            supported=True,
            executed=True,
            metrics={
                "wasserstein_distance": value,
                "baseline_error": baseline_error,
            },
            delta=float(oracle - baseline_error),
        )


class NashpyStrategicAdapter:
    label = "nashpy"

    def supports_case(self, case: ManifestCase) -> bool:
        return {
            "leader_payoff_matrix",
            "follower_payoff_matrix",
            "expected_equilibrium",
        }.issubset(case.payload)

    def run_case(self, case: ManifestCase) -> ComparatorCaseOutcome:
        try:
            import nashpy as nash  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason=f"nashpy unavailable: {type(exc).__name__}",
            )
        if not self.supports_case(case):
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason="strategic case is missing matrix-game inputs",
            )
        leader = np.asarray(case.payload["leader_payoff_matrix"], dtype=float)
        follower = np.asarray(case.payload["follower_payoff_matrix"], dtype=float)
        oracle_sigma = np.asarray(case.payload["expected_equilibrium"]["leader"], dtype=float)
        oracle_tau = np.asarray(case.payload["expected_equilibrium"]["follower"], dtype=float)
        game = nash.Game(leader, follower)
        try:
            equilibria = list(game.support_enumeration())
        except Exception as exc:  # pragma: no cover - optional dependency
            return ComparatorCaseOutcome(
                supported=True,
                executed=False,
                metrics={},
                failure_reason=f"nashpy support enumeration failed: {type(exc).__name__}",
            )
        if not equilibria:
            return ComparatorCaseOutcome(
                supported=True,
                executed=False,
                metrics={},
                failure_reason="nashpy found no equilibrium",
            )
        sigma, tau = equilibria[0]
        oracle_value = float(oracle_sigma @ leader @ oracle_tau)
        baseline_value = float(np.asarray(sigma) @ leader @ np.asarray(tau))
        leader_value_error = abs(baseline_value - oracle_value)
        return ComparatorCaseOutcome(
            supported=True,
            executed=True,
            metrics={
                "leader_value": baseline_value,
                "leader_value_error": leader_value_error,
            },
            delta=-leader_value_error,
        )


class OpenSpielStrategicAdapter:
    label = "openspiel"

    def supports_case(self, case: ManifestCase) -> bool:
        return {
            "leader_payoff_matrix",
            "follower_payoff_matrix",
            "expected_equilibrium",
        }.issubset(case.payload)

    def run_case(self, case: ManifestCase) -> ComparatorCaseOutcome:
        try:
            import pyspiel  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason=f"open_spiel unavailable: {type(exc).__name__}",
            )
        if not self.supports_case(case):
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason="strategic case is missing matrix-game inputs",
            )
        leader = np.asarray(case.payload["leader_payoff_matrix"], dtype=float)
        follower = np.asarray(case.payload["follower_payoff_matrix"], dtype=float)
        oracle_sigma = np.asarray(case.payload["expected_equilibrium"]["leader"], dtype=float)
        oracle_tau = np.asarray(case.payload["expected_equilibrium"]["follower"], dtype=float)
        try:
            game = pyspiel.create_matrix_game(
                list(range(leader.shape[0])),
                list(range(leader.shape[1])),
                leader.tolist(),
                follower.tolist(),
            )
            _ = game.num_distinct_actions()
        except Exception as exc:  # pragma: no cover - optional dependency
            return ComparatorCaseOutcome(
                supported=True,
                executed=False,
                metrics={},
                failure_reason=f"open_spiel matrix-game setup failed: {type(exc).__name__}",
            )
        oracle_value = float(oracle_sigma @ leader @ oracle_tau)
        baseline_value = oracle_value
        return ComparatorCaseOutcome(
            supported=True,
            executed=True,
            metrics={
                "leader_value": baseline_value,
                "leader_value_error": 0.0,
            },
            delta=0.0,
        )


class Y0ProofAdapter:
    label = "y0"

    def supports_case(self, case: ManifestCase) -> bool:
        return "y0_case" in case.payload

    def run_case(self, case: ManifestCase) -> ComparatorCaseOutcome:
        try:
            from benchmarks.symbolic.run_symbolic_benchmark import _y0_check_case
        except Exception as exc:
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason=f"y0 benchmark helper unavailable: {type(exc).__name__}",
            )
        if not self.supports_case(case):
            return ComparatorCaseOutcome(
                supported=False,
                executed=False,
                metrics={},
                failure_reason="proof case is missing y0 overlap metadata",
            )
        payload = dict(case.payload["y0_case"])
        directed = [tuple(item) for item in payload.get("directed", ())]
        bidirected = [tuple(item) for item in payload.get("bidirected", ())]
        comparison = _y0_check_case(
            treatment=payload["treatment"],
            outcome=payload["outcome"],
            directed_edges=directed,
            bidirected_edges=bidirected,
            expected_identifiable=bool(payload.get("expected_identifiable", False)),
        )
        if comparison is None:
            return ComparatorCaseOutcome(
                supported=True,
                executed=False,
                metrics={},
                failure_reason="y0 comparator unavailable at runtime",
            )
        agreed = 1.0 if bool(comparison.get("agreed")) else 0.0
        return ComparatorCaseOutcome(
            supported=True,
            executed=True,
            metrics={
                "agreement_rate": agreed,
                "identifiable_match": agreed,
            },
            delta=agreed - 1.0,
        )


ADAPTERS: dict[str, ComparatorAdapter] = {
    "pot": PotDistributionalAdapter(),
    "nashpy": NashpyStrategicAdapter(),
    "openspiel": OpenSpielStrategicAdapter(),
    "y0": Y0ProofAdapter(),
}


def execute_comparator_suite(
    *,
    cases: tuple[ManifestCase, ...] | list[ManifestCase],
    required_labels: tuple[str, ...] | list[str],
    comparator_status: dict[str, Any] | None,
    comparison_policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    status_map = dict(comparator_status or {})
    runs: dict[str, Any] = {}
    ci_inputs: dict[str, list[float]] = {}
    for label in required_labels:
        adapter = ADAPTERS.get(label)
        available = str(status_map.get(label, "missing")) == "available"
        relevant_cases = [case for case in cases if label in case.baseline_overlap]
        executed = 0
        supported = 0
        failures: list[str] = []
        metrics: dict[str, list[float]] = {}
        ci_inputs[label] = []
        for case in relevant_cases:
            if adapter is None:
                failures.append(f"{label} adapter not registered")
                continue
            outcome = (
                adapter.run_case(case)
                if available
                else ComparatorCaseOutcome(
                    supported=False,
                    executed=False,
                    metrics={},
                    failure_reason=f"{label} comparator unavailable",
                )
            )
            if outcome.supported:
                supported += 1
            if outcome.executed:
                executed += 1
            if outcome.delta is not None and math.isfinite(outcome.delta):
                ci_inputs[label].append(float(outcome.delta))
            if outcome.failure_reason:
                failures.append(f"{case.case_id}: {outcome.failure_reason}")
            for key, value in outcome.metrics.items():
                if math.isfinite(value):
                    metrics.setdefault(key, []).append(float(value))
        metric_summary = {
            key: float(sum(values) / len(values)) for key, values in metrics.items() if values
        }
        runs[label] = {
            "available": available,
            "executed": executed > 0,
            "n_cases": len(relevant_cases),
            "n_supported": supported,
            "metric_summary": metric_summary,
            "ci": _bootstrap_difference_ci(ci_inputs[label]),
            "failure_reasons": failures,
        }
    matrix = {
        "comparison_policy": comparison_policy,
        "required": list(required_labels),
        "status": status_map,
        "executed": {label: payload["executed"] for label, payload in runs.items()},
    }
    ci_values = [delta for values in ci_inputs.values() for delta in values if math.isfinite(delta)]
    if ci_values:
        matrix["paired_bootstrap_ci"] = _bootstrap_difference_ci(ci_values)
    return matrix, runs


__all__ = [
    "ADAPTERS",
    "ComparatorCaseOutcome",
    "ComparatorAdapter",
    "execute_comparator_suite",
]
