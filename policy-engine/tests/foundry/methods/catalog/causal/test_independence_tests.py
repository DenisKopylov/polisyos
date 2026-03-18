from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _setup() -> tuple:
    ensure_causal_methods_registered()
    return MethodRegistry.get_instance(), MethodDispatcher.get_instance()


def _dispatch(fqn: str, state: dict, params: dict) -> dict:
    registry, dispatcher = _setup()
    method_cls = registry.get(fqn)
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params=params,
        seed=0,
    )
    return result.output["result"]


# ---------------------------------------------------------------------------
# HSICIndependenceTest
# ---------------------------------------------------------------------------


def test_hsic_detects_dependence() -> None:
    """HSIC should reject independence when Y = f(X) with strong signal."""
    rng = np.random.default_rng(1)
    n = 120
    X = rng.normal(size=(n, 1))
    Y = X ** 2 + 0.05 * rng.normal(size=(n, 1))

    out = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={"n_bootstrap": 299, "alpha": 0.05},
    )

    assert out["test_name"] == "hsic"
    assert isinstance(out["statistic"], float)
    assert 0.0 <= out["p_value"] <= 1.0
    # Strong dependence — should be rejected (passed=False)
    assert out["passed"] is False


def test_hsic_passes_for_independent() -> None:
    """HSIC should not reject independence for genuinely independent X, Y."""
    rng = np.random.default_rng(999)
    n = 200
    X = rng.normal(size=(n, 2))
    Y = rng.normal(size=(n, 2))  # independent of X

    out = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={"n_bootstrap": 299, "alpha": 0.05},
    )

    assert out["passed"] is True
    assert out["p_value"] >= 0.05
    assert "n_obs" in out["metadata"]
    assert out["metadata"]["n_obs"] == n


def test_hsic_output_structure() -> None:
    """All expected fields are present in HSIC output."""
    rng = np.random.default_rng(7)
    n = 60
    X = rng.normal(size=(n, 1))
    Y = rng.normal(size=(n, 1))

    out = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={"n_bootstrap": 99, "alpha": 0.05},
    )

    required = {"test_name", "statistic", "p_value", "passed", "critical_value", "metadata"}
    assert required <= set(out.keys())
    assert out["critical_value"] == 0.05


# ---------------------------------------------------------------------------
# KCIConditionalTest
# ---------------------------------------------------------------------------


def test_kci_detects_conditional_dependence() -> None:
    """KCI should reject X ⊥ Y | Z when X -> Y directly (not via Z)."""
    rng = np.random.default_rng(22)
    n = 100
    Z = rng.normal(size=(n, 1))
    X = Z + 0.3 * rng.normal(size=(n, 1))
    Y = X + Z + 0.1 * rng.normal(size=(n, 1))  # direct X->Y path

    out = _dispatch(
        "causal.diagnostics.independence.kci@1.0.0",
        state={"X": X, "Y": Y, "Z": Z},
        params={"n_bootstrap": 199, "alpha": 0.05},
    )

    assert out["test_name"] == "kci"
    assert 0.0 <= out["p_value"] <= 1.0
    # Strong direct path X->Y: should be rejected (passed=False)
    assert out["passed"] is False


def test_kci_passes_when_conditionally_independent() -> None:
    """KCI should not reject X ⊥ Y | Z for a chain X <- Z -> Y."""
    rng = np.random.default_rng(333)
    n = 150
    Z = rng.normal(size=(n, 1))
    X = Z + 0.2 * rng.normal(size=(n, 1))
    Y = Z + 0.2 * rng.normal(size=(n, 1))  # X and Y independent given Z

    out = _dispatch(
        "causal.diagnostics.independence.kci@1.0.0",
        state={"X": X, "Y": Y, "Z": Z},
        params={"n_bootstrap": 199, "alpha": 0.05},
    )

    assert out["passed"] is True
    assert "bandwidth_z" in out["metadata"]


# ---------------------------------------------------------------------------
# PartialCorrelationTest
# ---------------------------------------------------------------------------


def test_partial_correlation_runs() -> None:
    """PartialCorrelationTest basic smoke test."""
    rng = np.random.default_rng(55)
    n = 100
    Z = rng.normal(size=(n, 2))
    X = Z[:, 0] + 0.5 * rng.normal(size=n)
    Y = Z[:, 1] + 0.5 * rng.normal(size=n)

    out = _dispatch(
        "causal.diagnostics.independence.partial_correlation@1.0.0",
        state={"X": X, "Y": Y, "Z": Z},
        params={"alpha": 0.05},
    )

    assert out["test_name"] == "partial_correlation"
    assert -1.0 <= out["metadata"]["partial_corr"] <= 1.0
    assert 0.0 <= out["p_value"] <= 1.0


def test_partial_correlation_detects_linear_dependence() -> None:
    """PartialCorrelation should detect strong linear dependence."""
    rng = np.random.default_rng(77)
    n = 200
    X = rng.normal(size=n)
    Y = 3.0 * X + 0.05 * rng.normal(size=n)  # near-perfect correlation

    out = _dispatch(
        "causal.diagnostics.independence.partial_correlation@1.0.0",
        state={"X": X, "Y": Y, "Z": None},
        params={"alpha": 0.05},
    )

    assert out["passed"] is False
    assert abs(out["metadata"]["partial_corr"]) > 0.9
