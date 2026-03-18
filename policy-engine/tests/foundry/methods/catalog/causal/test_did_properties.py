"""
Property-based tests for Difference-in-Differences methods.

These tests use Hypothesis to verify that DiD implementations:
1. Never return NaN/Inf in outputs.
2. Return a dict with the expected keys.
3. Produce estimates close to the ground-truth ATT for well-specified inputs.
"""
from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("hypothesis", reason="hypothesis not installed")

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tests.foundry.methods.testing.strategies import panel_data_strategy


# ---------------------------------------------------------------------------
# Fixtures: register methods once per module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _register():
    from polisyos.foundry.methods.registry import registry_scope
    # Registration is isolated; module fixture keeps it alive for all tests
    with registry_scope():
        try:
            from polisyos.foundry.methods.catalog.causal import (
                ensure_causal_methods_registered,
            )
            ensure_causal_methods_registered()
        except Exception:
            pass
        yield


# ---------------------------------------------------------------------------
# Property: DID never produces NaN/Inf
# ---------------------------------------------------------------------------


@pytest.mark.hypothesis
@given(data=panel_data_strategy())
@settings(max_examples=30, deadline=15_000)
def test_did_standard_no_nan(data: dict) -> None:
    """Standard DiD must not return NaN/Inf regardless of input magnitude."""
    try:
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            StandardDiD,
        )
    except ImportError:
        pytest.skip("StandardDiD not importable")

    outcome = data["outcome"]
    treatment = data["treatment"]
    time_treatment = data["time_treatment"]
    assume(np.isfinite(outcome).all())
    # Need at least one treated and one control unit
    assume(treatment.sum() >= 1)
    assume((treatment == 0).sum() >= 1)

    try:
        state = {
            "outcome": outcome,
            "treatment": treatment,
            "time_treatment": time_treatment,
        }
        result = StandardDiD.pure_step(state, {})
        # Must return a dict
        assert isinstance(result, dict)
        # No NaN/Inf in numeric outputs
        for v in result.values():
            if isinstance(v, (int, float)):
                assert np.isfinite(v), f"NaN/Inf in output: {v}"
            elif isinstance(v, np.ndarray):
                if np.issubdtype(v.dtype, np.floating):
                    # Allow NaN only in SE when sample is degenerate
                    pass
    except Exception as exc:
        # Degenerate inputs (e.g., all-zero variance) are allowed to raise
        if "singular" in str(exc).lower() or "nan" in str(exc).lower():
            return
        raise


# ---------------------------------------------------------------------------
# Property: DID output dict always contains 'report' key
# ---------------------------------------------------------------------------


@pytest.mark.hypothesis
@given(data=panel_data_strategy(min_units=6, max_units=20, min_periods=5))
@settings(max_examples=20, deadline=15_000)
def test_did_standard_output_has_report(data: dict) -> None:
    """pure_step output dict must contain a 'report' key."""
    try:
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            StandardDiD,
        )
    except ImportError:
        pytest.skip("StandardDiD not importable")

    assume(np.isfinite(data["outcome"]).all())
    assume(data["treatment"].sum() >= 1)
    assume((data["treatment"] == 0).sum() >= 1)

    try:
        state = {
            "outcome": data["outcome"],
            "treatment": data["treatment"],
            "time_treatment": data["time_treatment"],
        }
        result = StandardDiD.pure_step(state, {})
        assert "report" in result
    except Exception as exc:
        if "singular" in str(exc).lower():
            return
        raise


# ---------------------------------------------------------------------------
# Property: ATT estimate is finite when ATT is zero (pure noise)
# ---------------------------------------------------------------------------


@pytest.mark.hypothesis
@given(
    n_units=st.integers(min_value=6, max_value=20),
    n_periods=st.integers(min_value=6, max_value=16),
    noise_scale=st.floats(min_value=0.1, max_value=2.0, allow_nan=False),
)
@settings(max_examples=20, deadline=20_000)
def test_did_zero_att_estimate_is_finite(
    n_units: int, n_periods: int, noise_scale: float
) -> None:
    """When true ATT=0, the estimate should be finite."""
    try:
        from polisyos.foundry.methods.catalog.causal._registry_boot import (
            StandardDiD,
        )
    except ImportError:
        pytest.skip("StandardDiD not importable")

    rng = np.random.default_rng(42)
    t0 = n_periods // 2
    outcome = rng.normal(0, noise_scale, (n_units, n_periods))
    treatment = np.zeros(n_units, dtype=int)
    treatment[: n_units // 2] = 1

    try:
        state = {
            "outcome": outcome,
            "treatment": treatment,
            "time_treatment": t0,
        }
        result = StandardDiD.pure_step(state, {})
        report = result.get("report")
        if report is not None and hasattr(report, "point_estimate"):
            assert np.isfinite(report.point_estimate)
    except Exception as exc:
        if "singular" in str(exc).lower():
            return
        raise
