"""Deterministic synthetic stress cases for BERL benchmarks."""

from __future__ import annotations


def duplicate_feature_rows(n: int = 32) -> list[dict[str, float]]:
    """Return rows where x2 duplicates x1 and f should be non-identifiable by feature."""

    _require_positive_n(n)
    rows: list[dict[str, float]] = []
    for index in range(n):
        x1 = (index - (n / 2.0)) / n
        rows.append({"x1": x1, "x2": x1, "outcome": x1})
    return rows


def high_correlation_rows(n: int = 32, *, rho: float = 0.95) -> list[dict[str, float]]:
    """Return rows with a deterministic high-correlation feature pair."""

    _require_positive_n(n)
    if not 0.0 <= rho <= 1.0:
        raise ValueError("rho must be in [0, 1]")
    rows: list[dict[str, float]] = []
    for index in range(n):
        x1 = (index - (n / 2.0)) / n
        low_amplitude_signal = ((index % 5) - 2.0) / (5.0 * n)
        x2 = (rho * x1) + ((1.0 - rho) * low_amplitude_signal)
        rows.append({"x1": x1, "x2": x2, "outcome": x1 + x2})
    return rows


def proxy_feature_rows(n: int = 32) -> list[dict[str, float]]:
    """Return a proxy-feature scenario with protected and proxy variables."""

    _require_positive_n(n)
    rows: list[dict[str, float]] = []
    for index in range(n):
        protected = float(index % 2)
        proxy = protected if index % 4 != 0 else 1.0 - protected
        need = float(index % 3) / 2.0
        rows.append({"protected": protected, "proxy": proxy, "need": need, "outcome": proxy + need})
    return rows


def xor_rows() -> list[dict[str, float]]:
    """Return a minimal XOR interaction stress case."""

    return [
        {"x1": 0.0, "x2": 0.0, "outcome": 0.0},
        {"x1": 0.0, "x2": 1.0, "outcome": 1.0},
        {"x1": 1.0, "x2": 0.0, "outcome": 1.0},
        {"x1": 1.0, "x2": 1.0, "outcome": 0.0},
    ]


def _require_positive_n(n: int) -> None:
    if n <= 1:
        raise ValueError("n must be greater than 1")
