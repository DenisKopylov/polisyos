from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
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


def test_parallel_trends_check_runs() -> None:
    pytest.importorskip("statsmodels")
    registry, dispatcher = _setup()

    rng = np.random.default_rng(41)
    outcome = np.vstack(
        [np.linspace(1.0, 3.5, 8) + rng.normal(scale=0.08, size=8) for _ in range(8)]
    )
    outcome[4:, 4:] += 0.5
    state = PanelObservationalData(
        outcome=outcome,
        treatment=np.array([0, 0, 0, 0, 1, 1, 1, 1]),
        time_treatment=4,
        treatment_timing=np.array([-1, -1, -1, -1, 4, 4, 4, 4]),
    )

    method_cls = registry.get("causal.diagnostics.parallel_trends_check@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={"alpha": 0.05},
        seed=43,
    )

    assert result.output["result"]["test_name"] == "parallel_trends_check"
    assert "p_value" in result.output["result"]


# ---------------------------------------------------------------------------
# PositivityDiagnostic tests
# ---------------------------------------------------------------------------


def test_positivity_diagnostic_passes_with_good_overlap() -> None:
    registry, dispatcher = _setup()
    rng = np.random.default_rng(7)
    n = 400
    X = rng.normal(size=(n, 3))
    # Balanced treatment assignment — good overlap
    treatment = rng.binomial(1, 0.5, size=n).astype(float)

    method_cls = registry.get("causal.diagnostics.positivity_check@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"X": X, "treatment": treatment},
        params={"min_threshold": 0.01, "overlap_band": 0.1},
        seed=0,
    )
    out = result.output["result"]
    assert out["passes_positivity"] is True
    assert 0.0 < out["ess_fraction"] <= 1.0
    assert 0.0 <= out["overlap_score"] <= 1.0
    assert out["n_obs"] == n
    assert out["n_treated"] + out["n_control"] == n


def test_positivity_diagnostic_flags_imbalance() -> None:
    registry, dispatcher = _setup()
    rng = np.random.default_rng(42)
    n = 300
    X = rng.normal(size=(n, 2))
    # Near-deterministic: treatment strongly predicted by X[:,0]
    logits = 10.0 * X[:, 0]
    probs = 1.0 / (1.0 + np.exp(-logits))
    treatment = (probs > 0.5).astype(float)

    method_cls = registry.get("causal.diagnostics.positivity_check@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"X": X, "treatment": treatment},
        params={"min_threshold": 0.05},
        seed=0,
    )
    out = result.output["result"]
    assert out["passes_positivity"] is False
    assert out["n_trimmed"] > 0


def test_positivity_diagnostic_ess_fraction_in_range() -> None:
    registry, dispatcher = _setup()
    rng = np.random.default_rng(99)
    n = 200
    X = rng.normal(size=(n, 2))
    treatment = rng.binomial(1, 0.4, size=n).astype(float)

    method_cls = registry.get("causal.diagnostics.positivity_check@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"X": X, "treatment": treatment},
        params={},
        seed=0,
    )
    out = result.output["result"]
    assert 0.0 <= out["ess_fraction"] <= 1.0
    assert out["effective_sample_size"] > 0.0
    assert set(out["propensity_percentiles"].keys()) >= {"p5", "p25", "p50", "p75", "p95"}


# ---------------------------------------------------------------------------
# SupportMismatchDiagnostic tests
# ---------------------------------------------------------------------------


def test_support_mismatch_diagnostic_runs() -> None:
    registry, dispatcher = _setup()
    rng = np.random.default_rng(10)
    n = 200
    # Small distributional shift
    X_source = rng.normal(size=(n, 3))
    X_target = rng.normal(loc=0.3, size=(n, 3))

    method_cls = registry.get("causal.diagnostics.support_mismatch@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"X_source": X_source, "X_target": X_target},
        params={"method": "logistic_trick", "ess_threshold": 0.1},
        seed=0,
    )
    out = result.output["result"]
    assert "passes_support_check" in out
    assert 0.0 < out["ess_fraction"] <= 1.0
    assert out["n_source"] == n
    assert out["n_target"] == n
    assert "weight_percentiles" in out
    assert out["density_ratio_method"] == "logistic_trick"


def test_support_mismatch_diagnostic_flags_severe_mismatch() -> None:
    registry, dispatcher = _setup()
    rng = np.random.default_rng(5)
    n = 300
    # Moderate-to-large shift: logistic classifier can learn different weights
    # N(0,1) vs N(2.5,1) — distributions overlap in tails but are clearly different
    X_source = rng.normal(loc=0.0, scale=1.0, size=(n, 2))
    X_target = rng.normal(loc=2.5, scale=1.0, size=(n, 2))

    method_cls = registry.get("causal.diagnostics.support_mismatch@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state={"X_source": X_source, "X_target": X_target},
        # High threshold: ESS fraction must be >= 0.9 to pass — unlikely for 2.5σ shift
        params={"ess_threshold": 0.9},
        seed=0,
    )
    out = result.output["result"]
    assert out["passes_support_check"] is False
    assert len(out["recommendations"]) > 0
