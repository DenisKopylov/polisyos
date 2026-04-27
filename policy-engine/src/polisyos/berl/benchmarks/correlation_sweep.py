"""Correlation-regime benchmark helpers for BERL."""

from __future__ import annotations

from dataclasses import dataclass

from polisyos.berl.benchmarks.synthetic_redundancy import high_correlation_rows
from polisyos.berl.metrics.redundancy import detect_redundancy_clusters


@dataclass(frozen=True, slots=True)
class CorrelationSweepCase:
    """One correlation-regime stress case."""

    rho: float
    rows: list[dict[str, float]]
    redundancy_detected: bool


def build_correlation_sweep(
    regimes: tuple[float, ...] = (0.0, 0.5, 0.95),
    *,
    n: int = 64,
    corr_threshold: float = 0.8,
) -> tuple[CorrelationSweepCase, ...]:
    """Return low/medium/high correlation cases required by BERL benchmarks."""

    cases: list[CorrelationSweepCase] = []
    for rho in regimes:
        rows = high_correlation_rows(n=n, rho=rho)
        clusters = detect_redundancy_clusters(rows, corr_threshold=corr_threshold)
        cases.append(
            CorrelationSweepCase(
                rho=rho,
                rows=rows,
                redundancy_detected=bool(clusters),
            )
        )
    return tuple(cases)
