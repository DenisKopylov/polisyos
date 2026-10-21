from __future__ import annotations

from collections.abc import Callable
from statistics import NormalDist
from types import SimpleNamespace

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal._econml_adapter import (
    _extract_ate_standard_error,
    build_hte_data,
    extract_cate_from_estimator,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData


class _DummyEffectInference:
    def __init__(self, stderr: np.ndarray | None) -> None:
        self.stderr = stderr


class _DummyPopulationSummary:
    def __init__(self, lo: float, hi: float, stderr: float) -> None:
        self._lo = float(lo)
        self._hi = float(hi)
        self.stderr_mean = float(stderr)
        self.pvalue_value: float | None = None

    def conf_int_mean(self, *, alpha: float | None = None) -> tuple[float, float]:
        return self._lo, self._hi

    def pvalue(self, *, value: float | None = None) -> float:
        self.pvalue_value = value
        return 0.12


class _DummyEstimator:
    def __init__(self, cate: np.ndarray, std_point: np.ndarray) -> None:
        self._cate = np.asarray(cate, dtype=float)
        self._std_point = np.asarray(std_point, dtype=float)

    def effect(self, x: np.ndarray) -> np.ndarray:
        return self._cate

    def effect_interval(self, x: np.ndarray, *, alpha: float) -> tuple[np.ndarray, np.ndarray]:
        critical_value = NormalDist().inv_cdf(1.0 - alpha / 2.0)
        half_width = critical_value * self._std_point
        return self._cate - half_width, self._cate + half_width

    def effect_inference(self, x: np.ndarray) -> _DummyEffectInference:
        return _DummyEffectInference(self._std_point)

    def ate_inference(self, x: np.ndarray) -> object:
        raise NotImplementedError("ate inference unavailable")


class _DummyBootstrapSummaryEstimator(_DummyEstimator):
    def __init__(self, cate: np.ndarray, std_point: np.ndarray) -> None:
        super().__init__(cate, std_point)
        self.summary = _DummyPopulationSummary(0.25, 0.75, 0.08)

    def ate_inference(self, x: np.ndarray) -> object:
        return self.summary


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
    assert any("normal-Wald fallback" in warning for warning in extracted["warnings"])
    assert extracted["cate_std_values"] == pytest.approx([0.1] * 50)
    assert extracted["cate_ci_lower_values"] == []
    assert extracted["cate_ci_upper_values"] == []


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
    assert extracted["ate_p_value"] == 0.12


class _InferenceShapeEstimator(_DummyEstimator):
    def __init__(self, cate: np.ndarray, stderr: object, *, interval: object = None) -> None:
        super().__init__(cate, np.full(cate.size, 0.1, dtype=float))
        self._stderr = stderr
        self._interval = interval

    def effect_interval(self, x: np.ndarray, *, alpha: float) -> object:
        if self._interval is None:
            raise NotImplementedError("interval unavailable")
        return self._interval

    def effect_inference(self, x: np.ndarray) -> object:
        # Deliberately include the ATE-only std_point trap: it must never become row SE.
        return SimpleNamespace(stderr=self._stderr, std_point=np.full(x.shape[0], 9.0))


def test_extract_uses_pointwise_stderr_and_preserves_singleton_axes() -> None:
    x = np.ones((4, 2), dtype=float)
    stderr = np.array([0.1, 0.2, 0.3, 0.4], dtype=float).reshape(4, 1, 1)
    lower = np.array([0.0, 0.1, 0.2, 0.3], dtype=float).reshape(4, 1)
    upper = np.array([0.4, 0.5, 0.6, 0.7], dtype=float).reshape(4, 1)

    extracted = extract_cate_from_estimator(
        _InferenceShapeEstimator(np.array([0.2, 0.3, 0.4, 0.5]), stderr, interval=(lower, upper)),
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(13),
    )

    assert extracted["cate_std_values"] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert extracted["cate_ci_lower_values"] == pytest.approx([0.0, 0.1, 0.2, 0.3])
    assert extracted["cate_ci_upper_values"] == pytest.approx([0.4, 0.5, 0.6, 0.7])


@pytest.mark.parametrize(
    "stderr",
    [
        np.array([0.1, np.nan, 0.3, 0.4]),
        np.array([0.1, 0.2, 0.3]),
        np.ones((4, 2)),
        np.array([0.1, 0.2, -0.3, 0.4]),
    ],
)
def test_extract_rejects_present_malformed_pointwise_stderr(stderr: np.ndarray) -> None:
    x = np.ones((4, 2), dtype=float)
    with pytest.raises(ValueError, match="effect_inference.stderr"):
        extract_cate_from_estimator(
            _InferenceShapeEstimator(np.linspace(0.2, 0.5, 4), stderr),
            x,
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="tree_based",
            rng=np.random.default_rng(17),
        )


def test_extract_preserves_native_ate_interval_when_pvalue_is_callable() -> None:
    x = np.ones((40, 2), dtype=float)
    cate = np.linspace(0.1, 0.9, 40)
    estimator = _DummyBootstrapSummaryEstimator(cate, np.full(40, 0.05))
    native = estimator.summary

    extracted = extract_cate_from_estimator(
        estimator,
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(19),
    )

    assert extracted["ate_ci_lower"] == 0.25
    assert extracted["ate_ci_upper"] == 0.75
    assert extracted["ate_p_value"] == 0.12
    assert native.pvalue_value == 0


class _ThrowingPValuePropertySummary(_DummyPopulationSummary):
    @property
    def pvalue(self) -> float:
        raise RuntimeError("property diagnostic must not erase native CI")


class _ThrowingPValueMethodSummary(_DummyPopulationSummary):
    def pvalue(self, *, value: float | None = None) -> float:
        raise RuntimeError("method diagnostic must not erase native CI")


class _InvalidPValueSummary(_DummyPopulationSummary):
    def __init__(self, value: float) -> None:
        super().__init__(0.25, 0.75, 0.08)
        self._value = value

    def pvalue(self, *, value: float | None = None) -> float:
        return self._value


class _ThrowingPValueEstimator(_DummyEstimator):
    def __init__(self, cate: np.ndarray, std_point: np.ndarray, summary: object) -> None:
        super().__init__(cate, std_point)
        self.summary = summary

    def ate_inference(self, x: np.ndarray) -> object:
        return self.summary


@pytest.mark.parametrize(
    ("summary_type", "expected_warning"),
    [
        (_ThrowingPValuePropertySummary, "member=pvalue; phase=access; exception=RuntimeError"),
        (_ThrowingPValueMethodSummary, "member=pvalue; phase=invoke; exception=RuntimeError"),
    ],
)
def test_optional_pvalue_failure_preserves_native_ate_interval(
    summary_type: type[_DummyPopulationSummary],
    expected_warning: str,
) -> None:
    x = np.ones((40, 2), dtype=float)
    cate = np.linspace(0.1, 0.9, 40)
    estimator = _ThrowingPValueEstimator(
        cate,
        np.full(40, 0.05),
        summary_type(0.25, 0.75, 0.08),
    )

    extracted = extract_cate_from_estimator(
        estimator,
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(29),
    )

    assert extracted["ate_ci_lower"] == 0.25
    assert extracted["ate_ci_upper"] == 0.75
    assert extracted["ate_p_value"] is None
    assert any(expected_warning in warning for warning in extracted["warnings"])
    assert all("private detail" not in warning for warning in extracted["warnings"])


@pytest.mark.parametrize("pvalue", [float("nan"), -0.01, 1.01])
def test_present_malformed_optional_pvalue_still_fails_closed(pvalue: float) -> None:
    x = np.ones((40, 2), dtype=float)
    cate = np.linspace(0.1, 0.9, 40)
    estimator = _ThrowingPValueEstimator(
        cate,
        np.full(40, 0.05),
        _InvalidPValueSummary(pvalue),
    )

    with pytest.raises(ValueError, match="ate_inference.pvalue"):
        extract_cate_from_estimator(
            estimator,
            x,
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="tree_based",
            rng=np.random.default_rng(31),
        )


class _GenericATEOptionalSummary:
    """Exercise the existing ATE summary member protocol without a backend fit."""

    def __init__(self) -> None:
        self.alpha_seen: float | None = None
        self.pvalue_argument: float | None = None

    def conf_int_mean(self, *, alpha: float | None = None) -> tuple[float, float]:
        self.alpha_seen = alpha
        return 0.25, 0.75

    def conf_int(self, *, alpha: float | None = None) -> tuple[float, float]:
        self.alpha_seen = alpha
        return 0.24, 0.76

    @property
    def stderr_mean(self) -> None:
        return None

    @property
    def mean_pred_stderr(self) -> float:
        return 0.08

    def pvalue(self, *, value: float | None = None) -> float:
        self.pvalue_argument = value
        return 0.12


class _GenericATEOptionalSummaryEstimator(_DummyEstimator):
    def __init__(self, summary: object) -> None:
        super().__init__(np.full(40, 0.5), np.full(40, 0.05))
        self.summary = summary

    def ate_inference(self, x: np.ndarray) -> object:
        return self.summary


def _optional_summary_failure(
    exception_type: type[Exception],
) -> Callable[..., None]:
    def raise_failure(self: object, *args: object, **kwargs: object) -> None:
        raise exception_type("private detail must not be included in the warning")

    return raise_failure


def _optional_summary_failure_type(
    member_name: str,
    access_shape: str,
    exception_type: type[Exception] = RuntimeError,
) -> type:
    namespace: dict[str, object] = {"__module__": __name__}
    if member_name == "conf_int":
        namespace["conf_int_mean"] = lambda self, *, alpha=None: None
    failure = _optional_summary_failure(exception_type)
    if access_shape == "property":
        namespace[member_name] = property(failure)
    else:
        namespace[member_name] = failure
    return type(f"_Failing_{member_name}_{access_shape}", (_GenericATEOptionalSummary,), namespace)


_OPTIONAL_SUMMARY_FAILURE_CASES = [
    pytest.param("pvalue", "property", RuntimeError, id="pvalue-getter"),
    pytest.param("pvalue", "method", RuntimeError, id="pvalue-call"),
    pytest.param("stderr_mean", "property", RuntimeError, id="stderr-mean-getter-with-alias"),
    pytest.param("stderr_mean", "method", RuntimeError, id="stderr-mean-call-with-alias"),
    pytest.param(
        "stderr_mean", "property", AttributeError, id="econml-stderr-mean-attributeerror-descriptor"
    ),
    pytest.param("mean_pred_stderr", "property", RuntimeError, id="mean-pred-stderr-getter"),
    pytest.param("mean_pred_stderr", "method", RuntimeError, id="mean-pred-stderr-call"),
    pytest.param("conf_int_mean", "method", RuntimeError, id="conf-int-mean-call-with-alias"),
    pytest.param("conf_int", "method", RuntimeError, id="conf-int-call-after-primary-absence"),
]


@pytest.mark.parametrize(
    ("member_name", "access_shape", "exception_type"), _OPTIONAL_SUMMARY_FAILURE_CASES
)
def test_optional_ate_summary_member_failures_are_scoped_and_warned(
    member_name: str,
    access_shape: str,
    exception_type: type[Exception],
) -> None:
    summary = _optional_summary_failure_type(member_name, access_shape, exception_type)()
    estimator = _GenericATEOptionalSummaryEstimator(summary)
    extracted = extract_cate_from_estimator(
        estimator,
        np.ones((40, 2), dtype=float),
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(37),
    )

    expected_phase = "access" if access_shape == "property" else "invoke"
    expected_warning = (
        "ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE: "
        f"member={member_name}; phase={expected_phase}; exception={exception_type.__name__}; value omitted"
    )
    assert any(expected_warning in warning for warning in extracted["warnings"])
    assert all("private detail" not in warning for warning in extracted["warnings"])
    assert np.isfinite(extracted["ate_ci_lower"])
    assert np.isfinite(extracted["ate_ci_upper"])
    if member_name == "conf_int_mean":
        assert extracted["ate_ci_lower"] == 0.24
        assert extracted["ate_ci_upper"] == 0.76
    elif member_name == "conf_int":
        assert extracted["ate_ci_lower"] == pytest.approx(0.5 - 1.96 * 0.08)
        assert extracted["ate_ci_upper"] == pytest.approx(0.5 + 1.96 * 0.08)
        assert any("normal-Wald fallback" in warning for warning in extracted["warnings"])
    else:
        assert extracted["ate_ci_lower"] == 0.25
        assert extracted["ate_ci_upper"] == 0.75
    if member_name == "pvalue":
        assert extracted["ate_p_value"] is None
    elif member_name in {"stderr_mean", "mean_pred_stderr"}:
        assert extracted["ate_p_value"] == 0.12
    if member_name == "pvalue":
        assert summary.mean_pred_stderr == 0.08
    if member_name == "conf_int_mean":
        assert summary.alpha_seen == 0.05


class _AttributeErrorMeanSEWithObservedAlias(_GenericATEOptionalSummary):
    def __init__(self) -> None:
        super().__init__()
        self.mean_pred_stderr_reads = 0

    @property
    def stderr_mean(self) -> float:
        raise AttributeError("EconML has no pred_stderr for point estimates")

    @property
    def mean_pred_stderr(self) -> float:
        self.mean_pred_stderr_reads += 1
        return 0.08


def test_econml_stderr_descriptor_attribute_error_consumes_and_returns_se_alias() -> None:
    summary = _AttributeErrorMeanSEWithObservedAlias()
    warnings: list[str] = []

    standard_error = _extract_ate_standard_error(summary, warnings=warnings)

    assert standard_error == pytest.approx(0.08)
    assert summary.mean_pred_stderr_reads == 1
    assert warnings == [
        "ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE: "
        "member=stderr_mean; phase=access; exception=AttributeError; value omitted"
    ]


def test_missing_optional_ate_summary_members_remain_silent_and_limited() -> None:
    extracted = extract_cate_from_estimator(
        _GenericATEOptionalSummaryEstimator(SimpleNamespace()),
        np.ones((40, 2), dtype=float),
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(41),
    )

    assert np.isfinite(extracted["ate_ci_lower"])
    assert np.isfinite(extracted["ate_ci_upper"])
    assert extracted["ate_p_value"] is None
    assert not any(
        "ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE" in warning for warning in extracted["warnings"]
    )


def test_mean_se_failure_with_absent_alias_keeps_native_interval() -> None:
    failing_summary = _optional_summary_failure_type("stderr_mean", "property")
    summary_type = type(
        "_FailingMeanSEWithoutAlias",
        (failing_summary,),
        {"mean_pred_stderr": property(lambda self: None)},
    )
    extracted = extract_cate_from_estimator(
        _GenericATEOptionalSummaryEstimator(summary_type()),
        np.ones((40, 2), dtype=float),
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(42),
    )

    assert extracted["ate_ci_lower"] == 0.25
    assert extracted["ate_ci_upper"] == 0.75
    assert any(
        "ATE_OPTIONAL_SUMMARY_MEMBER_UNAVAILABLE: "
        "member=stderr_mean; phase=access; exception=RuntimeError; value omitted" in warning
        for warning in extracted["warnings"]
    )


class _MalformedATEOptionalSummary(_GenericATEOptionalSummary):
    def __init__(self, *, stderr_mean: object = None, interval: object = None) -> None:
        super().__init__()
        self._malformed_stderr_mean = stderr_mean
        self._malformed_interval = interval

    @property
    def stderr_mean(self) -> object:
        return self._malformed_stderr_mean

    @property
    def mean_pred_stderr(self) -> None:
        return None

    def conf_int_mean(self, *, alpha: float | None = None) -> object:
        return self._malformed_interval


@pytest.mark.parametrize(
    ("stderr_mean", "message"),
    [
        (float("nan"), "must be finite"),
        (-0.01, "nonnegative standard error"),
        ([0.08, 0.09], "exactly one scalar"),
    ],
)
def test_malformed_returned_ate_standard_error_still_fails_closed(
    stderr_mean: object,
    message: str,
) -> None:
    estimator = _GenericATEOptionalSummaryEstimator(
        _MalformedATEOptionalSummary(stderr_mean=stderr_mean, interval=(0.25, 0.75))
    )
    with pytest.raises(ValueError, match=message):
        extract_cate_from_estimator(
            estimator,
            np.ones((40, 2), dtype=float),
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="tree_based",
            rng=np.random.default_rng(43),
        )


@pytest.mark.parametrize(
    ("interval", "message"),
    [
        ((float("nan"), 0.75), "must be finite"),
        ((0.75, 0.25), "reversed confidence interval"),
        ((0.25,), "lower/upper pair"),
    ],
)
def test_malformed_returned_ate_interval_still_fails_closed(
    interval: object,
    message: str,
) -> None:
    estimator = _GenericATEOptionalSummaryEstimator(
        _MalformedATEOptionalSummary(stderr_mean=0.08, interval=interval)
    )
    with pytest.raises(ValueError, match=message):
        extract_cate_from_estimator(
            estimator,
            np.ones((40, 2), dtype=float),
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="tree_based",
            rng=np.random.default_rng(47),
        )


@pytest.mark.parametrize("alpha", [0.01, 0.05, 0.10])
def test_legacy_normal_wald_fallback_remains_fixed_and_unqualified(alpha: float) -> None:
    x = np.ones((50, 2), dtype=float)
    cate = np.linspace(0.2, 0.8, 50)
    std = np.full(50, 0.1, dtype=float)
    extracted = extract_cate_from_estimator(
        _DummyEstimator(cate, std),
        x,
        alpha=alpha,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(23),
    )
    expected_se = np.sqrt((np.var(cate, ddof=1) + np.mean(std**2)) / cate.size)
    half_width = extracted["ate_ci_upper"] - extracted["ate"]
    assert half_width == pytest.approx(1.96 * expected_se)
    assert any("fixed 1.96" in warning for warning in extracted["warnings"])
    assert any("remains unqualified" in warning for warning in extracted["warnings"])


class _NarrowPopulationSummary:
    def __init__(self, ate: float) -> None:
        self.ate = ate
        self.stderr_mean = 0.001
        self.alpha_seen: float | None = None

    def conf_int_mean(self, *, alpha: float | None = None) -> tuple[float, float]:
        self.alpha_seen = alpha
        return self.ate - 0.001, self.ate + 0.001


class _NarrowNativeIntervalEstimator(_DummyEstimator):
    def ate_inference(self, x: np.ndarray) -> object:
        self.summary = _NarrowPopulationSummary(float(np.mean(self._cate)))
        return self.summary


@pytest.mark.parametrize("alpha", [0.01, 0.05, 0.10])
def test_legacy_guarded_widening_remains_fixed_1_96_but_native_ci_receives_alpha(
    alpha: float,
) -> None:
    x = np.ones((50, 2), dtype=float)
    cate = np.linspace(0.2, 0.8, 50)
    std = np.full(50, 0.1, dtype=float)
    estimator = _NarrowNativeIntervalEstimator(cate, std)

    extracted = extract_cate_from_estimator(
        estimator,
        x,
        alpha=alpha,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(47),
    )

    expected_se = np.sqrt((np.var(cate, ddof=1) + np.mean(std**2)) / cate.size)
    half_width = extracted["ate_ci_upper"] - extracted["ate"]
    assert estimator.summary.alpha_seen == alpha
    assert half_width == pytest.approx(1.96 * expected_se)
    assert any("fixed 1.96" in warning for warning in extracted["warnings"])
    assert any("remains unqualified" in warning for warning in extracted["warnings"])


def test_extract_preserves_unknown_optional_vectors_without_std_point_substitution() -> None:
    x = np.ones((4, 2), dtype=float)
    extracted = extract_cate_from_estimator(
        _InferenceShapeEstimator(np.linspace(0.2, 0.5, 4), None),
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="tree_based",
        rng=np.random.default_rng(29),
    )

    assert extracted["cate_std_values"] == []
    assert extracted["cate_ci_lower_values"] == []
    assert extracted["cate_ci_upper_values"] == []
    assert any("per-row standard errors" in warning for warning in extracted["warnings"])
    assert any("per-row CIs omitted" in warning for warning in extracted["warnings"])


class _MalformedEffectEstimator(_DummyEstimator):
    def effect(self, x: np.ndarray) -> np.ndarray:
        return np.ones((x.shape[0], 2), dtype=float)


def test_extract_rejects_effect_output_with_multiple_outcomes() -> None:
    x = np.ones((4, 2), dtype=float)
    with pytest.raises(ValueError, match="effect must be one value per observation"):
        extract_cate_from_estimator(
            _MalformedEffectEstimator(np.linspace(0.2, 0.5, 4), np.full(4, 0.1)),
            x,
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="tree_based",
            rng=np.random.default_rng(31),
        )


def test_ate_standard_error_does_not_use_pointwise_dispersion_as_mean_se() -> None:
    inference = SimpleNamespace(std_point=100.0, stderr_point=90.0)
    warnings: list[str] = []

    assert _extract_ate_standard_error(inference, warnings=warnings) is None
    assert _extract_ate_standard_error(SimpleNamespace(stderr_mean=0.08), warnings=warnings) == 0.08


class _NativeShapEstimator(_DummyEstimator):
    feature_importances_ = np.array([0.25, 0.75], dtype=float)

    def __init__(self, cate: np.ndarray, explanations: object) -> None:
        super().__init__(cate, np.full(cate.size, 0.1, dtype=float))
        self._explanations = explanations

    def shap_values(
        self,
        x: np.ndarray,
        *,
        feature_names: list[str],
        background_samples: int,
    ) -> object:
        assert feature_names == ["x0", "x1"]
        assert background_samples == x.shape[0]
        return self._explanations


class _MissingShapEstimator(_DummyEstimator):
    feature_importances_ = np.array([0.25, 0.75], dtype=float)


@pytest.mark.parametrize(
    ("explanations", "message"),
    [
        (
            {
                "Y0": {"T0": SimpleNamespace(values=np.ones((4, 2)))},
                "Y1": {},
            },
            "one outcome",
        ),
        (
            {
                "Y0": {
                    "T0": SimpleNamespace(values=np.ones((4, 2))),
                    "T1": SimpleNamespace(values=np.ones((4, 2))),
                }
            },
            "one treatment",
        ),
        ({"Y0": {"T0": SimpleNamespace()}}, "missing values"),
        ({"Y0": {"T0": SimpleNamespace(values=np.ones((4, 1)))}}, "match evaluation shape"),
        ({"Y0": {"T0": SimpleNamespace(values=np.full((4, 2), np.nan))}}, "must be finite"),
    ],
)
def test_native_shap_rejects_ambiguous_or_misaligned_results(
    explanations: object,
    message: str,
) -> None:
    x = np.ones((4, 2), dtype=float)

    with pytest.raises(ValueError, match=message):
        extract_cate_from_estimator(
            _NativeShapEstimator(np.linspace(0.2, 0.5, 4), explanations),
            x,
            alpha=0.05,
            feature_names=["x0", "x1"],
            feature_importance_method="shap",
            rng=np.random.default_rng(37),
        )


class _FailingShapEstimator(_NativeShapEstimator):
    def shap_values(
        self,
        x: np.ndarray,
        *,
        feature_names: list[str],
        background_samples: int,
    ) -> object:
        raise RuntimeError("backend unavailable")


def test_native_shap_failure_is_labeled_as_tree_based_fallback() -> None:
    x = np.ones((4, 2), dtype=float)
    estimator = _FailingShapEstimator(np.linspace(0.2, 0.5, 4), {})

    extracted = extract_cate_from_estimator(
        estimator,
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="shap",
        rng=np.random.default_rng(41),
    )

    assert {item["method"] for item in extracted["feature_importances"]} == {"tree_based"}
    assert any(
        "Estimator-native SHAP failed (RuntimeError)" in warning
        for warning in extracted["warnings"]
    )


def test_missing_native_shap_is_labeled_as_tree_based_fallback() -> None:
    x = np.ones((4, 2), dtype=float)
    estimator = _MissingShapEstimator(np.linspace(0.2, 0.5, 4), np.full(4, 0.1))

    extracted = extract_cate_from_estimator(
        estimator,
        x,
        alpha=0.05,
        feature_names=["x0", "x1"],
        feature_importance_method="shap",
        rng=np.random.default_rng(43),
    )

    assert {item["method"] for item in extracted["feature_importances"]} == {"tree_based"}
    assert any("does not expose native shap_values" in warning for warning in extracted["warnings"])
