from __future__ import annotations

import numpy as np
import pytest

from polisyos.ir.analytics.partial_identification import (
    BoundMethod,
    PartialIdentificationResult,
    compute_manski_bounds,
)


def test_manski_bounds_symmetric_case() -> None:
    """When E[Y|X=0]=0.4, E[Y|X=1]=0.6, p0=p1=0.5, support [0,1]."""
    result = compute_manski_bounds(
        outcome_conditioned=np.array([0.4, 0.6]),
        treatment_probs=np.array([0.5, 0.5]),
        outcome_support=(0.0, 1.0),
    )
    assert result.method == BoundMethod.MANSKI
    assert result.lower_bound < result.upper_bound
    assert result.lower_bound < 0.2  # true ATE=0.2 is within bounds
    assert result.upper_bound > 0.2
    assert result.bound_width == pytest.approx(result.upper_bound - result.lower_bound)


def test_manski_bounds_informativeness() -> None:
    """Wide bounds should be non-informative."""
    result = compute_manski_bounds(
        outcome_conditioned=np.array([0.5, 0.5]),
        treatment_probs=np.array([0.5, 0.5]),
        outcome_support=(0.0, 1.0),
    )
    # ATE = 0, but bounds are wide: [-0.5, 0.5]
    assert result.bound_width == pytest.approx(1.0)
    assert not result.is_informative


def test_manski_bounds_narrow_support() -> None:
    """Narrow outcome support produces narrow bounds."""
    result = compute_manski_bounds(
        outcome_conditioned=np.array([0.45, 0.55]),
        treatment_probs=np.array([0.5, 0.5]),
        outcome_support=(0.4, 0.6),
    )
    assert result.bound_width < 0.5
    assert result.is_informative


def test_manski_bounds_extreme_treatment() -> None:
    """When nearly everyone is treated, bounds shrink."""
    result = compute_manski_bounds(
        outcome_conditioned=np.array([0.3, 0.7]),
        treatment_probs=np.array([0.01, 0.99]),
        outcome_support=(0.0, 1.0),
    )
    # With p1~1.0, imputation uncertainty is minimal for treated group
    assert result.lower_bound < result.upper_bound


def test_partial_identification_result_schema_version() -> None:
    r = PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=-0.3,
        upper_bound=0.5,
        confidence=0.6,
    )
    assert r.schema_version == "1.0"
    assert r.bound_width == pytest.approx(0.8)
    assert not r.is_informative  # 0.8 > 0.5 threshold


def test_partial_identification_informative_narrow() -> None:
    r = PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=0.1,
        upper_bound=0.3,
        confidence=0.9,
    )
    assert r.bound_width == pytest.approx(0.2)
    assert r.is_informative
