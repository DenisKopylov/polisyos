"""Helpers for normalizing feedback-solver configuration into numeric arrays."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from polisyos.core.contracts.foundry import FeedbackConfig, FeedbackStateSnapshot


@dataclass(frozen=True)
class PreparedFeedbackConfig:
    """Numeric view of the public feedback config used by the solver."""

    config: FeedbackConfig
    variable_ids: tuple[str, ...]
    initial_values: np.ndarray
    scales: np.ndarray
    lower_bounds: np.ndarray
    upper_bounds: np.ndarray
    weights: np.ndarray
    finite_difference_steps: np.ndarray


def prepare_feedback_config(
    config: FeedbackConfig,
    *,
    initial_state: FeedbackStateSnapshot,
) -> PreparedFeedbackConfig:
    """Convert a public `FeedbackConfig` plus initial snapshot into numeric arrays."""

    if len(config.variables) != len(initial_state.values):
        raise ValueError(
            "Feedback initial state dimensionality does not match config variables: "
            f"{len(initial_state.values)} != {len(config.variables)}"
        )
    for index, start in enumerate(config.solver.multi_start_values):
        if len(start) != len(config.variables):
            raise ValueError(
                "Feedback multi_start_values entry dimensionality does not match config variables: "
                f"entry {index} has {len(start)} values, expected {len(config.variables)}"
            )

    variable_ids = tuple(spec.variable_id for spec in config.variables)
    scales = np.asarray(
        [float(spec.scale) if spec.scale is not None else 1.0 for spec in config.variables],
        dtype=float,
    )
    lower_bounds = np.asarray(
        [(-np.inf if spec.lower_bound is None else spec.lower_bound) for spec in config.variables],
        dtype=float,
    )
    upper_bounds = np.asarray(
        [(np.inf if spec.upper_bound is None else spec.upper_bound) for spec in config.variables],
        dtype=float,
    )
    weights = np.asarray([float(spec.weight) for spec in config.variables], dtype=float)
    finite_difference_steps = np.asarray(
        [
            (
                float(spec.finite_difference_step)
                if spec.finite_difference_step is not None
                else float(config.solver.jacobian_eps)
            )
            for spec in config.variables
        ],
        dtype=float,
    )

    return PreparedFeedbackConfig(
        config=config,
        variable_ids=variable_ids,
        initial_values=np.asarray(initial_state.values, dtype=float),
        scales=scales,
        lower_bounds=lower_bounds,
        upper_bounds=upper_bounds,
        weights=weights,
        finite_difference_steps=finite_difference_steps,
    )


def snapshot_from_vector(
    prepared: PreparedFeedbackConfig,
    values: np.ndarray,
    *,
    notes: list[str] | None = None,
) -> FeedbackStateSnapshot:
    """Convert a numeric feedback vector back into the public snapshot model."""

    vector = np.asarray(values, dtype=float)
    return FeedbackStateSnapshot(
        variable_ids=list(prepared.variable_ids),
        values=vector.tolist(),
        scales=prepared.scales.tolist(),
        lower_bounds=[None if np.isneginf(v) else float(v) for v in prepared.lower_bounds],
        upper_bounds=[None if np.isposinf(v) else float(v) for v in prepared.upper_bounds],
        weights=prepared.weights.tolist(),
        notes=list(notes or []),
    )


def project_bounds(prepared: PreparedFeedbackConfig, values: np.ndarray) -> np.ndarray:
    """Clip a feedback vector into its feasible box constraints."""

    vector = np.asarray(values, dtype=float)
    return np.minimum(np.maximum(vector, prepared.lower_bounds), prepared.upper_bounds)
