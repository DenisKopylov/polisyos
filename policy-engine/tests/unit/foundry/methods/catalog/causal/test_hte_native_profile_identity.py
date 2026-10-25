from __future__ import annotations

import importlib.abc
import importlib.util
import inspect
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_candidate_path = os.environ.get("POLISYOS_HTE_V2_CANDIDATE")
_module_name = "polisyos.foundry.methods.catalog.causal.hte_v2"
if _candidate_path:

    class _CandidateHTEFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
            if fullname == _module_name:
                return importlib.util.spec_from_file_location(fullname, _candidate_path)
            return None

    sys.meta_path.insert(0, _CandidateHTEFinder())
    sys.modules.pop(_module_name, None)

from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorDispatchContext,
    OwnedAttemptAnchorRef,
    OwnedAttemptPhysicalSourceBindingRef,
    OwnedHTERequestContextV1,
)
from polisyos.foundry.methods.catalog.causal import hte_v2
from polisyos.foundry.methods.catalog.causal.hte_v2 import (
    CausalForestEstimatorV2,
    ForestDRLearnerEstimatorV2,
    HTEWriterReadyIntervalV1,
    _capture_facts,
    _native_interval_candidate,
    build_hte_data,
    build_owned_hte_input_capture,
    validate_hte_writer_ready_json,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData


def _data(n_rows: int = 40) -> HTEObservationalData:
    rows = np.arange(n_rows, dtype=float)
    treatment = rows.astype(int) % 2
    return HTEObservationalData(
        outcome=rows / 10.0 + treatment * 0.5,
        treatment=treatment,
        covariates=np.column_stack((rows, rows % 5)),
        confounders=(rows.astype(int) % 7).reshape(-1, 1),
        feature_names=["row", "row_mod_five"],
        confounder_names=["row_mod_seven"],
    )


def _params_for(method: type) -> dict[str, Any]:
    params = {parameter.name: parameter.default for parameter in method.signature.parameters}
    params.update(
        alpha=0.05,
        control_value=0.0,
        treated_value=1.0,
        random_state=7,
        n_jobs=1,
    )
    return params


def _context_for(method: type, params: dict[str, Any], data: HTEObservationalData):
    materialization_binding_ref = OwnedAttemptPhysicalSourceBindingRef(
        artifact_id="sha256:" + "5" * 64,
        kind="foundry.hte.physical_source_materialization_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "6" * 64,
    )
    request = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="population",
        outcome_variable_status="declared",
        outcome_variable_id="outcome",
        treatment_variable_status="declared",
        treatment_variable_id="treatment",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=float(params["alpha"]),
        requested_guarantee_status="declared",
        requested_guarantee="population_sampling_coverage",
        materialization_binding_ref=materialization_binding_ref,
    )
    capture = build_owned_hte_input_capture(
        data,
        source_data_ref={
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "ir.observation_method_input",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        method_class=method,
        method_abi_digest=method.signature.abi_digest(),
        resolved_params=params,
        seed=int(params["random_state"]),
        request_context=request,
    )
    return OwnedAttemptAnchorDispatchContext(
        anchor_ref=OwnedAttemptAnchorRef(
            artifact_id="sha256:" + "3" * 64,
            kind="runtime.owned_attempt_anchor",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "4" * 64,
        ),
        input_capture=capture,
        method_abi_digest=capture.method_abi_digest,
    )


def _facts_for(method: type, data: HTEObservationalData, params: dict[str, Any]):
    context = _context_for(method, params, data)
    return _capture_facts(
        build_hte_data(data),
        data,
        {**params, "__seed__": int(params["random_state"])},
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        method_profile_id=method.owned_hte_profile_id,
        runtime_context=context,
    )


@pytest.mark.parametrize(
    ("method", "expected_class"),
    [
        (CausalForestEstimatorV2, "econml.dml.causal_forest.CausalForestDML"),
        (ForestDRLearnerEstimatorV2, "econml.dr._drlearner.ForestDRLearner"),
    ],
)
def test_real_native_profile_identity_emits_limited_conditional_interval(
    method: type,
    expected_class: str,
) -> None:
    pytest.importorskip("econml")
    if _candidate_path:
        assert Path(hte_v2.__file__).resolve() == Path(_candidate_path).resolve()

    data = _data(40 if method is CausalForestEstimatorV2 else 250)
    params = _params_for(method)
    context = _context_for(method, params, data)
    result = method.pure_step_with_runtime_context(data, params, runtime_context=context)
    writer = validate_hte_writer_ready_json(result["hte_outcome_write_ready"])

    assert isinstance(writer, HTEWriterReadyIntervalV1)
    assert writer.native_capture.estimator_class == expected_class
    assert writer.resource_receipt.estimator_before_class_fqn == expected_class
    assert writer.resource_receipt.estimator_after_class_fqn == expected_class
    assert writer.resource_receipt.execution_status == "returned"
    assert writer.native_capture.method_profile_id == method.owned_hte_profile_id
    assert writer.interval_semantics == "native_mean_confidence_interval"
    assert writer.lower_bound <= writer.point_estimate <= writer.upper_bound
    assert writer.capture.request_target_scope == "population"
    assert writer.capture.requested_guarantee == "population_sampling_coverage"
    assert "target_population_not_established_by_this_fit" in writer.limitations
    assert "causal_interpretation_is_conditional_on_declared_assumptions" in writer.limitations
    assert writer.native_capture.conditional_assumptions == (
        "consistency",
        "conditional_unconfoundedness_given_observed_covariates",
        "overlap_on_selected_covariate_support",
    )


def test_native_profile_gate_uses_actual_class_and_rejects_wrong_class_params_and_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("econml")
    from econml.dml.causal_forest import CausalForestDML
    from econml.dr._drlearner import ForestDRLearner

    data = _data()
    method = CausalForestEstimatorV2
    params = _params_for(method)
    facts = _facts_for(method, data, params)
    selected = build_hte_data(data)
    cate = np.zeros(data.outcome.shape[0], dtype=float)
    config = {
        "n_estimators": 100,
        "max_depth": None,
        "min_samples_leaf": 5,
        "max_samples": 0.5,
        "honest": True,
        "cv": 3,
        "random_state": int(params["random_state"]),
        "model_y": "auto",
        "model_t": "auto",
        "discrete_treatment": True,
        "n_jobs": 1,
        "inference": "auto",
    }

    wrong_class, reason = _native_interval_candidate(
        ForestDRLearner(n_jobs=1, n_estimators=32),
        selected.x,
        cate=cate,
        facts=facts,
        params=params,
        estimator_params=config,
        profile_kind="causal_forest",
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        nuisance_model_classes=(),
    )
    assert wrong_class is None
    assert reason == "method_profile_not_qualified"

    wrong_params = {**config, "n_estimators": 99}
    rejected_params, reason = _native_interval_candidate(
        CausalForestDML(n_jobs=1, n_estimators=100),
        selected.x,
        cate=cate,
        facts=facts,
        params=params,
        estimator_params=wrong_params,
        profile_kind="causal_forest",
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        nuisance_model_classes=(),
    )
    assert rejected_params is None
    assert reason == "method_profile_not_qualified"

    monkeypatch.setattr(hte_v2, "_installed_econml_distribution_root", lambda: None)
    rejected_source, reason = _native_interval_candidate(
        CausalForestDML(n_jobs=1, n_estimators=100),
        selected.x,
        cate=cate,
        facts=facts,
        params=params,
        estimator_params=config,
        profile_kind="causal_forest",
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        nuisance_model_classes=(),
    )
    assert rejected_source is None
    assert reason == "method_profile_not_qualified"
    assert "estimator_class" not in inspect.signature(_native_interval_candidate).parameters


def test_all_hte_routes_cannot_supply_an_estimator_identity_label() -> None:
    for route in (
        hte_v2._method_result,
        hte_v2._execute_with_profile,
        hte_v2._execute_with_profile_unscoped,
    ):
        assert "estimator_class" not in inspect.signature(route).parameters


@pytest.mark.parametrize(
    ("method", "profile_kind", "expected_class", "source_file"),
    [
        (
            CausalForestEstimatorV2,
            "causal_forest",
            "econml.dml.causal_forest.CausalForestDML",
            "econml/dml/causal_forest.py",
        ),
        (
            ForestDRLearnerEstimatorV2,
            "forest_dr",
            "econml.dr._drlearner.ForestDRLearner",
            "econml/dr/_drlearner.py",
        ),
    ],
)
def test_both_native_profiles_refuse_constructor_parameter_and_source_pin_drift(
    method: type,
    profile_kind: str,
    expected_class: str,
    source_file: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("econml")
    from econml.dml.causal_forest import CausalForestDML
    from econml.dr._drlearner import ForestDRLearner

    params = _params_for(method)
    data = _data()
    facts = _facts_for(method, data, params)
    selected = build_hte_data(data)
    if method is CausalForestEstimatorV2:
        expected_model = CausalForestDML
        config = {
            "n_estimators": 100,
            "max_depth": None,
            "min_samples_leaf": 5,
            "max_samples": 0.5,
            "honest": True,
            "cv": 3,
            "random_state": int(params["random_state"]),
            "model_y": "auto",
            "model_t": "auto",
            "discrete_treatment": True,
            "n_jobs": 1,
            "inference": "auto",
        }
    else:
        expected_model = ForestDRLearner
        config = {
            "model_regression": "auto",
            "model_propensity": "auto",
            "discrete_outcome": False,
            "min_propensity": 0.001,
            "categories": "auto",
            "cv": 2,
            "mc_iters": 1,
            "mc_agg": "mean",
            "n_estimators": 32,
            "max_depth": None,
            "min_samples_split": 5,
            "min_samples_leaf": 5,
            "max_samples": 0.45,
            "min_balancedness_tol": 0.45,
            "honest": True,
            "subforest_size": 2,
            "n_jobs": 1,
            "random_state": int(params["random_state"]),
            "inference": "auto",
        }

    def construct(estimator_params: dict[str, Any]) -> object:
        kwargs = {
            key: value
            for key, value in estimator_params.items()
            if profile_kind != "forest_dr" or key != "inference"
        }
        return expected_model(**kwargs)

    drifted_config = {**config, "n_estimators": config["n_estimators"] + 1}
    drifted_model = construct(drifted_config)
    rejected_params, reason = _native_interval_candidate(
        drifted_model,
        selected.x,
        cate=np.zeros(data.outcome.shape[0], dtype=float),
        facts=facts,
        params=params,
        estimator_params=drifted_config,
        profile_kind=profile_kind,
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        nuisance_model_classes=(),
    )
    assert rejected_params is None
    assert reason == "method_profile_not_qualified"

    model = construct(config)
    false_source_pins = dict(hte_v2._ECONML_SOURCE_FILES_SHA256)
    false_source_pins[source_file] = "0" * 64
    monkeypatch.setattr(hte_v2, "_ECONML_SOURCE_FILES_SHA256", false_source_pins)
    rejected_source, reason = _native_interval_candidate(
        model,
        selected.x,
        cate=np.zeros(data.outcome.shape[0], dtype=float),
        facts=facts,
        params=params,
        estimator_params=config,
        profile_kind=profile_kind,
        method_fqn=method.signature.fqn,
        method_abi="2.0.0",
        nuisance_model_classes=(),
    )
    assert rejected_source is None
    assert reason == "method_profile_not_qualified"
    assert f"{type(model).__module__}.{type(model).__qualname__}" == expected_class
