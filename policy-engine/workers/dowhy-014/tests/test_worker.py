"""Real pinned backend oracles; synthetic properties carry no real-data authority."""

from __future__ import annotations

import json
import sys

import numpy as np
import pytest
import statsmodels.api as sm

from protocol import REQUEST_SCHEMA, decode, digest, validate_request
from worker import execute, interval, linear_ate


def request(seed=19, n=500):
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


def bind(value):
    value.pop("request_id", None)
    value.pop("request_sha256", None)
    value["request_id"] = digest(value)
    value["request_sha256"] = digest(value)
    return value


def oracle(value):
    data = np.asarray(value["basis"]["rows"])
    return sm.OLS(data[:, 1], sm.add_constant(data[:, [0, 2]])).fit()


def test_actual_dowhy_identification_estimation_matches_independent_statsmodels():
    value = request()
    response = execute(value)
    result = response["result"]
    expected = oracle(value)
    assert result["point"] == pytest.approx(expected.params[1], abs=1e-12)
    assert result["interval"] == pytest.approx(expected.conf_int(alpha=0.05)[1], abs=1e-12)
    assert result["standard_error"] == pytest.approx(expected.bse[1], abs=1e-12)
    assert result["effective_confidence_level"] == 0.95
    assert result["adjustment_set"] == ["X"]
    assert (
        result["estimator_class"]
        == "dowhy.causal_estimators.linear_regression_estimator.LinearRegressionEstimator"
    )
    assert response["authority"] == "candidate_computation_only"
    assert response["versions"]["dowhy"] == "0.14"


def test_known_gaussian_dgp_nominal_95_coverage_over_independent_replicates():
    covered = 0
    # Independent IID draws from a full-rank correctly specified homoscedastic DGP.
    for seed in range(1000, 1200):
        value = request(seed, n=180)
        actual = linear_ate(value)
        expected = oracle(value)
        assert actual["interval"] == pytest.approx(expected.conf_int(alpha=0.05)[1], abs=1e-11)
        covered += actual["interval"][0] <= 2 <= actual["interval"][1]
    # Predeclared conservative binomial band for 200 independent 95% intervals.
    assert 180 <= covered <= 199, covered
    print(
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
    )


@pytest.mark.parametrize(
    "value", [[1, 2, 3], [[1, 2], [3, 4]], [3, 1], [float("nan"), 2], [1, float("inf")]]
)
def test_intervals_are_rejected_without_flattening_selection_or_repair(value):
    with pytest.raises(ValueError):
        interval(value)


@pytest.mark.parametrize("value", [[1, 2], [[1, 2]], None])
def test_exact_supported_interval_shapes_and_legitimate_point_only(value):
    assert interval(value) == (None if value is None else [1.0, 2.0])


def test_real_estimator_point_only_is_retained_without_synthesizing_ci(monkeypatch):
    from dowhy import CausalModel

    original = CausalModel.estimate_effect

    def point_only(self, *args, **kwargs):
        actual = original(self, *args, **kwargs)
        actual.get_confidence_intervals = lambda **kwargs: None
        actual.get_standard_error = lambda: None
        return actual

    monkeypatch.setattr(CausalModel, "estimate_effect", point_only)
    result = linear_ate(request())
    assert result["point"] == pytest.approx(2.016134929864521)
    assert result["interval"] is None and result["effective_confidence_level"] is None
    assert result["standard_error"] is None and result["inference_status"] == "point_only"


def test_actual_backend_confidence_level_divergence_is_refused(monkeypatch):
    from dowhy import CausalModel

    original = CausalModel.estimate_effect

    def wrong_level(self, *args, **kwargs):
        kwargs["method_params"] = {"confidence_level": 0.9}
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CausalModel, "estimate_effect", wrong_level)
    with pytest.raises(ValueError, match="effective estimator confidence level"):
        linear_ate(request())


def test_real_graph_identification_cannot_relabel_a_different_adjustment():
    value = request()
    value["parameters"]["adjustment_set"] = []
    with pytest.raises(ValueError, match="adjustment set mismatch"):
        linear_ate(value)


def test_actual_unblocked_latent_backdoor_does_not_identify_ate():
    value = request()
    value["graph"]["payload"] = "digraph { U -> A; U -> Y; A -> Y; X; }"
    value["parameters"]["adjustment_set"] = []
    with pytest.raises(ValueError, match="not identified"):
        linear_ate(value)


def test_hash_alignment_duplicate_json_and_row_id_negatives():
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


def gcm_request():
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


def test_genuine_gcm_assignment_fit_residual_rows_and_every_bootstrap_refit():
    from dowhy.gcm.fitting_sampling import fit as installed_fit

    value = gcm_request()
    calls = []

    def observe(frame, event, arg):
        if event == "call" and frame.f_code is installed_fit.__code__:
            calls.append(frame.f_code.co_filename)

    assert "site-packages/dowhy/gcm/fitting_sampling.py" in installed_fit.__code__.co_filename
    sys.setprofile(observe)
    try:
        actual = execute(value)["result"]
    finally:
        sys.setprofile(None)
    assert len(calls) == 4, "Actual installed gcm.fit must execute for base and every bootstrap"
    rows = np.asarray(value["basis"]["rows"])
    models = [actual, *actual["bootstrap_models"]]
    index_sets = [list(range(len(rows))), *value["parameters"]["bootstrap_indices"]]
    for fitted, indices in zip(models, index_sets, strict=True):
        selected = rows[indices]
        expected = sm.OLS(selected[:, 1], sm.add_constant(selected[:, 0])).fit()
        assert fitted["fit_function"] == "dowhy.gcm.fit"
        assert fitted["row_ids"] == [value["basis"]["row_ids"][i] for i in indices]
        assert fitted["mechanisms"]["X"]["observed_samples"] == selected[:, 0].tolist()
        child = fitted["mechanisms"]["Y"]
        assert child["intercept"] == pytest.approx(expected.params[0])
        assert child["coefficients"] == {"X": pytest.approx(expected.params[1])}
        assert child["residual_samples"] == pytest.approx(expected.resid, abs=1e-12)
    assert len({m["mechanisms"]["Y"]["coefficients"]["X"] for m in models}) == 4


def test_gcm_fit_removal_keeps_imports_and_version_but_cannot_export_fitted_mechanisms(monkeypatch):
    from dowhy import gcm

    monkeypatch.setattr(gcm, "fit", lambda *args, **kwargs: None)
    assert callable(gcm.fit)
    with pytest.raises((AttributeError, ValueError, TypeError)):
        execute(gcm_request())
