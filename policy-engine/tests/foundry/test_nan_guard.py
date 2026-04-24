"""Tests for NaN guard runtime checks."""

from __future__ import annotations

import jax.numpy as jnp
import pytest

from polisyos.foundry.methods.exceptions import (
    NaNGuardConfigurationError,
    NaNGuardEvaluationError,
)
from polisyos.foundry.runtime.nan_guard import (
    NaNGuard,
    create_nan_guard_for_profile,
)


class TestNaNGuardBasics:
    def test_disabled_guard_always_passes(self) -> None:
        guard = NaNGuard(enabled=False)

        state = {"slot": jnp.array([jnp.nan, 1.0, 2.0])}
        result = guard.check_state(state, "slot", "mech", time_step=0)

        assert result is True
        report = guard.get_report()
        assert report.ok is True
        assert report.checks_performed == 0

    def test_enabled_guard_catches_nan(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"income_slot": jnp.array([jnp.nan, 1.0, 2.0])}
        result = guard.check_state(state, "income_slot", "income_tax", time_step=5)

        assert result is False

        report = guard.get_report()
        assert report.ok is False
        assert len(report.diagnostics) == 1
        assert report.first_failure_step == 5

        diag = report.diagnostics[0]
        assert diag.slot_id == "income_slot"
        assert diag.mechanism_id == "income_tax"
        assert diag.nan_count == 1
        assert diag.inf_count == 0

    def test_enabled_guard_catches_inf(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"slot": jnp.array([1.0, jnp.inf, -jnp.inf])}
        result = guard.check_state(state, "slot", "mech", time_step=0)

        assert result is False

        report = guard.get_report()
        diag = report.diagnostics[0]
        assert diag.inf_count == 2
        assert diag.nan_count == 0

    def test_clean_array_passes(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"slot": jnp.array([1.0, 2.0, 3.0])}
        result = guard.check_state(state, "slot", "mech", time_step=0)

        assert result is True
        report = guard.get_report()
        assert report.ok is True
        assert report.checks_performed == 1

    def test_missing_slot_fails_closed(self) -> None:
        guard = NaNGuard(enabled=True)

        with pytest.raises(NaNGuardConfigurationError):
            guard.check_state({"other_slot": jnp.array([1.0])}, "slot", "mech", time_step=0)

    def test_jax_array_coercion_failure_raises_typed_error(self, monkeypatch) -> None:
        guard = NaNGuard(enabled=True)

        def _boom(value):
            raise TypeError("broken asarray")

        monkeypatch.setattr("jax.numpy.asarray", _boom)

        with pytest.raises(NaNGuardEvaluationError):
            guard.check_state({"slot": jnp.array([1.0])}, "slot", "mech", time_step=0)


class TestNaNGuardDiagnostics:
    def test_sample_indices_limited(self) -> None:
        guard = NaNGuard(enabled=True)

        arr = jnp.full(100, jnp.nan)
        state = {"slot": arr}
        guard.check_state(state, "slot", "mech", time_step=0)

        report = guard.get_report()
        diag = report.diagnostics[0]
        assert len(diag.sample_indices) <= 10

    def test_heuristic_cause_detection(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"utility": jnp.array([jnp.nan])}
        guard.check_state(state, "utility", "utility_calc", time_step=0)

        report = guard.get_report()
        diag = report.diagnostics[0]
        assert "log" in diag.possible_cause.lower() or "utility" in diag.possible_cause.lower()

    def test_value_stats_on_partial_nan(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"slot": jnp.array([jnp.nan, 1.0, 2.0, 3.0])}
        guard.check_state(state, "slot", "mech", time_step=0)

        report = guard.get_report()
        diag = report.diagnostics[0]

        assert "min" in diag.value_stats
        assert diag.value_stats["min"] == 1.0
        assert diag.value_stats["max"] == 3.0


class TestNaNGuardCheckInterval:
    def test_check_interval_skips_steps(self) -> None:
        guard = NaNGuard(enabled=True, check_interval=5)

        state = {"slot": jnp.array([jnp.nan])}

        guard.check_state(state, "slot", "mech", time_step=1)
        guard.check_state(state, "slot", "mech", time_step=2)
        guard.check_state(state, "slot", "mech", time_step=5)

        report = guard.get_report()
        assert report.checks_performed == 1
        assert len(report.diagnostics) == 1


class TestNaNGuardProfileFactory:
    def test_strict_profile_enabled(self) -> None:
        guard = create_nan_guard_for_profile("strict")
        assert guard.enabled is True

    def test_fast_profile_disabled(self) -> None:
        guard = create_nan_guard_for_profile("fast")
        assert guard.enabled is False

    def test_mvp_profile_enabled_with_interval(self) -> None:
        guard = create_nan_guard_for_profile("mvp")
        assert guard.enabled is True
        assert guard._check_interval > 1


class TestNaNGuardReset:
    def test_reset_clears_state(self) -> None:
        guard = NaNGuard(enabled=True)

        state = {"slot": jnp.array([jnp.nan])}
        guard.check_state(state, "slot", "mech", time_step=0)

        assert guard.get_report().ok is False

        guard.reset()

        report = guard.get_report()
        assert report.ok is True
        assert report.checks_performed == 0
        assert len(report.diagnostics) == 0
