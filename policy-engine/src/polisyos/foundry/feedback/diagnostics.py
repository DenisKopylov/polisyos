"""Trace records and convergence helpers for the feedback fixed-point solver."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from .config import PreparedFeedbackConfig


@dataclass(frozen=True)
class SolveTraceRecord:
    """Internal numeric iteration record later converted to contract DTOs."""

    stage_alpha: float
    iteration: int
    residual_norm: float
    step_norm: float
    damping: float
    method: str
    accepted: bool
    iterate: np.ndarray
    residual: np.ndarray
    diagnostics: dict[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()


def scaled_inf_norm(
    values: np.ndarray,
    *,
    prepared: PreparedFeedbackConfig,
) -> float:
    """Weighted scaled infinity norm used throughout the solver."""

    vector = np.asarray(values, dtype=float)
    denom = np.maximum(prepared.scales, 1.0e-12)
    weighted = prepared.weights * vector / denom
    return float(np.max(np.abs(weighted)))


def converged(
    current: np.ndarray,
    map_value: np.ndarray,
    residual: np.ndarray,
    *,
    prepared: PreparedFeedbackConfig,
    budget_gap: float | None = None,
) -> bool:
    """Return whether both residual and proposed step satisfy solve tolerances."""

    cfg = prepared.config.solver
    residual_norm = scaled_inf_norm(residual, prepared=prepared)
    step_norm = scaled_inf_norm(map_value - current, prepared=prepared)
    state_norm = max(1.0, scaled_inf_norm(map_value, prepared=prepared))
    basic = (
        residual_norm <= cfg.atol + cfg.rtol * state_norm
        and step_norm <= cfg.xtol + cfg.rtol * state_norm
    )
    if not basic:
        return False
    if cfg.budget_diagnostic_id is None or cfg.budget_tolerance is None or budget_gap is None:
        return basic
    return abs(float(budget_gap)) <= float(cfg.budget_tolerance)


def detect_divergence(records: list[SolveTraceRecord], *, patience: int) -> bool:
    """Return whether residual norms are growing over the recent window."""

    if len(records) < patience + 1:
        return False
    recent = [record.residual_norm for record in records[-(patience + 1) :]]
    return all(right > left for left, right in pairwise(recent))


def detect_stagnation(records: list[SolveTraceRecord], *, patience: int) -> bool:
    """Return whether residual norms have stalled over the recent window."""

    if len(records) < patience:
        return False
    recent = [record.residual_norm for record in records[-patience:]]
    improvement = max(recent) - min(recent)
    return improvement <= max(1.0e-12, 0.05 * max(recent))


def detect_two_cycle(
    records: list[SolveTraceRecord],
    *,
    patience: int,
    tolerance: float,
) -> bool:
    """Return whether the recent iterates look like a stable two-cycle."""

    if len(records) < patience:
        return False
    recent = records[-patience:]
    if len(recent) < 4:
        return False
    even = [record.iterate for record in recent[-4::2]]
    odd = [record.iterate for record in recent[-3::2]]
    even_gap = max(float(np.max(np.abs(even[0] - even[-1]))), 0.0)
    odd_gap = max(float(np.max(np.abs(odd[0] - odd[-1]))), 0.0)
    cross_gap = float(np.max(np.abs(recent[-1].iterate - recent[-2].iterate)))
    return even_gap <= tolerance and odd_gap <= tolerance and cross_gap > tolerance
