from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.contracts.foundry import (
    FeedbackConfig,
    FeedbackSolverConfig,
    FeedbackStateSnapshot,
    FeedbackVariableSpec,
)
from polisyos.foundry.feedback.config import PreparedFeedbackConfig, prepare_feedback_config
from polisyos.foundry.feedback.jacobian import finite_difference_jacobian, summarize_jacobian


def _prepared() -> PreparedFeedbackConfig:
    variables = [
        FeedbackVariableSpec(
            variable_id="x",
            source_kind="state_path",
            source_ref="market.x",
            target_kind="state_path",
            target_ref="policy.x",
            initial_value=0.25,
            lower_bound=-5.0,
            upper_bound=5.0,
            scale=1.0,
            finite_difference_step=1.0e-5,
        ),
        FeedbackVariableSpec(
            variable_id="y",
            source_kind="state_path",
            source_ref="market.y",
            target_kind="state_path",
            target_ref="policy.y",
            initial_value=-0.5,
            lower_bound=-5.0,
            upper_bound=5.0,
            scale=1.0,
            finite_difference_step=2.0e-5,
        ),
    ]
    config = FeedbackConfig(variables=variables, solver=FeedbackSolverConfig())
    return prepare_feedback_config(
        config,
        initial_state=FeedbackStateSnapshot(
            variable_ids=["x", "y"],
            values=[0.25, -0.5],
            scales=[1.0, 1.0],
            lower_bounds=[-5.0, -5.0],
            upper_bounds=[5.0, 5.0],
            weights=[1.0, 1.0],
        ),
    )


def test_affine_jacobian_uses_nonzero_baseline_with_or_without_supplied_value() -> None:
    matrix = np.asarray([[2.0, -3.0], [0.5, 4.0]], dtype=float)
    offset = np.asarray([7.0, -2.5], dtype=float)
    point = np.asarray([1.25, -0.75], dtype=float)

    def evaluate(value: np.ndarray) -> np.ndarray:
        return matrix @ value + offset

    baseline = evaluate(point)

    estimated = finite_difference_jacobian(evaluate, point, prepared=_prepared())
    estimated_with_baseline = finite_difference_jacobian(
        evaluate,
        point,
        prepared=_prepared(),
        baseline_map=baseline,
    )

    assert np.all(np.abs(baseline) > 0.0)
    assert np.allclose(estimated, matrix, atol=1.0e-9)
    assert np.allclose(estimated_with_baseline, matrix, atol=1.0e-9)


@pytest.mark.parametrize(
    ("matrix", "expected_fold"),
    [
        (np.asarray([[1.0 - 0.125]], dtype=float), True),
        (np.asarray([[1.0 - 0.126]], dtype=float), False),
    ],
)
def test_fold_diagnostic_tracks_singular_value_boundary(
    matrix: np.ndarray,
    expected_fold: bool,
) -> None:
    summary = summarize_jacobian(matrix, fold_singular_value_threshold=0.125)

    assert summary.near_fold is expected_fold
    assert summary.near_fold == (summary.smallest_singular_value_i_minus_j <= 0.125)


@pytest.mark.parametrize(
    ("eigenvalue", "expected_flip"),
    [(-1.0, True), (-1.051, False)],
)
def test_flip_diagnostic_tracks_eigenvalue_boundary(
    eigenvalue: float,
    expected_flip: bool,
) -> None:
    summary = summarize_jacobian(
        np.asarray([[eigenvalue]], dtype=float),
        flip_eigenvalue_tolerance=5.0e-2,
    )

    assert summary.near_flip is expected_flip
