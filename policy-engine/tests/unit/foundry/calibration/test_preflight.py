from __future__ import annotations

import numpy as np
import numpy.testing as npt
import pytest

from polisyos.foundry.calibration.preflight import (
    _align_by_length,
    _normalize_raw_target,
)


class TestNormalizeRawTarget:
    def test_normalize_raw_target_tuple(self) -> None:
        values = np.array([1.0, 2.0, 3.0])
        time = np.array([0, 1, 2])
        result_values, result_time = _normalize_raw_target((values, time))
        npt.assert_array_equal(result_values, values)
        npt.assert_array_equal(result_time, time)

    def test_normalize_raw_target_dict(self) -> None:
        raw = {"values": [1.0, 2.0], "time": [0, 1]}
        result_values, result_time = _normalize_raw_target(raw)
        npt.assert_array_equal(result_values, np.array([1.0, 2.0]))
        npt.assert_array_equal(result_time, np.array([0, 1]))

    def test_normalize_raw_target_scalar_reshape(self) -> None:
        result_values, result_time = _normalize_raw_target(5.0)
        assert result_values.shape == (1,)
        npt.assert_allclose(result_values, [5.0])
        assert result_time is None

    def test_normalize_raw_target_dict_missing_values_raises(self) -> None:
        with pytest.raises(ValueError, match="must contain"):
            _normalize_raw_target({"time": [0, 1]})


class TestAlignByLength:
    def test_align_by_length_exact_match(self) -> None:
        values = np.array([1.0, 2.0, 3.0])
        result = _align_by_length(values, steps=3, fill_value=None)
        npt.assert_array_equal(result, values)

    def test_align_by_length_padding(self) -> None:
        values = np.array([1.0, 2.0])
        result = _align_by_length(values, steps=4, fill_value=0.0)
        assert result.shape == (4,)
        npt.assert_array_equal(result[:2], values)
        npt.assert_array_equal(result[2:], [0.0, 0.0])

    def test_align_by_length_truncation(self) -> None:
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _align_by_length(values, steps=3, fill_value=None)
        assert result.shape == (3,)
        npt.assert_array_equal(result, [1.0, 2.0, 3.0])

    def test_align_by_length_padding_with_last_value(self) -> None:
        values = np.array([1.0, 2.0, 3.0])
        result = _align_by_length(values, steps=5, fill_value=None)
        assert result.shape == (5,)
        npt.assert_allclose(result[3:], [3.0, 3.0])
