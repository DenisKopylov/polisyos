"""
Tests for MethodOutputMonitor — anomaly detection on pure_step outputs.
"""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.output_monitor import (
    AnomalyFlag,
    MethodOutputMonitor,
    _try_as_array,
    get_output_monitor,
)

# ---------------------------------------------------------------------------
# AnomalyFlag
# ---------------------------------------------------------------------------


class TestAnomalyFlag:
    def test_str_includes_reason_and_severity(self):
        flag = AnomalyFlag(key="x", reason="nan_detected", severity="error", detail="3 NaNs")
        s = str(flag)
        assert "ERROR" in s
        assert "nan_detected" in s
        assert "x" in s

    def test_str_includes_z_score_when_set(self):
        flag = AnomalyFlag(key="y", reason="distribution_shift", severity="warning", z_score=5.2)
        assert "z=5.20" in str(flag)

    def test_str_no_z_when_none(self):
        flag = AnomalyFlag(key="y", reason="nan_detected", severity="error")
        assert "z=" not in str(flag)

    def test_frozen(self):
        flag = AnomalyFlag(key="x", reason="nan_detected", severity="error")
        with pytest.raises((AttributeError, TypeError)):
            flag.key = "z"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# check_basic — NaN / Inf detection
# ---------------------------------------------------------------------------


class TestCheckBasicNanInf:
    def setup_method(self):
        self.monitor = MethodOutputMonitor()

    def test_clean_output_no_flags(self):
        result = {"coefficients": np.array([1.0, 2.0, 3.0])}
        flags = self.monitor.check_basic(result)
        assert flags == []

    def test_nan_detected(self):
        result = {"coefficients": np.array([1.0, float("nan"), 3.0])}
        flags = self.monitor.check_basic(result)
        assert len(flags) == 1
        assert flags[0].reason == "nan_detected"
        assert flags[0].severity == "error"
        assert flags[0].key == "coefficients"

    def test_inf_detected(self):
        result = {"se": np.array([0.1, float("inf"), 0.2])}
        flags = self.monitor.check_basic(result)
        assert len(flags) == 1
        assert flags[0].reason == "inf_detected"

    def test_both_nan_and_inf(self):
        arr = np.array([float("nan"), float("inf"), 1.0])
        result = {"values": arr}
        flags = self.monitor.check_basic(result)
        reasons = {f.reason for f in flags}
        assert "nan_detected" in reasons
        assert "inf_detected" in reasons

    def test_integer_array_skipped(self):
        result = {"counts": np.array([1, 2, 3])}
        flags = self.monitor.check_basic(result)
        assert flags == []

    def test_empty_array_flagged(self):
        result = {"empty": np.array([], dtype=float)}
        flags = self.monitor.check_basic(result)
        assert any(f.reason == "empty_array" for f in flags)

    def test_2d_nan_detected(self):
        arr = np.full((3, 3), fill_value=float("nan"))
        result = {"matrix": arr}
        flags = self.monitor.check_basic(result)
        assert len(flags) == 1
        assert flags[0].reason == "nan_detected"
        assert "9" in flags[0].detail  # 9 NaN values

    def test_non_array_value_skipped(self):
        result = {"status": "ok", "count": 42}
        flags = self.monitor.check_basic(result)
        assert flags == []


# ---------------------------------------------------------------------------
# check_basic — key mismatch
# ---------------------------------------------------------------------------


class TestCheckBasicKeyMismatch:
    def setup_method(self):
        self.monitor = MethodOutputMonitor()

    def test_unexpected_key_flagged(self):
        result = {"a": np.array([1.0]), "b": np.array([2.0])}
        flags = self.monitor.check_basic(result, expected_keys={"a"})
        assert any(f.reason == "unexpected_key" and f.key == "b" for f in flags)

    def test_missing_key_flagged(self):
        result = {"a": np.array([1.0])}
        flags = self.monitor.check_basic(result, expected_keys={"a", "b"})
        assert any(f.reason == "missing_key" and f.key == "b" for f in flags)

    def test_missing_key_severity_is_error(self):
        result = {}
        flags = self.monitor.check_basic(result, expected_keys={"required"})
        assert flags[0].severity == "error"

    def test_no_expected_keys_no_mismatch_flags(self):
        result = {"x": np.array([1.0])}
        flags = self.monitor.check_basic(result, expected_keys=None)
        assert all(f.reason not in {"unexpected_key", "missing_key"} for f in flags)


# ---------------------------------------------------------------------------
# check_statistical
# ---------------------------------------------------------------------------


class TestCheckStatistical:
    def setup_method(self):
        self.monitor = MethodOutputMonitor(z_score_threshold=3.0)

    def _warm_up(self, fqn: str, key: str, values: list[float]) -> None:
        for v in values:
            self.monitor.record(fqn, {key: np.array([v])})

    def test_no_history_no_flags(self):
        result = {"ate": np.array([0.5])}
        flags = self.monitor.check_statistical("causal.did.test@1.0.0", result)
        assert flags == []

    def test_within_distribution_no_flags(self):
        fqn = "causal.did.test@1.0.0"
        self._warm_up(fqn, "ate", [1.0, 1.1, 0.9, 1.0, 1.05, 0.95, 1.0, 1.0, 1.02, 0.98])
        result = {"ate": np.array([1.01])}
        flags = self.monitor.check_statistical(fqn, result)
        assert not any(f.reason == "distribution_shift" for f in flags)

    def test_outlier_detected(self):
        fqn = "causal.did.outlier@1.0.0"
        self._warm_up(fqn, "ate", [1.0] * 20)
        result = {"ate": np.array([100.0])}
        flags = self.monitor.check_statistical(fqn, result)
        assert any(f.reason == "distribution_shift" for f in flags)
        flag = next(f for f in flags if f.reason == "distribution_shift")
        assert flag.z_score is not None
        assert flag.z_score > 3.0

    def test_nan_in_result_skipped(self):
        fqn = "causal.did.nan_test@1.0.0"
        self._warm_up(fqn, "ate", [1.0] * 15)
        result = {"ate": np.array([float("nan")])}
        flags = self.monitor.check_statistical(fqn, result)
        # NaN arrays are skipped (check_basic handles them)
        assert not any(f.reason == "distribution_shift" for f in flags)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_output_monitor_returns_same_instance(self):
        m1 = get_output_monitor()
        m2 = get_output_monitor()
        assert m1 is m2

    def test_singleton_is_method_output_monitor(self):
        assert isinstance(get_output_monitor(), MethodOutputMonitor)


# ---------------------------------------------------------------------------
# _try_as_array helper
# ---------------------------------------------------------------------------


class TestTryAsArray:
    def test_ndarray_passthrough(self):
        arr = np.array([1.0, 2.0])
        assert _try_as_array(arr) is arr

    def test_list_converted(self):
        result = _try_as_array([1.0, 2.0])
        assert isinstance(result, np.ndarray)

    def test_string_returns_none(self):
        assert _try_as_array("hello") is None

    def test_dict_returns_none(self):
        assert _try_as_array({"a": 1}) is None

    def test_scalar_float_converted(self):
        arr = _try_as_array(3.14)
        assert arr is not None
        assert float(arr) == pytest.approx(3.14)
