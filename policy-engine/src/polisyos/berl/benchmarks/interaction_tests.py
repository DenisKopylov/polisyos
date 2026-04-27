"""Interaction-heavy and support-stress benchmark helpers."""

from __future__ import annotations

from polisyos.berl.benchmarks.synthetic_redundancy import xor_rows


def threshold_tree_rows(n: int = 32, *, threshold: float = 0.5) -> list[dict[str, float]]:
    """Return a one-feature threshold stress case."""

    if n <= 1:
        raise ValueError("n must be greater than 1")
    rows: list[dict[str, float]] = []
    for index in range(n):
        x1 = index / (n - 1)
        rows.append({"x1": x1, "x2": 1.0 - x1, "outcome": float(x1 > threshold)})
    return rows


def out_of_support_masking_rows() -> list[dict[str, float]]:
    """Return rows where independent masking would create unrealistic pairs."""

    return [
        {"age": 16.0, "employment_years": 0.0, "outcome": 0.0},
        {"age": 30.0, "employment_years": 10.0, "outcome": 1.0},
        {"age": 45.0, "employment_years": 25.0, "outcome": 1.0},
        {"age": 70.0, "employment_years": 40.0, "outcome": 0.0},
    ]


def interaction_suite() -> dict[str, list[dict[str, float]]]:
    """Return interaction-heavy cases required by the benchmark acceptance criteria."""

    return {
        "xor_interaction": xor_rows(),
        "threshold_tree": threshold_tree_rows(),
        "out_of_support_masking": out_of_support_masking_rows(),
    }
