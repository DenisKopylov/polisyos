"""Behavioral checks for successor HTE owner-policy execution receipts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorRef,
    OwnedHTERequestContextV1,
    SelectedArtifactRef,
)
from polisyos.core.contracts.runtime import (
    DirectMethodExecutionHTEResourceEvidence,
    DirectMethodExecutionHTESummary,
    DirectMethodExecutionHTETargetRelation,
    DirectMethodExecutionSelection,
    _expected_content_admitted_limitations,
)


def _resource_evidence(
    *,
    method_fqn: str,
    execution_scope: str,
    execution_status: str,
) -> dict[str, object]:
    assert execution_scope == "producer_scoped_joblib_parallelism_one"
    method_profile = {
        "causal.hte.causal_forest@2.0.0": "econml.causal_forest_dml.native_mean@2.0",
        "causal.hte.double_ml@2.0.0": "econml.dml.point_only@2.0",
        "causal.hte.meta_learner@2.0.0": "econml.meta_learner.point_only@2.0",
        "causal.hte.forest_dr@2.0.0": "econml.forest_dr.native_mean@2.0",
    }[method_fqn]
    estimator_required = method_fqn in {
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    }
    evidence: dict[str, object] = {
        "owner_policy_ref": {
            "artifact_id": "sha256:" + "a" * 64,
            "kind": "runtime.observational_input_resource_policy",
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        },
        "owner_policy_digest": "c" * 64,
        "owner_policy_schema_version": "polisyos.runtime.observational_input_resource_policy.v5",
        "owner_policy_revision": "r5",
        "owner_policy_method_fqn": method_fqn,
        "owner_policy_method_profile_id": method_profile,
        "owner_policy_execution_scope": execution_scope,
        "owner_policy_max_jobs": 1,
        "owner_policy_required_estimator_n_jobs": 1 if estimator_required else None,
        "execution_status": execution_status,
        "estimator_observation_status": (
            "recomputed"
            if estimator_required and execution_status == "returned"
            else "not_established"
            if estimator_required
            else "not_applicable"
        ),
        "estimator_before_class_fqn": (
            "econml.dml.CausalForestDML"
            if estimator_required and execution_status == "returned"
            else None
        ),
        "estimator_before_n_jobs": (
            1 if estimator_required and execution_status == "returned" else None
        ),
        "estimator_before_params_sha256": (
            "d" * 64 if estimator_required and execution_status == "returned" else None
        ),
        "estimator_after_class_fqn": (
            "econml.dml.CausalForestDML"
            if estimator_required and execution_status == "returned"
            else None
        ),
        "estimator_after_n_jobs": (
            1 if estimator_required and execution_status == "returned" else None
        ),
        "estimator_after_params_sha256": (
            "d" * 64 if estimator_required and execution_status == "returned" else None
        ),
        "joblib_observation_status": (
            "recomputed" if execution_status in {"returned", "raised"} else "not_established"
        ),
        "joblib_profile_id": None,
        "joblib_profile_revision": None,
        "joblib_implementation": None,
        "joblib_implementation_version": None,
        "joblib_scope": None,
        "joblib_max_jobs": None,
        "joblib_started": False,
        "joblib_finished": False,
        "joblib_exit_status": "not_started",
        "joblib_entry_effective_jobs": None,
        "joblib_entry_backend_fqn": None,
        "joblib_entry_config_sha256": None,
        "joblib_entry_implementation_version": None,
        "joblib_exit_effective_jobs": None,
        "joblib_exit_backend_fqn": None,
        "joblib_exit_config_sha256": None,
        "joblib_exit_implementation_version": None,
    }
    if execution_status in {"returned", "raised"}:
        exit_status = execution_status
        evidence.update(
            {
                "joblib_profile_id": "joblib.parallel_config.current_thread@1.0",
                "joblib_profile_revision": "1.0",
                "joblib_implementation": "joblib.parallel_config",
                "joblib_implementation_version": "1.5.3",
                "joblib_scope": "current_thread_joblib",
                "joblib_max_jobs": 1,
                "joblib_started": True,
                "joblib_finished": True,
                "joblib_exit_status": exit_status,
                "joblib_entry_effective_jobs": 1,
                "joblib_entry_backend_fqn": "joblib._parallel_backends.SequentialBackend",
                "joblib_entry_config_sha256": "e" * 64,
                "joblib_entry_implementation_version": "1.5.3",
                "joblib_exit_effective_jobs": 1,
                "joblib_exit_backend_fqn": "joblib._parallel_backends.SequentialBackend",
                "joblib_exit_config_sha256": "e" * 64,
                "joblib_exit_implementation_version": "1.5.3",
            }
        )
    return evidence


@pytest.mark.parametrize(
    ("method_fqn", "scope"),
    [
        ("causal.hte.causal_forest@2.0.0", "producer_scoped_joblib_parallelism_one"),
        ("causal.hte.forest_dr@2.0.0", "producer_scoped_joblib_parallelism_one"),
        ("causal.hte.double_ml@2.0.0", "producer_scoped_joblib_parallelism_one"),
        ("causal.hte.meta_learner@2.0.0", "producer_scoped_joblib_parallelism_one"),
    ],
)
def test_returned_hte_resource_receipt_reconciles_to_selected_policy(
    method_fqn: str,
    scope: str,
) -> None:
    evidence = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope=scope,
        execution_status="returned",
    )

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "returned"
    assert admitted.owner_policy_method_fqn == method_fqn


@pytest.mark.parametrize(
    ("method_fqn", "execution_scope"),
    [
        ("causal.hte.causal_forest@2.0.0", "estimator_n_jobs_one"),
        (
            "causal.hte.double_ml@2.0.0",
            "producer_scoped_joblib_parallelism_one",
        ),
    ],
)
def test_historical_r4_resource_receipt_remains_readable(
    method_fqn: str,
    execution_scope: str,
) -> None:
    evidence = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence.update(
        {
            "owner_policy_schema_version": (
                "polisyos.runtime.observational_input_resource_policy.v4"
            ),
            "owner_policy_revision": "r4",
            "owner_policy_execution_scope": execution_scope,
        }
    )
    if execution_scope == "estimator_n_jobs_one":
        evidence.update(
            {
                "joblib_observation_status": "not_applicable",
                "joblib_profile_id": None,
                "joblib_profile_revision": None,
                "joblib_implementation": None,
                "joblib_implementation_version": None,
                "joblib_scope": None,
                "joblib_max_jobs": None,
                "joblib_started": False,
                "joblib_finished": False,
                "joblib_exit_status": "not_started",
                "joblib_entry_effective_jobs": None,
                "joblib_entry_backend_fqn": None,
                "joblib_entry_config_sha256": None,
                "joblib_entry_implementation_version": None,
                "joblib_exit_effective_jobs": None,
                "joblib_exit_backend_fqn": None,
                "joblib_exit_config_sha256": None,
                "joblib_exit_implementation_version": None,
            }
        )

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.owner_policy_revision == "r4"
    assert admitted.owner_policy_execution_scope == execution_scope
    assert admitted.joblib_observation_status == (
        "not_applicable" if execution_scope == "estimator_n_jobs_one" else "recomputed"
    )


def test_returned_refusal_preserves_joblib_configuration_drift() -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.double_ml@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence["joblib_exit_config_sha256"] = "f" * 64

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "returned"
    assert admitted.joblib_entry_config_sha256 == "e" * 64
    assert admitted.joblib_exit_config_sha256 == "f" * 64


def test_raised_hte_resource_receipt_is_not_a_numeric_positive() -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.meta_learner@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="raised",
    )
    evidence["joblib_entry_effective_jobs"] = 2
    evidence["joblib_exit_effective_jobs"] = 3
    evidence["joblib_exit_config_sha256"] = "f" * 64

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "raised"
    assert admitted.joblib_exit_status == "raised"
    assert admitted.joblib_entry_effective_jobs == 2
    assert admitted.joblib_exit_effective_jobs == 3


def test_raised_estimator_receipt_preserves_observed_drift() -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.causal_forest@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="raised",
    )
    evidence["estimator_observation_status"] = "recomputed"
    evidence["estimator_before_class_fqn"] = "econml.dml.CausalForestDML"
    evidence["estimator_before_params_sha256"] = "d" * 64
    evidence["estimator_before_n_jobs"] = 2
    evidence["estimator_after_n_jobs"] = 3
    evidence["estimator_after_class_fqn"] = "econml.dml.OtherEstimator"
    evidence["estimator_after_params_sha256"] = "f" * 64

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "raised"
    assert admitted.estimator_before_n_jobs == 2
    assert admitted.estimator_after_n_jobs == 3
    assert admitted.estimator_after_class_fqn == "econml.dml.OtherEstimator"
    assert admitted.estimator_after_params_sha256 == "f" * 64


@pytest.mark.parametrize(("before", "after"), [(-1, -1), (-1, 0), (0, 0)])
def test_raised_estimator_refusal_preserves_lossless_n_jobs_observations(
    before: int,
    after: int,
) -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.causal_forest@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="raised",
    )
    evidence.update(
        {
            "estimator_observation_status": "recomputed",
            "estimator_before_class_fqn": "econml.dml.CausalForestDML",
            "estimator_before_params_sha256": "d" * 64,
            "estimator_before_n_jobs": before,
            "estimator_after_class_fqn": "econml.dml.CausalForestDML",
            "estimator_after_params_sha256": "d" * 64,
            "estimator_after_n_jobs": after,
        }
    )

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "raised"
    assert admitted.estimator_before_n_jobs == before
    assert admitted.estimator_after_n_jobs == after


def test_estimator_n_jobs_observation_rejects_boolean_as_integer() -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.causal_forest@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="raised",
    )
    evidence.update(
        {
            "estimator_observation_status": "recomputed",
            "estimator_before_class_fqn": "econml.dml.CausalForestDML",
            "estimator_before_params_sha256": "d" * 64,
            "estimator_before_n_jobs": True,
            "estimator_after_class_fqn": "econml.dml.CausalForestDML",
            "estimator_after_params_sha256": "d" * 64,
            "estimator_after_n_jobs": 1,
        }
    )

    with pytest.raises(ValidationError):
        DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)


@pytest.mark.parametrize(("before", "after"), [(-1, -1), (-1, 0), (0, 0)])
def test_returned_hte_refusal_preserves_lossless_n_jobs_observations(
    before: int,
    after: int,
) -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.causal_forest@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence.update(
        {
            "estimator_before_n_jobs": before,
            "estimator_after_n_jobs": after,
        }
    )

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "returned"
    assert admitted.estimator_before_n_jobs == before
    assert admitted.estimator_after_n_jobs == after


def test_joblib_effective_jobs_observation_rejects_boolean_as_integer() -> None:
    evidence = _resource_evidence(
        method_fqn="causal.hte.double_ml@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence["joblib_entry_effective_jobs"] = True

    with pytest.raises(ValidationError):
        DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)


def _numeric_summary_payload(
    resource_evidence: dict[str, object],
) -> dict[str, object]:
    """Build a valid point-summary envelope around one typed resource receipt."""
    sha = "a" * 64

    def ref(kind: str, seed: str) -> dict[str, str]:
        return {
            "artifact_id": "sha256:" + seed * 64,
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + "b" * 64,
        }

    return {
        "schema_version": "1.0",
        "kind": "point_estimate",
        "method_fqn": "causal.hte.causal_forest@2.0.0",
        "method_abi_digest": sha,
        "method_profile_id": "econml.causal_forest_dml.native_mean@2.0",
        "resolved_params_sha256": sha,
        "owned_attempt_anchor_ref": {
            **ref("runtime.owned_attempt_anchor", "c"),
        },
        "hte_outcome_ref": ref("ir.hte_outcome", "d"),
        "point_result_ref": ref("ir.hte_point_result", "e"),
        "hte_result_ref": None,
        "inference_basis_ref": None,
        "refusal_diagnostic_ref": None,
        "materialization_binding_ref": ref(
            "foundry.hte.physical_source_materialization_binding", "f"
        ),
        "method_result_ref": ref("scientist.method_result.causal.hte", "1"),
        "method_evidence_ref": ref("scientist.method_evidence", "2"),
        "source_data_ref": ref("foundry.data_snapshot", "3"),
        "selected_rows_status": "recomputed",
        "n_selected_rows": 4,
        "selected_rows_sha256": sha,
        "selected_row_order_sha256": sha,
        "selected_x_sha256": sha,
        "computed_estimand_status": "recomputed",
        "computed_estimand": "mean_effect_over_selected_x",
        "computed_target_scope_status": "recomputed",
        "computed_target_scope": "selected_evaluation_rows",
        "measure_unit_status": "not_established",
        "measure_unit": None,
        "request_estimand_status": "not_established",
        "request_estimand": None,
        "request_target_scope_status": "not_established",
        "request_target_scope": None,
        "outcome_variable_status": "not_established",
        "outcome_variable_id": None,
        "treatment_variable_status": "not_established",
        "treatment_variable_id": None,
        "request_contrast_status": "not_established",
        "control_value": None,
        "treated_value": None,
        "request_alpha_status": "not_established",
        "requested_alpha": None,
        "requested_guarantee_status": "not_established",
        "requested_guarantee": None,
        "computed_guarantee_status": "computed",
        "computed_guarantee": "candidate_point",
        "target_relation": _target_relation_payload(
            computed_scope_status="recomputed",
            computed_scope="selected_evaluation_rows",
            computed_guarantee_status="computed",
            computed_guarantee="candidate_point",
            source_content_status="content_bound",
            row_order_status="recomputed",
            profile_status="qualified",
        ),
        "inference_status": "not_requested",
        "inference_reason": "inference_not_requested",
        "point_estimate": 0.25,
        "lower_bound": None,
        "upper_bound": None,
        "confidence_level": None,
        "refusal_stage": None,
        "refusal_reason": None,
        "refusal_diagnostic_code": None,
        "resource_evidence": resource_evidence,
        "limitations": ("candidate_point_only",),
    }


@pytest.mark.parametrize(
    ("resource_field", "resource_value", "expected_error"),
    [
        (
            "estimator_after_n_jobs",
            2,
            "direct_method_hte_numeric_estimator_policy_not_qualified",
        ),
        (
            "joblib_entry_effective_jobs",
            2,
            "direct_method_hte_numeric_joblib_policy_not_qualified",
        ),
    ],
)
def test_numeric_summary_rejects_losslessly_preserved_policy_violations(
    resource_field: str,
    resource_value: int,
    expected_error: str,
) -> None:
    resource = _resource_evidence(
        method_fqn="causal.hte.causal_forest@2.0.0",
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    resource[resource_field] = resource_value

    with pytest.raises(ValidationError, match=expected_error):
        DirectMethodExecutionHTESummary.model_validate(_numeric_summary_payload(resource))


def _target_relation_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "requested_scope_status": "not_established",
        "requested_scope": None,
        "requested_guarantee_status": "not_established",
        "requested_guarantee": None,
        "computed_scope_status": "not_established",
        "computed_scope": None,
        "computed_guarantee_status": "not_established",
        "computed_guarantee": None,
        "source_content_status": "not_established",
        "row_order_status": "not_established",
        "contrast_status": "not_established",
        "estimand_status": "not_established",
        "alpha_status": "not_established",
        "profile_status": "not_established",
        "scope_disposition": "not_established",
        "guarantee_disposition": "not_established",
        "overall_disposition": "not_established",
    }
    payload.update(updates)
    return payload


def test_typed_population_scope_mismatch_survives_unknown_content_and_row_order() -> None:
    relation = DirectMethodExecutionHTETargetRelation.model_validate(
        _target_relation_payload(
            requested_scope_status="declared",
            requested_scope="population",
            computed_scope_status="recomputed",
            computed_scope="selected_evaluation_rows",
            scope_disposition="requested_claim_not_satisfied",
            overall_disposition="requested_claim_not_satisfied",
        )
    )

    assert relation.scope_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"
    assert relation.source_content_status == "not_established"
    assert relation.row_order_status == "not_established"


def test_typed_guarantee_mismatch_survives_unrelated_unknowns() -> None:
    relation = DirectMethodExecutionHTETargetRelation.model_validate(
        _target_relation_payload(
            requested_guarantee_status="declared",
            requested_guarantee="backend_conditional_interval",
            computed_guarantee_status="computed",
            computed_guarantee="candidate_point",
            guarantee_disposition="requested_claim_not_satisfied",
            overall_disposition="requested_claim_not_satisfied",
        )
    )

    assert relation.guarantee_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"
    assert relation.alpha_status == "not_established"
    assert relation.profile_status == "not_established"


def test_matching_typed_scope_stays_unknown_without_source_and_row_order_evidence() -> None:
    relation = DirectMethodExecutionHTETargetRelation.model_validate(
        _target_relation_payload(
            requested_scope_status="declared",
            requested_scope="selected_evaluation_rows",
            computed_scope_status="recomputed",
            computed_scope="selected_evaluation_rows",
        )
    )

    assert relation.scope_disposition == "not_established"
    assert relation.overall_disposition == "not_established"


@pytest.mark.parametrize(
    "method_fqn",
    [
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ],
)
def test_returned_refusal_preserves_estimator_drift(method_fqn: str) -> None:
    evidence = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence["estimator_after_n_jobs"] = 2

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "returned"
    assert admitted.estimator_after_n_jobs == 2


@pytest.mark.parametrize(
    "method_fqn",
    [
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ],
)
def test_returned_refusal_preserves_non_one_effective_jobs(
    method_fqn: str,
) -> None:
    evidence = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    evidence["joblib_entry_effective_jobs"] = 2

    admitted = DirectMethodExecutionHTEResourceEvidence.model_validate(evidence)

    assert admitted.execution_status == "returned"
    assert admitted.joblib_entry_effective_jobs == 2


def _identity_ref(kind: str, artifact_char: str, profile_char: str = "b") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + artifact_char * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile_char * 64,
    )


def _direct_selection_with_search_binding(
    *,
    summary_binding_updates: dict[str, object] | None = None,
    context_binding_updates: dict[str, object] | None = None,
    summary_source_ref: ArtifactRef | None = None,
    summary_schema_version: str = "1.0",
) -> DirectMethodExecutionSelection:
    method_fqn = "causal.hte.causal_forest@2.0.0"
    binding_ref = _identity_ref("scientist.search.uncertainty_task_binding", "a")
    context_binding_payload = {
        **binding_ref.model_dump(mode="json"),
        **(context_binding_updates or {}),
    }
    context_binding_ref = SelectedArtifactRef.model_validate(
        context_binding_payload,
        strict=True,
    )
    context = OwnedHTERequestContextV1(
        request_estimand_status="declared",
        request_estimand="mean_effect_over_selected_x",
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="declared",
        outcome_variable_id="outcome.effect",
        treatment_variable_status="declared",
        treatment_variable_id="treatment.policy",
        contrast_status="declared",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="not_established",
        search_uncertainty_task_binding_ref=context_binding_ref,
    )
    input_ref = _identity_ref("ir.observation_method_input", "7")
    anchor_ref = OwnedAttemptAnchorRef.model_validate(
        _identity_ref("runtime.owned_attempt_anchor", "c").model_dump(mode="python"),
        strict=True,
    )
    hte_outcome_ref = _identity_ref("ir.hte_outcome", "d")
    point_result_ref = _identity_ref("ir.hte_point_result", "e")
    policy_ref = _identity_ref("runtime.observational_input_resource_policy", "9")
    method_result_ref = _identity_ref("scientist.method_result.causal.hte", "1")
    method_evidence_ref = _identity_ref("scientist.method_evidence", "2")
    resource = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    resource["owner_policy_ref"] = policy_ref.model_dump(mode="json")
    summary_payload = _numeric_summary_payload(resource)
    summary_payload.update(
        {
            "schema_version": summary_schema_version,
            "owned_attempt_anchor_ref": anchor_ref.model_dump(mode="json"),
            "hte_outcome_ref": hte_outcome_ref.model_dump(mode="json"),
            "point_result_ref": point_result_ref.model_dump(mode="json"),
            "method_result_ref": method_result_ref.model_dump(mode="json"),
            "method_evidence_ref": method_evidence_ref.model_dump(mode="json"),
            "source_data_ref": (summary_source_ref or input_ref).model_dump(mode="json"),
            "search_uncertainty_task_binding_ref": {
                **binding_ref.model_dump(mode="json"),
                **(summary_binding_updates or {}),
            },
            "request_estimand_status": "declared",
            "request_estimand": context.request_estimand,
            "request_target_scope_status": "declared",
            "request_target_scope": context.request_target_scope,
            "outcome_variable_status": "declared",
            "outcome_variable_id": context.outcome_variable_id,
            "treatment_variable_status": "declared",
            "treatment_variable_id": context.treatment_variable_id,
            "request_contrast_status": "declared",
            "control_value": context.control_value,
            "treated_value": context.treated_value,
            "request_alpha_status": "declared",
            "requested_alpha": context.requested_alpha,
            "target_relation": {
                "requested_scope_status": "declared",
                "requested_scope": "selected_evaluation_rows",
                "requested_guarantee_status": "not_established",
                "requested_guarantee": None,
                "computed_scope_status": "recomputed",
                "computed_scope": "selected_evaluation_rows",
                "computed_guarantee_status": "computed",
                "computed_guarantee": "candidate_point",
                "source_content_status": "content_bound",
                "row_order_status": "recomputed",
                "contrast_status": "not_established",
                "estimand_status": "not_established",
                "alpha_status": "not_established",
                "profile_status": "qualified",
                "scope_disposition": "satisfied",
                "guarantee_disposition": "not_established",
                "overall_disposition": "not_established",
            },
        }
    )
    summary = DirectMethodExecutionHTESummary.model_validate(
        summary_payload,
        strict=True,
    )
    return DirectMethodExecutionSelection(
        job_id="job-identity",
        run_id="run-identity",
        attempt=1,
        requested_source_ref=input_ref,
        observational_run_intent_ref=_identity_ref("runtime.observational_run_intent", "3"),
        content_admitted_intent_ref=_identity_ref(
            "runtime.content_admitted_observational_run_intent", "4"
        ),
        resource_policy_ref=policy_ref,
        submitted_input_ref=input_ref,
        effective_input_ref=input_ref,
        method_result_ref=method_result_ref,
        method_evidence_ref=method_evidence_ref,
        owned_attempt_anchor_ref=anchor_ref,
        hte_outcome_ref=hte_outcome_ref,
        point_result_ref=point_result_ref,
        contract_target_id="foundry.causal.hte_observational_data.v1",
        contract_target=("polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"),
        method_fqn=method_fqn,
        method_version="2.0.0",
        method_abi_digest="a" * 64,
        method_build_digest="b" * 64,
        method_build_digest_scope="class_source_only",
        resource_policy_digest="c" * 64,
        source_protocol="method_input_envelope_v1",
        normalization="canonical_passthrough",
        limitations=_expected_content_admitted_limitations(
            "method_input_envelope_v1",
            source_access_revalidation_status=None,
        ),
        method_dispatch_binding_status="recomputed",
        owned_hte_request_context=context,
        hte=summary,
    )


def test_direct_selection_search_binding_join_uses_complete_identity_across_ref_types() -> None:
    selection = _direct_selection_with_search_binding()

    assert selection.hte is not None
    assert selection.owned_hte_request_context is not None
    summary_ref = selection.hte.search_uncertainty_task_binding_ref
    context_ref = selection.owned_hte_request_context.search_uncertainty_task_binding_ref
    assert type(summary_ref) is ArtifactRef
    assert type(context_ref) is SelectedArtifactRef
    assert artifact_ref_identity_key(summary_ref) == artifact_ref_identity_key(context_ref)


@pytest.mark.parametrize(
    ("summary_binding_updates", "expected_error"),
    [
        (
            {"artifact_id": "sha256:" + "0" * 64},
            "direct_method_execution_hte_summary_request_context_mismatch",
        ),
        (
            {"manifest_profile_sha256": "sha256:" + "f" * 64},
            "direct_method_execution_hte_summary_request_context_mismatch",
        ),
        (
            {"kind": "scientist.search.other_binding"},
            "direct_method_hte_summary_search_binding_ref_invalid",
        ),
        (
            {"media_type": "application/octet-stream"},
            "direct_method_hte_summary_search_binding_ref_invalid",
        ),
    ],
)
def test_direct_selection_search_binding_join_rejects_nonidentical_or_invalid_summary_ref(
    summary_binding_updates: dict[str, object],
    expected_error: str,
) -> None:
    with pytest.raises(ValidationError, match=expected_error):
        _direct_selection_with_search_binding(summary_binding_updates=summary_binding_updates)


@pytest.mark.parametrize(
    "context_binding_updates",
    [
        {"manifest_profile_sha256": "sha256:" + "f" * 64},
        {"artifact_id": "sha256:" + "0" * 64},
        {"kind": "scientist.search.other_binding"},
        {"media_type": "application/octet-stream"},
    ],
)
def test_direct_selection_search_binding_join_rejects_invalid_context_ref(
    context_binding_updates: dict[str, object],
) -> None:
    expected_error = (
        "owned_attempt_search_binding_ref_kind_mismatch"
        if "kind" in context_binding_updates or "media_type" in context_binding_updates
        else "direct_method_execution_hte_summary_request_context_mismatch"
    )
    with pytest.raises(ValidationError, match=expected_error):
        _direct_selection_with_search_binding(context_binding_updates=context_binding_updates)


def test_direct_selection_search_binding_join_keeps_summary_schema_gate() -> None:
    with pytest.raises(ValidationError):
        _direct_selection_with_search_binding(summary_schema_version="2.0")


def test_direct_selection_search_binding_join_keeps_caller_source_ref_gate() -> None:
    with pytest.raises(
        ValidationError,
        match="direct_method_execution_hte_summary_selection_mismatch",
    ):
        _direct_selection_with_search_binding(
            summary_source_ref=_identity_ref("ir.observation_method_input", "8")
        )
