"""Behavioral tests for the v2 method-local parallelism receipt."""

from __future__ import annotations

import base64
import hashlib
import json
import math
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from joblib import effective_n_jobs, parallel_config

from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorDispatchContext,
    OwnedAttemptAnchorRef,
    OwnedAttemptHTEInputCapture,
    OwnedHTERequestContextV1,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.numpy_runner import NumpyRunner
from polisyos.foundry.methods.backends.protocol import RuntimeContextDispatchError
from polisyos.foundry.methods.catalog.causal.forest_dr import (
    ForestDRLearnerEstimatorV11,
)
from polisyos.foundry.methods.catalog.causal.hte_v2 import (
    CausalForestEstimatorV2,
    DoubleMachineLearningV2,
    ForestDRLearnerEstimatorV2,
    HTEProducerResourceReceiptV1,
    HTEWriterReadyPointV1,
    HTEWriterReadyRefusalV1,
    MetaLearnerEstimatorV2,
    _attach_resource_receipt,
    _capture_estimator_observation,
    _capture_facts,
    _capture_joblib_observation,
    _econml_source_profile_digest,
    _finite_effect,
    _JoblibProfileFailure,
    _method_identity,
    _native_extraction_entry,
    _not_started_resource_receipt,
    _one_scalar,
    _pinned_econml_constructor_values,
    _refusal_output,
    _resource_receipt,
    _run_with_joblib_profile,
    _validate_numeric_resource_receipt,
    build_hte_data,
    build_owned_hte_input_capture,
    validate_hte_writer_ready_json,
)
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    _capture_matches_writer_ready,
)


def test_joblib_profile_is_scoped_to_one_method_call_and_restored() -> None:
    """A v2 DML/Meta call must override and then restore the caller's joblib context."""
    observed_inner: list[int] = []

    with parallel_config(n_jobs=3):
        before = effective_n_jobs(n_jobs=None)
        value, receipt = _run_with_joblib_profile(
            lambda: (
                observed_inner.append(effective_n_jobs(n_jobs=None)),
                effective_n_jobs(n_jobs=None),
            )[1],
            method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
        )
        after = effective_n_jobs(n_jobs=None)

    assert before == after
    assert value == 1
    assert observed_inner == [1]
    assert receipt.execution_status == "returned"
    assert receipt.scope == "producer_scoped_joblib_parallelism_one"
    assert receipt.joblib_started is True
    assert receipt.joblib_finished is True
    assert receipt.joblib_exit_status == "returned"
    assert receipt.joblib_entry_effective_jobs == receipt.joblib_exit_effective_jobs == 1
    assert receipt.joblib_entry_config_sha256 == receipt.joblib_exit_config_sha256


@pytest.mark.parametrize(
    ("module_name", "class_name", "class_fqn"),
    [
        (
            "econml.dml.causal_forest",
            "CausalForestDML",
            "econml.dml.causal_forest.CausalForestDML",
        ),
        (
            "econml.dr._drlearner",
            "ForestDRLearner",
            "econml.dr._drlearner.ForestDRLearner",
        ),
    ],
)
def test_pinned_econml_constructor_observation_covers_every_field_and_fails_closed(
    module_name: str,
    class_name: str,
    class_fqn: str,
) -> None:
    """Capture the complete pinned constructor surface and exact one-job value."""
    import importlib
    import inspect

    pytest.importorskip("econml")
    from polisyos.foundry.methods.catalog.causal.hte_v2 import _capture_estimator_observation

    estimator_type = getattr(importlib.import_module(module_name), class_name)
    estimator = estimator_type(n_jobs=1, n_estimators=8)
    assert not callable(getattr(estimator, "get_params", None))

    constructor_parameters = inspect.signature(estimator_type.__init__).parameters
    expected_fields = {name for name in constructor_parameters if name != "self"}
    configured_values = _pinned_econml_constructor_values(estimator)
    assert set(configured_values) == expected_fields

    before = _capture_estimator_observation(estimator)
    assert before["class_fqn"] == class_fqn
    assert before["n_jobs"] == 1
    estimator.n_estimators += 1
    after = _capture_estimator_observation(estimator)
    assert before["params_sha256"] != after["params_sha256"]

    for invalid_n_jobs in (True, -1, 2):
        estimator.n_jobs = invalid_n_jobs
        with pytest.raises(ValueError, match="hte_estimator_n_jobs_not_one"):
            _capture_estimator_observation(estimator)

    estimator.n_jobs = 1
    del estimator.n_jobs
    with pytest.raises(ValueError, match="hte_estimator_n_jobs_not_one"):
        _capture_estimator_observation(estimator)

    class ForeignEstimatorWithoutGetter:
        pass

    with pytest.raises(ValueError, match="hte_estimator_n_jobs_not_one"):
        _capture_estimator_observation(ForeignEstimatorWithoutGetter())


@pytest.mark.parametrize("invalid_effective_jobs", [True, False, 0, -1, 1.5, "1", np.int64(1)])
def test_invalid_joblib_effective_jobs_refuse_before_method_callback(
    monkeypatch: pytest.MonkeyPatch,
    invalid_effective_jobs: object,
) -> None:
    """Only a positive built-in int may qualify the selected one-job profile."""
    import joblib

    from polisyos.foundry.methods.catalog.causal import hte_v2

    def callback_must_not_run(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise AssertionError("invalid Joblib observation must refuse before method execution")

    monkeypatch.setattr(joblib, "effective_n_jobs", lambda n_jobs=-1: invalid_effective_jobs)
    monkeypatch.setattr(hte_v2, "_execute_with_profile_unscoped", callback_must_not_run)

    result = CausalForestEstimatorV2.pure_step({}, {})
    refusal = validate_hte_writer_ready_json(result["hte_outcome_write_ready"])
    assert isinstance(refusal, HTEWriterReadyRefusalV1)

    assert refusal.diagnostic_code == "resource_profile_invalid"
    assert refusal.refusal_stage == "prepare"
    assert refusal.refusal_reason == "method_profile_unavailable"
    assert refusal.resource_receipt.execution_status == "not_started"
    assert refusal.resource_receipt.joblib_started is False


@pytest.mark.parametrize("invalid_exit_jobs", [True, False, 0, -1, 1.5, "1", np.int64(1)])
def test_invalid_joblib_exit_after_callback_never_emits_point_or_completed_receipt(
    monkeypatch: pytest.MonkeyPatch,
    invalid_exit_jobs: object,
) -> None:
    """A malformed exit observation cannot become a false complete resource receipt."""
    import joblib

    from polisyos.foundry.methods.catalog.causal import hte_v2

    values = iter((1, invalid_exit_jobs))
    callback_calls: list[bool] = []

    def callback_returns_candidate(*_args: object, **_kwargs: object) -> dict[str, Any]:
        callback_calls.append(True)
        return {"hte_outcome_write_ready": {"kind": "point_estimate"}}

    monkeypatch.setattr(joblib, "effective_n_jobs", lambda n_jobs=-1: next(values))
    monkeypatch.setattr(hte_v2, "_execute_with_profile_unscoped", callback_returns_candidate)

    with pytest.raises(
        ValueError,
        match="hte_joblib_resource_observation_invalid_after_start",
    ):
        CausalForestEstimatorV2.pure_step({}, {})

    assert callback_calls == [True]


def _owned_context_for(method_class: type, *, seed: int) -> OwnedAttemptAnchorDispatchContext:
    """Build one well-formed Core context for a backend dispatch seam test."""
    signature = method_class.signature
    resolved_params = {item.name: item.default for item in signature.parameters}
    params_sha256 = hashlib.sha256(
        json.dumps(
            {"params": resolved_params, "seed": seed},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    request = OwnedHTERequestContextV1(
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="not_established",
        request_target_scope=None,
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="not_established",
        control_value=None,
        treated_value=None,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
    )
    capture = OwnedAttemptHTEInputCapture(
        source_data_ref={
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "ir.observation_method_input",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        source_data_sha256="3" * 64,
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="3" * 64,
        selected_rows_sha256="4" * 64,
        selected_x_sha256="5" * 64,
        selected_row_order_sha256="6" * 64,
        fit_rows_sha256="7" * 64,
        eval_rows_sha256="7" * 64,
        fit_eval_relation="same_selected_rows",
        n_selected_rows=2,
        n_treated=0,
        n_control=0,
        n_features=1,
        source_feature_names=None,
        n_confounders=0,
        sample_ids_status="not_established",
        sample_ids_sha256=None,
        method_fqn=signature.fqn,
        method_abi="2.0.0",
        method_abi_digest="8" * 64,
        method_profile_id=method_class.owned_hte_profile_id,
        resolved_params_sha256=params_sha256,
        resolved_params=resolved_params,
        seed=seed,
        request_context=request,
    )
    anchor_ref = OwnedAttemptAnchorRef(
        artifact_id="sha256:" + "9" * 64,
        kind="runtime.owned_attempt_anchor",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    return OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=capture,
        method_abi_digest="8" * 64,
    )


def test_dispatch_passes_owner_context_separately_and_preserves_legacy_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same method uses its typed context hook only for that invocation."""
    method = CausalForestEstimatorV2
    context = _owned_context_for(method, seed=19)
    runtime_calls: list[OwnedAttemptAnchorDispatchContext] = []
    legacy_calls: list[bool] = []

    def legacy_step(state, params):
        legacy_calls.append(True)
        return {"hte_outcome_write_ready": {"route": "legacy"}}

    def owner_step(state, params, *, runtime_context):
        runtime_calls.append(runtime_context)
        return {"hte_outcome_write_ready": {"route": "owner_context"}}

    monkeypatch.setattr(method, "pure_step", staticmethod(legacy_step))
    monkeypatch.setattr(method, "pure_step_with_runtime_context", staticmethod(owner_step))
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    dispatcher.register_runner(NumpyRunner())

    owner_result = dispatcher.dispatch(
        method_class=method,
        signature=method.signature,
        state={},
        params={},
        seed=19,
        runtime_context=context,
    )
    legacy_result = dispatcher.dispatch(
        method_class=method,
        signature=method.signature,
        state={},
        params={},
        seed=19,
    )

    assert runtime_calls == [context]
    assert legacy_calls == [True]
    assert owner_result.output["hte_outcome_write_ready"]["route"] == "owner_context"
    assert legacy_result.output["hte_outcome_write_ready"]["route"] == "legacy"


def test_dispatch_rejects_owner_context_for_a_different_registered_method() -> None:
    """A valid context cannot be silently dropped on a sibling HTE method."""
    context = _owned_context_for(CausalForestEstimatorV2, seed=23)
    method = DoubleMachineLearningV2
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    dispatcher.register_runner(NumpyRunner())

    with pytest.raises(RuntimeContextDispatchError, match="method_identity_mismatch"):
        dispatcher.dispatch(
            method_class=method,
            signature=method.signature,
            state={},
            params={},
            seed=23,
            runtime_context=context,
        )


def test_pre_fit_capture_copies_owner_selected_materialization_binding() -> None:
    """The producer capture retains the exact physical binding ref from Runtime."""
    binding_ref = {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "foundry.hte.physical_source_materialization_binding",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "c" * 64,
    }
    request = OwnedHTERequestContextV1(
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="not_established",
        request_target_scope=None,
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="not_established",
        control_value=None,
        treated_value=None,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        materialization_binding_ref=binding_ref,
    )
    data = HTEObservationalData(
        outcome=np.linspace(0.0, 1.0, 40),
        treatment=np.tile(np.array([0, 1]), 20),
        covariates=np.arange(40, dtype=float).reshape(40, 1),
    )
    method = CausalForestEstimatorV2
    resolved_params = {item.name: item.default for item in method.signature.parameters}
    capture = build_owned_hte_input_capture(
        data,
        source_data_ref={
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "ir.observation_method_input",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        method_class=method,
        method_abi_digest="8" * 64,
        resolved_params=resolved_params,
        seed=19,
        request_context=request,
    )

    assert capture.materialization_binding_ref == request.materialization_binding_ref
    assert (
        capture.request_context.materialization_binding_ref == request.materialization_binding_ref
    )
    assert (capture.n_treated, capture.n_control) == (0, 0)


def test_pre_fit_capture_recomputes_asymmetric_counts_and_rejects_drift() -> None:
    """The owner capture and writer-ready facts use actual selected treatment rows."""
    binding_ref = {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "foundry.hte.physical_source_materialization_binding",
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "c" * 64,
    }
    request = OwnedHTERequestContextV1(
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="not_established",
        request_target_scope=None,
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        materialization_binding_ref=binding_ref,
    )
    data = HTEObservationalData(
        outcome=np.linspace(0.0, 1.0, 40),
        treatment=np.asarray([1] * 7 + [0] * 33),
        covariates=np.arange(40, dtype=float).reshape(40, 1),
        feature_names=["covariate"],
    )
    method = CausalForestEstimatorV2
    resolved_params = {item.name: item.default for item in method.signature.parameters}
    resolved_params.update(control_value=0.0, treated_value=1.0)
    capture = build_owned_hte_input_capture(
        data,
        source_data_ref={
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "ir.observation_method_input",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        method_class=method,
        method_abi_digest="8" * 64,
        resolved_params=resolved_params,
        seed=19,
        request_context=request,
    )
    method_fqn, method_abi, method_profile_id = _method_identity(method)
    params_with_seed = {**resolved_params, "__seed__": 19}
    anchor_ref = OwnedAttemptAnchorRef(
        artifact_id="sha256:" + "9" * 64,
        kind="runtime.owned_attempt_anchor",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    runtime_context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=capture,
        method_abi_digest="8" * 64,
    )
    selected_data = build_hte_data(data)
    facts = _capture_facts(
        selected_data,
        data,
        params_with_seed,
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        runtime_context=runtime_context,
    )

    assert (capture.n_treated, capture.n_control) == (7, 33)
    assert (facts.n_treated, facts.n_control) == (7, 33)
    assert facts.source_feature_names == ("covariate",)
    owner_anchor = SimpleNamespace(input_capture=capture)
    assert _capture_matches_writer_ready(
        writer_capture=facts,
        anchor=owner_anchor,
        anchor_ref=anchor_ref,
    )
    tampered_facts = facts.model_copy(update={"n_treated": 6, "n_control": 34})
    assert not _capture_matches_writer_ready(
        writer_capture=tampered_facts,
        anchor=owner_anchor,
        anchor_ref=anchor_ref,
    )
    tampered_names = facts.model_copy(update={"source_feature_names": ("forged",)})
    assert not _capture_matches_writer_ready(
        writer_capture=tampered_names,
        anchor=owner_anchor,
        anchor_ref=anchor_ref,
    )

    tampered_name_capture = capture.model_copy(update={"source_feature_names": ("forged",)})
    tampered_name_context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=tampered_name_capture,
        method_abi_digest="8" * 64,
    )
    with pytest.raises(ValueError, match="owned_hte_input_capture_mismatch"):
        _capture_facts(
            selected_data,
            data,
            params_with_seed,
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            runtime_context=tampered_name_context,
        )

    tampered_capture = capture.model_copy(update={"n_treated": 6, "n_control": 34})
    tampered_context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=tampered_capture,
        method_abi_digest="8" * 64,
    )
    with pytest.raises(ValueError, match="owned_hte_input_capture_mismatch"):
        _capture_facts(
            selected_data,
            data,
            params_with_seed,
            method_fqn=method_fqn,
            method_abi=method_abi,
            method_profile_id=method_profile_id,
            runtime_context=tampered_context,
        )


def test_normal_typed_refusal_records_returned_scope_without_estimator() -> None:
    """A returned refusal is not mislabeled as an execution exception."""
    value, receipt = _run_with_joblib_profile(
        lambda: {"hte_outcome_write_ready": {"kind": "refusal"}},
        method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
    )

    assert value == {"hte_outcome_write_ready": {"kind": "refusal"}}
    assert receipt.execution_status == "returned"
    assert receipt.joblib_exit_status == "returned"
    assert receipt.joblib_started is True
    assert receipt.joblib_finished is True
    assert receipt.estimator_before_class_fqn is None
    assert receipt.estimator_after_class_fqn is None


def test_propagated_callback_error_records_raised_scope() -> None:
    """Only an exception that crosses the method-local scope is marked raised."""

    def fail() -> None:
        raise RuntimeError("method callback failed")

    try:
        _run_with_joblib_profile(
            fail,
            method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
        )
    except _JoblibProfileFailure as exc:
        assert exc.receipt.execution_status == "raised"
        assert exc.receipt.joblib_exit_status == "raised"
        assert exc.receipt.joblib_started is True
        assert exc.receipt.joblib_finished is True
    else:
        raise AssertionError("a propagated callback failure must retain raised status")


def test_returned_but_unqualified_resource_measurement_is_not_called_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Measured mismatch produces a refusal receipt with the actual returned lifecycle."""
    from polisyos.foundry.methods.catalog.causal import hte_v2

    observations = iter(
        (
            {
                "effective_jobs": 2,
                "backend_fqn": "joblib._parallel_backends.LokyBackend",
                "implementation_version": "1.5.3",
                "config_sha256": "a" * 64,
            },
            {
                "effective_jobs": 3,
                "backend_fqn": "joblib._parallel_backends.ThreadingBackend",
                "implementation_version": "1.5.3",
                "config_sha256": "b" * 64,
            },
        )
    )
    monkeypatch.setattr(hte_v2, "_capture_joblib_observation", lambda: next(observations))

    with pytest.raises(_JoblibProfileFailure) as raised:
        _run_with_joblib_profile(
            lambda: pytest.fail("callback must not execute under an invalid entry profile"),
            method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
        )

    receipt = raised.value.receipt
    assert raised.value.diagnostic_code == "resource_profile_invalid"
    assert receipt.execution_status == "returned"
    assert receipt.joblib_exit_status == "returned"
    assert receipt.joblib_entry_effective_jobs == 2
    assert receipt.joblib_exit_effective_jobs == 3
    assert receipt.joblib_entry_backend_fqn != receipt.joblib_exit_backend_fqn


@pytest.mark.parametrize(
    "payload",
    [
        True,
        np.bool_(True),
        np.asarray([True]),
        [1.0, True],
        np.asarray([1.0, True], dtype=object),
    ],
)
def test_numeric_native_payloads_reject_boolean_scalars_and_vectors(
    payload: object,
) -> None:
    """Boolean values cannot become numeric effect or inference evidence."""
    with pytest.raises(ValueError):
        _one_scalar(payload, name="native_bound")
    with pytest.raises(ValueError, match="point_estimate_invalid"):
        _finite_effect(payload, n_rows=2)


def test_econml_profile_recomputes_recorded_source_bytes(tmp_path, monkeypatch) -> None:
    """A pinned profile fails when an implementation source file changes."""
    from polisyos.foundry.methods.catalog.causal import hte_v2

    metadata = b"Name: econml\nVersion: 0.17.0\n"
    source_path = "econml/dml/causal_forest.py"
    source = b"class PinnedImplementation: pass\n"
    source_digest = hashlib.sha256(source).hexdigest()
    record = (
        f"{source_path},sha256="
        f"{base64.urlsafe_b64encode(bytes.fromhex(source_digest)).decode().rstrip('=')},"
        f"{len(source)}\n"
    ).encode()
    dist_info = tmp_path / "econml-0.17.0.dist-info"
    package_file = tmp_path / source_path
    dist_info.mkdir()
    package_file.parent.mkdir(parents=True)
    (dist_info / "METADATA").write_bytes(metadata)
    (dist_info / "RECORD").write_bytes(record)
    package_file.write_bytes(source)

    source_files = {source_path: source_digest}
    metadata_digest = hashlib.sha256(metadata).hexdigest()
    record_digest = hashlib.sha256(record).hexdigest()
    identity = {
        "distribution": "econml",
        "version": "0.17.0",
        "metadata_sha256": metadata_digest,
        "record_sha256": record_digest,
        "source_files": source_files,
    }
    expected_profile = hte_v2._sha256(identity)
    monkeypatch.setattr(hte_v2, "_ECONML_METADATA_SHA256", metadata_digest)
    monkeypatch.setattr(hte_v2, "_ECONML_RECORD_SHA256", record_digest)
    monkeypatch.setattr(hte_v2, "_ECONML_SOURCE_FILES_SHA256", source_files)
    monkeypatch.setattr(hte_v2, "_ECONML_SOURCE_PROFILE_SHA256", expected_profile)

    assert _econml_source_profile_digest(tmp_path) == expected_profile
    package_file.write_bytes(source + b"# changed source bytes\n")
    assert _econml_source_profile_digest(tmp_path) is None


def test_native_entry_rejects_same_basename_foreign_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Matching a module path and class name cannot substitute for exact classes."""
    import sys
    from pathlib import Path
    from types import ModuleType

    module_names = (
        "econml",
        "econml.dml",
        "econml.dml.causal_forest",
        "econml.dr",
        "econml.dr._drlearner",
        "econml.inference",
        "econml.inference._inference",
    )
    modules = {}
    for name in module_names:
        module = ModuleType(name)
        if name in {"econml", "econml.dml", "econml.dr", "econml.inference"}:
            module.__path__ = []  # type: ignore[attr-defined]
        modules[name] = module
        monkeypatch.setitem(sys.modules, name, module)
    for parent_name, child_name in (
        ("econml", "dml"),
        ("econml", "dr"),
        ("econml", "inference"),
        ("econml.dml", "causal_forest"),
        ("econml.dr", "_drlearner"),
        ("econml.inference", "_inference"),
    ):
        setattr(modules[parent_name], child_name, modules[f"{parent_name}.{child_name}"])

    expected_estimator = type("CausalForestDML", (), {"__module__": "econml.dml.causal_forest"})
    expected_inference = type(
        "_GenericSingleOutcomeModelFinalWithCovInference",
        (),
        {"__module__": "econml.dml.causal_forest"},
    )
    modules["econml.dml.causal_forest"].CausalForestDML = expected_estimator
    modules[
        "econml.dml.causal_forest"
    ]._GenericSingleOutcomeModelFinalWithCovInference = expected_inference
    modules["econml.dr._drlearner"].ForestDRLearner = type(
        "ForestDRLearner", (), {"__module__": "econml.dr._drlearner"}
    )
    modules["econml.inference._inference"].GenericModelFinalInferenceDiscrete = type(
        "GenericModelFinalInferenceDiscrete",
        (),
        {"__module__": "econml.inference._inference"},
    )
    modules["econml.inference._inference"].PopulationSummaryResults = type(
        "PopulationSummaryResults",
        (),
        {"__module__": "econml.inference._inference"},
    )
    foreign_estimator = type("CausalForestDML", (), {"__module__": "econml.dml.causal_forest"})
    foreign_inference = type(
        "_GenericSingleOutcomeModelFinalWithCovInference",
        (),
        {"__module__": "econml.dml.causal_forest"},
    )
    assert foreign_estimator.__qualname__ == expected_estimator.__qualname__
    assert foreign_inference.__qualname__ == expected_inference.__qualname__

    assert (
        _native_extraction_entry(
            foreign_estimator(),
            expected_inference(),
            None,
            profile_kind="causal_forest",
            distribution_root=Path("/untrusted/econml"),
        )
        is None
    )
    assert (
        _native_extraction_entry(
            expected_estimator(),
            foreign_inference(),
            None,
            profile_kind="causal_forest",
            distribution_root=Path("/untrusted/econml"),
        )
        is None
    )


def test_estimator_n_jobs_receipt_requires_live_deep_config() -> None:
    """CF/ForestDR resource evidence comes from the instantiated estimator itself."""

    class ConfiguredEstimator:
        __module__ = "econml.test_estimators"

        def get_params(self, *, deep: bool) -> dict[str, int]:
            assert deep is True
            return {"n_jobs": 1}

    observation = _capture_estimator_observation(ConfiguredEstimator())
    with parallel_config(n_jobs=1):
        joblib_entry = _capture_joblib_observation()
        joblib_exit = _capture_joblib_observation()
    receipt = _resource_receipt(
        method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
        status="returned",
        estimator_before=observation,
        estimator_after=observation,
        joblib_entry=joblib_entry,
        joblib_exit=joblib_exit,
        joblib_exit_status="returned",
    )

    assert receipt.execution_status == "returned"
    assert receipt.scope == "producer_scoped_joblib_parallelism_one"
    assert receipt.estimator_before_n_jobs == receipt.estimator_after_n_jobs == 1
    assert receipt.estimator_before_params_sha256 == receipt.estimator_after_params_sha256
    assert receipt.joblib_entry_effective_jobs == receipt.joblib_exit_effective_jobs == 1
    assert receipt.joblib_entry_config_sha256 == receipt.joblib_exit_config_sha256


def test_native_numeric_receipt_requires_exact_profile_estimator_class() -> None:
    """A stable one-job class from another module cannot qualify as native CF."""

    class SameShapeDifferentEstimator:
        def get_params(self, *, deep: bool) -> dict[str, int]:
            assert deep is True
            return {"n_jobs": 1}

    observation = _capture_estimator_observation(SameShapeDifferentEstimator())
    with parallel_config(n_jobs=1):
        joblib_entry = _capture_joblib_observation()
        joblib_exit = _capture_joblib_observation()
    receipt = _resource_receipt(
        method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
        status="returned",
        estimator_before=observation,
        estimator_after=observation,
        joblib_entry=joblib_entry,
        joblib_exit=joblib_exit,
        joblib_exit_status="returned",
    )

    with pytest.raises(
        ValueError, match="native_hte_candidate_requires_recomputed_estimator_config"
    ):
        _validate_numeric_resource_receipt(CausalForestEstimatorV2.owned_hte_profile_id, receipt)


def test_point_only_methods_require_joblib_receipt_without_estimator_claim() -> None:
    """DML/Meta v2 bind the producer-wide cap without inventing estimator n_jobs."""
    with parallel_config(n_jobs=1):
        joblib_entry = _capture_joblib_observation()
        joblib_exit = _capture_joblib_observation()

    receipt = _resource_receipt(
        method_profile_id=DoubleMachineLearningV2.owned_hte_profile_id,
        status="returned",
        joblib_entry=joblib_entry,
        joblib_exit=joblib_exit,
        joblib_exit_status="returned",
    )

    assert receipt.scope == "producer_scoped_joblib_parallelism_one"
    assert receipt.joblib_entry_effective_jobs == receipt.joblib_exit_effective_jobs == 1
    assert receipt.estimator_before_class_fqn is None
    assert receipt.estimator_after_class_fqn is None


def test_numeric_resource_receipt_cannot_omit_joblib_lifecycle() -> None:
    """A method policy's producer-wide cap cannot be inferred from estimator n_jobs."""

    class ConfiguredEstimator:
        __module__ = "econml.test_estimators"

        def get_params(self, *, deep: bool) -> dict[str, int]:
            assert deep is True
            return {"n_jobs": 1}

    observation = _capture_estimator_observation(ConfiguredEstimator())
    try:
        _resource_receipt(
            method_profile_id=CausalForestEstimatorV2.owned_hte_profile_id,
            status="returned",
            estimator_before=observation,
            estimator_after=observation,
        )
    except ValueError as exc:
        assert "started_hte_producer_requires_full_joblib_lifecycle" in str(exc)
    else:
        raise AssertionError("estimator n_jobs alone cannot establish the producer cap")


def test_estimator_n_jobs_receipt_rejects_inherited_or_parallel_config() -> None:
    """An absent estimator value cannot inherit the policy's one-job claim."""

    class UnconfiguredEstimator:
        def get_params(self, *, deep: bool) -> dict[str, int | None]:
            assert deep is True
            return {"n_jobs": None}

    try:
        _capture_estimator_observation(UnconfiguredEstimator())
    except ValueError as exc:
        assert str(exc) == "hte_estimator_n_jobs_not_one"
    else:
        raise AssertionError("missing n_jobs must fail closed")


def test_only_the_registered_successor_forest_dr_can_use_owner_context() -> None:
    """The 1.x method stays outside the successor anchor and finalizer path."""
    assert _method_identity(ForestDRLearnerEstimatorV2) == (
        "causal.hte.forest_dr@2.0.0",
        "2.0.0",
        "econml.forest_dr.native_mean@2.0",
    )
    try:
        _method_identity(ForestDRLearnerEstimatorV11)
    except ValueError as exc:
        assert str(exc) == "method_class_not_registered_for_hte_v2"
    else:
        raise AssertionError("legacy ForestDR must bypass the v2 owner-context path")


def test_writer_ready_rejects_legacy_schema_pair_even_if_other_fields_are_valid() -> None:
    """A legacy FQN/schema pair cannot be laundered through the v2 refusal union."""
    try:
        HTEWriterReadyRefusalV1.model_validate(
            {
                "kind": "refusal",
                "method_fqn": "causal.hte.forest_dr@1.1.0",
                "method_abi": "1.1.0",
                "method_profile_id": "econml.forest_dr.native_mean@1.1",
                "resource_receipt": _not_started_resource_receipt(
                    ForestDRLearnerEstimatorV2.owned_hte_profile_id
                ),
                "limitations": ("legacy_identity_not_admitted_to_v2",),
                "refusal_stage": "prepare",
                "refusal_reason": "required_input_unavailable",
                "diagnostic_code": "hte_input_invalid",
            },
            strict=True,
        )
    except ValueError as exc:
        assert "hte_method_identity_profile_mismatch" in str(exc)
    else:
        raise AssertionError("legacy schema pairs must not enter the successor union")


def test_all_successor_classes_have_one_explicit_method_profile_pair() -> None:
    """Registered identities stay disjoint across all four v2 producers."""
    classes = (
        CausalForestEstimatorV2,
        DoubleMachineLearningV2,
        MetaLearnerEstimatorV2,
        ForestDRLearnerEstimatorV2,
    )
    pairs = {
        (method_class.owned_hte_method_fqn, method_class.owned_hte_profile_id)
        for method_class in classes
    }
    assert len(pairs) == len(classes)
    assert all(_method_identity(method_class)[1] == "2.0.0" for method_class in classes)


def _writer_ready_point_json(*, feature_names: list[str] | None) -> dict[str, Any]:
    """Build a no-fit writer value with the same JSON boundary as MethodResult."""
    method = DoubleMachineLearningV2
    source_data = HTEObservationalData(
        outcome=np.linspace(0.0, 1.0, 40),
        treatment=np.tile(np.asarray([0, 1]), 20),
        covariates=np.arange(80, dtype=float).reshape(40, 2),
        feature_names=feature_names,
    )
    resolved_params = {item.name: item.default for item in method.signature.parameters}
    params_with_seed = {**resolved_params, "__seed__": 19}
    method_fqn, method_abi, method_profile_id = _method_identity(method)
    capture = _capture_facts(
        build_hte_data(source_data),
        source_data,
        params_with_seed,
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        runtime_context=None,
    )
    _, receipt = _run_with_joblib_profile(
        lambda: {},
        method_profile_id=method_profile_id,
    )
    point = HTEWriterReadyPointV1(
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        resource_receipt=receipt,
        limitations=("native_interval_not_requested",),
        kind="point_estimate",
        capture=capture,
        point_estimate=0.25,
        inference_status="not_requested",
        inference_reason="inference_not_requested",
        cate_values=tuple(0.25 for _ in range(capture.n_selected_rows)),
        native_diagnostic=None,
    )
    return point.model_dump(mode="json")


def test_writer_ready_json_boundary_round_trips_json_tuples_without_weakening_python() -> None:
    """Only the explicit JSON boundary maps arrays back to strict tuple fields."""
    from pydantic import ValidationError

    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready,
        validate_hte_writer_ready_json,
    )

    payload = _writer_ready_point_json(feature_names=["earnings", "schooling"])
    with pytest.raises(ValidationError):
        validate_hte_writer_ready(payload)

    parsed = validate_hte_writer_ready_json(payload)
    assert isinstance(parsed, HTEWriterReadyPointV1)
    assert validate_hte_writer_ready(parsed) == parsed
    assert parsed.limitations == ("native_interval_not_requested",)
    assert parsed.capture.source_feature_names == ("earnings", "schooling")
    assert len(parsed.cate_values) == parsed.capture.n_selected_rows == 40

    receipt = HTEProducerResourceReceiptV1.model_validate(payload["resource_receipt"], strict=True)
    attached = _attach_resource_receipt(
        {"hte_outcome_write_ready": payload},
        receipt,
    )
    attached_value = validate_hte_writer_ready_json(attached["hte_outcome_write_ready"])
    assert isinstance(attached_value, HTEWriterReadyPointV1)
    assert attached_value.capture.source_feature_names == ("earnings", "schooling")

    refusal_output = _refusal_output(
        payload["method_fqn"],
        payload["method_abi"],
        DoubleMachineLearningV2.owned_hte_profile_id,
        diagnostic_code="resource_profile_invalid",
        resource_receipt=receipt,
        capture=payload["capture"],
    )
    refusal = validate_hte_writer_ready_json(refusal_output["hte_outcome_write_ready"])
    assert isinstance(refusal, HTEWriterReadyRefusalV1)
    assert refusal.capture is not None
    assert refusal.capture.source_feature_names == ("earnings", "schooling")


def test_writer_ready_json_boundary_preserves_absent_feature_names_and_refusal() -> None:
    """JSON input preserves absent optional names and validates the refusal branch."""
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    point_payload = _writer_ready_point_json(feature_names=None)
    point = validate_hte_writer_ready_json(point_payload)
    assert isinstance(point, HTEWriterReadyPointV1)
    assert point.capture.source_feature_names is None

    method = DoubleMachineLearningV2
    method_fqn, method_abi, method_profile_id = _method_identity(method)
    refusal = HTEWriterReadyRefusalV1(
        kind="refusal",
        method_fqn=method_fqn,
        method_abi=method_abi,
        method_profile_id=method_profile_id,
        resource_receipt=_not_started_resource_receipt(method_profile_id),
        capture=None,
        limitations=("input_not_available",),
        refusal_stage="prepare",
        refusal_reason="required_input_unavailable",
        diagnostic_code="hte_input_invalid",
    )
    refusal_json = refusal.model_dump(mode="json")
    parsed_refusal = validate_hte_writer_ready_json(refusal_json)
    assert isinstance(parsed_refusal, HTEWriterReadyRefusalV1)
    assert parsed_refusal.limitations == ("input_not_available",)


def test_writer_ready_json_boundary_rejects_malformed_values_without_coercion() -> None:
    """Malformed JSON members, unknown fields, and non-string keys stay rejected."""
    from copy import deepcopy

    from pydantic import ValidationError

    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    payload = _writer_ready_point_json(feature_names=["earnings", "schooling"])

    malformed_member = deepcopy(payload)
    malformed_member["cate_values"][0] = "not-a-number"  # type: ignore[index]
    with pytest.raises(ValidationError):
        validate_hte_writer_ready_json(malformed_member)

    boolean_number = deepcopy(payload)
    boolean_number["cate_values"][0] = True  # type: ignore[index]
    with pytest.raises(ValidationError):
        validate_hte_writer_ready_json(boolean_number)

    unknown_field = deepcopy(payload)
    unknown_field["unexpected"] = "not-in-schema"
    with pytest.raises(ValidationError):
        validate_hte_writer_ready_json(unknown_field)

    wrong_schema = deepcopy(payload)
    wrong_schema["kind"] = "unsupported_variant"
    with pytest.raises(ValidationError):
        validate_hte_writer_ready_json(wrong_schema)

    non_string_key = deepcopy(payload)
    non_string_key["capture"]["resolved_params"][1] = "must-not-be-stringified"  # type: ignore[index]
    with pytest.raises((TypeError, ValueError), match="JSON object keys must be strings"):
        validate_hte_writer_ready_json(non_string_key)

    non_json_object = deepcopy(payload)
    non_json_object["capture"]["resolved_params"]["python_only"] = object()  # type: ignore[index]
    with pytest.raises(TypeError, match="non-JSON value"):
        validate_hte_writer_ready_json(non_json_object)

    python_tuple = deepcopy(payload)
    python_tuple["limitations"] = ("not-json-array",)
    with pytest.raises(TypeError, match="non-JSON value"):
        validate_hte_writer_ready_json(python_tuple)

    non_finite_number = deepcopy(payload)
    non_finite_number["point_estimate"] = float("nan")
    with pytest.raises((TypeError, ValueError)):
        validate_hte_writer_ready_json(non_finite_number)


# These tests exercise the actual EconML producer. `model_type` selects a
# constructor; it is provenance, not an EconML constructor keyword.
def _dml_selector_fixture(selector: str):
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorDispatchContext,
        OwnedAttemptAnchorRef,
        OwnedHTERequestContextV1,
    )

    rng = np.random.default_rng(1601)
    treatment = np.tile(np.asarray([0, 1], dtype=np.int64), 20)
    rng.shuffle(treatment)
    covariates = rng.normal(size=(40, 2))
    outcome = (
        1.4 * treatment
        + 0.6 * covariates[:, 0]
        - 0.25 * covariates[:, 1]
        + rng.normal(scale=0.2, size=40)
    )
    state = HTEObservationalData(
        outcome=outcome,
        treatment=treatment,
        covariates=covariates,
        feature_names=["baseline", "income"],
    )
    params = {item.name: item.default for item in DoubleMachineLearningV2.signature.parameters}
    params.update(model_type=selector, control_value=0.0, treated_value=1.0)
    request = OwnedHTERequestContextV1(
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="not_established",
        request_target_scope=None,
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        materialization_binding_ref={
            "artifact_id": "sha256:" + "b" * 64,
            "kind": "foundry.hte.physical_source_materialization_binding",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "c" * 64,
        },
    )
    capture = build_owned_hte_input_capture(
        state,
        source_data_ref={
            "artifact_id": "sha256:" + "1" * 64,
            "kind": "ir.observation_method_input",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "2" * 64,
        },
        method_class=DoubleMachineLearningV2,
        method_abi_digest="8" * 64,
        resolved_params=params,
        seed=0,
        request_context=request,
    )
    anchor_ref = OwnedAttemptAnchorRef(
        artifact_id="sha256:" + "9" * 64,
        kind="runtime.owned_attempt_anchor",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=capture,
        method_abi_digest="8" * 64,
    )
    return state, params, context


@pytest.mark.parametrize(
    ("selector", "constructor_name"),
    [
        ("linear", "LinearDML"),
        ("sparse", "SparseLinearDML"),
        ("kernel", "KernelDML"),
    ],
)
def test_dml_selector_dispatches_to_real_constructor_without_laundering(
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
    constructor_name: str,
) -> None:
    """Each supported selector fits a real model and remains owner-bound."""
    from types import MappingProxyType

    import econml.dml
    from threadpoolctl import threadpool_limits

    state, params, context = _dml_selector_fixture(selector)
    immutable_params = MappingProxyType(dict(params))
    original_params = dict(immutable_params)
    real_constructor = getattr(econml.dml, constructor_name)
    constructor_calls: list[dict[str, Any]] = []

    def observed_constructor(*args: Any, **kwargs: Any) -> Any:
        constructor_calls.append(dict(kwargs))
        return real_constructor(*args, **kwargs)

    observed_constructor.__name__ = real_constructor.__name__
    observed_constructor.__qualname__ = real_constructor.__qualname__
    monkeypatch.setattr(econml.dml, constructor_name, observed_constructor)

    with threadpool_limits(limits=1):
        output = DoubleMachineLearningV2.pure_step_with_runtime_context(
            state,
            immutable_params,
            runtime_context=context,
        )

    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    outcome = output["hte_outcome_write_ready"]
    assert outcome["kind"] == "point_estimate"
    point = validate_hte_writer_ready_json(outcome)
    assert isinstance(point, HTEWriterReadyPointV1)
    assert constructor_calls and len(constructor_calls) == 1
    assert "model_type" not in constructor_calls[0]
    assert point.method_profile_id == "econml.dml.point_only@2.0"
    assert math.isfinite(point.point_estimate)
    assert point.inference_reason == "inference_not_requested"
    assert point.cate_values and len(point.cate_values) == 40
    assert point.capture.resolved_params["model_type"] == selector
    assert point.capture.resolved_params_sha256 == context.input_capture.resolved_params_sha256
    assert point.capture.source_feature_names == ("baseline", "income")
    assert point.capture.n_treated == point.capture.n_control == 20
    assert point.resource_receipt.execution_status == "returned"
    assert point.resource_receipt.joblib_max_jobs == 1
    assert dict(immutable_params) == original_params


def test_dml_selector_reintroduction_is_a_typed_fit_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reintroducing the selector as a constructor kwarg must fail closed."""
    from types import MappingProxyType

    import econml.dml
    from threadpoolctl import threadpool_limits

    state, params, context = _dml_selector_fixture("linear")
    immutable_params = MappingProxyType(dict(params))
    real_constructor = econml.dml.LinearDML
    constructor_errors: list[str] = []

    def reintroduced_selector(*args: Any, **kwargs: Any) -> Any:
        try:
            return real_constructor(*args, model_type="linear", **kwargs)
        except TypeError as exc:
            constructor_errors.append(str(exc))
            raise

    reintroduced_selector.__name__ = real_constructor.__name__
    reintroduced_selector.__qualname__ = real_constructor.__qualname__
    monkeypatch.setattr(econml.dml, "LinearDML", reintroduced_selector)

    with threadpool_limits(limits=1):
        output = DoubleMachineLearningV2.pure_step_with_runtime_context(
            state,
            immutable_params,
            runtime_context=context,
        )

    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    outcome = validate_hte_writer_ready_json(output["hte_outcome_write_ready"])
    assert isinstance(outcome, HTEWriterReadyRefusalV1)
    assert constructor_errors
    assert outcome.refusal_stage == "fit"
    assert outcome.diagnostic_code == "hte_fit_failed"
    assert outcome.capture is not None
    assert outcome.capture.resolved_params["model_type"] == "linear"
    assert outcome.capture.resolved_params_sha256 == context.input_capture.resolved_params_sha256
    assert outcome.resource_receipt.execution_status == "returned"
    assert outcome.resource_receipt.joblib_max_jobs == 1


def test_dml_unknown_selector_remains_a_preparation_refusal() -> None:
    """The constructor split does not turn malformed selectors into defaults."""
    from types import MappingProxyType

    state, params, context = _dml_selector_fixture("not-a-supported-model")
    immutable_params = MappingProxyType(dict(params))
    original_params = dict(immutable_params)
    output = DoubleMachineLearningV2.pure_step_with_runtime_context(
        state,
        immutable_params,
        runtime_context=context,
    )
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    outcome = validate_hte_writer_ready_json(output["hte_outcome_write_ready"])
    assert isinstance(outcome, HTEWriterReadyRefusalV1)
    assert outcome.refusal_stage == "prepare"
    assert outcome.diagnostic_code == "dml_profile_invalid"
    assert dict(immutable_params) == original_params


def test_dml_invalid_supplied_state_is_typed_invalid_input_not_absence() -> None:
    """Malformed supplied data remains a strict invalid-input refusal."""
    from types import MappingProxyType

    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        validate_hte_writer_ready_json,
    )

    state, params, context = _dml_selector_fixture("linear")
    malformed_state = state.model_dump()
    malformed_state["outcome"] = state.outcome[:-1]
    output = DoubleMachineLearningV2.pure_step_with_runtime_context(
        malformed_state,
        MappingProxyType(dict(params)),
        runtime_context=context,
    )
    outcome = validate_hte_writer_ready_json(output["hte_outcome_write_ready"])
    assert isinstance(outcome, HTEWriterReadyRefusalV1)
    assert outcome.refusal_stage == "prepare"
    assert outcome.refusal_reason == "invalid_selected_input"
    assert outcome.diagnostic_code == "hte_input_invalid"
    assert outcome.capture is None
