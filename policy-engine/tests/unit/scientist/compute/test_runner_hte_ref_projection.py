from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypeVar, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.contracts.runtime import DirectMethodExecutionHTESummary
    from polisyos.ir.analytics.hte import HTEFinalizedArtifactRefs
    from polisyos.scientist.compute.runner import (
        MethodExecutionRefOutcome,
        _RuntimeHTEFinalizedArtifactRefs,
    )

_TestModel = TypeVar("_TestModel", bound=BaseModel)


def _ref(model_type: type[_TestModel], seed: int, *, kind: str | None = None) -> _TestModel:
    """Build one selected IR ref with a unique content/profile identity."""
    if kind is None:
        field = model_type.model_fields.get("kind")
        if (
            field is None
            or get_origin(field.annotation) is not Literal
            or type(field.default) is not str
            or field.default not in get_args(field.annotation)
        ):
            raise ValueError("test_reference_kind_required")
        selected_kind = field.default
    elif type(kind) is str and kind:
        selected_kind = kind
    else:
        raise ValueError("test_reference_kind_invalid")
    payload = {
        "artifact_id": "sha256:" + f"{seed:064x}",
        "kind": selected_kind,
        "media_type": "application/json",
        "manifest_profile_sha256": "sha256:" + f"{seed + 100:064x}",
    }
    return model_type.model_validate(payload, strict=True)


def test_generic_ref_helper_requires_an_explicit_kind() -> None:
    from polisyos.ir.registry.refs import ArtifactRefModel

    with pytest.raises(ValueError, match="test_reference_kind_required"):
        _ref(ArtifactRefModel, 8)


def _refs_for_variant(
    variant: str, *, include_invocation_basis: bool = True
) -> HTEFinalizedArtifactRefs:
    """Construct one legal complete HTE ref set for each persisted outcome variant."""
    from polisyos.ir.analytics.hte import HTEFinalizedArtifactRefs
    from polisyos.ir.registry.refs import (
        ArtifactRefModel,
        ATEInferenceBasisRef,
        HTEOutcomeRef,
        HTEPhysicalSourceMaterializationBindingRef,
        HTEPointResultRef,
        HTERefusalDiagnosticRef,
        HTEResultEvidenceRef,
        OwnedAttemptAnchorRef,
    )

    if variant not in {"point", "interval", "refusal"}:
        raise ValueError(variant)
    return HTEFinalizedArtifactRefs(
        owned_attempt_anchor_ref=_ref(OwnedAttemptAnchorRef, 1),
        materialization_binding_ref=_ref(HTEPhysicalSourceMaterializationBindingRef, 2),
        hte_outcome_ref=_ref(HTEOutcomeRef, 3),
        point_result_ref=_ref(HTEPointResultRef, 4) if variant == "point" else None,
        hte_result_ref=_ref(HTEResultEvidenceRef, 5) if variant == "interval" else None,
        inference_basis_ref=_ref(ATEInferenceBasisRef, 6) if variant == "interval" else None,
        refusal_diagnostic_ref=_ref(HTERefusalDiagnosticRef, 7) if variant == "refusal" else None,
        # Generic transport only; this synthetic kind asserts no producer or authority contract.
        invocation_basis_ref=(
            _ref(ArtifactRefModel, 8, kind="test.generic_transport_reference")
            if include_invocation_basis
            else None
        ),
    )


@pytest.mark.parametrize(
    ("variant", "null_fields"),
    [
        (
            "point",
            ("hte_result_ref", "inference_basis_ref", "refusal_diagnostic_ref"),
        ),
        (
            "interval",
            ("point_result_ref", "refusal_diagnostic_ref"),
        ),
        (
            "refusal",
            ("point_result_ref", "hte_result_ref", "inference_basis_ref"),
        ),
    ],
)
def test_core_projection_preserves_the_complete_hte_ref_set_and_nullable_roles(
    variant: str,
    null_fields: tuple[str, ...],
) -> None:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorRef as CoreOwnedAttemptAnchorRef,
    )
    from polisyos.scientist.compute.runner import _normalize_hte_finalized_artifact_refs

    source = _refs_for_variant(variant)
    projected = _normalize_hte_finalized_artifact_refs(source)

    assert type(projected.owned_attempt_anchor_ref) is CoreOwnedAttemptAnchorRef
    for field in (
        "materialization_binding_ref",
        "hte_outcome_ref",
        "point_result_ref",
        "hte_result_ref",
        "inference_basis_ref",
        "refusal_diagnostic_ref",
        "invocation_basis_ref",
    ):
        source_ref = getattr(source, field)
        projected_ref = getattr(projected, field)
        if field in null_fields:
            assert source_ref is None
            assert projected_ref is None
            continue
        assert source_ref is not None
        assert type(projected_ref) is CoreArtifactRef
        assert projected_ref.model_dump(mode="json") == source_ref.model_dump(mode="json")
        assert projected_ref.manifest_profile_sha256 == source_ref.manifest_profile_sha256


@pytest.mark.parametrize(
    ("field", "updates"),
    [
        ("hte_outcome_ref", {"kind": "ir.counterfeit_hte_outcome"}),
        ("hte_outcome_ref", {"manifest_profile_sha256": None}),
    ],
)
def test_core_projection_revalidates_selected_role_profiles_and_kinds(
    field: str,
    updates: dict[str, object],
) -> None:
    from polisyos.scientist.compute.runner import _normalize_hte_finalized_artifact_refs

    source = _refs_for_variant("point")
    bad_ref = getattr(source, field).model_copy(update=updates)
    bad_bundle = source.model_copy(update={field: bad_ref})

    with pytest.raises((TypeError, ValueError, ValidationError)):
        _normalize_hte_finalized_artifact_refs(bad_bundle)


def test_core_projection_preserves_identity_without_claiming_summary_binding() -> None:
    from polisyos.ir.registry.refs import HTEOutcomeRef
    from polisyos.scientist.compute.runner import _normalize_hte_finalized_artifact_refs

    source = _refs_for_variant("point")
    changed_id = "sha256:" + "f" * 64
    changed_payload = source.hte_outcome_ref.model_dump(mode="json")
    changed_payload["artifact_id"] = changed_id
    changed_ref = HTEOutcomeRef.model_validate(changed_payload, strict=True)
    changed_bundle = source.model_copy(update={"hte_outcome_ref": changed_ref})

    projected = _normalize_hte_finalized_artifact_refs(changed_bundle)

    # The JSON projection preserves the source identity exactly. Runtime still
    # binds this ref to the independently projected summary at outcome creation.
    assert str(projected.hte_outcome_ref.artifact_id) == changed_id


@pytest.mark.parametrize(
    "changes",
    [
        {"point_result_ref": None},
        {"hte_outcome_ref": "not-an-ir-reference"},
    ],
)
def test_core_projection_revalidates_the_bundle_role_set_before_projection(
    changes: dict[str, object],
) -> None:
    from polisyos.scientist.compute.runner import _normalize_hte_finalized_artifact_refs

    source = _refs_for_variant("point")
    unvalidated_copy = source.model_copy(update=changes)

    with pytest.raises((TypeError, ValueError, ValidationError)):
        _normalize_hte_finalized_artifact_refs(unvalidated_copy)


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


def _core_ref(kind: str, seed: int) -> CoreArtifactRef:
    from polisyos.core.artifacts import ArtifactRef

    return ArtifactRef.model_validate(
        {
            "artifact_id": "sha256:" + f"{seed:064x}",
            "kind": kind,
            "media_type": "application/json",
            "manifest_profile_sha256": "sha256:" + f"{seed + 300:064x}",
        },
        strict=True,
    )


def _summary_for(
    projected: _RuntimeHTEFinalizedArtifactRefs,
) -> DirectMethodExecutionHTESummary:
    from polisyos.core.contracts.runtime import DirectMethodExecutionHTESummary

    method_fqn = "causal.hte.causal_forest@2.0.0"
    resource_evidence = _resource_evidence(
        method_fqn=method_fqn,
        execution_scope="producer_scoped_joblib_parallelism_one",
        execution_status="returned",
    )
    payload = _numeric_summary_payload(resource_evidence)
    payload.update(
        {
            "owned_attempt_anchor_ref": projected.owned_attempt_anchor_ref.model_dump(mode="json"),
            "hte_outcome_ref": projected.hte_outcome_ref.model_dump(mode="json"),
            "point_result_ref": (
                projected.point_result_ref.model_dump(mode="json")
                if projected.point_result_ref is not None
                else None
            ),
            "hte_result_ref": (
                projected.hte_result_ref.model_dump(mode="json")
                if projected.hte_result_ref is not None
                else None
            ),
            "inference_basis_ref": (
                projected.inference_basis_ref.model_dump(mode="json")
                if projected.inference_basis_ref is not None
                else None
            ),
            "refusal_diagnostic_ref": (
                projected.refusal_diagnostic_ref.model_dump(mode="json")
                if projected.refusal_diagnostic_ref is not None
                else None
            ),
            "materialization_binding_ref": projected.materialization_binding_ref.model_dump(
                mode="json"
            ),
            "method_result_ref": _core_ref("scientist.method_result.causal.hte", 11).model_dump(
                mode="json"
            ),
            "method_evidence_ref": _core_ref("scientist.method_evidence", 12).model_dump(
                mode="json"
            ),
        }
    )
    return DirectMethodExecutionHTESummary.model_validate(payload, strict=True)


def _consume_hte_refs(
    projected: _RuntimeHTEFinalizedArtifactRefs,
    summary: DirectMethodExecutionHTESummary,
) -> MethodExecutionRefOutcome:
    from polisyos.scientist.compute.runner import MethodExecutionRefOutcome

    return MethodExecutionRefOutcome(
        job_id="job-hte-ref-projection",
        run_id="run-hte-ref-projection",
        attempt=1,
        requested_source_ref=_core_ref("foundry.data_snapshot", 21),
        observational_run_intent_ref=_core_ref("scientist.observational_run_intent", 22),
        content_admitted_intent_ref=_core_ref("scientist.content_admitted_intent", 23),
        submitted_input_ref=_core_ref("scientist.method_input", 24),
        effective_input_ref=_core_ref("scientist.method_input", 25),
        method_result_ref=summary.method_result_ref,
        method_evidence_ref=summary.method_evidence_ref,
        resource_policy_ref=_core_ref("runtime.observational_input_resource_policy", 26),
        method_fqn="causal.hte.causal_forest@2.0.0",
        method_version="2.0.0",
        method_abi_digest="a" * 64,
        method_build_digest="b" * 64,
        method_build_digest_scope="class_source_only",
        resource_policy_digest="c" * 64,
        source_protocol="legacy_hte_json_v1",
        normalization="canonical_passthrough",
        limitations=(),
        method_dispatch_binding_status="recomputed",
        candidate_outcome=None,
        owned_attempt_anchor_ref=projected.owned_attempt_anchor_ref,
        hte_outcome_ref=projected.hte_outcome_ref,
        point_result_ref=projected.point_result_ref,
        hte_result_ref=projected.hte_result_ref,
        inference_basis_ref=projected.inference_basis_ref,
        refusal_diagnostic_ref=projected.refusal_diagnostic_ref,
        invocation_basis_ref=projected.invocation_basis_ref,
        hte_summary=summary,
    )


def test_runtime_consumer_binds_refs_and_accepts_absent_invocation_basis() -> None:
    from polisyos.ir.registry.refs import HTEOutcomeRef
    from polisyos.scientist.compute.runner import _normalize_hte_finalized_artifact_refs

    source = _refs_for_variant("point", include_invocation_basis=False)
    original_projection = _normalize_hte_finalized_artifact_refs(source)
    summary = _summary_for(original_projection)
    original_outcome = _consume_hte_refs(original_projection, summary)

    assert original_outcome.invocation_basis_ref is None
    assert original_outcome.hte_outcome_ref == summary.hte_outcome_ref

    changed_id = "sha256:" + "f" * 64
    changed_payload = source.hte_outcome_ref.model_dump(mode="json")
    changed_payload["artifact_id"] = changed_id
    changed_ref = HTEOutcomeRef.model_validate(changed_payload, strict=True)
    changed_source = source.model_copy(update={"hte_outcome_ref": changed_ref})
    changed_projection = _normalize_hte_finalized_artifact_refs(changed_source)

    assert str(changed_projection.hte_outcome_ref.artifact_id) == changed_id
    with pytest.raises(ValueError, match="method_execution_hte_outcome_summary_invalid"):
        _consume_hte_refs(changed_projection, summary)


def test_artifact_ref_view_materializes_full_core_reference_identity_as_fresh_models() -> None:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.scientist.compute.runner import _ArtifactRefView

    # This synthetic transport reference makes no claim about an invocation-basis producer.
    source = _core_ref("test.generic_transport_reference", 31)
    view = _ArtifactRefView.capture(source)
    first = view.materialize()
    second = view.materialize()

    assert type(source) is CoreArtifactRef
    assert type(first) is CoreArtifactRef
    assert first is not source
    assert second is not source
    assert first is not second
    assert first.artifact_id is not source.artifact_id
    source_identity = (
        str(source.artifact_id),
        source.kind,
        source.media_type,
        source.manifest_profile_sha256,
    )
    for materialized in (first, second):
        assert (
            str(materialized.artifact_id),
            materialized.kind,
            materialized.media_type,
            materialized.manifest_profile_sha256,
        ) == source_identity


def test_artifact_ref_view_materializes_genuine_posterior_summary_owner_identity() -> None:
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryRef
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.compute.runner import _ArtifactRefView

    source = _ref(PosteriorSummaryRef, 32)
    assert type(source.artifact_id) is IRArtifactID

    view = _ArtifactRefView.capture(source)
    first = view.materialize_posterior_summary()
    second = view.materialize_posterior_summary()

    assert type(first) is PosteriorSummaryRef
    assert type(first.artifact_id) is IRArtifactID
    assert first is not source
    assert second is not source
    assert first is not second
    assert first.artifact_id is not source.artifact_id
    source_identity = (
        str(source.artifact_id),
        source.kind,
        source.media_type,
        source.manifest_profile_sha256,
    )
    for materialized in (first, second):
        assert (
            str(materialized.artifact_id),
            materialized.kind,
            materialized.media_type,
            materialized.manifest_profile_sha256,
        ) == source_identity


def test_artifact_ref_view_rejects_model_constructed_wrong_owner_id_pairs() -> None:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryRef
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.compute.runner import _ArtifactRefView

    profile = "sha256:" + "e" * 64
    wrong_owner_refs = (
        CoreArtifactRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=CoreArtifactID(profile),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
    )
    for ref in wrong_owner_refs:
        with pytest.raises(
            ValueError,
            match="method_execution_requires_full_profile_artifact_refs",
        ):
            _ArtifactRefView.capture(ref)


def test_artifact_ref_view_rejects_malformed_values_in_nominal_owner_ids() -> None:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryRef
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.compute.runner import _ArtifactRefView

    profile = "sha256:" + "f" * 64
    malformed_owner_refs = (
        CoreArtifactRef.model_construct(
            artifact_id=CoreArtifactID.model_construct(root="not-a-sha256-id"),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID.model_construct(root="not-a-sha256-id"),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
    )
    for ref in malformed_owner_refs:
        with pytest.raises(ValidationError):
            _ArtifactRefView.capture(ref)


def test_posterior_summary_ref_view_rejects_wrong_kind_media_type_and_profile() -> None:
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryRef
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.compute.runner import _ArtifactRefView

    profile = "sha256:" + "9" * 64
    wrong_kind = PosteriorSummaryRef.model_construct(
        artifact_id=IRArtifactID(profile),
        kind="ir.counterfeit_posterior_summary",
        media_type="application/json",
        manifest_profile_sha256=profile,
    )
    with pytest.raises(ValidationError):
        _ArtifactRefView.capture(wrong_kind)

    wrong_media_type = PosteriorSummaryRef.model_construct(
        artifact_id=IRArtifactID(profile),
        kind="ir.posterior_summary",
        media_type="text/plain",
        manifest_profile_sha256=profile,
    )
    with pytest.raises(ValidationError):
        _ArtifactRefView.capture(wrong_media_type)

    wrong_profile = PosteriorSummaryRef.model_construct(
        artifact_id=IRArtifactID(profile),
        kind="ir.posterior_summary",
        media_type="application/json",
        manifest_profile_sha256="sha256:NOT_LOWERCASE_HEX",
    )
    with pytest.raises(ValidationError):
        _ArtifactRefView.capture(wrong_profile)


def test_artifact_ref_capture_bounds_owner_state_before_serializing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import numpy as np

    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
    from polisyos.ir.analytics.posterior_summary import PosteriorSummaryRef
    from polisyos.ir.artifacts import ArtifactID as IRArtifactID
    from polisyos.scientist.compute.runner import _ArtifactRefView

    serializer_calls: list[str] = []
    core_serializer = CoreArtifactRef.model_dump_json
    posterior_serializer = PosteriorSummaryRef.model_dump_json

    def spy_core_serializer(ref: CoreArtifactRef) -> str:
        serializer_calls.append("core")
        return core_serializer(ref)

    def spy_posterior_serializer(ref: PosteriorSummaryRef) -> str:
        serializer_calls.append("posterior")
        return posterior_serializer(ref)

    monkeypatch.setattr(CoreArtifactRef, "model_dump_json", spy_core_serializer)
    monkeypatch.setattr(PosteriorSummaryRef, "model_dump_json", spy_posterior_serializer)

    valid_core = _core_ref("test.generic_transport_reference", 71)
    valid_posterior = _ref(PosteriorSummaryRef, 72)
    core_view = _ArtifactRefView.capture(valid_core)
    posterior_view = _ArtifactRefView.capture(valid_posterior)
    assert serializer_calls == ["core", "posterior"]
    assert core_view.materialize() == valid_core
    assert posterior_view.materialize_posterior_summary() == valid_posterior

    serializer_calls.clear()
    profile = "sha256:" + "a" * 64
    core_id_with_extra = CoreArtifactID.model_construct(root=profile)
    core_id_with_extra.__dict__["unmodeled_payload"] = np.ones(100_000)
    malformed_refs = (
        valid_core.model_copy(update={"kind": np.ones(100_000)}),
        valid_core.model_copy(update={"kind": "test.generic_transport_reference"}),
        valid_core.model_copy(update={"media_type": "m" * 256}),
        valid_core.model_copy(update={"manifest_profile_sha256": None}),
        valid_core.model_copy(update={"manifest_profile_sha256": "p" * 100_000}),
        CoreArtifactRef.model_construct(
            artifact_id=CoreArtifactID.model_construct(root=np.ones(100_000)),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        CoreArtifactRef.model_construct(
            artifact_id=CoreArtifactID.model_construct(root="sha256:" + "a" * 100_000),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        CoreArtifactRef.model_construct(
            artifact_id=CoreArtifactID.model_construct(root="not-a-sha256-id"),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        CoreArtifactRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        CoreArtifactRef.model_construct(
            artifact_id=core_id_with_extra,
            kind="test.generic_transport_reference",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID.model_construct(root=np.ones(100_000)),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID.model_construct(root="not-a-sha256-id"),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=CoreArtifactID(profile),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="ir.posterior_summary",
            media_type=np.ones(100_000),
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="ir.counterfeit_posterior_summary",
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="k" * 100_000,
            media_type="application/json",
            manifest_profile_sha256=profile,
        ),
        PosteriorSummaryRef.model_construct(
            artifact_id=IRArtifactID(profile),
            kind="ir.posterior_summary",
            media_type="application/json",
            manifest_profile_sha256="sha256:NOT_LOWERCASE_HEX",
        ),
    )
    malformed_refs[1].__dict__["unmodeled_payload"] = np.ones(100_000)

    for ref in malformed_refs:
        with pytest.raises((TypeError, ValueError)):
            _ArtifactRefView.capture(ref)
    assert serializer_calls == []
