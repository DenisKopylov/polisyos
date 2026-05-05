from __future__ import annotations

import numpy as np
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from polisyos.foundry.data_plane.bindings import _apply_transform

_HEALTH_CHECKS = [HealthCheck.function_scoped_fixture, HealthCheck.too_slow]


@st.composite
def _matrices(draw) -> np.ndarray:
    rows = draw(st.integers(min_value=1, max_value=4))
    cols = draw(st.integers(min_value=1, max_value=4))
    flat = draw(
        st.lists(
            st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
            min_size=rows * cols,
            max_size=rows * cols,
        )
    )
    return np.asarray(flat, dtype=np.float32).reshape(rows, cols)


@given(
    values=_matrices(),
    lower=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
    upper=st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, suppress_health_check=_HEALTH_CHECKS)
def test_clip_transform_preserves_shape_and_bounds(
    values: np.ndarray,
    lower: float,
    upper: float,
) -> None:
    if lower > upper:
        lower, upper = upper, lower

    clipped = _apply_transform(
        op="clip",
        value=values,
        params={"min": lower, "max": upper},
    )

    assert isinstance(clipped, np.ndarray)
    assert clipped.shape == values.shape
    assert np.all(clipped >= lower)
    assert np.all(clipped <= upper)
    assert np.allclose(clipped, np.clip(values, lower, upper))


@given(
    values=_matrices(),
    digits=st.integers(min_value=0, max_value=4),
)
@settings(max_examples=100, suppress_health_check=_HEALTH_CHECKS)
def test_round_transform_matches_numpy_round(
    values: np.ndarray,
    digits: int,
) -> None:
    rounded = _apply_transform(
        op="round",
        value=values,
        params={"digits": digits},
    )

    assert isinstance(rounded, np.ndarray)
    assert rounded.shape == values.shape
    assert np.allclose(rounded, np.round(values, decimals=digits))
