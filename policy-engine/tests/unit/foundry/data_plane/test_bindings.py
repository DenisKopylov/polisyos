from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.data_plane.bindings import InputBindingsBuildResult, _apply_transform


class TestInputBindingsBuildResult:
    def test_result_fields(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1", "b2"),
        )
        assert result.applied_binding_ids == ("b1", "b2")
        assert result.input_bindings_ref is not None

    def test_result_empty_bindings(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=(),
        )
        assert len(result.applied_binding_ids) == 0

    def test_result_frozen(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1",),
        )
        with pytest.raises(AttributeError):
            result.applied_binding_ids = ("b2",)  # type: ignore[misc]

    def test_result_tuple_immutability(self) -> None:
        result = InputBindingsBuildResult(
            input_bindings_ref=MagicMock(),
            input_binding_report_ref=MagicMock(),
            bound_state_snapshot_ref=MagicMock(),
            applied_binding_ids=("b1", "b2", "b3"),
        )
        assert isinstance(result.applied_binding_ids, tuple)
        assert len(result.applied_binding_ids) == 3


def test_apply_transform_vectorized_fast_paths_match_scalar_semantics() -> None:
    values = np.array([-1.7, 0.0, 2.2, 8.9], dtype=np.float32)
    expected_ints = [int(item) for item in values.tolist()]

    clipped = _apply_transform(op="clip", value=values, params={"min": -1, "max": 5})
    rounded = _apply_transform(op="round", value=values, params={"digits": 0})
    ints = _apply_transform(op="to_int", value=values, params={})
    bools = _apply_transform(op="to_bool", value=jnp.array([0.0, 1.0, 2.0]), params={})

    assert isinstance(clipped, np.ndarray)
    assert isinstance(rounded, np.ndarray)
    assert isinstance(ints, np.ndarray)
    assert isinstance(bools, jnp.ndarray)
    assert np.allclose(clipped, np.array([-1.0, 0.0, 2.2, 5.0], dtype=np.float32))
    assert np.allclose(rounded, np.array([-2.0, 0.0, 2.0, 9.0], dtype=np.float32))
    assert ints.tolist() == expected_ints
    assert np.asarray(bools).tolist() == [False, True, True]


def test_apply_transform_decimal_slow_path_preserves_multidimensional_shape() -> None:
    values = jnp.array([[1, 2], [3, 4]], dtype=jnp.int32)

    decimals = _apply_transform(op="to_decimal", value=values, params={})

    assert decimals == [
        [Decimal("1"), Decimal("2")],
        [Decimal("3"), Decimal("4")],
    ]
