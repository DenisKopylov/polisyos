"""Semantic tests for successor HTE point and native-interval artifacts."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.causal import CausalMethod
from polisyos.ir.analytics.hte import (
    ATEInferenceBasis,
    ATEInferenceBasisRef,
    HTEInputSourceRef,
    HTEIntervalOutcome,
    HTEOutcome,
    HTEPhysicalSourceMaterializationBindingRef,
    HTEPointEstimate,
    HTEPointResult,
    HTERefusalDiagnosticRef,
    HTERefusalOutcome,
    HTEResourceExecutionEvidenceV1,
    HTEResourcePolicyRef,
    HTEResult,
    HTEResultEvidenceRef,
    HTETargetRelationV1,
    MethodExecutionEvidenceRef,
    MethodResultEvidenceRef,
    OwnedAttemptAnchorRef,
    load_ate_inference_basis,
    load_hte_result_v2,
    persist_ate_inference_basis,
    persist_hte_result_v2,
)
from polisyos.ir.artifacts import ArtifactID, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec


def _profiled_ref(ref_type: type, value: int, *, kind: str | None = None):
    payload = {
        "artifact_id": ArtifactID.from_sha256_hex(f"{value:064x}"),
        "manifest_profile_sha256": f"sha256:{value + 1000:064x}",
    }
    if kind is not None:
        payload.update(kind=kind, media_type="application/json")
    return ref_type.model_validate(payload, strict=True)


def _returned_forest_resource() -> HTEResourceExecutionEvidenceV1:
    policy_ref = _profiled_ref(
        HTEResourcePolicyRef,
        1,
        kind="runtime.observational_input_resource_policy",
    )
    estimator_class = "econml.dml.causal_forest.CausalForestDML"
    estimator_params_sha256 = "a" * 64
    return HTEResourceExecutionEvidenceV1(
        owner_policy_ref=policy_ref,
        owner_policy_digest="b" * 64,
        owner_policy_schema_version="polisyos.runtime.observational_input_resource_policy.v5",
        owner_policy_revision="r5",
        owner_policy_method_fqn="causal.hte.causal_forest@2.0.0",
        owner_policy_method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        owner_policy_execution_scope="producer_scoped_joblib_parallelism_one",
        owner_policy_max_jobs=1,
        owner_policy_required_estimator_n_jobs=1,
        execution_status="returned",
        estimator_observation_status="recomputed",
        estimator_before_class_fqn=estimator_class,
        estimator_before_n_jobs=1,
        estimator_before_params_sha256=estimator_params_sha256,
        estimator_after_class_fqn=estimator_class,
        estimator_after_n_jobs=1,
        estimator_after_params_sha256=estimator_params_sha256,
        joblib_observation_status="recomputed",
        joblib_started=True,
        joblib_finished=True,
        joblib_exit_status="returned",
        joblib_profile_id="joblib.parallel_config.current_thread@1.0",
        joblib_profile_revision="1.0",
        joblib_implementation="joblib.parallel_config",
        joblib_implementation_version="1.5.3",
        joblib_scope="current_thread_joblib",
        joblib_max_jobs=1,
        joblib_entry_effective_jobs=1,
        joblib_entry_backend_fqn="joblib._parallel_backends.SequentialBackend",
        joblib_entry_config_sha256="5" * 64,
        joblib_entry_implementation_version="1.5.3",
        joblib_exit_effective_jobs=1,
        joblib_exit_backend_fqn="joblib._parallel_backends.SequentialBackend",
        joblib_exit_config_sha256="5" * 64,
        joblib_exit_implementation_version="1.5.3",
    )


def _returned_forest_refusal_resource() -> HTEResourceExecutionEvidenceV1:
    """Preserve returned joblib execution when refusal preceded estimator creation."""
    payload = _returned_forest_resource().model_dump(mode="json")
    payload.update(
        estimator_observation_status="not_established",
        estimator_before_class_fqn=None,
        estimator_before_n_jobs=None,
        estimator_before_params_sha256=None,
        estimator_after_class_fqn=None,
        estimator_after_n_jobs=None,
        estimator_after_params_sha256=None,
    )
    return HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)


def _returned_forest_unqualified_resource() -> HTEResourceExecutionEvidenceV1:
    """Retain an actual returned but unqualified joblib/estimator observation."""
    payload = _returned_forest_resource().model_dump(mode="json")
    payload.update(
        estimator_observation_status="recomputed",
        estimator_before_n_jobs=-1,
        estimator_after_n_jobs=-1,
        joblib_entry_effective_jobs=2,
        joblib_exit_effective_jobs=3,
        joblib_exit_backend_fqn="joblib._parallel_backends.ThreadingBackend",
        joblib_exit_config_sha256="6" * 64,
    )
    return HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)


def _point_result_with_resource(resource: HTEResourceExecutionEvidenceV1) -> HTEPointResult:
    return HTEPointResult(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        resolved_params_sha256="d" * 64,
        source_data_ref=_source_ref(),
        materialization_binding_ref=_materialization_binding_ref(),
        source_data_sha256="e" * 64,
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="e" * 64,
        selected_rows_sha256="f" * 64,
        selected_x_sha256="1" * 64,
        selected_row_order_sha256="2" * 64,
        n_selected_rows=2,
        point_estimate=2.0,
        cate_values=(1.0, 3.0),
        owned_attempt_anchor_ref=_profiled_ref(OwnedAttemptAnchorRef, 5),
        method_result_ref=_profiled_ref(MethodResultEvidenceRef, 6),
        method_evidence_ref=_profiled_ref(MethodExecutionEvidenceRef, 7),
        resource_evidence=resource,
    )


def _source_ref() -> HTEInputSourceRef:
    return _profiled_ref(
        HTEInputSourceRef,
        2,
        kind="ir.hte_observational_input",
    )


def _materialization_binding_ref() -> HTEPhysicalSourceMaterializationBindingRef:
    return _profiled_ref(
        HTEPhysicalSourceMaterializationBindingRef,
        9,
        kind="foundry.hte.physical_source_materialization_binding",
    )


def test_physical_materialization_ref_requires_selected_foundry_binding() -> None:
    """The ref cannot be replaced by an arbitrary kind or an unselected object."""
    selected = _materialization_binding_ref()
    assert selected.kind == "foundry.hte.physical_source_materialization_binding"
    assert selected.manifest_profile_sha256 is not None

    payload = selected.model_dump(mode="python")
    payload["manifest_profile_sha256"] = None
    with pytest.raises(ValidationError):
        HTEPhysicalSourceMaterializationBindingRef.model_validate(payload, strict=True)


def _legacy_hte_result() -> HTEResult:
    return HTEResult.from_estimates(
        method=CausalMethod.CAUSAL_FOREST,
        ate=2.0,
        ate_ci_lower=1.0,
        ate_ci_upper=3.0,
        confidence_level=0.95,
        cate_values=[1.0, 3.0],
        n_treated=1,
        n_control=1,
    )


def _returned_forest_dr_resource() -> HTEResourceExecutionEvidenceV1:
    """Return a native ForestDR receipt with its exact profile classes."""
    payload = _returned_forest_resource().model_dump(mode="python")
    estimator_class = "econml.dr._drlearner.ForestDRLearner"
    payload.update(
        owner_policy_method_fqn="causal.hte.forest_dr@2.0.0",
        owner_policy_method_profile_id="econml.forest_dr.native_mean@2.0",
        estimator_before_class_fqn=estimator_class,
        estimator_after_class_fqn=estimator_class,
    )
    return HTEResourceExecutionEvidenceV1.model_validate(payload, strict=True)


def _valid_native_basis(*, method: str = "causal.hte.causal_forest@2.0.0") -> ATEInferenceBasis:
    """Return a complete synthetic basis exercising a supported profile tuple."""
    is_forest_dr = method == "causal.hte.forest_dr@2.0.0"
    method_profile_id = (
        "econml.forest_dr.native_mean@2.0"
        if is_forest_dr
        else "econml.causal_forest_dml.native_mean@2.0"
    )
    estimator_class = (
        "econml.dr._drlearner.ForestDRLearner"
        if is_forest_dr
        else "econml.dml.causal_forest.CausalForestDML"
    )
    inference_class = (
        "econml.inference._inference.GenericModelFinalInferenceDiscrete"
        if is_forest_dr
        else "econml.dml.causal_forest._GenericSingleOutcomeModelFinalWithCovInference"
    )
    resource = _returned_forest_dr_resource() if is_forest_dr else _returned_forest_resource()
    target_relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="recomputed",
        profile_status="qualified",
        scope_disposition="satisfied",
        guarantee_disposition="satisfied",
        overall_disposition="not_established",
    )
    stderr_values = (0.1,)
    resolved_params = {"alpha": 0.05}

    def canonical_sha256(payload: object) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    return ATEInferenceBasis(
        inference_profile_id="econml_native_mean_over_selected_x@1.0",
        method_fqn=method,
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id=method_profile_id,
        estimator_class=estimator_class,
        inference_class=inference_class,
        econml_version="0.17.0",
        econml_source_profile_sha256=(
            "27b24c985f552585d38a3cd163301feb0f3755bf1e39c32c3abdbb1b865dba56"
        ),
        ate_inference_method="econml._cate_estimator.TreatmentExpansionMixin.ate_inference",
        conf_int_mean_method="econml.inference._inference.PopulationSummaryResults.conf_int_mean",
        native_result_class="econml.inference._inference.PopulationSummaryResults",
        inference_route="ate_inference.conf_int_mean",
        resolved_params_sha256=canonical_sha256({"params": resolved_params, "seed": 1}),
        source_data_sha256="e" * 64,
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="1" * 64,
        selected_rows_sha256="2" * 64,
        resolved_params=resolved_params,
        seed=1,
        fit_rows_sha256="3" * 64,
        eval_rows_sha256="3" * 64,
        fit_eval_relation="same_selected_rows",
        sample_ids_status="not_established",
        sample_ids_sha256=None,
        estimator_params_sha256=canonical_sha256({}),
        estimator_params={},
        nuisance_model_classes=(),
        alpha=0.05,
        confidence_level=0.95,
        native_point=1.0,
        native_lower_bound=0.5,
        native_upper_bound=1.5,
        native_mean_pred=1.0,
        native_mean_pred_stderr=0.1,
        native_stderr_mean=None,
        standard_error_source="mean_pred_stderr",
        standard_error_value=0.1,
        native_pred_stderr_values=stderr_values,
        selected_x_sha256="5" * 64,
        native_pred_sha256="6" * 64,
        native_pred_stderr_sha256=canonical_sha256(list(stderr_values)),
        selected_row_order_sha256="8" * 64,
        n_selected_rows=1,
        contrast_status="established",
        control_value=0.0,
        treated_value=1.0,
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="declared",
        request_target_scope="selected_evaluation_rows",
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        target_relation=target_relation,
        conditional_assumptions=("conditional model assumptions remain explicit",),
        source_data_ref=_source_ref(),
        materialization_binding_ref=_materialization_binding_ref(),
        invocation_basis_ref=None,
        invocation_basis_status="not_established",
        invocation_basis_reason="no_invocation_basis_artifact_contract",
        owned_attempt_anchor_ref=_profiled_ref(OwnedAttemptAnchorRef, 5),
        resource_evidence=resource,
        native_result_disposition="legacy_hte_result_admitted",
        native_result_disposition_reason=None,
        hte_result_ref=_profiled_ref(HTEResultEvidenceRef, 8),
        point_result_ref=None,
        method_result_ref=_profiled_ref(MethodResultEvidenceRef, 6),
        method_evidence_ref=_profiled_ref(MethodExecutionEvidenceRef, 7),
    )


def _population_request_relation() -> HTETargetRelationV1:
    return HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="population",
        requested_guarantee_status="declared",
        requested_guarantee="population_sampling_coverage",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="recomputed",
        profile_status="qualified",
        scope_disposition="requested_claim_not_satisfied",
        guarantee_disposition="requested_claim_not_satisfied",
        overall_disposition="requested_claim_not_satisfied",
    )


@pytest.mark.parametrize(
    "method",
    [
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ],
)
def test_native_basis_accepts_only_the_two_exact_registered_profile_tuples(method: str) -> None:
    """Both source-qualified routes pass with their own estimator/inference pair."""
    basis = _valid_native_basis(method=method)

    assert ATEInferenceBasis.model_validate(basis.model_dump(mode="python"), strict=True) == basis


@pytest.mark.parametrize(
    "method",
    [
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ],
)
def test_native_basis_profiled_cas_round_trip_for_each_supported_tuple(
    tmp_path,
    method: str,
) -> None:
    """A valid supported profile survives the ordinary persisted reader."""
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    basis = _valid_native_basis(method=method)

    ref = persist_ate_inference_basis(store, basis)

    assert load_ate_inference_basis(store, ref) == basis


@pytest.mark.parametrize(
    ("field", "forged_value"),
    [
        ("method_fqn", "causal.hte.forest_dr@2.0.0"),
        ("method_abi", "2.1.0"),
        ("method_profile_id", "econml.forest_dr.native_mean@2.0"),
        ("econml_version", "0.17.999-attacker"),
        ("econml_source_profile_sha256", "0" * 64),
        ("estimator_class", "attacker.ForgedEstimator"),
        ("inference_class", "attacker.ForgedInference"),
        ("ate_inference_method", "attacker.ForgedEstimator.ate_inference"),
        ("conf_int_mean_method", "attacker.ForgedResults.conf_int_mean"),
        ("native_result_class", "attacker.ForgedResults"),
        ("inference_route", "attacker.route"),
    ],
)
def test_native_basis_rejects_each_forged_persisted_profile_identity(
    tmp_path,
    field: str,
    forged_value: str,
) -> None:
    """Strict model and fresh CAS load reject identity edits with pinned digest intact."""
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    basis = _valid_native_basis()
    model_payload = basis.model_dump(mode="python")
    model_payload[field] = forged_value

    with pytest.raises(ValidationError):
        ATEInferenceBasis.model_validate(model_payload, strict=True)

    payload = basis.model_dump(mode="json")
    payload[field] = forged_value
    raw_ref = put_json_artifact(
        store,
        payload,
        kind="ir.ate_inference_basis",
        schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
        schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ref = ATEInferenceBasisRef.model_validate(raw_ref, strict=True)
    with pytest.raises(ValidationError):
        load_ate_inference_basis(store, ref)


def test_native_basis_rejects_coherently_forged_basis_and_resource_estimator_classes(
    tmp_path,
) -> None:
    """Changing both resource observations cannot cross-pair a different estimator."""
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path / "cas"))
    basis = _valid_native_basis()
    other_estimator = "econml.dr._drlearner.ForestDRLearner"
    model_payload = basis.model_dump(mode="python")
    model_payload["estimator_class"] = other_estimator
    model_payload["resource_evidence"]["estimator_before_class_fqn"] = other_estimator
    model_payload["resource_evidence"]["estimator_after_class_fqn"] = other_estimator

    with pytest.raises(ValidationError, match="native_inference_profile_identity_mismatch"):
        ATEInferenceBasis.model_validate(model_payload, strict=True)

    payload = basis.model_dump(mode="json")
    payload["estimator_class"] = other_estimator
    payload["resource_evidence"]["estimator_before_class_fqn"] = other_estimator
    payload["resource_evidence"]["estimator_after_class_fqn"] = other_estimator
    raw_ref = put_json_artifact(
        store,
        payload,
        kind="ir.ate_inference_basis",
        schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
        schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    ref = ATEInferenceBasisRef.model_validate(raw_ref, strict=True)
    with pytest.raises(ValidationError, match="native_inference_profile_identity_mismatch"):
        load_ate_inference_basis(store, ref)


def test_hte_result_v1_round_trips_as_the_native_interval_carrier(tmp_path) -> None:
    """The interval chain reuses the immutable, validated HTEResult v1 payload."""
    result = _legacy_hte_result()
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))

    ref = persist_hte_result_v2(store, result)
    loaded = load_hte_result_v2(store, ref)

    assert loaded == result
    assert ref.kind == "ir.hte_result"
    assert ref.manifest_profile_sha256 is not None


def test_hte_manifest_mapping_path_still_checks_selected_identity(tmp_path, monkeypatch) -> None:
    """A direct Mapping remains admitted only when its selected identity matches."""
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    basis = _valid_native_basis()
    ref = persist_ate_inference_basis(store, basis)
    manifest = store.get_manifest(ref.artifact_id)
    payload: dict[str, object] = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)

    original_get_manifest = type(store).get_manifest

    def mapping_manifest_for_target(_store: object, artifact_id: object) -> object:
        if artifact_id == ref.artifact_id:
            return payload
        return original_get_manifest(_store, artifact_id)

    monkeypatch.setattr(type(store), "get_manifest", mapping_manifest_for_target)
    assert load_ate_inference_basis(store, ref) == basis

    payload["kind"] = "ir.forged_inference_basis"
    with pytest.raises(ValueError, match="hte_selected_manifest_identity_mismatch"):
        load_ate_inference_basis(store, ref)


def test_hte_manifest_rejects_non_mapping_model_dump(tmp_path, monkeypatch) -> None:
    """A present manifest with a malformed dump fails closed instead of defaulting."""
    store = ensure_ir_artifact_store(FileSystemCAS(tmp_path))
    basis = _valid_native_basis()
    ref = persist_ate_inference_basis(store, basis)

    class MalformedManifest:
        def model_dump(self, **_kwargs: object) -> object:
            return ["schema", "not", "a", "mapping"]

    original_get_manifest = type(store).get_manifest

    def malformed_manifest_for_target(_store: object, artifact_id: object) -> object:
        if artifact_id == ref.artifact_id:
            return MalformedManifest()
        return original_get_manifest(_store, artifact_id)

    monkeypatch.setattr(type(store), "get_manifest", malformed_manifest_for_target)
    with pytest.raises(ValueError, match="hte_manifest_invalid"):
        load_ate_inference_basis(store, ref)


def test_hte_result_v1_still_rejects_an_interval_that_excludes_its_point() -> None:
    """The new native producer cannot bypass legacy HTEResult's interval law."""
    with pytest.raises(ValidationError, match="ate must lie inside ate_ci"):
        HTEResult.from_estimates(
            method=CausalMethod.CAUSAL_FOREST,
            ate=2.0,
            ate_ci_lower=0.0,
            ate_ci_upper=1.0,
            cate_values=[2.0],
        )


def test_returned_refusal_can_preserve_missing_estimator_without_numeric_promotion() -> None:
    """A refusal may preserve normal scope exit; numeric results still need an estimator."""
    refusal_resource = _returned_forest_refusal_resource()
    assert refusal_resource.execution_status == "returned"
    assert refusal_resource.joblib_exit_status == "returned"
    assert refusal_resource.estimator_observation_status == "not_established"

    with pytest.raises(
        ValidationError, match="numeric_hte_result_requires_stable_n_jobs_one_estimator"
    ):
        _point_result_with_resource(refusal_resource)


def test_returned_refusal_preserves_unqualified_measurements_but_point_is_rejected() -> None:
    """Observed resource drift remains visible without promoting a numeric result."""
    resource = _returned_forest_unqualified_resource()
    assert resource.execution_status == "returned"
    assert resource.estimator_before_n_jobs == resource.estimator_after_n_jobs == -1
    assert resource.joblib_entry_effective_jobs == 2
    assert resource.joblib_exit_effective_jobs == 3

    with pytest.raises(
        ValidationError, match="numeric_hte_result_requires_returned_one_job_profile"
    ):
        _point_result_with_resource(resource)


def test_returned_refusal_round_trip_keeps_joblib_context_drift() -> None:
    """A refusal artifact retains measured entry/exit drift without a numeric result."""
    resource = _returned_forest_unqualified_resource()
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="population",
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        computed_scope_status="not_established",
        computed_scope=None,
        computed_guarantee_status="not_established",
        computed_guarantee=None,
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="not_established",
        guarantee_disposition="not_established",
        overall_disposition="not_established",
    )
    source = _source_ref()
    refusal = HTERefusalOutcome(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        refusal_stage="fit",
        refusal_reason="method_execution_failed",
        diagnostic_code="hte_fit_failed",
        owned_attempt_anchor_ref=_profiled_ref(OwnedAttemptAnchorRef, 5),
        anchor_status="pre_output_anchor_resolved",
        requested_source_ref=source,
        requested_source_status="declared",
        source_data_ref=source,
        source_data_status="content_bound",
        materialization_binding_ref=_materialization_binding_ref(),
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="e" * 64,
        selected_rows_sha256="f" * 64,
        selected_x_sha256="1" * 64,
        selected_row_order_sha256="2" * 64,
        resolved_params_sha256="d" * 64,
        n_selected_rows=2,
        selected_rows_status="recomputed",
        method_result_ref=_profiled_ref(MethodResultEvidenceRef, 6),
        method_result_status="available",
        method_evidence_ref=_profiled_ref(MethodExecutionEvidenceRef, 7),
        method_evidence_status="available",
        resource_evidence=resource,
        invocation_basis_ref=None,
        invocation_basis_status="not_established",
        invocation_basis_reason="not_available_at_refusal_stage",
        refusal_diagnostic_ref=_profiled_ref(HTERefusalDiagnosticRef, 8),
        request_estimand_status="not_established",
        request_estimand=None,
        request_target_scope_status="declared",
        request_target_scope="population",
        outcome_variable_status="not_established",
        outcome_variable_id=None,
        treatment_variable_status="not_established",
        treatment_variable_id=None,
        contrast_status="not_established",
        control_value=None,
        treated_value=None,
        request_alpha_status="not_established",
        requested_alpha=None,
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        target_relation=relation,
        limitations=("resource_profile_not_qualified",),
    )

    loaded = HTEOutcome.model_validate_json(
        json.dumps(refusal.model_dump(mode="json")), strict=True
    )
    assert loaded.root.resource_evidence.joblib_entry_effective_jobs == 2
    assert loaded.root.resource_evidence.joblib_exit_effective_jobs == 3
    assert (
        loaded.root.resource_evidence.joblib_exit_backend_fqn
        == "joblib._parallel_backends.ThreadingBackend"
    )


def test_refusal_outcome_preserves_returned_resource_without_success_artifacts() -> None:
    """A typed method refusal can retain owner facts without fabricated numeric refs."""
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="population",
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        computed_scope_status="not_established",
        computed_scope=None,
        computed_guarantee_status="not_established",
        computed_guarantee=None,
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="not_established",
        guarantee_disposition="not_established",
        overall_disposition="not_established",
    )
    source = _source_ref()
    refusal = HTERefusalOutcome(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        refusal_stage="prepare",
        refusal_reason="required_input_unavailable",
        diagnostic_code="contrast_not_established",
        owned_attempt_anchor_ref=_profiled_ref(OwnedAttemptAnchorRef, 5),
        anchor_status="pre_output_anchor_resolved",
        requested_source_ref=source,
        requested_source_status="declared",
        source_data_ref=source,
        source_data_status="content_bound",
        materialization_binding_ref=_materialization_binding_ref(),
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="e" * 64,
        selected_rows_sha256="f" * 64,
        selected_x_sha256="1" * 64,
        selected_row_order_sha256="2" * 64,
        resolved_params_sha256="d" * 64,
        n_selected_rows=2,
        selected_rows_status="recomputed",
        method_result_ref=_profiled_ref(MethodResultEvidenceRef, 6),
        method_result_status="available",
        method_evidence_ref=_profiled_ref(MethodExecutionEvidenceRef, 7),
        method_evidence_status="available",
        resource_evidence=_returned_forest_refusal_resource(),
        invocation_basis_ref=None,
        invocation_basis_status="not_established",
        invocation_basis_reason="not_available_at_refusal_stage",
        refusal_diagnostic_ref=_profiled_ref(HTERefusalDiagnosticRef, 8),
        request_estimand_status="declared",
        request_estimand="requested_candidate_estimand",
        request_target_scope_status="declared",
        request_target_scope="population",
        outcome_variable_status="declared",
        outcome_variable_id="outcome.y",
        treatment_variable_status="declared",
        treatment_variable_id="treatment.t",
        contrast_status="established",
        control_value=0.0,
        treated_value=1.0,
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        target_relation=relation,
        limitations=("no_effect_estimate_published",),
    )

    loaded = HTEOutcome.model_validate_json(
        json.dumps(refusal.model_dump(mode="json")), strict=True
    )

    assert loaded.kind == "refusal"
    assert loaded.root.resource_evidence.execution_status == "returned"
    assert loaded.root.resource_evidence.estimator_observation_status == "not_established"


def test_interval_outcome_reuses_legacy_result_and_preserves_unmet_population_request() -> None:
    """A fitted-row HTEResult interval cannot imply population coverage."""
    outcome = HTEIntervalOutcome(
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_abi="2.0.0",
        method_abi_digest="c" * 64,
        method_profile_id="econml.causal_forest_dml.native_mean@2.0",
        input_profile_id="all_source_rows_in_input_order@1.0",
        selected_input_sha256="e" * 64,
        selected_rows_sha256="f" * 64,
        selected_x_sha256="1" * 64,
        selected_row_order_sha256="2" * 64,
        resolved_params_sha256="d" * 64,
        n_selected_rows=2,
        source_data_ref=_source_ref(),
        materialization_binding_ref=_materialization_binding_ref(),
        invocation_basis_ref=None,
        invocation_basis_status="not_established",
        invocation_basis_reason="no_invocation_basis_artifact_contract",
        owned_attempt_anchor_ref=_profiled_ref(OwnedAttemptAnchorRef, 5),
        resource_evidence=_returned_forest_resource(),
        method_result_ref=_profiled_ref(MethodResultEvidenceRef, 6),
        method_evidence_ref=_profiled_ref(MethodExecutionEvidenceRef, 7),
        request_estimand_status="declared",
        request_estimand="owner_requested_estimand_candidate",
        request_target_scope_status="declared",
        request_target_scope="population",
        outcome_variable_status="declared",
        outcome_variable_id="outcome_y",
        treatment_variable_status="declared",
        treatment_variable_id="treatment_x",
        request_alpha_status="declared",
        requested_alpha=0.05,
        requested_guarantee_status="declared",
        requested_guarantee="population_sampling_coverage",
        contrast_status="established",
        control_value=0.0,
        treated_value=1.0,
        target_relation=_population_request_relation(),
        limitations=(
            "selected_rows_do_not_establish_population_coverage",
            "source_variable_identity_not_established",
        ),
        point_estimate=HTEPointEstimate(
            value=2.0,
            measure_unit_status="not_established",
            measure_unit=None,
        ),
        lower_bound=1.0,
        upper_bound=3.0,
        confidence_level=0.95,
        interval_semantics="native_mean_confidence_interval",
        inference_status="native_ate_inference_validated",
        hte_result_ref=_profiled_ref(HTEResultEvidenceRef, 8),
        inference_basis_ref=_profiled_ref(ATEInferenceBasisRef, 4),
    )

    loaded = HTEOutcome.model_validate_json(
        json.dumps(outcome.model_dump(mode="json")), strict=True
    )

    assert loaded.kind == "interval_estimate"
    assert loaded.root.point_estimate.value == 2.0
    assert (loaded.root.lower_bound, loaded.root.upper_bound) == (1.0, 3.0)
    assert loaded.root.target_relation.estimand_status == "not_established"
    assert loaded.root.target_relation.overall_disposition == "requested_claim_not_satisfied"
    assert "source_variable_identity_not_established" in loaded.root.limitations

    excluded_point = loaded.model_dump(mode="python")
    excluded_point["lower_bound"] = 2.5
    with pytest.raises(ValidationError, match="point-containment"):
        HTEOutcome.model_validate(excluded_point, strict=True)


@pytest.mark.parametrize(
    ("requested_scope", "expected_scope"),
    [
        ("selected_evaluation_rows", "satisfied"),
        ("population", "requested_claim_not_satisfied"),
        ("custom_cohort", "not_established"),
    ],
)
@pytest.mark.parametrize(
    ("requested_guarantee", "expected_guarantee"),
    [
        ("candidate_point", "requested_claim_not_satisfied"),
        ("backend_conditional_interval", "satisfied"),
        ("population_sampling_coverage", "requested_claim_not_satisfied"),
    ],
)
def test_target_relation_uses_three_valued_scope_guarantee_composition(
    requested_scope: str,
    expected_scope: str,
    requested_guarantee: str,
    expected_guarantee: str,
) -> None:
    """Known request mismatches survive an unknown source-variable binding."""
    has_known_mismatch = "requested_claim_not_satisfied" in {
        expected_scope,
        expected_guarantee,
    }
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope=requested_scope,
        requested_guarantee_status="declared",
        requested_guarantee=requested_guarantee,
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="recomputed",
        profile_status="qualified",
        scope_disposition=expected_scope,
        guarantee_disposition=expected_guarantee,
        overall_disposition=(
            "requested_claim_not_satisfied" if has_known_mismatch else "not_established"
        ),
    )

    assert relation.estimand_status == "not_established"
    assert relation.overall_disposition == (
        "requested_claim_not_satisfied" if has_known_mismatch else "not_established"
    )


def test_known_population_scope_mismatch_survives_unknown_source_and_row_order() -> None:
    """A known population-versus-selected-rows mismatch outranks unrelated unknowns."""
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="population",
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="not_established",
        computed_guarantee=None,
        source_content_status="not_established",
        row_order_status="not_established",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="requested_claim_not_satisfied",
        guarantee_disposition="not_established",
        overall_disposition="requested_claim_not_satisfied",
    )

    assert relation.scope_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"


def test_unknown_scope_and_guarantee_stay_not_established_without_mismatch() -> None:
    """Unknown request axes do not become either satisfied or mismatched."""
    relation = HTETargetRelationV1(
        requested_scope_status="not_established",
        requested_scope=None,
        requested_guarantee_status="not_established",
        requested_guarantee=None,
        computed_scope_status="not_established",
        computed_scope=None,
        computed_guarantee_status="not_established",
        computed_guarantee=None,
        source_content_status="not_established",
        row_order_status="not_established",
        contrast_status="not_established",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="not_established",
        guarantee_disposition="not_established",
        overall_disposition="not_established",
    )

    assert relation.scope_disposition == "not_established"
    assert relation.guarantee_disposition == "not_established"
    assert relation.overall_disposition == "not_established"


def test_unbound_source_identity_cannot_be_promoted_by_serialized_status() -> None:
    """A matching request cannot self-assert a missing source-variable binding."""
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="recomputed",
        profile_status="qualified",
        scope_disposition="satisfied",
        guarantee_disposition="satisfied",
        overall_disposition="not_established",
    )

    assert relation.scope_disposition == "satisfied"
    assert relation.guarantee_disposition == "satisfied"
    assert relation.overall_disposition == "not_established"

    bound_payload = relation.model_dump(mode="python")
    bound_payload.update(estimand_status="recomputed", overall_disposition="satisfied")
    with pytest.raises(ValidationError, match="estimand_status"):
        HTETargetRelationV1.model_validate(bound_payload, strict=True)


def test_known_guarantee_mismatch_survives_unknown_alpha_and_source_identity() -> None:
    """A claim mismatch remains known even when unrelated predicates are unknown."""
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="population_sampling_coverage",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="backend_conditional_interval",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="qualified",
        scope_disposition="satisfied",
        guarantee_disposition="requested_claim_not_satisfied",
        overall_disposition="requested_claim_not_satisfied",
    )

    assert relation.guarantee_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"


def test_point_only_output_records_known_interval_guarantee_mismatch() -> None:
    """A computed point output cannot satisfy a declared interval request."""
    relation = HTETargetRelationV1(
        requested_scope_status="declared",
        requested_scope="selected_evaluation_rows",
        requested_guarantee_status="declared",
        requested_guarantee="backend_conditional_interval",
        computed_scope_status="recomputed",
        computed_scope="selected_evaluation_rows",
        computed_guarantee_status="computed",
        computed_guarantee="candidate_point",
        source_content_status="content_bound",
        row_order_status="recomputed",
        contrast_status="recomputed",
        estimand_status="not_established",
        alpha_status="not_established",
        profile_status="not_established",
        scope_disposition="satisfied",
        guarantee_disposition="requested_claim_not_satisfied",
        overall_disposition="requested_claim_not_satisfied",
    )

    assert relation.guarantee_disposition == "requested_claim_not_satisfied"
    assert relation.overall_disposition == "requested_claim_not_satisfied"
