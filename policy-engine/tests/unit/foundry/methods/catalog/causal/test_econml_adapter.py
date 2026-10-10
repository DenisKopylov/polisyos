from __future__ import annotations

import numpy as np

from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    build_hte_data,
    extract_cate_from_estimator,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData


class _DummyEffectInference:
    def __init__(self, std_point: np.ndarray) -> None:
        self.std_point = std_point


class _DummyPopulationSummary:
    def __init__(self, lo: float, hi: float, stderr: float) -> None:
        self._lo = float(lo)
        self._hi = float(hi)
        self.stderr_mean = float(stderr)

    def conf_int_mean(self, alpha: float = 0.05) -> tuple[float, float]:
        return self._lo, self._hi


class _DummyEstimator:
    def __init__(self, cate: np.ndarray, std_point: np.ndarray) -> None:
        self._cate = np.asarray(cate, dtype=float)
        self._std_point = np.asarray(std_point, dtype=float)

    def effect(self, x: np.ndarray) -> np.ndarray:
        return self._cate

    def effect_interval(self, x: np.ndarray, *, alpha: float) -> tuple[np.ndarray, np.ndarray]:
        half_width = 1.96 * self._std_point
        return self._cate - half_width, self._cate + half_width

    def effect_inference(self, x: np.ndarray) -> _DummyEffectInference:
        return _DummyEffectInference(self._std_point)

    def ate_inference(self, x: np.ndarray) -> object:
        raise RuntimeError("ate inference unavailable")


class _DummyBootstrapSummaryEstimator(_DummyEstimator):
    def ate_inference(self, x: np.ndarray) -> object:
        return _DummyPopulationSummary(0.25, 0.75, 0.08)


def test_build_hte_data_keeps_w_none_when_confounders_are_absent() -> None:
    data = HTEObservationalData(
        outcome=np.linspace(0.0, 1.0, 40),
        treatment=np.array([0, 1] * 20, dtype=int),
        covariates=np.ones((40, 3), dtype=float),
        feature_names=["x0", "x1", "x2"],
    )

    built = build_hte_data(data)

    assert built.w is None
    assert built.feature_names == ["x0", "x1", "x2"]
    assert built.confounder_names == []


def test_extract_cate_from_estimator_uses_wald_fallback_for_ate_ci() -> None:
    x = np.ones((50, 2), dtype=float)
    cate = np.linspace(0.2, 0.8, 50)
    std = np.full(50, 0.1, dtype=float)

    extracted = extract_cate_from_estimator(
        _DummyEstimator(cate, std),
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(7),
    )

    assert np.isfinite(extracted["ate_ci_lower"])
    assert np.isfinite(extracted["ate_ci_upper"])
    assert extracted["ate_ci_lower"] < extracted["ate"] < extracted["ate_ci_upper"]
    assert any("Wald fallback" in warning for warning in extracted["warnings"])


def test_extract_cate_from_estimator_supports_population_summary_ci() -> None:
    x = np.ones((40, 2), dtype=float)
    cate = np.linspace(0.1, 0.9, 40)
    std = np.full(40, 0.05, dtype=float)

    extracted = extract_cate_from_estimator(
        _DummyBootstrapSummaryEstimator(cate, std),
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(11),
    )

    assert extracted["ate_ci_lower"] == 0.25
    assert extracted["ate_ci_upper"] == 0.75
