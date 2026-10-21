from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchor,
    OwnedAttemptAnchorDispatchContext,
    OwnedAttemptAnchorProjectionAssociation,
    OwnedAttemptAnchorRef,
    OwnedAttemptHTEInputCapture,
    OwnedHTERequestContextV1,
)
from polisyos.runtime.http.services.control.owned_attempt_anchor import (
    _require_method_evidence_materialization_binding,
    _selection_ref,
    _writer_ready_matches_outcome,
)


def _ref(kind: str, suffix: str) -> dict[str, str]:
    return {
        "artifact_id": "sha256:" + suffix * 64,
        "kind": kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + "f" * 64,
    }


def _anchor_payload() -> dict[str, Any]:
    now = datetime.now(UTC)
    effective_ref = _ref("ir.observation_method_input", "a")
    params = {"alpha": 0.05, "control_value": 0.0, "treated_value": 1.0}
    treatment_values = (0.0, 1.0, 0.0, 0.0)
    n_treated = sum(value == params["treated_value"] for value in treatment_values)
    n_control = sum(value == params["control_value"] for value in treatment_values)
    params_hash = hashlib.sha256(
        json.dumps(
            {"params": params, "seed": 11},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "captured_at": now,
        "job_id": "job.hte.one",
        "run_id": "run.hte.one",
        "tenant_id": "tenant.one",
        "cell_id": None,
        "attempt": 1,
        "worker_id": "worker.one",
        "lease_expires_at": now + timedelta(minutes=5),
        "job_created_event": {
            "event_id": 1,
            "job_id": "job.hte.one",
            "event_type": "job_created",
            "payload_sha256": "sha256:" + "1" * 64,
            "created_at": now - timedelta(seconds=3),
        },
        "job_running_event": {
            "event_id": 2,
            "job_id": "job.hte.one",
            "event_type": "job_running",
            "payload_sha256": "sha256:" + "2" * 64,
            "created_at": now - timedelta(seconds=1),
        },
        "requested_source_ref": _ref("ir.observation_method_input", "b"),
        "observational_run_intent_ref": _ref("runtime.observational_run_intent", "c"),
        "resource_policy_ref": _ref("runtime.observational_input_resource_policy", "e"),
        "selection_digest": "3" * 64,
        "source_manifest_sha256": "4" * 64,
        "method_fqn": "causal.hte.causal_forest@2.0.0",
        "method_version": "2.0.0",
        "method_abi_digest": "5" * 64,
        "method_build_digest": "6" * 64,
        "resource_policy_digest": "7" * 64,
        "resource_policy_schema_version": "polisyos.runtime.observational_input_resource_policy.v4",
        "resource_policy_revision": "r4",
        "resource_policy_method_contract_target": (
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ),
        "resource_policy_required_estimator_n_jobs": 1,
        "resource_policy_method_fqn": "causal.hte.causal_forest@2.0.0",
        "resource_policy_method_profile_id": "econml.causal_forest_dml.native_mean@2.0",
        "resource_policy_execution_scope": "estimator_n_jobs_one",
        "resource_policy_max_jobs": 1,
        "source_protocol": "method_input_envelope_v1",
        "resolved_params_sha256": params_hash,
        "request_context": {
            "request_estimand_status": "declared",
            "request_estimand": "mean_effect_over_selected_x",
            "request_target_scope_status": "declared",
            "request_target_scope": "selected_evaluation_rows",
            "outcome_variable_status": "declared",
            "outcome_variable_id": "outcome.effect",
            "treatment_variable_status": "declared",
            "treatment_variable_id": "treatment.policy",
            "contrast_status": "declared",
            "control_value": 0.0,
            "treated_value": 1.0,
            "request_alpha_status": "declared",
            "requested_alpha": 0.05,
            "requested_guarantee_status": "declared",
            "requested_guarantee": "backend_conditional_interval",
        },
        "input_admission": {
            "admission_status": "input_admitted",
            "content_admitted_intent_ref": _ref(
                "runtime.content_admitted_observational_run_intent", "d"
            ),
            "submitted_input_ref": _ref("ir.observation_method_input", "b"),
            "effective_input_ref": effective_ref,
            "normalization": "canonical_passthrough",
            "input_capture": {
                "source_data_ref": effective_ref,
                "source_data_sha256": "8" * 64,
                "input_profile_id": "all_source_rows_in_input_order@1.0",
                "selected_input_sha256": "8" * 64,
                "selected_rows_sha256": "9" * 64,
                "selected_x_sha256": "a" * 64,
                "selected_row_order_sha256": "b" * 64,
                "fit_rows_sha256": "b" * 64,
                "eval_rows_sha256": "b" * 64,
                "fit_eval_relation": "same_selected_rows",
                "n_selected_rows": len(treatment_values),
                "n_treated": n_treated,
                "n_control": n_control,
                "n_features": 2,
                "source_feature_names": None,
                "n_confounders": 0,
                "sample_ids_status": "not_established",
                "sample_ids_sha256": None,
                "method_fqn": "causal.hte.causal_forest@2.0.0",
                "method_abi": "2.0.0",
                "method_abi_digest": "5" * 64,
                "method_profile_id": "econml.causal_forest_dml.native_mean@2.0",
                "resolved_params_sha256": params_hash,
                "resolved_params": params,
                "seed": 11,
                "request_context": {
                    "request_estimand_status": "declared",
                    "request_estimand": "mean_effect_over_selected_x",
                    "request_target_scope_status": "declared",
                    "request_target_scope": "selected_evaluation_rows",
                    "outcome_variable_status": "declared",
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_status": "declared",
                    "treatment_variable_id": "treatment.policy",
                    "contrast_status": "declared",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "request_alpha_status": "declared",
                    "requested_alpha": 0.05,
                    "requested_guarantee_status": "declared",
                    "requested_guarantee": "backend_conditional_interval",
                },
            },
        },
        "predicate_origins": {
            "owner_attempt_fence": "recomputed",
            "lifecycle_event_chain": "recomputed",
            "requested_source_identity": "independently_reconciled",
            "selected_method_abi": "independently_reconciled",
            "selected_resource_policy": "independently_reconciled",
            "resolved_params_and_seed": "independently_reconciled",
            "selected_input_content": "recomputed",
            "request_estimand": "independently_reconciled",
            "request_target_scope": "independently_reconciled",
            "outcome_variable": "independently_reconciled",
            "treatment_variable": "independently_reconciled",
            "treatment_contrast": "independently_reconciled",
            "requested_alpha": "independently_reconciled",
            "requested_guarantee": "independently_reconciled",
            "estimator_job_cap": "independently_reconciled",
            "selected_producer_job_cap": "not_established",
            "actual_execution_resource_context": "not_established",
            "search_dependency_inventory": "not_established",
            "completed_output_owner_association": "not_established",
        },
    }


def test_anchor_contract_rejects_source_data_rebound_to_another_profile() -> None:
    payload = _anchor_payload()
    payload["input_admission"]["input_capture"]["source_data_ref"] = _ref(
        "ir.observation_method_input", "f"
    )

    with pytest.raises(
        ValidationError, match="owned_attempt_anchor_admitted_input_binding_mismatch"
    ):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_anchor_reference_requires_an_exact_selected_profile() -> None:
    ref = _ref("runtime.owned_attempt_anchor", "a")
    ref["manifest_profile_sha256"] = None  # type: ignore[assignment]

    with pytest.raises(ValidationError):
        OwnedAttemptAnchorRef.model_validate(ref, strict=True)


def test_predicate_origin_does_not_admit_consumer_asserted_gate_fact() -> None:
    payload = _anchor_payload()
    payload["predicate_origins"]["owner_attempt_fence"] = "consumer_asserted"

    with pytest.raises(ValidationError):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_anchor_contract_accepts_complete_profile_and_request_capture() -> None:
    anchor = OwnedAttemptAnchor.model_validate(_anchor_payload(), strict=True)

    assert anchor.request_context.request_estimand_status == "declared"
    assert anchor.input_capture.source_data_ref.manifest_profile_sha256 is not None


def test_anchor_contract_rejects_policy_revision_not_bound_to_selected_profile() -> None:
    payload = _anchor_payload()
    payload["resource_policy_revision"] = "r2"

    with pytest.raises(
        ValidationError,
        match="owned_attempt_resource_policy_profile_revision_mismatch",
    ):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_anchor_contract_rejects_method_specific_policy_profile_mismatch() -> None:
    payload = _anchor_payload()
    payload["resource_policy_execution_scope"] = "producer_scoped_joblib_parallelism_one"
    payload["predicate_origins"]["selected_producer_job_cap"] = "independently_reconciled"

    with pytest.raises(
        ValidationError,
        match="owned_attempt_resource_policy_profile_revision_mismatch",
    ):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_anchor_contract_keeps_dml_producer_cap_distinct_from_estimator_cap() -> None:
    payload = _anchor_payload()
    payload["method_fqn"] = "causal.hte.double_ml@2.0.0"
    capture = payload["input_admission"]["input_capture"]
    capture["method_fqn"] = "causal.hte.double_ml@2.0.0"
    capture["method_profile_id"] = "econml.dml.point_only@2.0"
    payload["resource_policy_method_fqn"] = "causal.hte.double_ml@2.0.0"
    payload["resource_policy_method_profile_id"] = "econml.dml.point_only@2.0"
    payload["resource_policy_execution_scope"] = "producer_scoped_joblib_parallelism_one"
    payload["resource_policy_required_estimator_n_jobs"] = None
    origins = payload["predicate_origins"]
    origins["estimator_job_cap"] = "not_established"
    origins["selected_producer_job_cap"] = "independently_reconciled"

    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)

    assert anchor.resource_policy_execution_scope == ("producer_scoped_joblib_parallelism_one")
    assert anchor.resource_policy_required_estimator_n_jobs is None
    assert anchor.predicate_origins.estimator_job_cap == "not_established"


@pytest.mark.parametrize(
    ("method_fqn", "profile_id", "required_estimator_n_jobs"),
    [
        (
            "causal.hte.causal_forest@2.0.0",
            "econml.causal_forest_dml.native_mean@2.0",
            1,
        ),
        ("causal.hte.double_ml@2.0.0", "econml.dml.point_only@2.0", None),
        ("causal.hte.meta_learner@2.0.0", "econml.meta_learner.point_only@2.0", None),
        (
            "causal.hte.forest_dr@2.0.0",
            "econml.forest_dr.native_mean@2.0",
            1,
        ),
    ],
)
def test_r5_policy_binds_producer_joblib_scope_for_each_successor_method(
    method_fqn: str,
    profile_id: str,
    required_estimator_n_jobs: int | None,
) -> None:
    payload = _anchor_payload()
    payload["resource_policy_schema_version"] = (
        "polisyos.runtime.observational_input_resource_policy.v5"
    )
    payload["resource_policy_revision"] = "r5"
    payload["resource_policy_method_fqn"] = method_fqn
    payload["resource_policy_method_profile_id"] = profile_id
    payload["resource_policy_execution_scope"] = "producer_scoped_joblib_parallelism_one"
    payload["resource_policy_required_estimator_n_jobs"] = required_estimator_n_jobs
    payload["resource_policy_max_jobs"] = 1
    payload["method_fqn"] = method_fqn
    capture = payload["input_admission"]["input_capture"]
    capture["method_fqn"] = method_fqn
    capture["method_profile_id"] = profile_id
    materialization_binding_ref = _ref("foundry.hte.physical_source_materialization_binding", "c")
    capture["materialization_binding_ref"] = materialization_binding_ref
    capture["request_context"]["materialization_binding_ref"] = materialization_binding_ref
    payload["request_context"]["materialization_binding_ref"] = materialization_binding_ref
    origins = payload["predicate_origins"]
    origins["estimator_job_cap"] = (
        "independently_reconciled" if required_estimator_n_jobs == 1 else "not_established"
    )
    origins["selected_producer_job_cap"] = "independently_reconciled"

    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)

    assert anchor.resource_policy_schema_version == (
        "polisyos.runtime.observational_input_resource_policy.v5"
    )
    assert anchor.resource_policy_revision == "r5"
    assert anchor.resource_policy_execution_scope == "producer_scoped_joblib_parallelism_one"
    assert anchor.resource_policy_max_jobs == 1
    assert anchor.resource_policy_required_estimator_n_jobs == required_estimator_n_jobs
    assert anchor.predicate_origins.selected_producer_job_cap == "independently_reconciled"
    assert anchor.predicate_origins.estimator_job_cap == origins["estimator_job_cap"]
    assert anchor.input_capture.materialization_binding_ref is not None
    assert (
        anchor.input_capture.materialization_binding_ref.artifact_id.root
        == (materialization_binding_ref["artifact_id"])
    )


def test_r5_anchor_rejects_removed_or_mismatched_physical_binding() -> None:
    payload = _anchor_payload()
    payload.update(
        resource_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        resource_policy_revision="r5",
        resource_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        resource_policy_max_jobs=1,
        resource_policy_method_fqn="causal.hte.causal_forest@2.0.0",
        resource_policy_method_profile_id="econml.causal_forest_dml.native_mean@2.0",
    )
    payload["predicate_origins"]["selected_producer_job_cap"] = "independently_reconciled"
    binding_ref = _ref("foundry.hte.physical_source_materialization_binding", "c")
    payload["input_admission"]["input_capture"]["materialization_binding_ref"] = binding_ref
    payload["input_admission"]["input_capture"]["request_context"][
        "materialization_binding_ref"
    ] = binding_ref
    payload["request_context"]["materialization_binding_ref"] = binding_ref

    missing = deepcopy(payload)
    del missing["input_admission"]["input_capture"]["materialization_binding_ref"]
    del missing["input_admission"]["input_capture"]["request_context"][
        "materialization_binding_ref"
    ]
    del missing["request_context"]["materialization_binding_ref"]
    with pytest.raises(
        ValidationError,
        match="owned_attempt_r5_physical_materialization_binding_required",
    ):
        OwnedAttemptAnchor.model_validate(missing, strict=True)

    mismatch = deepcopy(payload)
    mismatch["input_admission"]["input_capture"]["request_context"][
        "materialization_binding_ref"
    ] = _ref("foundry.hte.physical_source_materialization_binding", "d")
    with pytest.raises(
        ValidationError,
        match="owned_attempt_input_materialization_binding_context_mismatch",
    ):
        OwnedAttemptAnchor.model_validate(mismatch, strict=True)


def test_r5_anchor_rejects_unprofiled_physical_binding() -> None:
    payload = _anchor_payload()
    payload.update(
        resource_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        resource_policy_revision="r5",
        resource_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        resource_policy_max_jobs=1,
        resource_policy_method_fqn="causal.hte.causal_forest@2.0.0",
        resource_policy_method_profile_id="econml.causal_forest_dml.native_mean@2.0",
    )
    payload["predicate_origins"]["selected_producer_job_cap"] = "independently_reconciled"
    binding_ref = _ref("foundry.hte.physical_source_materialization_binding", "c")
    binding_ref.pop("manifest_profile_sha256")
    payload["input_admission"]["input_capture"]["materialization_binding_ref"] = binding_ref
    payload["input_admission"]["input_capture"]["request_context"][
        "materialization_binding_ref"
    ] = binding_ref
    payload["request_context"]["materialization_binding_ref"] = binding_ref

    with pytest.raises(ValidationError, match="manifest_profile_sha256"):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_runtime_evidence_requires_the_owner_selected_physical_binding() -> None:
    """The worker evidence cannot omit or replace Runtime's materialization ref."""
    payload = _anchor_payload()
    payload.update(
        resource_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        resource_policy_revision="r5",
        resource_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        resource_policy_max_jobs=1,
        resource_policy_method_fqn="causal.hte.causal_forest@2.0.0",
        resource_policy_method_profile_id="econml.causal_forest_dml.native_mean@2.0",
    )
    payload["predicate_origins"]["selected_producer_job_cap"] = "independently_reconciled"
    binding_ref = _ref("foundry.hte.physical_source_materialization_binding", "c")
    capture = payload["input_admission"]["input_capture"]
    capture["materialization_binding_ref"] = binding_ref
    capture["request_context"]["materialization_binding_ref"] = binding_ref
    payload["request_context"]["materialization_binding_ref"] = binding_ref
    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)

    _require_method_evidence_materialization_binding(
        anchor=anchor,
        evidence_payload={"materialization_binding_ref": binding_ref},
    )

    with pytest.raises(
        ValueError,
        match="owned_attempt_method_evidence_materialization_binding_mismatch",
    ):
        _require_method_evidence_materialization_binding(
            anchor=anchor,
            evidence_payload={},
        )

    replaced = deepcopy(binding_ref)
    replaced["artifact_id"] = "sha256:" + "d" * 64
    with pytest.raises(
        ValueError,
        match="owned_attempt_method_evidence_materialization_binding_mismatch",
    ):
        _require_method_evidence_materialization_binding(
            anchor=anchor,
            evidence_payload={"materialization_binding_ref": replaced},
        )

    legacy_anchor = OwnedAttemptAnchor.model_validate(_anchor_payload(), strict=True)
    with pytest.raises(
        ValueError,
        match="owned_attempt_method_evidence_unselected_materialization_binding",
    ):
        _require_method_evidence_materialization_binding(
            anchor=legacy_anchor,
            evidence_payload={"materialization_binding_ref": binding_ref},
        )


def test_r5_policy_does_not_relabel_the_r4_estimator_only_tuple() -> None:
    payload = _anchor_payload()
    payload["resource_policy_schema_version"] = (
        "polisyos.runtime.observational_input_resource_policy.v5"
    )
    payload["resource_policy_revision"] = "r5"

    with pytest.raises(
        ValidationError,
        match="owned_attempt_r5_physical_materialization_binding_required",
    ):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_typed_dispatch_context_preserves_scientific_params_and_capture() -> None:
    from polisyos.foundry.methods.catalog.causal.hte_v2 import OwnedHTEInputCaptureV1

    payload = _anchor_payload()
    binding_ref = _ref("foundry.hte.physical_source_materialization_binding", "f")
    payload["request_context"]["materialization_binding_ref"] = binding_ref
    admitted = payload["input_admission"]["input_capture"]
    admitted["materialization_binding_ref"] = binding_ref
    admitted["request_context"]["materialization_binding_ref"] = binding_ref
    admitted["source_feature_names"] = ("income", "region")
    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)
    anchor_ref = OwnedAttemptAnchorRef.model_validate(_ref("runtime.owned_attempt_anchor", "c"))
    context = OwnedAttemptAnchorDispatchContext(
        anchor_ref=anchor_ref,
        input_capture=anchor.input_capture,
        method_abi_digest=anchor.method_abi_digest,
    )

    capture_payload = context.hte_capture_payload()
    capture = OwnedHTEInputCaptureV1.model_validate(
        capture_payload,
        strict=True,
    )

    assert capture.request_estimand == "mean_effect_over_selected_x"
    assert (capture.n_treated, capture.n_control) == (1, 3)
    assert capture.source_feature_names == ("income", "region")
    assert isinstance(capture_payload["source_feature_names"], tuple)
    assert context.anchor_ref == anchor_ref
    assert "__owned_attempt_anchor_ref__" not in capture_payload
    assert "capture_status" not in capture_payload
    assert "selected_input_status" not in capture_payload
    assert "selected_rows_status" not in capture_payload


@pytest.mark.parametrize(
    ("contrast_status", "control_value", "treated_value", "n_treated", "n_control", "error"),
    [
        (
            "declared",
            0.0,
            1.0,
            0,
            0,
            "owned_attempt_input_treatment_counts_do_not_cover_rows",
        ),
        (
            "not_established",
            None,
            None,
            1,
            3,
            "owned_attempt_input_treatment_counts_without_declared_contrast",
        ),
    ],
)
def test_core_capture_counts_follow_explicit_contrast_status(
    contrast_status: str,
    control_value: float | None,
    treated_value: float | None,
    n_treated: int,
    n_control: int,
    error: str,
) -> None:
    payload = _anchor_payload()["input_admission"]["input_capture"]
    payload["n_treated"] = n_treated
    payload["n_control"] = n_control
    payload["request_context"]["contrast_status"] = contrast_status
    payload["request_context"]["control_value"] = control_value
    payload["request_context"]["treated_value"] = treated_value

    with pytest.raises(ValidationError, match=error):
        OwnedAttemptHTEInputCapture.model_validate(payload, strict=True)


@pytest.mark.parametrize("missing_field", ["n_treated", "n_control"])
def test_core_capture_requires_both_treatment_count_fields(missing_field: str) -> None:
    payload = _anchor_payload()["input_admission"]["input_capture"]
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        OwnedAttemptHTEInputCapture.model_validate(payload, strict=True)


def test_core_capture_unknown_contrast_preserves_zero_counts() -> None:
    payload = _anchor_payload()["input_admission"]["input_capture"]
    payload["n_treated"] = 0
    payload["n_control"] = 0
    payload["request_context"]["contrast_status"] = "not_established"
    payload["request_context"]["control_value"] = None
    payload["request_context"]["treated_value"] = None
    # The unknown request contrast must also be absent from estimator params;
    # keep the persisted params digest truthful instead of retaining a hidden
    # resolved 0/1 contrast beside the not-established request.
    resolved_params = dict(payload["resolved_params"])
    resolved_params.pop("control_value")
    resolved_params.pop("treated_value")
    payload["resolved_params"] = resolved_params
    payload["resolved_params_sha256"] = hashlib.sha256(
        json.dumps(
            {"params": resolved_params, "seed": payload["seed"]},
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    capture = OwnedAttemptHTEInputCapture.model_validate(payload, strict=True)

    assert (capture.n_treated, capture.n_control) == (0, 0)


def test_core_capture_rejects_source_feature_name_width_drift() -> None:
    payload = _anchor_payload()["input_admission"]["input_capture"]
    payload["source_feature_names"] = ("only_one",)

    with pytest.raises(ValidationError, match="owned_attempt_input_feature_names_width_mismatch"):
        OwnedAttemptHTEInputCapture.model_validate(payload, strict=True)


def test_input_refusal_has_no_admitted_refs_or_synthetic_row_count() -> None:
    payload = _anchor_payload()
    payload["input_admission"] = {
        "admission_status": "input_admission_refused",
        "refusal": {
            "refusal_code": "empty_selected_input",
            "failure_stage": "empty_selected_input",
            "observed_manifest_selection_bytes": 0,
            "observed_manifest_verification_bytes": 0,
            "observed_payload_bytes": 0,
            "observed_source_bytes": 0,
            "source_usage_complete": True,
            "payload_integrity_verified": False,
        },
    }
    payload["predicate_origins"]["selected_input_content"] = "not_established"
    payload["predicate_origins"]["request_estimand"] = "not_established"
    payload["predicate_origins"]["request_target_scope"] = "not_established"
    payload["predicate_origins"]["outcome_variable"] = "not_established"
    payload["predicate_origins"]["treatment_variable"] = "not_established"
    payload["predicate_origins"]["treatment_contrast"] = "not_established"
    payload["predicate_origins"]["requested_alpha"] = "not_established"
    payload["predicate_origins"]["requested_guarantee"] = "not_established"
    payload["request_context"] = {
        name: None if name.endswith("_status") is False else "not_established"
        for name in payload["request_context"]
    }
    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)

    assert anchor.input_admission.admission_status == "input_admission_refused"
    assert "n_selected_rows" not in anchor.input_admission.refusal.model_dump()
    with pytest.raises(ValueError, match="owned_attempt_input_admission_refused"):
        _ = anchor.input_capture

    payload["input_admission"]["refusal"]["n_selected_rows"] = 0
    with pytest.raises(ValidationError):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_requested_guarantee_requires_explicit_intent_value() -> None:
    payload = _anchor_payload()
    payload["request_context"]["requested_guarantee"] = None
    payload["input_admission"]["input_capture"]["request_context"]["requested_guarantee"] = None

    with pytest.raises(ValidationError, match="owned_attempt_request_context_status_mismatch"):
        OwnedAttemptAnchor.model_validate(payload, strict=True)


def test_owner_association_detects_a_point_value_changed_after_method_execution() -> None:
    writer_ready = SimpleNamespace(
        kind="point_estimate",
        point_estimate=2.0,
        inference_status="unsupported",
        inference_reason="method_profile_not_qualified",
    )
    selected_outcome = SimpleNamespace(
        kind="point_estimate",
        point_estimate=SimpleNamespace(value=2.0),
        inference_status="unsupported",
        inference_reason="method_profile_not_qualified",
    )
    forged_outcome = SimpleNamespace(
        kind="point_estimate",
        point_estimate=SimpleNamespace(value=2.1),
        inference_status="unsupported",
        inference_reason="method_profile_not_qualified",
    )

    assert _writer_ready_matches_outcome(writer_ready, selected_outcome)
    assert not _writer_ready_matches_outcome(writer_ready, forged_outcome)


def test_owner_selection_without_the_anchor_ref_fails_closed() -> None:
    selection = SimpleNamespace(owned_attempt_anchor_ref=None)

    with pytest.raises(
        ValueError,
        match="owned_attempt_owner_selection_ref_missing:owned_attempt_anchor_ref",
    ):
        _selection_ref(selection, "owned_attempt_anchor_ref", required=True)


def _projection_association_payload(*, outcome_kind: str = "point_estimate") -> dict[str, Any]:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "verified_at": now,
        "anchor_ref": _ref("runtime.owned_attempt_anchor", "a"),
        "outcome_ref": _ref("ir.hte_outcome", "b"),
        "outcome_kind": outcome_kind,
        "selected_summary_sha256": "c" * 64,
        "source_data_ref": _ref("ir.observation_method_input", "d"),
        "source_data_summary_status": "content_bound",
        "resource_policy_ref": _ref("runtime.observational_input_resource_policy", "e"),
        "method_result_ref": _ref("scientist.method_result.causal.hte", "f"),
        "method_evidence_ref": _ref("scientist.method_evidence", "1"),
        "invocation_basis_ref": None,
        "point_result_ref": _ref("ir.hte_point_result", "2"),
        "hte_result_ref": None,
        "inference_basis_ref": None,
        "refusal_diagnostic_ref": None,
        "job_completed_event": {
            "event_id": 3,
            "job_id": "job.hte.one",
            "event_type": "job_completed",
            "payload_sha256": "sha256:" + "3" * 64,
            "created_at": now,
        },
        "job_id": "job.hte.one",
        "run_id": "run.hte.one",
        "tenant_id": "tenant.one",
        "cell_id": None,
        "attempt": 1,
    }
    if outcome_kind == "refusal":
        payload.update(
            point_result_ref=None,
            source_data_summary_status="content_bound",
            refusal_diagnostic_ref=_ref("ir.hte_refusal_diagnostic", "4"),
        )
    return payload


def test_projection_association_marks_scalar_summary_as_worker_admitted() -> None:
    association = OwnedAttemptAnchorProjectionAssociation.model_validate(
        _projection_association_payload(),
        strict=True,
    )

    assert association.status == "owner_projection_reconciled"
    assert association.content_validation_status == "worker_admitted_not_recomputed"
    assert association.manifest_identity_status == "independently_reconciled"
    assert association.point_result_ref is not None
    assert association.hte_result_ref is None


def test_projection_association_refusal_has_diagnostic_and_no_numeric_refs() -> None:
    association = OwnedAttemptAnchorProjectionAssociation.model_validate(
        _projection_association_payload(outcome_kind="refusal"),
        strict=True,
    )

    assert association.outcome_kind == "refusal"
    assert association.source_data_summary_status == "content_bound"
    assert association.refusal_diagnostic_ref is not None
    assert association.point_result_ref is None


def test_projection_association_cannot_claim_content_recomputation() -> None:
    payload = _projection_association_payload()
    payload["content_validation_status"] = "recomputed"

    with pytest.raises(ValidationError):
        OwnedAttemptAnchorProjectionAssociation.model_validate(payload, strict=True)


def test_numeric_projection_requires_source_summary_binding() -> None:
    payload = _projection_association_payload()
    payload["source_data_summary_status"] = "not_established"

    with pytest.raises(ValidationError):
        OwnedAttemptAnchorProjectionAssociation.model_validate(payload, strict=True)


def test_absent_search_binding_preserves_the_legacy_request_context_dump() -> None:
    """Standalone v2 contexts omit the optional field from canonical bytes."""
    anchor = OwnedAttemptAnchor.model_validate(_anchor_payload(), strict=True)

    assert "search_uncertainty_task_binding_ref" not in anchor.request_context.model_dump(
        mode="json"
    )
    assert "search_uncertainty_task_binding_ref" not in (
        anchor.input_capture.request_context.model_dump(mode="json")
    )
    assert anchor.request_context.model_dump(mode="json") == (
        anchor.input_capture.request_context.model_dump(mode="json")
    )


def test_search_binding_ref_is_profiled_and_bound_in_anchor_capture() -> None:
    payload = _anchor_payload()
    binding_ref = _ref("scientist.search.uncertainty_task_binding", "c")
    payload["request_context"]["search_uncertainty_task_binding_ref"] = binding_ref
    payload["input_admission"]["input_capture"]["request_context"][
        "search_uncertainty_task_binding_ref"
    ] = binding_ref

    anchor = OwnedAttemptAnchor.model_validate(payload, strict=True)
    assert anchor.request_context.search_uncertainty_task_binding_ref is not None
    assert (
        anchor.request_context.search_uncertainty_task_binding_ref.artifact_id.root
        == binding_ref["artifact_id"]
    )

    mismatched_context = dict(payload["request_context"])
    mismatched_context["search_uncertainty_task_binding_ref"] = _ref("ir.other_artifact", "d")
    with pytest.raises(ValidationError, match="owned_attempt_search_binding_ref_kind_mismatch"):
        OwnedHTERequestContextV1.model_validate(mismatched_context, strict=True)

    unprofiled_ref = {
        key: value for key, value in binding_ref.items() if key != "manifest_profile_sha256"
    }
    unprofiled_context = dict(payload["request_context"])
    unprofiled_context["search_uncertainty_task_binding_ref"] = unprofiled_ref
    with pytest.raises(ValidationError):
        OwnedHTERequestContextV1.model_validate(unprofiled_context, strict=True)


def test_projection_association_preserves_only_the_profiled_search_binding_ref() -> None:
    payload = _projection_association_payload()
    binding_ref = _ref("scientist.search.uncertainty_task_binding", "c")
    payload["search_uncertainty_task_binding_ref"] = binding_ref

    association = OwnedAttemptAnchorProjectionAssociation.model_validate(payload, strict=True)
    assert association.search_uncertainty_task_binding_ref is not None
    assert (
        association.search_uncertainty_task_binding_ref.artifact_id.root
        == binding_ref["artifact_id"]
    )

    payload["search_uncertainty_task_binding_ref"] = _ref("ir.other_artifact", "d")
    with pytest.raises(
        ValidationError, match="owned_attempt_projection_search_binding_ref_invalid"
    ):
        OwnedAttemptAnchorProjectionAssociation.model_validate(payload, strict=True)
