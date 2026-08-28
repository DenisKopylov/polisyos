from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.calibration.dp_ci import (
    CITestThresholdPolicy,
    CITestThresholdPolicySet,
    ci_threshold_scope,
)
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
    Y = X**2 + 0.05 * rng.normal(size=(n, 1))

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


def test_hsic_dp_calibration_reports_shifted_threshold() -> None:
    rng = np.random.default_rng(42)
    n = 140
    X = rng.normal(size=(n, 1))
    Y = rng.normal(size=(n, 1))

    base = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={"n_bootstrap": 199, "alpha": 0.05},
    )
    dp = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={
            "n_bootstrap": 199,
            "alpha": 0.05,
            "dp_context": {"mechanism": "gaussian_counts", "epsilon": 0.35, "delta": 1e-6},
        },
    )

    assert dp["calibration_mode"] == "dp_permutation_quantile"
    assert dp["critical_statistic_value"] >= base["critical_statistic_value"]
    assert dp["dp_context_summary"]["mechanism"] == "gaussian_counts"
    assert dp["metadata"]["sample_size_requirement"]["family"] == "kernel_ci"
    assert dp["naive_fpr_inflation_bound"]["reject_probability_upper_bound"] >= dp["alpha"]


def test_hsic_consumes_resolved_dp_policy() -> None:
    dp_context = {"mechanism": "gaussian_counts", "epsilon": 0.7, "delta": 0.0}
    policies = CITestThresholdPolicySet(
        policies=(
            CITestThresholdPolicy(
                alpha_base=0.10,
                mc_bootstrap_B=49,
                threshold_scope=ci_threshold_scope(
                    family="kernel_ci",
                    query_type="hsic",
                    estimator="permutation",
                    dp_context=dp_context,
                    readiness_target="diagnostic",
                ),
                threshold_registry_version=2,
            ),
        )
    )

    rng = np.random.default_rng(123)
    X = rng.normal(size=(100, 1))
    Y = rng.normal(size=(100, 1))

    out = _dispatch(
        "causal.diagnostics.independence.hsic@1.0.0",
        state={"X": X, "Y": Y},
        params={
            "alpha": 0.05,
            "n_bootstrap": 199,
            "dp_context": dp_context,
            "ci_threshold_policies": policies.model_dump(mode="python"),
        },
    )

    assert out["alpha"] == pytest.approx(0.10)
    assert out["metadata"]["n_bootstrap"] == 49
    assert out["metadata"]["threshold_registry_scope"]["dp_mechanism"] == "gaussian_counts"
    assert out["metadata"]["threshold_registry_scope"]["dp_epsilon_bucket"] == "0.5_to_1.0"


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


def test_categorical_ci_detects_dependence() -> None:
    rng = np.random.default_rng(202)
    n = 240
    X = rng.integers(0, 2, size=n)
    Y = X.copy()

    out = _dispatch(
        "causal.diagnostics.independence.categorical_ci@1.0.0",
        state={"X": X, "Y": Y},
        params={"alpha": 0.05, "statistic_family": "g2"},
    )

    assert out["test_name"] == "categorical_ci"
    assert out["passed"] is False
    assert out["metadata"]["degrees_of_freedom"] >= 1


def test_categorical_ci_passes_when_conditionally_independent() -> None:
    rng = np.random.default_rng(303)
    n = 320
    Z = rng.integers(0, 3, size=n)
    X = np.where(rng.random(n) < (0.2 + 0.2 * Z), "x1", "x0")
    Y = np.where(rng.random(n) < (0.25 + 0.15 * Z), "y1", "y0")

    out = _dispatch(
        "causal.diagnostics.independence.categorical_ci@1.0.0",
        state={"X": X, "Y": Y, "Z": Z},
        params={"alpha": 0.05, "statistic_family": "chi2"},
    )

    assert out["passed"] is True
    assert out["metadata"]["valid_strata"] >= 1


def test_categorical_ci_dp_gaussian_threshold_exceeds_classical() -> None:
    rng = np.random.default_rng(404)
    n = 260
    X = rng.integers(0, 3, size=n)
    Y = rng.integers(0, 3, size=n)

    base = _dispatch(
        "causal.diagnostics.independence.categorical_ci@1.0.0",
        state={"X": X, "Y": Y},
        params={"alpha": 0.05, "statistic_family": "g2"},
    )
    dp = _dispatch(
        "causal.diagnostics.independence.categorical_ci@1.0.0",
        state={"X": X, "Y": Y},
        params={
            "alpha": 0.05,
            "statistic_family": "g2",
            "dp_context": {"mechanism": "gaussian_counts", "epsilon": 0.4, "delta": 1e-6},
        },
    )

    assert dp["calibration_mode"] == "analytic_weighted_chi2"
    assert dp["critical_statistic_value"] >= base["critical_statistic_value"]
    assert dp["metadata"]["sample_size_requirement"]["family"] == "categorical_ci"


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


def test_partial_correlation_flags_missing_dp_calibration() -> None:
    rng = np.random.default_rng(505)
    X = rng.normal(size=120)
    Y = rng.normal(size=120)

    out = _dispatch(
        "causal.diagnostics.independence.partial_correlation@1.0.0",
        state={"X": X, "Y": Y, "Z": None},
        params={
            "alpha": 0.05,
            "dp_context": {"mechanism": "gaussian_counts", "epsilon": 1.0, "delta": 1e-6},
        },
    )

    assert out["metadata"]["dp_calibration_supported"] is False
