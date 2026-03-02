from __future__ import annotations

import math

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import sensitivity_metrics as sensitivity_module
from polisyos.foundry.methods.causal import GraphCausalData, ensure_causal_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _instrumental_fixture(n: int = 600, seed: int = 123) -> GraphCausalData:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    logits = 0.8 * z
    p = 1.0 / (1.0 + np.exp(-logits))
    treatment = rng.binomial(1, p, size=n).astype(float)
    outcome = 0.9 * treatment + 0.7 * z + rng.normal(0.0, 0.4, size=n)
    return GraphCausalData(
        data=np.column_stack([treatment, outcome, z]),
        column_names=["T", "Y", "Z"],
        treatment="T",
        outcome="Y",
        graph_dot="digraph { Z -> T; Z -> Y; T -> Y; }",
        graph_ref="cas:graph:instrumental",
        covariates=["Z"],
    )


def _continuous_treatment_fixture(n: int = 400, seed: int = 321) -> GraphCausalData:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=n)
    treatment = 0.6 * z + rng.normal(0.0, 0.3, size=n)
    outcome = 0.7 * treatment + 0.8 * z + rng.normal(0.0, 0.4, size=n)
    return GraphCausalData(
        data=np.column_stack([treatment, outcome, z]),
        column_names=["T", "Y", "Z"],
        treatment="T",
        outcome="Y",
        graph_dot="digraph { Z -> T; Z -> Y; T -> Y; }",
        graph_ref="cas:graph:continuous-treatment",
        covariates=["Z"],
    )


def _dispatch_result(data: GraphCausalData, *, params: dict[str, object]):
    ensure_causal_methods_registered()
    method_cls = MethodRegistry.get_instance().get("causal.sensitivity.sensitivity_metrics@1.0.0")
    result = MethodDispatcher.get_instance().dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params=params,
        seed=11,
    )
    return result.output


def test_sensitivity_metrics_evalue_matches_hand_calculation():
    payload = _dispatch_result(
        _instrumental_fixture(),
        params={
            "point_estimate": 0.5,
            "confidence_interval": [0.2, 0.8],
            "standard_error": 0.1,
            "sample_size": 600,
            "conversion_method": "ate_to_rr_log",
            "covariates": ["Z"],
        },
    )

    result = payload["sensitivity_result"]
    rr = math.exp(0.5)
    expected = rr + math.sqrt(rr * (rr - 1.0))
    assert abs(result.e_value - expected) <= 1.0e-10
    assert result.conversion_method == "ate_to_rr_log"
    assert result.e_value_result is not None
    assert result.e_value_result.method == "ate_to_rr_log"


def test_sensitivity_metrics_auto_conversion_uses_rr_approx_when_baseline_risk_provided():
    payload = _dispatch_result(
        _instrumental_fixture(),
        params={
            "point_estimate": 0.05,
            "confidence_interval": [0.01, 0.09],
            "conversion_method": "auto",
            "baseline_risk": 0.4,
            "covariates": ["Z"],
        },
    )

    result = payload["sensitivity_result"]
    expected_rr = 0.45 / 0.4
    expected_e = expected_rr + math.sqrt(expected_rr * (expected_rr - 1.0))
    assert result.conversion_method == "ate_to_rr_approx"
    assert abs(result.e_value - expected_e) <= 1.0e-10


def test_sensitivity_metrics_graceful_without_sensemakr(monkeypatch):
    monkeypatch.setattr(
        sensitivity_module,
        "_load_sensemakr_module",
        lambda: (_ for _ in ()).throw(ModuleNotFoundError("sensemakr missing")),
    )

    payload = _dispatch_result(
        _instrumental_fixture(),
        params={
            "point_estimate": 0.3,
            "confidence_interval": [0.1, 0.5],
            "standard_error": 0.2,
            "sample_size": 600,
            "conversion_method": "ate_to_rr_log",
            "covariates": ["Z"],
        },
    )

    result = payload["sensitivity_result"]
    warnings = payload.get("warnings", [])
    assert result.robustness_value is None
    assert any("sensemakr unavailable" in str(item) for item in warnings)


def test_sensitivity_metrics_is_robust_requires_all_available_metrics(monkeypatch):
    monkeypatch.setattr(
        sensitivity_module,
        "_compute_robustness",
        lambda **kwargs: (0.2, 0.1, None),
    )
    monkeypatch.setattr(
        sensitivity_module,
        "_compute_rosenbaum_gamma",
        lambda **kwargs: (2.0, 0.2, None),
    )

    payload = _dispatch_result(
        _instrumental_fixture(),
        params={
            "point_estimate": 0.4,
            "confidence_interval": [0.2, 0.6],
            "standard_error": 0.1,
            "sample_size": 600,
            "e_value_threshold": 1.2,
            "robustness_value_threshold": 0.05,
            "rosenbaum_gamma_threshold": 1.5,
            "covariates": ["Z"],
        },
    )
    assert payload["sensitivity_result"].is_robust is True

    monkeypatch.setattr(
        sensitivity_module,
        "_compute_rosenbaum_gamma",
        lambda **kwargs: (1.1, 0.2, None),
    )
    payload_weak = _dispatch_result(
        _instrumental_fixture(),
        params={
            "point_estimate": 0.4,
            "confidence_interval": [0.2, 0.6],
            "standard_error": 0.1,
            "sample_size": 600,
            "e_value_threshold": 1.2,
            "robustness_value_threshold": 0.05,
            "rosenbaum_gamma_threshold": 1.5,
            "covariates": ["Z"],
        },
    )
    assert payload_weak["sensitivity_result"].is_robust is False


def test_sensitivity_metrics_skips_rosenbaum_for_non_binary_treatment():
    payload = _dispatch_result(
        _continuous_treatment_fixture(),
        params={
            "point_estimate": 0.2,
            "confidence_interval": [0.1, 0.3],
            "standard_error": 0.08,
            "sample_size": 400,
            "conversion_method": "ate_to_rr_log",
            "covariates": ["Z"],
        },
    )
    result = payload["sensitivity_result"]
    warnings = payload.get("warnings", [])
    assert result.rosenbaum_gamma is None
    assert result.rosenbaum_p_value is None
    assert any("treatment must be binary" in str(item) for item in warnings)
