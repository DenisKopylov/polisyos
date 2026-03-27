"""Tests for distributional residual tests."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.scientist.backtesting.distributional import (
    test_residual_autocorrelation as check_autocorrelation,
    test_residual_normality as check_normality,
    test_residual_stationarity as check_stationarity,
)


class TestNormality:
    def test_normal_data(self):
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=200).tolist()
        result = check_normality(data)
        # Normal data should not be rejected (though Shapiro can be strict)
        assert result.statistic > 0

    def test_non_normal_data(self):
        # Heavily skewed data
        data = [1.0] * 50 + [100.0] * 5
        result = check_normality(data)
        assert result.reject_null is True

    def test_insufficient_data(self):
        result = check_normality([1.0, 2.0])
        assert result.description == "insufficient_data"
        assert result.reject_null is False


class TestAutocorrelation:
    def test_iid_data(self):
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=200).tolist()
        result = check_autocorrelation(data)
        assert result.test_name == "ljung_box_approx"

    def test_autocorrelated_data(self):
        # AR(1) process
        rng = np.random.default_rng(42)
        data = [0.0]
        for _ in range(200):
            data.append(0.9 * data[-1] + rng.normal(0, 0.1))
        result = check_autocorrelation(data)
        assert result.reject_null is True

    def test_insufficient_data(self):
        result = check_autocorrelation([1.0, 2.0])
        assert result.reject_null is False


class TestStationarity:
    def test_stationary(self):
        rng = np.random.default_rng(42)
        data = rng.normal(0, 1, size=100).tolist()
        result = check_stationarity(data)
        assert result.reject_null is False

    def test_non_stationary(self):
        # Mean shift
        data = [0.0] * 50 + [100.0] * 50
        result = check_stationarity(data)
        assert result.reject_null is True

    def test_insufficient_data(self):
        result = check_stationarity([1.0, 2.0])
        assert result.reject_null is False
