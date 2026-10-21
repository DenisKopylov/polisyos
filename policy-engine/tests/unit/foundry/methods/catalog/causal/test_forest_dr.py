from __future__ import annotations

import sys
from importlib import import_module
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal.forest_dr import (
    ForestDRLearnerEstimator,
    ForestDRLearnerEstimatorV11,
)
from polisyos.ir.analytics.causal import CausalMethod


def _make_hte_data(n: int = 250, seed: int = 0) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 4))
    e = 1.0 / (1.0 + np.exp(-(0.7 * X[:, 0] - 0.4 * X[:, 1])))
    T = rng.binomial(1, np.clip(e, 0.05, 0.95)).astype(float)
    tau = 0.4 + 0.7 * X[:, 2]
    mu = 1.3 * X[:, 0] - 0.6 * X[:, 3]
    Y = mu + tau * T + rng.normal(scale=0.35, size=n)
    return {"outcome": Y, "treatment": T, "covariates": X}


def test_forest_dr_gracefully_fails_without_backend():
    state = _make_hte_data()
    result = ForestDRLearnerEstimator.pure_step(state, {"__seed__": 7})
    report = result["report"]
    assert report.method == CausalMethod.FOREST_DR
    assert report.status.value in {"success", "numerical_failure"}


def test_forest_dr_output_shape_when_backend_available_or_graceful_failure():
    state = _make_hte_data(n=180, seed=3)
    result = ForestDRLearnerEstimator.pure_step(
        state,
        {
            "__seed__": 11,
            "n_estimators": 64,
            "cv_folds": 2,
            "subforest_size": 2,
        },
    )
    report = result["report"]
    assert report.method == CausalMethod.FOREST_DR
    if report.status.value == "success":
        hte_result = result["hte_result"]
        assert len(hte_result.cate_values) == 180
        assert np.isfinite(hte_result.ate)


def test_forest_dr_serial_abi_is_additive_and_enforces_single_job():
    legacy = ForestDRLearnerEstimator.signature
    serial = ForestDRLearnerEstimatorV11.signature

    assert legacy.fqn == "causal.hte.forest_dr@1.0.0"
    assert legacy.abi_digest() == "d7216b0e22a0df3e667944dd3ce02dfdf636397b8595387477b40cc100473818"
    assert "n_jobs" not in {parameter.name for parameter in legacy.parameters}
    assert serial.fqn == "causal.hte.forest_dr@1.1.0"
    assert serial.abi_digest() == "c47789927627661e4eedd78368cc710181060dc1e705b8484cbf089fe50234e4"
    n_jobs = next(parameter for parameter in serial.parameters if parameter.name == "n_jobs")
    assert n_jobs.default == 1
    assert n_jobs.bounds == (1, 1)

    state = _make_hte_data(n=40)
    for invalid in (True, False, 1.0, "1", None, 0, 2, -1):
        with pytest.raises(ValueError, match="requires n_jobs=1"):
            ForestDRLearnerEstimatorV11.pure_step(state, {"n_jobs": invalid})


def _install_forest_dr_pipeline_fakes(monkeypatch, *, fail_at: str | None = None):
    module = import_module("polisyos.foundry.methods.catalog.causal.forest_dr")
    original_build_hte_data = module.build_hte_data
    original_build_subgroups = module.build_cate_quantile_subgroups
    original_hte_result = module.HTEResult
    original_success_report = module.build_success_report
    original_wrap_output = module.wrap_causal_output
    original_extract_cate = module.extract_cate_from_estimator
    state = {"active": False}
    events: list[tuple[str, bool]] = []
    records: dict[str, object] = {}

    def record(name: str) -> None:
        events.append((name, state["active"]))

    class ThreadLimit:
        def __enter__(self):
            assert not state["active"]
            state["active"] = True
            record("limit_enter")
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            record("limit_exit")
            state["active"] = False
            return False

    threadpoolctl = ModuleType("threadpoolctl")

    def threadpool_limits(*, limits: int):
        assert limits == 1
        return ThreadLimit()

    threadpoolctl.threadpool_limits = threadpool_limits
    monkeypatch.setitem(sys.modules, "threadpoolctl", threadpoolctl)

    econml = ModuleType("econml")
    econml_dr = ModuleType("econml.dr")

    class FakeForestDRLearner:
        def __init__(self, **kwargs):
            record("construct")
            records["estimator_params"] = kwargs
            self.feature_importances_ = np.array([0.1, 0.2, 0.3, 0.4])

        def fit(self, y, treatment, *, X, W):
            record("fit")
            if fail_at == "fit":
                raise RuntimeError("fit failure")

        def effect(self, x):
            record("effect")
            return np.linspace(0.2, 0.8, x.shape[0])

        def effect_interval(self, x, *, alpha):
            record("effect_interval")
            effects = np.linspace(0.2, 0.8, x.shape[0])
            return effects - 0.1, effects + 0.1

        def effect_inference(self, x):
            record("effect_inference")
            return SimpleNamespace(stderr=np.full(x.shape[0], 0.1))

        def shap_values(self, x, *, feature_names=None, background_samples=100):
            record("shap_values")
            records["shap_args"] = (feature_names, background_samples)
            return {"Y0": {"T0": SimpleNamespace(values=np.ones(x.shape, dtype=float))}}

        def ate_inference(self, x):
            record("ate_inference")
            return SimpleNamespace(
                conf_int=lambda alpha: (0.1, 0.9),
                pvalue=0.05,
                stderr_mean=0.1,
            )

    econml_dr.ForestDRLearner = FakeForestDRLearner
    econml.dr = econml_dr
    monkeypatch.setitem(sys.modules, "econml", econml)
    monkeypatch.setitem(sys.modules, "econml.dr", econml_dr)
    monkeypatch.setattr(module, "require_econml", lambda: None)

    def build_hte_data(state_value):
        record("prepare_input")
        return original_build_hte_data(state_value)

    def extract_cate_from_estimator(
        model,
        x,
        *,
        alpha,
        feature_names,
        feature_importance_method,
        rng,
    ):
        record(f"extract:{feature_importance_method}")
        if fail_at == "extract":
            raise RuntimeError("extraction failure")
        return original_extract_cate(
            model,
            x,
            alpha=alpha,
            feature_names=feature_names,
            feature_importance_method=feature_importance_method,
            rng=rng,
        )

    def build_subgroups(**kwargs):
        record("subgroups")
        return original_build_subgroups(**kwargs)

    def build_hte_result(**kwargs):
        record("hte_result")
        return original_hte_result(**kwargs)

    def build_success_report(**kwargs):
        record("report")
        return original_success_report(**kwargs)

    def wrap_causal_output(report, *, warnings, extras):
        record("wrap")
        return original_wrap_output(report, warnings=warnings, extras=extras)

    monkeypatch.setattr(module, "build_hte_data", build_hte_data)
    monkeypatch.setattr(module, "extract_cate_from_estimator", extract_cate_from_estimator)
    monkeypatch.setattr(module, "build_cate_quantile_subgroups", build_subgroups)
    monkeypatch.setattr(module, "HTEResult", build_hte_result)
    monkeypatch.setattr(module, "build_success_report", build_success_report)
    monkeypatch.setattr(module, "wrap_causal_output", wrap_causal_output)
    return state, events, records


@pytest.mark.parametrize("feature_method", ["tree_based", "shap"])
def test_forest_dr_v11_thread_limit_covers_the_complete_producer(monkeypatch, feature_method):
    state, events, records = _install_forest_dr_pipeline_fakes(monkeypatch)

    result = ForestDRLearnerEstimatorV11.pure_step(
        _make_hte_data(n=8), {"feature_importance_method": feature_method}
    )

    assert records["estimator_params"]["n_jobs"] == 1
    assert result["hte_result"].econml_params["n_jobs"] == 1
    assert result["report"].method_params["n_jobs"] == 1
    if feature_method == "shap":
        assert result["hte_result"].feature_importances[0].method == "shap"
        assert records["shap_args"] == (["x0", "x1", "x2", "x3"], 8)
    stages = [name for name, _active in events if name not in {"limit_enter", "limit_exit"}]
    assert stages == [
        "prepare_input",
        "construct",
        "fit",
        f"extract:{feature_method}",
        "effect",
        "effect_interval",
        "effect_inference",
        "ate_inference",
        *(["shap_values"] if feature_method == "shap" else []),
        "subgroups",
        "hte_result",
        "report",
        "wrap",
    ]
    assert all(active for name, active in events if name not in {"limit_enter", "limit_exit"})
    assert events[-1] == ("limit_exit", True)
    assert state["active"] is False


@pytest.mark.parametrize("fail_at", ["fit", "extract"])
def test_forest_dr_v11_thread_limit_unwinds_on_producer_failure(monkeypatch, fail_at):
    state, events, _records = _install_forest_dr_pipeline_fakes(monkeypatch, fail_at=fail_at)

    with pytest.raises(RuntimeError, match="failure"):
        ForestDRLearnerEstimatorV11.pure_step(_make_hte_data(n=8), {})

    assert events[-1] == ("limit_exit", True)
    assert state["active"] is False


def test_forest_dr_v10_preserves_unbounded_legacy_execution_contract(monkeypatch):
    state, events, records = _install_forest_dr_pipeline_fakes(monkeypatch)

    result = ForestDRLearnerEstimator.pure_step(_make_hte_data(n=8), {})

    assert state["active"] is False
    assert all(name not in {"limit_enter", "limit_exit"} for name, _active in events)
    assert records["estimator_params"].get("n_jobs") is None
    assert "n_jobs" not in result["hte_result"].econml_params
    assert "n_jobs" not in result["report"].method_params
    assert not any(active for _name, active in events)
