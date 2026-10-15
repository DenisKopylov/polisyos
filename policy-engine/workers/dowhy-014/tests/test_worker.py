"""Real pinned backend oracles; synthetic properties carry no real-data authority."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import FrameType

import numpy as np
import pytest
import statsmodels.api as sm
from protocol import REQUEST_SCHEMA, decode, digest, validate_request
from worker import execute, interval, linear_ate, scalar


def request(seed: int = 19, n: int = 500) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    a = rng.binomial(1, 1 / (1 + np.exp(-x)))
    y = 2 * a + 1.5 * x + rng.normal(size=n)
    rows = np.column_stack([a, y, x]).tolist()
    ids = [f"synthetic:{i}" for i in range(n)]
    graph = "digraph { X -> A; X -> Y; A -> Y; }"
    result = {
        "schema": REQUEST_SCHEMA,
        "profile": "dowhy-014",
        "operation": "linear_ate",
        "source": {"artifact_ref": {"artifact_id": "synthetic:source"}, "content_sha256": "0" * 64},
        "basis": {
            "columns": ["A", "Y", "X"],
            "rows": rows,
            "row_ids": ids,
            "data_sha256": digest({"columns": ["A", "Y", "X"], "rows": rows}),
            "row_sha256": digest(ids),
        },
        "graph": {"representation": "dot", "payload": graph, "sha256": digest(graph)},
        "parameters": {
            "treatment": "A",
            "outcome": "Y",
            "adjustment_set": ["X"],
            "estimand_type": "nonparametric-ate",
            "method_name": "backdoor.linear_regression",
            "control_value": 0,
            "treatment_value": 1,
            "target_units": "ate",
            "confidence_level": 0.95,
        },
        "seed": seed,
    }
    return bind(result)


def bind(value: dict[str, Any]) -> dict[str, Any]:
    value.pop("request_id", None)
    value.pop("request_sha256", None)
    value["request_id"] = digest(value)
    value["request_sha256"] = digest(value)
    return value


def oracle(value: dict[str, Any]) -> sm.regression.linear_model.RegressionResultsWrapper:
    data = np.asarray(value["basis"]["rows"])
    return sm.OLS(data[:, 1], sm.add_constant(data[:, [0, 2]])).fit()


def test_actual_dowhy_identification_estimation_matches_independent_statsmodels() -> None:
    value = request()
    response = execute(value)
    result = response["result"]
    expected = oracle(value)
    np.testing.assert_equal(result["point"] == pytest.approx(expected.params[1], abs=1e-12), True)
    np.testing.assert_equal(
        result["interval"] == pytest.approx(expected.conf_int(alpha=0.05)[1], abs=1e-12), True
    )
    np.testing.assert_equal(
        result["standard_error"] == pytest.approx(expected.bse[1], abs=1e-12), True
    )
    np.testing.assert_equal(result["effective_confidence_level"], 0.95)
    np.testing.assert_equal(result["adjustment_set"], ["X"])
    np.testing.assert_equal(
        result["estimator_class"],
        "dowhy.causal_estimators.linear_regression_estimator.LinearRegressionEstimator",
    )
    np.testing.assert_equal(response["authority"], "candidate_computation_only")
    np.testing.assert_equal(response["versions"]["dowhy"], "0.14")


def test_known_gaussian_dgp_nominal_95_coverage_over_independent_replicates() -> None:
    covered = 0
    # Independent IID draws from a full-rank correctly specified homoscedastic DGP.
    for seed in range(1000, 1200):
        value = request(seed, n=180)
        actual = linear_ate(value)
        expected = oracle(value)
        np.testing.assert_equal(
            actual["interval"] == pytest.approx(expected.conf_int(alpha=0.05)[1], abs=1e-11),
            True,
        )
        covered += actual["interval"][0] <= 2 <= actual["interval"][1]
    # Predeclared conservative binomial band for 200 independent 95% intervals.
    np.testing.assert_equal(180 <= covered <= 199, True, str(covered))
    sys.stdout.write(
        json.dumps(
            {
                "replicates": 200,
                "covered": int(covered),
                "truth": 2,
                "nominal_level": 0.95,
                "allowed_covered": [180, 199],
                "scope": "known IID homoscedastic Gaussian synthetic DGP",
            }
        )
        + "\n"
    )


@pytest.mark.parametrize(
    ("value", "error_message"),
    [
        ([1, 2, 3], "unsupported confidence interval shape/value"),
        ([[1, 2], [3, 4]], "unsupported confidence interval shape/value"),
        ([3, 1], "reversed confidence interval"),
        ([float("nan"), 2], "finite numeric primitives required"),
        ([1, float("inf")], "finite numeric primitives required"),
    ],
)
def test_intervals_are_rejected_without_flattening_selection_or_repair(
    value: object, error_message: str
) -> None:
    with pytest.raises(ValueError, match=error_message):
        interval(value)


@pytest.mark.parametrize("value", [[1, 2], [[1, 2]], None])
def test_exact_supported_interval_shapes_and_legitimate_point_only(value: object) -> None:
    np.testing.assert_equal(interval(value), None if value is None else [1.0, 2.0])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("interval", ["1.0", "3.0"]),
        ("interval", [True, 3.0]),
        ("value", "2.0"),
        ("value", True),
        ("value", 10**1000),
        ("standard_error", "0.1"),
        ("standard_error", False),
    ],
)
def test_actual_backend_numeric_primitives_are_not_coerced(
    monkeypatch: pytest.MonkeyPatch, field: str, value: object
) -> None:
    from dowhy import CausalModel

    original = CausalModel.estimate_effect
    calls = []

    def malformed(self: object, *args: object, **kwargs: object) -> object:
        actual = original(self, *args, **kwargs)
        calls.append(type(actual.estimator).__module__)
        if field == "interval":
            actual.get_confidence_intervals = lambda **kwargs: value
        elif field == "standard_error":
            actual.get_standard_error = lambda: value
        else:
            actual.value = value
        return actual

    monkeypatch.setattr(CausalModel, "estimate_effect", malformed)
    with pytest.raises(ValueError, match="numeric primitives"):
        linear_ate(request())
    np.testing.assert_equal(calls, ["dowhy.causal_estimators.linear_regression_estimator"])


def test_actual_numpy_numeric_scalar_and_interval_types_remain_supported() -> None:
    for value in [np.float32(2), np.float64(2), np.int32(2), np.int64(2)]:
        np.testing.assert_equal(scalar(value), 2.0)
    for dtype in [np.float32, np.float64, np.int32, np.int64]:
        np.testing.assert_equal(interval(np.array([1, 3], dtype=dtype)), [1.0, 3.0])
        np.testing.assert_equal(interval(np.array([[1, 3]], dtype=dtype)), [1.0, 3.0])


def test_real_estimator_point_only_is_retained_without_synthesizing_ci(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dowhy import CausalModel

    original = CausalModel.estimate_effect

    def point_only(self: object, *args: object, **kwargs: object) -> object:
        actual = original(self, *args, **kwargs)
        actual.get_confidence_intervals = lambda **kwargs: None
        actual.get_standard_error = lambda: None
        return actual

    monkeypatch.setattr(CausalModel, "estimate_effect", point_only)
    result = linear_ate(request())
    np.testing.assert_equal(result["point"] == pytest.approx(2.016134929864521), True)
    np.testing.assert_equal(result["interval"], None)
    np.testing.assert_equal(result["effective_confidence_level"], None)
    np.testing.assert_equal(result["standard_error"], None)
    np.testing.assert_equal(result["inference_status"], "point_only")


def test_actual_backend_confidence_level_divergence_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dowhy import CausalModel

    original = CausalModel.estimate_effect

    def wrong_level(self: object, *args: object, **kwargs: object) -> object:
        kwargs["method_params"] = {"confidence_level": 0.9}
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CausalModel, "estimate_effect", wrong_level)
    with pytest.raises(ValueError, match="effective estimator confidence level"):
        linear_ate(request())


def test_real_graph_identification_cannot_relabel_a_different_adjustment() -> None:
    value = request()
    value["parameters"]["adjustment_set"] = []
    with pytest.raises(ValueError, match="adjustment set mismatch"):
        linear_ate(value)


def test_actual_unblocked_latent_backdoor_does_not_identify_ate() -> None:
    value = request()
    value["graph"]["payload"] = "digraph { U -> A; U -> Y; A -> Y; X; }"
    value["parameters"]["adjustment_set"] = []
    with pytest.raises(ValueError, match="not identified"):
        linear_ate(value)


def test_hash_alignment_duplicate_json_and_row_id_negatives() -> None:
    value = request(n=30)
    value["basis"]["rows"][0][1] += 10
    bind(value)
    with pytest.raises(ValueError, match="data binding"):
        validate_request(value)
    value = request(n=30)
    value["basis"]["row_ids"][1] = value["basis"]["row_ids"][0]
    value["basis"]["row_sha256"] = digest(value["basis"]["row_ids"])
    bind(value)
    with pytest.raises(ValueError, match="row"):
        validate_request(value)
    with pytest.raises(ValueError, match="duplicate"):
        decode(b'{"schema":"a","schema":"b"}')


def gcm_request() -> dict[str, Any]:
    value = request(n=80)
    rows = np.asarray(value["basis"]["rows"])
    # Genuine continuous root with independently generated linear Gaussian outcome.
    x = rows[:, 2]
    y = 2 * x + np.random.default_rng(901).normal(size=len(x))
    value["operation"] = "gcm_fit"
    value["basis"]["columns"] = ["X", "Y"]
    value["basis"]["rows"] = np.column_stack([x, y]).tolist()
    value["basis"]["data_sha256"] = digest({"columns": ["X", "Y"], "rows": value["basis"]["rows"]})
    graph = {"nodes": ["X", "Y"], "edges": [["X", "Y"]]}
    value["graph"] = {"representation": "dag", "payload": graph, "sha256": digest(graph)}
    indices = np.random.default_rng(111).integers(0, len(x), size=(3, len(x))).tolist()
    value["parameters"] = {
        "mechanisms": {"X": "empirical", "Y": "linear_additive_noise"},
        "bootstrap_indices": indices,
    }
    return bind(value)


def test_genuine_gcm_assignment_fit_residual_rows_and_every_bootstrap_refit() -> None:
    from dowhy.gcm.fitting_sampling import fit as installed_fit

    value = gcm_request()
    calls = []

    def observe(frame: FrameType, event: str, arg: object) -> None:
        if event == "call" and frame.f_code is installed_fit.__code__:
            calls.append(frame.f_code.co_filename)

    np.testing.assert_equal(
        "site-packages/dowhy/gcm/fitting_sampling.py" in installed_fit.__code__.co_filename,
        True,
    )
    sys.setprofile(observe)
    try:
        actual = execute(value)["result"]
    finally:
        sys.setprofile(None)
    np.testing.assert_equal(
        len(calls), 4, "Actual installed gcm.fit must execute for base and every bootstrap"
    )
    rows = np.asarray(value["basis"]["rows"])
    models = [actual, *actual["bootstrap_models"]]
    index_sets = [list(range(len(rows))), *value["parameters"]["bootstrap_indices"]]
    for fitted, indices in zip(models, index_sets, strict=True):
        selected = rows[indices]
        expected = sm.OLS(selected[:, 1], sm.add_constant(selected[:, 0])).fit()
        np.testing.assert_equal(fitted["fit_function"], "dowhy.gcm.fit")
        np.testing.assert_equal(fitted["row_ids"], [value["basis"]["row_ids"][i] for i in indices])
        np.testing.assert_equal(
            fitted["mechanisms"]["X"]["observed_samples"], selected[:, 0].tolist()
        )
        child = fitted["mechanisms"]["Y"]
        np.testing.assert_equal(child["intercept"] == pytest.approx(expected.params[0]), True)
        np.testing.assert_equal(
            child["coefficients"] == {"X": pytest.approx(expected.params[1])}, True
        )
        np.testing.assert_equal(
            child["residual_samples"] == pytest.approx(expected.resid, abs=1e-12), True
        )
    np.testing.assert_equal(len({m["mechanisms"]["Y"]["coefficients"]["X"] for m in models}), 4)


def test_gcm_fit_removal_keeps_imports_and_version_but_cannot_export_fitted_mechanisms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dowhy import gcm

    monkeypatch.setattr(gcm, "fit", lambda *args, **kwargs: None)
    np.testing.assert_equal(callable(gcm.fit), True)
    with pytest.raises((AttributeError, ValueError, TypeError)):
        execute(gcm_request())
