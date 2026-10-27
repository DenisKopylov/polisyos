"""Persist and reconcile source-bound HTE outcomes in the Scientist CAS path.

The HTE producer returns a private writer-ready value inside the ordinary
method result. This bridge joins that value to the Runtime-owned pre-output
anchor and selected result/evidence refs, persists the typed IR chain, then
returns only profiled refs and a scalar-only Runtime projection.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeGuard

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, CoreJSONArtifactBoundedMemberReader
    from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorDispatchContext
    from polisyos.core.contracts.runtime import DirectMethodExecutionHTESummary
    from polisyos.foundry.data_plane import HTEPhysicalSourceMaterializationBinding
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        HTEWriterReadyIntervalV1,
        HTEWriterReadyPointV1,
        HTEWriterReadyRefusalV1,
        HTEWriterReadyV1,
    )
    from polisyos.ir import ArtifactStore as IRArtifactStore
    from polisyos.ir.analytics import HTEPointResultRef, HTEResultEvidenceRef
    from polisyos.ir.analytics.hte import ATEInferenceBasis, HTEFinalizedArtifactRefs


_BOOTSTRAP_LIMITS = (1_048_576, 64, 100_000, 65_536)
_HTE_RESULT_KIND = "scientist.method_result.causal.hte"
_METHOD_RESULT_SCHEMA = "polisyos.scientist.MethodResult"
_METHOD_EVIDENCE_KIND = "scientist.method_evidence"
_METHOD_EVIDENCE_SCHEMA = "polisyos.scientist.MethodExecutionEvidence"
_ANCHOR_SCHEMA = "polisyos.runtime.OwnedAttemptAnchor"
_RESOURCE_POLICY_SCHEMA = "polisyos.runtime.ObservationalInputResourcePolicy"
_SOURCE_VARIABLE_IDENTITY_LIMITATION = "source_variable_identity_not_established"

type _NativeResultDisposition = Literal[
    "legacy_hte_result_admitted", "legacy_hte_result_unrepresentable"
]
type _NativeResultDispositionReason = (
    Literal["point_not_contained_in_legacy_interval", "native_bounds_unordered"] | None
)


@dataclass(frozen=True, slots=True)
class HTEFinalizedRuntimeOutput:
    """Return the persisted IR refs and bounded Runtime projection together."""

    artifact_refs: HTEFinalizedArtifactRefs
    summary: DirectMethodExecutionHTESummary


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _core_ref(ref: Any, artifact_ref_type: type[Any]) -> Any:
    """Project one owner ref into the exact Core model without losing identity."""
    return _project_model(ref, artifact_ref_type)


def _ir_ref(ref: Any, artifact_ref_type: type[Any]) -> Any:
    """Project one Core ref into the exact IR model without losing identity."""
    return _project_model(ref, artifact_ref_type)


def _project_model(value: Any, model_type: type[Any]) -> Any:
    """Revalidate a typed boundary value through its lossless JSON projection.

    Core, Foundry, and IR intentionally own separate ref classes. Strict
    Pydantic validation does not accept a different owner's model instance,
    even when all serialized fields match. The JSON projection is the existing
    persisted ABI between those owners; revalidation preserves the full
    artifact ID, kind, media type, and selected manifest profile.
    """
    model_dump = getattr(value, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else value
    projected = model_type.model_validate(payload, strict=True)
    if callable(model_dump) and projected.model_dump(mode="json") != payload:
        raise ValueError("hte_bridge_cross_owner_projection_changed_identity")
    return projected


def _is_writer_ready_json_object(value: object) -> TypeGuard[dict[str, object]]:
    """Narrow a JSON boundary value to an object with exact string keys.

    Nested values remain subject to the HTE writer-ready owner validator,
    which rejects values that are not lossless JSON.
    """
    return type(value) is dict and all(type(key) is str for key in value)


def _validate_native_writer_identity(
    writer: HTEWriterReadyV1,
    *,
    method_fqn: str,
    method_abi: str,
    method_abi_digest: str,
    method_profile_id: str,
) -> None:
    """Bind a native result to the complete Runtime-owned method identity.

    The producer writer-ready validator admits native captures with a well-formed
    ABI digest, but does not bind that digest to the pre-output Runtime anchor.
    This gate checks the whole identity tuple before this bridge persists any
    finalized HTE artifact; a basis must never inherit an owner digest that the native result
    did not itself carry.
    """
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        HTEWriterReadyIntervalV1,
        HTEWriterReadyPointV1,
    )

    if isinstance(writer, HTEWriterReadyIntervalV1):
        native = writer.native_capture
    elif isinstance(writer, HTEWriterReadyPointV1):
        native = writer.native_diagnostic
    else:
        return
    if native is None:
        return
    owner_identity = (method_fqn, method_abi, method_abi_digest, method_profile_id)
    native_identity = (
        native.method_fqn,
        native.method_abi,
        native.method_abi_digest,
        native.method_profile_id,
    )
    if native_identity != owner_identity:
        raise ValueError("hte_bridge_native_method_identity_mismatch")


def _read_bounded(
    store: CoreJSONArtifactBoundedMemberReader,
    ref: Any,
    *,
    limits: Any,
    artifact_ref_type: type[Any],
    schema_name: str,
    schema_version: str,
) -> tuple[Any, Any, Any]:
    """Read one profiled JSON object under explicit manifest and payload caps."""
    from polisyos.core.artifacts import (
        artifact_manifest_profile_sha256,
        read_core_json_artifact_bounded,
    )

    selected_ref = _core_ref(ref, artifact_ref_type)
    if selected_ref.manifest_profile_sha256 is None:
        raise ValueError("hte_bridge_ref_profile_missing")
    bounded = read_core_json_artifact_bounded(store, selected_ref, limits=limits)
    manifest = bounded.manifest
    schema = manifest.artifact_schema
    if (
        bounded.effective_ref != selected_ref
        or manifest.artifact_id != selected_ref.artifact_id
        or manifest.kind != selected_ref.kind
        or manifest.media_type != selected_ref.media_type
        or schema is None
        or schema.name != schema_name
        or str(schema.version) != schema_version
        or artifact_manifest_profile_sha256(manifest) != selected_ref.manifest_profile_sha256
    ):
        raise ValueError("hte_bridge_selected_manifest_identity_mismatch")
    return bounded.value, manifest, bounded


def _manifest_inputs(manifest: Any) -> tuple[tuple[str, str, str | None], ...]:
    inputs = getattr(manifest, "inputs", None)
    if not isinstance(inputs, (tuple, list)):
        raise ValueError("hte_bridge_manifest_inputs_missing")
    normalized: list[tuple[str, str, str | None]] = []
    for item in inputs:
        artifact_id = getattr(item, "artifact_id", None)
        role = getattr(item, "role", None)
        profile = getattr(item, "manifest_profile_sha256", None)
        if not isinstance(artifact_id, str) and artifact_id is not None:
            artifact_id = str(artifact_id)
        if not isinstance(artifact_id, str) or not artifact_id or not isinstance(role, str):
            raise ValueError("hte_bridge_manifest_input_invalid")
        if profile is not None and not isinstance(profile, str):
            raise ValueError("hte_bridge_manifest_input_profile_invalid")
        normalized.append((artifact_id, role, profile))
    return tuple(normalized)


def _expected_inputs(
    refs: tuple[tuple[Any, str], ...], artifact_ref_type: type[Any]
) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(
        (
            str(ref.artifact_id),
            role,
            _core_ref(ref, artifact_ref_type).manifest_profile_sha256,
        )
        for ref, role in refs
    )


def _assert_manifest_inputs(
    manifest: Any,
    expected: tuple[tuple[Any, str], ...],
    artifact_ref_type: type[Any],
) -> None:
    if _manifest_inputs(manifest) != _expected_inputs(expected, artifact_ref_type):
        raise ValueError("hte_bridge_manifest_lineage_mismatch")


def _input_refs(refs: tuple[tuple[Any, str], ...], artifact_ref_type: type[Any]) -> list[Any]:
    from polisyos.core.artifacts import input_ref_from_artifact_ref

    return [
        input_ref_from_artifact_ref(_core_ref(ref, artifact_ref_type), role=role)
        for ref, role in refs
    ]


def _owner_binding_inputs(
    *,
    materialization_binding_ref: object | None,
    search_uncertainty_task_binding_ref: object | None,
) -> tuple[tuple[object, str], ...]:
    """Return physical and Search owner edges in the reader's canonical order."""
    physical_inputs = (
        ()
        if materialization_binding_ref is None
        else ((materialization_binding_ref, "physical_source_materialization_binding"),)
    )
    search_inputs = (
        ()
        if search_uncertainty_task_binding_ref is None
        else ((search_uncertainty_task_binding_ref, "search_uncertainty_task_binding"),)
    )
    return (*physical_inputs, *search_inputs)


def _numeric_outcome_inputs(
    *,
    result_ref: object,
    result_role: Literal["point_result", "hte_result"],
    inference_basis_ref: object | None,
    base_inputs: tuple[tuple[object, str], ...],
) -> tuple[tuple[object, str], ...]:
    """Place an optional inference basis after the result and before its bases."""
    result_inputs = ((result_ref, result_role),)
    basis_inputs = (
        () if inference_basis_ref is None else ((inference_basis_ref, "inference_basis"),)
    )
    return (*result_inputs, *basis_inputs, *base_inputs)


def _refusal_diagnostic_inputs(
    *,
    anchor_ref: object,
    method_result_ref: object,
    method_evidence_ref: object,
    resource_policy_ref: object,
    owner_binding_inputs: tuple[tuple[object, str], ...],
) -> tuple[tuple[object, str], ...]:
    """Build the ordered owner lineage for a refusal diagnostic."""
    return (
        (anchor_ref, "owned_attempt_anchor"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        *owner_binding_inputs,
    )


def _refusal_outcome_inputs(
    *,
    refusal_diagnostic_ref: object,
    anchor_ref: object,
    method_result_ref: object,
    method_evidence_ref: object,
    resource_policy_ref: object,
    source_data_ref: object,
    owner_binding_inputs: tuple[tuple[object, str], ...],
) -> tuple[tuple[object, str], ...]:
    """Build the ordered owner lineage for a refusal outcome."""
    return (
        (refusal_diagnostic_ref, "refusal_diagnostic"),
        (anchor_ref, "owned_attempt_anchor"),
        (method_result_ref, "method_result"),
        (method_evidence_ref, "method_evidence"),
        (resource_policy_ref, "resource_policy"),
        (source_data_ref, "source_data"),
        *owner_binding_inputs,
    )


def _source_ref_matches(left: Any, right: Any) -> bool:
    return _canonical_json(left.model_dump(mode="json")) == _canonical_json(
        right.model_dump(mode="json")
    )


def _validate_writer_capture(writer_ready: Any, context: Any, anchor: Any) -> None:
    capture = getattr(writer_ready, "capture", None)
    core_capture = context.input_capture
    if type(core_capture) is not type(anchor.input_capture):
        raise ValueError("hte_bridge_dispatch_capture_type_mismatch")
    if capture is None:
        # A method may refuse during its own preparation step before it has
        # reconstructed the selected arrays. The pre-dispatch anchor already
        # contains those facts from Runtime's real preparation boundary, while
        # the persisted MethodResult and execution evidence bind this exact
        # method refusal. Do not pretend the writer supplied a second capture.
        if (
            getattr(writer_ready, "kind", None) != "refusal"
            or getattr(writer_ready, "refusal_stage", None) != "prepare"
            or getattr(writer_ready, "method_fqn", None) != core_capture.method_fqn
            or getattr(writer_ready, "method_abi", None) != core_capture.method_abi
            or getattr(writer_ready, "method_profile_id", None) != core_capture.method_profile_id
        ):
            raise ValueError("hte_bridge_success_capture_missing")
        return

    core_payload = core_capture.model_dump(mode="json", exclude={"request_context"})
    request_context = core_capture.request_context.model_dump(mode="json", exclude_none=False)
    request_context["search_uncertainty_task_binding_ref"] = (
        None
        if core_capture.request_context.search_uncertainty_task_binding_ref is None
        else core_capture.request_context.search_uncertainty_task_binding_ref.model_dump(
            mode="json"
        )
    )
    expected_capture = {
        **core_payload,
        **request_context,
        "source_data_ref_status": "capture_matched",
        "owned_attempt_anchor_ref": context.anchor_ref.model_dump(mode="json"),
    }
    actual_capture = capture.model_dump(mode="json", exclude_none=False)
    if (
        capture.source_data_ref_status != "capture_matched"
        or not _source_ref_matches(capture.owned_attempt_anchor_ref, context.anchor_ref)
        or capture.method_abi_digest != context.method_abi_digest
        or actual_capture != expected_capture
        or not _source_ref_matches(capture.source_data_ref, core_capture.source_data_ref)
        or not _source_ref_matches(capture.source_data_ref, anchor.effective_input_ref)
    ):
        raise ValueError("hte_bridge_writer_capture_owner_mismatch")


def _policy_payload(anchor: Any, policy: Any, policy_ref: Any) -> dict[str, Any]:
    expected_profiles = {
        "causal.hte.causal_forest@2.0.0": (
            "econml.causal_forest_dml.native_mean@2.0",
            "producer_scoped_joblib_parallelism_one",
            1,
        ),
        "causal.hte.double_ml@2.0.0": (
            "econml.dml.point_only@2.0",
            "producer_scoped_joblib_parallelism_one",
            None,
        ),
        "causal.hte.meta_learner@2.0.0": (
            "econml.meta_learner.point_only@2.0",
            "producer_scoped_joblib_parallelism_one",
            None,
        ),
        "causal.hte.forest_dr@2.0.0": (
            "econml.forest_dr.native_mean@2.0",
            "producer_scoped_joblib_parallelism_one",
            1,
        ),
    }
    expected = expected_profiles[anchor.method_fqn]
    if (
        policy.digest() != anchor.resource_policy_digest
        or policy.schema_version != "polisyos.runtime.observational_input_resource_policy.v5"
        or policy.revision != "r5"
        or policy.method_fqn != anchor.method_fqn
        or policy.method_profile_id != expected[0]
        or policy.execution_scope != expected[1]
        or policy.max_jobs != 1
        or policy.required_estimator_n_jobs != expected[2]
        or policy.method_contract_target
        != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        or anchor.resource_policy_schema_version != policy.schema_version
        or anchor.resource_policy_revision != policy.revision
        or anchor.resource_policy_method_fqn != policy.method_fqn
        or anchor.resource_policy_method_profile_id != policy.method_profile_id
        or anchor.resource_policy_execution_scope != policy.execution_scope
        or anchor.resource_policy_max_jobs != policy.max_jobs
        or anchor.resource_policy_required_estimator_n_jobs != policy.required_estimator_n_jobs
    ):
        raise ValueError("hte_bridge_resource_policy_owner_mismatch")
    return {
        "owner_policy_ref": policy_ref,
        "owner_policy_digest": anchor.resource_policy_digest,
        "owner_policy_schema_version": policy.schema_version,
        "owner_policy_revision": policy.revision,
        "owner_policy_method_fqn": policy.method_fqn,
        "owner_policy_method_profile_id": policy.method_profile_id,
        "owner_policy_execution_scope": policy.execution_scope,
        "owner_policy_max_jobs": policy.max_jobs,
        "owner_policy_required_estimator_n_jobs": policy.required_estimator_n_jobs,
    }


def _expected_refusal_limitations(
    writer: HTEWriterReadyRefusalV1,
    physical_binding: HTEPhysicalSourceMaterializationBinding,
) -> tuple[str, ...]:
    """Derive refusal limitations from the typed writer and verified binding facts.

    Callers pass only the selected binding after the Foundry owner has resolved
    its bytes, identity, and expected input refs. The physical binding expressly
    leaves semantic variable alignment unestablished; a refusal publishes no
    effect estimate. Preserve method limitations and append those two facts in
    one canonical order for both producer and consumer.
    """
    from polisyos.foundry.data_plane import HTEPhysicalSourceMaterializationBinding
    from polisyos.foundry.methods.catalog.causal.hte_v2 import HTEWriterReadyRefusalV1

    if type(writer) is not HTEWriterReadyRefusalV1:
        raise TypeError("hte_refusal_limitations_require_typed_refusal_writer")
    if type(physical_binding) is not HTEPhysicalSourceMaterializationBinding:
        raise TypeError("hte_refusal_limitations_require_verified_physical_binding")
    if (
        physical_binding.binding_scope != "physical_materialization_only"
        or physical_binding.semantic_alignment_status != "not_established"
    ):
        raise ValueError("hte_refusal_limitation_binding_semantics_invalid")
    return tuple(
        dict.fromkeys(
            (
                *writer.limitations,
                "no_effect_estimate_published",
                _SOURCE_VARIABLE_IDENTITY_LIMITATION,
            )
        )
    )


def _resource_evidence(
    anchor: Any,
    policy: Any,
    receipt: Any,
    ir_model: type[Any],
    *,
    policy_ref: Any,
    method_profile_id: str,
) -> Any:
    from polisyos.ir.analytics import HTEResourcePolicyRef

    owner = _policy_payload(anchor, policy, policy_ref)
    owner["owner_policy_ref"] = _ir_ref(policy_ref, HTEResourcePolicyRef)
    fields = receipt.model_dump(mode="json", exclude_none=False)
    fields.pop("schema_version", None)
    fields.pop("scope", None)
    if receipt.method_profile_id != method_profile_id:
        raise ValueError("hte_bridge_resource_receipt_profile_mismatch")
    fields.pop("method_profile_id", None)
    if receipt.scope != "producer_scoped_joblib_parallelism_one":
        raise ValueError("hte_bridge_joblib_scope_receipt_mismatch")
    joblib_observed = receipt.joblib_started
    estimator_required = policy.required_estimator_n_jobs == 1
    estimator_fields = (
        "estimator_before_class_fqn",
        "estimator_before_n_jobs",
        "estimator_before_params_sha256",
        "estimator_after_class_fqn",
        "estimator_after_n_jobs",
        "estimator_after_params_sha256",
    )
    estimator_complete = all(fields.get(name) is not None for name in estimator_fields)
    if any(fields.get(name) is not None for name in estimator_fields) and not estimator_complete:
        raise ValueError("hte_bridge_partial_estimator_observation")
    if estimator_complete and not estimator_required:
        raise ValueError("hte_bridge_estimator_observation_not_required_by_policy")
    if not estimator_required and not estimator_complete:
        fields.update(dict.fromkeys(estimator_fields))
    fields.update(
        {
            "estimator_observation_status": (
                "recomputed"
                if estimator_complete
                else "not_established"
                if estimator_required
                else "not_applicable"
            ),
            "joblib_observation_status": "recomputed" if joblib_observed else "not_established",
            "joblib_scope": "current_thread_joblib" if joblib_observed else None,
            "joblib_max_jobs": 1 if joblib_observed else None,
        }
    )
    if not joblib_observed:
        fields.update(
            {
                "joblib_profile_id": None,
                "joblib_profile_revision": None,
                "joblib_implementation": None,
                "joblib_implementation_version": None,
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
    payload = {
        **owner,
        "physical_thread_limit_status": "not_established",
        "physical_thread_limit": None,
        **fields,
    }
    return ir_model.model_validate(payload, strict=True)


def _target_relation(
    capture: Any,
    *,
    request_context: Any | None = None,
    validated_writer_capture: Any | None = None,
    computed_guarantee: str | None,
    profile_status: str,
    interval_alpha: float | None,
    refusal: bool = False,
    ir_model: type[Any],
) -> Any:
    request = request_context if request_context is not None else capture
    request_scope_status = request.request_target_scope_status
    request_scope = request.request_target_scope
    request_guarantee_status = request.requested_guarantee_status
    request_guarantee = request.requested_guarantee
    # The request context contains only owner-frozen selectors. Scientific
    # parameters belong to the admitted input capture and are reconciled
    # separately against the persisted anchor.
    resolved = capture.resolved_params
    resolved_control = resolved.get("control_value")
    resolved_treated = resolved.get("treated_value")
    method_contrast_matches = (resolved_control is None and resolved_treated is None) or (
        resolved_control is not None
        and resolved_treated is not None
        and not isinstance(resolved_control, bool)
        and not isinstance(resolved_treated, bool)
        and isinstance(resolved_control, (int, float))
        and isinstance(resolved_treated, (int, float))
        and math.isfinite(float(resolved_control))
        and math.isfinite(float(resolved_treated))
        and math.isclose(
            float(resolved_control), float(request.control_value), rel_tol=0.0, abs_tol=1.0e-12
        )
        and math.isclose(
            float(resolved_treated), float(request.treated_value), rel_tol=0.0, abs_tol=1.0e-12
        )
    )
    # This capture has already passed _validate_writer_capture against the
    # immutable Core input capture and request context. Its numeric values are
    # the producer-use witness; method parameters may intentionally be null.
    contrast_recomputed = (
        request.contrast_status == "declared"
        and validated_writer_capture is not None
        and validated_writer_capture.contrast_status == "declared"
        and validated_writer_capture.control_value == request.control_value
        and validated_writer_capture.treated_value == request.treated_value
        and method_contrast_matches
    )
    # The selected HTE input contract carries numeric Y/T arrays but no typed
    # binding from requested variable IDs to those arrays. Matching a request
    # label is not a recomputation of variable identity, so keep this predicate
    # unknown while preserving the numerical candidate.
    alpha_recomputed = (
        request.request_alpha_status == "declared"
        and isinstance(resolved.get("alpha"), (int, float))
        and not isinstance(resolved.get("alpha"), bool)
        and math.isclose(
            float(resolved["alpha"]),
            float(request.requested_alpha),
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        and (
            interval_alpha is None
            or math.isclose(
                float(interval_alpha),
                float(request.requested_alpha),
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
        )
    )
    if refusal:
        computed_scope_status = "not_established"
        computed_scope = None
        guarantee_status = "not_established"
        guarantee = None
        profile = "not_established"
        alpha_status = "not_established"
        contrast_status = "recomputed" if contrast_recomputed else "not_established"
        estimand_status = "not_established"
    else:
        computed_scope_status = "recomputed"
        computed_scope = "selected_evaluation_rows"
        guarantee_status = "computed"
        guarantee = computed_guarantee
        profile = profile_status
        alpha_status = "recomputed" if alpha_recomputed else "not_established"
        contrast_status = "recomputed" if contrast_recomputed else "not_established"
        estimand_status = "not_established"
    scope_predicates_bound = (
        request_scope_status == "declared" and computed_scope_status == "recomputed" and not refusal
    )
    if not scope_predicates_bound:
        scope_disposition = "not_established"
    elif request_scope == computed_scope:
        scope_disposition = "satisfied"
    elif request_scope == "population":
        scope_disposition = "requested_claim_not_satisfied"
    else:
        scope_disposition = "not_established"

    guarantee_predicates_bound = (
        request_guarantee_status == "declared" and guarantee_status == "computed" and not refusal
    )
    if not guarantee_predicates_bound:
        guarantee_disposition = "not_established"
    elif request_guarantee == guarantee:
        guarantee_disposition = "satisfied"
    else:
        guarantee_disposition = "requested_claim_not_satisfied"

    dispositions = {scope_disposition, guarantee_disposition}
    overall = (
        "requested_claim_not_satisfied"
        if "requested_claim_not_satisfied" in dispositions
        else "not_established"
        if "not_established" in dispositions
        or contrast_status != "recomputed"
        or estimand_status != "recomputed"
        else "satisfied"
    )
    return ir_model.model_validate(
        {
            "requested_scope_status": request_scope_status,
            "requested_scope": request_scope,
            "requested_guarantee_status": request_guarantee_status,
            "requested_guarantee": request_guarantee,
            "computed_scope_status": computed_scope_status,
            "computed_scope": computed_scope,
            "computed_guarantee_status": guarantee_status,
            "computed_guarantee": guarantee,
            "source_content_status": "content_bound",
            "row_order_status": "recomputed",
            "contrast_status": contrast_status,
            "estimand_status": estimand_status,
            "alpha_status": alpha_status,
            "profile_status": profile,
            "scope_disposition": scope_disposition,
            "guarantee_disposition": guarantee_disposition,
            "overall_disposition": overall,
        },
        strict=True,
    )


def _request_fields(capture: Any) -> dict[str, Any]:
    from polisyos.ir.analytics import (
        HTEPhysicalSourceMaterializationBindingRef,
        SearchUncertaintyTaskBindingRef,
    )

    return {
        "request_estimand_status": capture.request_estimand_status,
        "request_estimand": capture.request_estimand,
        "request_target_scope_status": capture.request_target_scope_status,
        "request_target_scope": capture.request_target_scope,
        "outcome_variable_status": capture.outcome_variable_status,
        "outcome_variable_id": capture.outcome_variable_id,
        "treatment_variable_status": capture.treatment_variable_status,
        "treatment_variable_id": capture.treatment_variable_id,
        "request_alpha_status": capture.request_alpha_status,
        "requested_alpha": capture.requested_alpha,
        "requested_guarantee_status": capture.requested_guarantee_status,
        "requested_guarantee": capture.requested_guarantee,
        "search_uncertainty_task_binding_ref": (
            None
            if capture.search_uncertainty_task_binding_ref is None
            else _ir_ref(
                capture.search_uncertainty_task_binding_ref,
                SearchUncertaintyTaskBindingRef,
            )
        ),
        "materialization_binding_ref": _ir_ref(
            capture.materialization_binding_ref,
            HTEPhysicalSourceMaterializationBindingRef,
        ),
        "contrast_status": "established"
        if capture.contrast_status == "declared"
        else "not_established",
        "control_value": capture.control_value,
        "treated_value": capture.treated_value,
    }


def _persist_and_check[RefT](
    *,
    store: CoreJSONArtifactBoundedMemberReader,
    ir_store: IRArtifactStore,
    model: Any,
    persist: Callable[..., RefT],
    inputs: tuple[tuple[Any, str], ...],
    artifact_ref_type: type[Any],
    limits: Any,
    schema_name: str,
    schema_version: str,
    validator: Any,
) -> RefT:
    ref = persist(ir_store, model, inputs=_input_refs(inputs, artifact_ref_type))
    core_ref = _core_ref(ref, artifact_ref_type)
    _, manifest, bounded = _read_bounded(
        store,
        core_ref,
        limits=limits,
        artifact_ref_type=artifact_ref_type,
        schema_name=schema_name,
        schema_version=schema_version,
    )
    _assert_manifest_inputs(manifest, inputs, artifact_ref_type)
    # Core's bounded raw bytes are canonical-profile bytes, whose numeric tags
    # are not the JSON representation consumed by IR model validators. The
    # bounded value has already been decoded and profile-verified from those
    # exact bytes; round-trip that semantic JSON value through the strict JSON
    # validator, matching IR's public artifact loaders.
    bounded_json = _canonical_json(bounded.value).encode("utf-8")
    if hasattr(validator, "validate_json"):
        loaded = validator.validate_json(bounded_json, strict=True)
    else:
        loaded = validator.model_validate_json(bounded_json, strict=True)
    if _canonical_json(loaded.model_dump(mode="json")) != _canonical_json(
        model.model_dump(mode="json")
    ):
        raise ValueError("hte_bridge_persisted_model_readback_mismatch")
    return ref


def _bounded_summary(
    *,
    outcome: Any,
    refs: Any,
    resource: Any,
    source_data_ref: Any,
    summary_model: type[Any],
    relation_model: type[Any],
    resource_model: type[Any],
) -> Any:
    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorRef as CoreOwnedAttemptAnchorRef,
    )

    request = outcome
    relation_payload = outcome.target_relation.model_dump(mode="json")
    # The IR relation is versioned as its own persisted contract; the Core
    # bounded summary embeds the same relation fields under the enclosing
    # summary schema and intentionally has no nested schema_version field.
    relation_payload.pop("schema_version")
    relation = relation_model.model_validate(relation_payload, strict=True)
    resource_payload = resource.model_dump(mode="json", exclude_none=False)
    resource_payload.pop("schema_version", None)
    resource_copy = resource_model.model_validate(resource_payload, strict=True)
    is_refusal = outcome.kind == "refusal"
    request_values = {
        "request_estimand_status": request.request_estimand_status,
        "request_estimand": request.request_estimand,
        "request_target_scope_status": request.request_target_scope_status,
        "request_target_scope": request.request_target_scope,
        "outcome_variable_status": request.outcome_variable_status,
        "outcome_variable_id": request.outcome_variable_id,
        "treatment_variable_status": request.treatment_variable_status,
        "treatment_variable_id": request.treatment_variable_id,
        "request_contrast_status": "declared"
        if request.contrast_status == "established"
        else "not_established",
        "control_value": request.control_value,
        "treated_value": request.treated_value,
        "request_alpha_status": request.request_alpha_status,
        "requested_alpha": request.requested_alpha,
        "requested_guarantee_status": request.requested_guarantee_status,
        "requested_guarantee": request.requested_guarantee,
        "search_uncertainty_task_binding_ref": (
            None
            if request.search_uncertainty_task_binding_ref is None
            else _core_ref(request.search_uncertainty_task_binding_ref, CoreArtifactRef)
        ),
    }
    if is_refusal:
        selected = {
            "selected_rows_status": "not_established",
            "n_selected_rows": None,
            "selected_rows_sha256": None,
            "selected_row_order_sha256": None,
            "selected_x_sha256": None,
            "computed_estimand_status": "not_established",
            "computed_estimand": None,
            "computed_target_scope_status": "not_established",
            "computed_target_scope": None,
            "computed_guarantee_status": "not_established",
            "computed_guarantee": None,
            "point_estimate": None,
            "lower_bound": None,
            "upper_bound": None,
            "confidence_level": None,
            "inference_status": None,
            "inference_reason": None,
            "refusal_stage": outcome.refusal_stage,
            "refusal_reason": outcome.refusal_reason,
            "refusal_diagnostic_code": outcome.diagnostic_code,
        }
    else:
        selected = {
            "selected_rows_status": "recomputed",
            "n_selected_rows": outcome.n_selected_rows,
            "selected_rows_sha256": outcome.selected_rows_sha256,
            "selected_row_order_sha256": outcome.selected_row_order_sha256,
            "selected_x_sha256": outcome.selected_x_sha256,
            "computed_estimand_status": "recomputed",
            "computed_estimand": "mean_effect_over_selected_x",
            "computed_target_scope_status": "recomputed",
            "computed_target_scope": "selected_evaluation_rows",
            "computed_guarantee_status": "computed",
            "computed_guarantee": outcome.target_relation.computed_guarantee,
            "point_estimate": outcome.point_estimate.value,
            "lower_bound": getattr(outcome, "lower_bound", None),
            "upper_bound": getattr(outcome, "upper_bound", None),
            "confidence_level": getattr(outcome, "confidence_level", None),
            "inference_status": outcome.inference_status,
            "inference_reason": getattr(outcome, "inference_reason", None),
            "refusal_stage": None,
            "refusal_reason": None,
            "refusal_diagnostic_code": None,
        }
    return summary_model.model_validate(
        {
            "schema_version": "1.0",
            "kind": outcome.kind,
            "method_fqn": outcome.method_fqn,
            "method_abi_digest": outcome.method_abi_digest,
            "method_profile_id": outcome.method_profile_id,
            "resolved_params_sha256": outcome.resolved_params_sha256,
            "owned_attempt_anchor_ref": _core_ref(
                refs.owned_attempt_anchor_ref, CoreOwnedAttemptAnchorRef
            ),
            "materialization_binding_ref": (
                None
                if refs.materialization_binding_ref is None
                else _core_ref(refs.materialization_binding_ref, CoreArtifactRef)
            ),
            "hte_outcome_ref": _core_ref(refs.hte_outcome_ref, CoreArtifactRef),
            "point_result_ref": (
                None
                if refs.point_result_ref is None
                else _core_ref(refs.point_result_ref, CoreArtifactRef)
            ),
            "hte_result_ref": (
                None
                if refs.hte_result_ref is None
                else _core_ref(refs.hte_result_ref, CoreArtifactRef)
            ),
            "inference_basis_ref": (
                None
                if refs.inference_basis_ref is None
                else _core_ref(refs.inference_basis_ref, CoreArtifactRef)
            ),
            "refusal_diagnostic_ref": (
                None
                if refs.refusal_diagnostic_ref is None
                else _core_ref(refs.refusal_diagnostic_ref, CoreArtifactRef)
            ),
            "method_result_ref": _core_ref(outcome.method_result_ref, CoreArtifactRef),
            "method_evidence_ref": _core_ref(outcome.method_evidence_ref, CoreArtifactRef),
            "source_data_ref": _core_ref(source_data_ref, CoreArtifactRef),
            **selected,
            "measure_unit_status": "not_established",
            "measure_unit": None,
            **request_values,
            "target_relation": relation,
            "resource_evidence": resource_copy,
            "limitations": outcome.limitations,
        },
        strict=True,
    )


def persist_runtime_hte_outcome(
    *,
    store: CoreJSONArtifactBoundedMemberReader,
    writer_ready: object,
    owned_attempt_anchor_context: OwnedAttemptAnchorDispatchContext,
    method_result_ref: ArtifactRef,
    method_evidence_ref: ArtifactRef,
) -> HTEFinalizedRuntimeOutput:
    """Join writer output to the owned anchor and persist a typed HTE chain.

    Args:
        store: The bounded Core JSON store already selected by Runtime admission.
        writer_ready: The producer's private HTE union carried in MethodResult.
        owned_attempt_anchor_context: The typed pre-output anchor returned by Runtime.
        method_result_ref: The selected CAS ref for the ordinary Scientist result.
        method_evidence_ref: The selected CAS ref for its execution evidence.

    Returns:
        HTEFinalizedRuntimeOutput: Profiled artifacts plus the scalar Runtime view.

    Raises:
        ValueError: If the input refs, selected profiles, owner capture, resource
            policy, or actual MethodResult output fail reconciliation.
    """
    from typing import Protocol, runtime_checkable

    from polisyos.core.artifacts import (
        ArtifactRef as CoreArtifactRef,
    )
    from polisyos.core.artifacts import (
        CoreJSONArtifactBoundedMemberReader,
        CoreJSONArtifactStore,
        CoreJsonReadLimits,
        ensure_ir_artifact_store,
        matches_artifact_store_protocol,
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchor,
        OwnedAttemptAnchorDispatchContext,
    )

    @runtime_checkable
    class _HTEBridgeCoreArtifactStore(
        CoreJSONArtifactStore,
        CoreJSONArtifactBoundedMemberReader,
        Protocol,
    ):
        """Core owner with bounded selected reads and profile-aware writes."""

    if not matches_artifact_store_protocol(store, _HTEBridgeCoreArtifactStore):
        raise TypeError("hte_bridge_requires_core_json_bounded_write_store")
    ir_store = ensure_ir_artifact_store(store)
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTEResourceEvidence,
        DirectMethodExecutionHTESummary,
        DirectMethodExecutionHTETargetRelation,
        ObservationalInputResourcePolicy,
    )
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        HTEWriterReadyIntervalV1,
        HTEWriterReadyPointV1,
        HTEWriterReadyRefusalV1,
        validate_hte_writer_ready_json,
    )
    from polisyos.ir.analytics import CausalMethod
    from polisyos.ir.analytics.hte import (
        _HTE_OUTCOME_ADAPTER,
        ATEInferenceBasis,
        ATEInferenceBasisRef,
        HTEFinalizedArtifactRefs,
        HTEInputSourceRef,
        HTEIntervalOutcome,
        HTEOutcomeRef,
        HTEPhysicalSourceMaterializationBindingRef,
        HTEPointEstimate,
        HTEPointOutcome,
        HTEPointResult,
        HTEPointResultRef,
        HTERefusalDiagnostic,
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
        SearchUncertaintyTaskBindingRef,
        persist_ate_inference_basis,
        persist_hte_outcome,
        persist_hte_point_result,
        persist_hte_refusal_diagnostic,
        persist_hte_result_v2,
    )

    if type(owned_attempt_anchor_context) is not OwnedAttemptAnchorDispatchContext:
        raise TypeError("hte_bridge_requires_typed_runtime_anchor_context")
    anchor_ref = owned_attempt_anchor_context.anchor_ref
    anchor_ref_core = _core_ref(anchor_ref, CoreArtifactRef)
    bootstrap_limits = CoreJsonReadLimits(*_BOOTSTRAP_LIMITS)
    anchor_bounded = read_core_json_artifact_bounded(
        store, anchor_ref_core, limits=bootstrap_limits
    )
    anchor = validate_core_model_bounded_read(OwnedAttemptAnchor, anchor_bounded)
    method_profile_id = anchor.resource_policy_method_profile_id
    if method_profile_id is None:
        raise ValueError("hte_bridge_resource_policy_profile_missing")
    anchor_refs = {
        "requested_source_ref": _core_ref(anchor.requested_source_ref, CoreArtifactRef),
        "observational_run_intent_ref": _core_ref(
            anchor.observational_run_intent_ref, CoreArtifactRef
        ),
        "content_admitted_intent_ref": _core_ref(
            anchor.content_admitted_intent_ref, CoreArtifactRef
        ),
        "submitted_input_ref": _core_ref(anchor.submitted_input_ref, CoreArtifactRef),
        "effective_input_ref": _core_ref(anchor.effective_input_ref, CoreArtifactRef),
        "resource_policy_ref": _core_ref(anchor.resource_policy_ref, CoreArtifactRef),
        "source_data_ref": _core_ref(anchor.input_capture.source_data_ref, CoreArtifactRef),
        "materialization_binding_ref": _core_ref(
            anchor.input_capture.materialization_binding_ref, CoreArtifactRef
        ),
        "search_uncertainty_task_binding_ref": (
            None
            if anchor.request_context.search_uncertainty_task_binding_ref is None
            else _core_ref(
                anchor.request_context.search_uncertainty_task_binding_ref, CoreArtifactRef
            )
        ),
    }
    if (
        anchor_bounded.effective_ref != anchor_ref_core
        or anchor.input_admission.admission_status != "input_admitted"
        or anchor.input_capture != owned_attempt_anchor_context.input_capture
        or anchor.method_abi_digest != owned_attempt_anchor_context.method_abi_digest
        or anchor.request_context != anchor.input_capture.request_context
        or anchor.input_capture.resolved_params_sha256 != anchor.resolved_params_sha256
    ):
        raise ValueError("hte_bridge_pre_output_anchor_capture_mismatch")

    policy_ref_core = anchor_refs["resource_policy_ref"]
    policy_bounded = read_core_json_artifact_bounded(
        store, policy_ref_core, limits=bootstrap_limits
    )
    policy_manifest = policy_bounded.manifest
    policy_schema = policy_manifest.artifact_schema
    if (
        policy_bounded.effective_ref != policy_ref_core
        or policy_manifest.kind != "runtime.observational_input_resource_policy"
        or policy_manifest.media_type != "application/json"
        or policy_schema is None
        or policy_schema.name != _RESOURCE_POLICY_SCHEMA
        or str(policy_schema.version) != "1.0"
    ):
        raise ValueError("hte_bridge_resource_policy_manifest_mismatch")
    policy = ObservationalInputResourcePolicy.model_validate(policy_bounded.value, strict=True)
    policy_fields = _policy_payload(anchor, policy, policy_ref_core)
    limits = CoreJsonReadLimits(
        max_bytes=policy.max_bytes,
        max_depth=policy.max_depth,
        max_elements=policy.max_elements,
        max_manifest_bytes=policy.max_manifest_bytes,
    )

    capture = anchor.input_capture
    materialization_binding_ref = anchor_refs["materialization_binding_ref"]
    if (
        materialization_binding_ref is None
        or not _source_ref_matches(
            materialization_binding_ref,
            anchor.request_context.materialization_binding_ref,
        )
        or materialization_binding_ref.kind != "foundry.hte.physical_source_materialization_binding"
        or materialization_binding_ref.media_type != "application/json"
        or materialization_binding_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("hte_bridge_r5_materialization_binding_missing_or_unselected")
    from polisyos.foundry.data_plane import (
        load_hte_physical_source_materialization_binding,
    )

    physical_binding = load_hte_physical_source_materialization_binding(
        store=store,
        binding_ref=materialization_binding_ref,
        expected_submitted_ref=anchor_refs["submitted_input_ref"],
        expected_effective_ref=anchor_refs["effective_input_ref"],
        limits=limits,
    )
    if (
        physical_binding.observation_count != capture.n_selected_rows
        or physical_binding.row_order_sha256 != f"sha256:{capture.selected_row_order_sha256}"
    ):
        raise ValueError("hte_bridge_physical_binding_capture_mismatch")
    materialization_binding_ir_ref = HTEPhysicalSourceMaterializationBindingRef.model_validate(
        materialization_binding_ref.model_dump(mode="json"), strict=True
    )

    method_result_ref_core = _core_ref(method_result_ref, CoreArtifactRef)
    method_evidence_ref_core = _core_ref(method_evidence_ref, CoreArtifactRef)
    result_payload, result_manifest, _ = _read_bounded(
        store,
        method_result_ref_core,
        limits=limits,
        artifact_ref_type=CoreArtifactRef,
        schema_name=_METHOD_RESULT_SCHEMA,
        schema_version="0.1.0",
    )
    evidence_payload, evidence_manifest, _ = _read_bounded(
        store,
        method_evidence_ref_core,
        limits=limits,
        artifact_ref_type=CoreArtifactRef,
        schema_name=_METHOD_EVIDENCE_SCHEMA,
        schema_version="0.1.0",
    )
    if method_result_ref_core.kind != _HTE_RESULT_KIND:
        raise ValueError("hte_bridge_method_result_kind_mismatch")
    if not isinstance(result_payload, Mapping) or not isinstance(evidence_payload, Mapping):
        raise ValueError("hte_bridge_method_artifact_payload_invalid")
    if not isinstance(evidence_payload.get("method_result_ref"), Mapping):
        raise ValueError("hte_bridge_method_evidence_result_ref_missing")
    if (
        CoreArtifactRef.model_validate(evidence_payload["method_result_ref"], strict=True)
        != method_result_ref_core
        or CoreArtifactRef.model_validate(
            evidence_payload.get("owned_attempt_anchor_ref"), strict=True
        )
        != anchor_ref_core
        or evidence_payload.get("method_fqn") != anchor.method_fqn
        or evidence_payload.get("method_version") != anchor.method_version
        or evidence_payload.get("method_abi_digest") != anchor.method_abi_digest
        or evidence_payload.get("resource_policy_digest") != anchor.resource_policy_digest
        or CoreArtifactRef.model_validate(evidence_payload.get("resource_policy_ref"), strict=True)
        != policy_ref_core
        or CoreArtifactRef.model_validate(evidence_payload.get("effective_input_ref"), strict=True)
        != anchor_refs["effective_input_ref"]
        or CoreArtifactRef.model_validate(
            evidence_payload.get("materialization_binding_ref"), strict=True
        )
        != materialization_binding_ref
        or CoreArtifactRef.model_validate(evidence_payload.get("requested_source_ref"), strict=True)
        != anchor_refs["requested_source_ref"]
    ):
        raise ValueError("hte_bridge_method_evidence_owner_binding_mismatch")

    source_refs = (
        (anchor_refs["requested_source_ref"], "requested_source"),
        (anchor_refs["observational_run_intent_ref"], "observational_run_intent"),
        (anchor_refs["content_admitted_intent_ref"], "content_admitted_intent"),
        (anchor_refs["submitted_input_ref"], "submitted_method_input"),
        (anchor_refs["effective_input_ref"], "effective_method_input"),
        (policy_ref_core, "method_resource_policy"),
        (materialization_binding_ref, "physical_source_materialization_binding"),
        (anchor_ref, "owned_attempt_anchor"),
    )
    _assert_manifest_inputs(result_manifest, source_refs, CoreArtifactRef)
    evidence_refs = ((method_result_ref_core, "method_result"), *source_refs)
    _assert_manifest_inputs(evidence_manifest, evidence_refs, CoreArtifactRef)

    if not _is_writer_ready_json_object(writer_ready):
        raise TypeError("writer-ready JSON payload must be a JSON object")
    writer = validate_hte_writer_ready_json(writer_ready)
    stored_writer_payload = result_payload.get("hte_outcome_write_ready")
    if not _is_writer_ready_json_object(stored_writer_payload):
        raise TypeError("writer-ready JSON payload must be a JSON object")
    stored_writer = validate_hte_writer_ready_json(stored_writer_payload)
    if _canonical_json(writer.model_dump(mode="json")) != _canonical_json(
        stored_writer.model_dump(mode="json")
    ):
        raise ValueError("hte_bridge_writer_ready_not_method_result_value")
    _validate_writer_capture(writer, owned_attempt_anchor_context, anchor)
    if (
        writer.method_fqn != anchor.method_fqn
        or writer.method_abi != anchor.method_version
        or writer.method_profile_id != method_profile_id
        or writer.resource_receipt.scope != anchor.resource_policy_execution_scope
    ):
        raise ValueError("hte_bridge_writer_method_profile_mismatch")
    _validate_native_writer_identity(
        writer,
        method_fqn=anchor.method_fqn,
        method_abi=anchor.method_version,
        method_abi_digest=anchor.method_abi_digest,
        method_profile_id=method_profile_id,
    )
    resource = _resource_evidence(
        anchor,
        policy,
        writer.resource_receipt,
        HTEResourceExecutionEvidenceV1,
        policy_ref=policy_ref_core,
        method_profile_id=method_profile_id,
    )
    source_ref = HTEInputSourceRef.model_validate(
        anchor_refs["source_data_ref"].model_dump(mode="json"), strict=True
    )
    point_ref = MethodResultEvidenceRef.model_validate(
        method_result_ref_core.model_dump(mode="json"), strict=True
    )
    evidence_ref = MethodExecutionEvidenceRef.model_validate(
        method_evidence_ref_core.model_dump(mode="json"), strict=True
    )
    anchor_ir_ref = OwnedAttemptAnchorDispatchContext.model_validate(
        owned_attempt_anchor_context, strict=True
    ).anchor_ref
    anchor_ir_ref = OwnedAttemptAnchorRef.model_validate(
        anchor_ir_ref.model_dump(mode="json"), strict=True
    )
    task_binding_ref = anchor_refs["search_uncertainty_task_binding_ref"]
    task_binding_ir_ref = (
        None
        if task_binding_ref is None
        else SearchUncertaintyTaskBindingRef.model_validate(
            task_binding_ref.model_dump(mode="json"), strict=True
        )
    )
    owner_binding_inputs = _owner_binding_inputs(
        materialization_binding_ref=materialization_binding_ir_ref,
        search_uncertainty_task_binding_ref=task_binding_ir_ref,
    )
    request_context = anchor.request_context
    request_fields = _request_fields(request_context)
    point_inputs = (
        (anchor_ir_ref, "owned_attempt_anchor"),
        (source_ref, "source_data"),
        (point_ref, "method_result"),
        (evidence_ref, "method_evidence"),
        (
            HTEResourcePolicyRef.model_validate(
                policy_fields["owner_policy_ref"].model_dump(mode="json")
            ),
            "resource_policy",
        ),
        *owner_binding_inputs,
    )
    # Resource policy stays at its fixed position; optional source and Search
    # bindings follow in their owner-defined order.
    resource_ref = point_inputs[4][0]
    point_result_ref: HTEPointResultRef | None = None
    hte_result_ref: HTEResultEvidenceRef | None = None
    basis_ref: ATEInferenceBasisRef | None = None
    refusal_ref: HTERefusalDiagnosticRef | None = None
    if isinstance(writer, HTEWriterReadyRefusalV1):
        refusal_limitations = _expected_refusal_limitations(writer, physical_binding)
        diagnostic = HTERefusalDiagnostic(
            diagnostic_origin="method_execution",
            method_fqn=anchor.method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=method_profile_id,
            search_uncertainty_task_binding_ref=task_binding_ir_ref,
            refusal_stage=writer.refusal_stage,
            refusal_reason=writer.refusal_reason,
            diagnostic_code=writer.diagnostic_code,
            owned_attempt_anchor_ref=anchor_ir_ref,
            materialization_binding_ref=materialization_binding_ir_ref,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            resource_evidence=resource,
            selected_rows_status="recomputed",
            n_selected_rows=capture.n_selected_rows,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            selected_x_sha256=capture.selected_x_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            limitations=refusal_limitations,
        )
        refusal_inputs = _refusal_diagnostic_inputs(
            anchor_ref=anchor_ir_ref,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            resource_policy_ref=resource_ref,
            owner_binding_inputs=owner_binding_inputs,
        )
        refusal_diagnostic_ref = _persist_and_check(
            store=store,
            ir_store=ir_store,
            model=diagnostic,
            persist=persist_hte_refusal_diagnostic,
            inputs=refusal_inputs,
            artifact_ref_type=CoreArtifactRef,
            limits=limits,
            schema_name=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_NAME,
            schema_version=HTERefusalDiagnosticRef.ARTIFACT_SCHEMA_VERSION,
            validator=HTERefusalDiagnostic,
        )
        refusal_ref = refusal_diagnostic_ref
        target_relation = _target_relation(
            capture,
            request_context=request_context,
            validated_writer_capture=writer.capture,
            computed_guarantee=None,
            profile_status="not_established",
            interval_alpha=None,
            refusal=True,
            ir_model=HTETargetRelationV1,
        )
        invocation_basis_reason: Literal[
            "not_available_at_refusal_stage", "no_invocation_basis_artifact_contract"
        ] = (
            "not_available_at_refusal_stage"
            if writer.refusal_stage == "prepare"
            else "no_invocation_basis_artifact_contract"
        )
        refusal_outcome = HTERefusalOutcome(
            method_fqn=anchor.method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=method_profile_id,
            refusal_stage=writer.refusal_stage,
            refusal_reason=writer.refusal_reason,
            diagnostic_code=writer.diagnostic_code,
            owned_attempt_anchor_ref=anchor_ir_ref,
            anchor_status="pre_output_anchor_resolved",
            requested_source_ref=HTEInputSourceRef.model_validate(
                anchor.requested_source_ref.model_dump(mode="json"), strict=True
            ),
            requested_source_status="declared",
            source_data_ref=source_ref,
            source_data_status="content_bound",
            input_profile_id=capture.input_profile_id,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            selected_x_sha256=capture.selected_x_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            resolved_params_sha256=capture.resolved_params_sha256,
            n_selected_rows=capture.n_selected_rows,
            selected_rows_status="recomputed",
            method_result_ref=point_ref,
            method_result_status="available",
            method_evidence_ref=evidence_ref,
            method_evidence_status="available",
            resource_evidence=resource,
            invocation_basis_ref=None,
            invocation_basis_status="not_established",
            invocation_basis_reason=invocation_basis_reason,
            refusal_diagnostic_ref=refusal_diagnostic_ref,
            **request_fields,
            target_relation=target_relation,
            limitations=refusal_limitations,
        )
        outcome_inputs = _refusal_outcome_inputs(
            refusal_diagnostic_ref=refusal_diagnostic_ref,
            anchor_ref=anchor_ir_ref,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            resource_policy_ref=resource_ref,
            source_data_ref=source_ref,
            owner_binding_inputs=owner_binding_inputs,
        )
        outcome_ref = _persist_and_check(
            store=store,
            ir_store=ir_store,
            model=refusal_outcome,
            persist=persist_hte_outcome,
            inputs=outcome_inputs,
            artifact_ref_type=CoreArtifactRef,
            limits=limits,
            schema_name=HTEOutcomeRef.ARTIFACT_SCHEMA_NAME,
            schema_version=HTEOutcomeRef.ARTIFACT_SCHEMA_VERSION,
            validator=_HTE_OUTCOME_ADAPTER,
        )
        refs = HTEFinalizedArtifactRefs(
            owned_attempt_anchor_ref=anchor_ir_ref,
            materialization_binding_ref=materialization_binding_ir_ref,
            hte_outcome_ref=outcome_ref,
            refusal_diagnostic_ref=refusal_diagnostic_ref,
        )
        summary = _bounded_summary(
            outcome=refusal_outcome,
            refs=refs,
            resource=resource,
            source_data_ref=source_ref,
            summary_model=DirectMethodExecutionHTESummary,
            relation_model=DirectMethodExecutionHTETargetRelation,
            resource_model=DirectMethodExecutionHTEResourceEvidence,
        )
        return HTEFinalizedRuntimeOutput(artifact_refs=refs, summary=summary)

    native_capture = (
        writer.native_capture if writer.kind == "interval_estimate" else writer.native_diagnostic
    )
    target_relation = _target_relation(
        capture,
        request_context=request_context,
        validated_writer_capture=writer.capture,
        computed_guarantee=(
            "backend_conditional_interval"
            if writer.kind == "interval_estimate"
            else "candidate_point"
        ),
        profile_status="qualified" if native_capture is not None else "point_only",
        interval_alpha=None if native_capture is None else native_capture.alpha,
        ir_model=HTETargetRelationV1,
    )
    if writer.resource_receipt.execution_status != "returned":
        raise ValueError("hte_bridge_numeric_candidate_requires_returned_resource_execution")
    point_estimate = HTEPointEstimate(
        value=writer.point_estimate,
        measure_unit_status="not_established",
        measure_unit=None,
    )

    def _basis_for_native(
        writer: HTEWriterReadyIntervalV1 | HTEWriterReadyPointV1,
        *,
        disposition: _NativeResultDisposition,
        disposition_reason: _NativeResultDispositionReason,
        hte_result_ref: HTEResultEvidenceRef | None = None,
        point_result_ref: HTEPointResultRef | None = None,
    ) -> ATEInferenceBasis:
        if writer.kind == "interval_estimate":
            native = writer.native_capture
        else:
            native = writer.native_diagnostic
            if native is None:
                raise ValueError("hte_bridge_native_inference_diagnostic_missing")
        if (
            anchor.method_fqn == "causal.hte.causal_forest@2.0.0"
            and method_profile_id == "econml.causal_forest_dml.native_mean@2.0"
            and native.method_fqn == anchor.method_fqn
            and native.method_abi == anchor.method_version
            and native.method_profile_id == method_profile_id
        ) or (
            anchor.method_fqn == "causal.hte.forest_dr@2.0.0"
            and method_profile_id == "econml.forest_dr.native_mean@2.0"
            and native.method_fqn == anchor.method_fqn
            and native.method_abi == anchor.method_version
            and native.method_profile_id == method_profile_id
        ):
            native_method_fqn = anchor.method_fqn
            native_method_profile_id = method_profile_id
        else:
            raise ValueError("hte_bridge_native_inference_profile_not_supported")
        return ATEInferenceBasis(
            inference_profile_id=native.inference_profile_id,
            method_fqn=native_method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=native_method_profile_id,
            estimator_class=native.estimator_class,
            inference_class=native.inference_class,
            econml_version=native.econml_version,
            econml_source_profile_sha256=native.econml_source_profile_sha256,
            ate_inference_method=native.ate_inference_method,
            conf_int_mean_method=native.conf_int_mean_method,
            native_result_class=native.native_result_class,
            inference_route=native.inference_route,
            resolved_params_sha256=capture.resolved_params_sha256,
            source_data_sha256=capture.source_data_sha256,
            input_profile_id=capture.input_profile_id,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            resolved_params=capture.resolved_params,
            seed=capture.seed,
            fit_rows_sha256=capture.fit_rows_sha256,
            eval_rows_sha256=capture.eval_rows_sha256,
            fit_eval_relation=capture.fit_eval_relation,
            sample_ids_status=capture.sample_ids_status,
            sample_ids_sha256=capture.sample_ids_sha256,
            estimator_params_sha256=native.estimator_params_sha256,
            estimator_params=native.estimator_params,
            nuisance_model_classes=native.nuisance_model_classes,
            alpha=native.alpha,
            confidence_level=native.confidence_level,
            native_point=native.native_point,
            native_lower_bound=native.native_lower_bound,
            native_upper_bound=native.native_upper_bound,
            native_mean_pred=native.native_mean_pred,
            native_mean_pred_stderr=native.native_mean_pred_stderr,
            native_stderr_mean=native.native_stderr_mean,
            standard_error_source=native.standard_error_source,
            standard_error_value=native.standard_error_value,
            native_pred_stderr_values=native.native_pred_stderr_values,
            selected_x_sha256=capture.selected_x_sha256,
            native_pred_sha256=native.native_pred_sha256,
            native_pred_stderr_sha256=native.native_pred_stderr_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            n_selected_rows=capture.n_selected_rows,
            contrast_status="established"
            if target_relation.contrast_status == "recomputed"
            else "not_established",
            control_value=(
                writer.capture.control_value
                if target_relation.contrast_status == "recomputed"
                else None
            ),
            treated_value=(
                writer.capture.treated_value
                if target_relation.contrast_status == "recomputed"
                else None
            ),
            request_estimand_status=request_context.request_estimand_status,
            request_estimand=request_context.request_estimand,
            request_target_scope_status=request_context.request_target_scope_status,
            request_target_scope=request_context.request_target_scope,
            outcome_variable_status=request_context.outcome_variable_status,
            outcome_variable_id=request_context.outcome_variable_id,
            treatment_variable_status=request_context.treatment_variable_status,
            treatment_variable_id=request_context.treatment_variable_id,
            request_alpha_status=request_context.request_alpha_status,
            requested_alpha=request_context.requested_alpha,
            requested_guarantee_status=request_context.requested_guarantee_status,
            requested_guarantee=request_context.requested_guarantee,
            search_uncertainty_task_binding_ref=task_binding_ir_ref,
            target_relation=target_relation,
            conditional_assumptions=native.conditional_assumptions,
            source_data_ref=source_ref,
            materialization_binding_ref=materialization_binding_ir_ref,
            invocation_basis_ref=None,
            invocation_basis_status="not_established",
            invocation_basis_reason="no_invocation_basis_artifact_contract",
            owned_attempt_anchor_ref=anchor_ir_ref,
            resource_evidence=resource,
            native_result_disposition=disposition,
            native_result_disposition_reason=disposition_reason,
            hte_result_ref=hte_result_ref,
            point_result_ref=point_result_ref,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
        )

    if writer.kind == "interval_estimate":
        native = writer.native_capture
        feature_names = tuple(capture.source_feature_names or ())
        legacy_result = HTEResult.model_validate(
            {
                "schema_version": "1.0",
                "method": (
                    CausalMethod.CAUSAL_FOREST
                    if anchor.method_fqn == "causal.hte.causal_forest@2.0.0"
                    else CausalMethod.FOREST_DR
                ),
                "ate": native.native_point,
                "ate_ci_lower": native.native_lower_bound,
                "ate_ci_upper": native.native_upper_bound,
                "confidence_level": native.confidence_level,
                "cate_values": list(writer.cate_values),
                "n_samples": capture.n_selected_rows,
                "n_treated": capture.n_treated,
                "n_control": capture.n_control,
                "n_features": len(feature_names),
                "feature_names": list(feature_names),
                "econml_estimator_class": native.estimator_class,
                "econml_params": native.estimator_params,
                "metadata": {
                    "method_fqn": anchor.method_fqn,
                    "method_abi": anchor.method_version,
                    "method_abi_digest": anchor.method_abi_digest,
                    "method_profile_id": method_profile_id,
                    "resolved_params_sha256": capture.resolved_params_sha256,
                    "source_data_sha256": capture.source_data_sha256,
                    "selected_input_sha256": capture.selected_input_sha256,
                    "selected_rows_sha256": capture.selected_rows_sha256,
                    "selected_x_sha256": capture.selected_x_sha256,
                    "selected_row_order_sha256": capture.selected_row_order_sha256,
                    "input_profile_id": capture.input_profile_id,
                    "resource_policy_digest": anchor.resource_policy_digest,
                    "materialization_binding_ref": materialization_binding_ir_ref.model_dump(
                        mode="json"
                    ),
                    "search_uncertainty_task_binding_ref": (
                        None
                        if task_binding_ir_ref is None
                        else task_binding_ir_ref.model_dump(mode="json")
                    ),
                    "econml_source_profile_sha256": native.econml_source_profile_sha256,
                    "ate_inference_method": native.ate_inference_method,
                    "conf_int_mean_method": native.conf_int_mean_method,
                    "native_result_class": native.native_result_class,
                    "native_pred_sha256": native.native_pred_sha256,
                    "native_pred_stderr_sha256": native.native_pred_stderr_sha256,
                    "observed_feature_count": capture.n_features,
                    "feature_names_status": (
                        "source_provided"
                        if capture.source_feature_names is not None
                        else "not_established"
                    ),
                },
            },
            strict=True,
        )
        persisted_hte_result_ref = _persist_and_check(
            store=store,
            ir_store=ir_store,
            model=legacy_result,
            persist=persist_hte_result_v2,
            inputs=point_inputs,
            artifact_ref_type=CoreArtifactRef,
            limits=limits,
            schema_name=HTEResultEvidenceRef.ARTIFACT_SCHEMA_NAME,
            schema_version=HTEResultEvidenceRef.ARTIFACT_SCHEMA_VERSION,
            validator=HTEResult,
        )
        hte_result_ref = persisted_hte_result_ref
        basis = _basis_for_native(
            writer,
            disposition="legacy_hte_result_admitted",
            disposition_reason=None,
            hte_result_ref=persisted_hte_result_ref,
        )
        basis_inputs = ((persisted_hte_result_ref, "hte_result"), *point_inputs)
        persisted_inference_basis_ref = _persist_and_check(
            store=store,
            ir_store=ir_store,
            model=basis,
            persist=persist_ate_inference_basis,
            inputs=basis_inputs,
            artifact_ref_type=CoreArtifactRef,
            limits=limits,
            schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
            schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
            validator=ATEInferenceBasis,
        )
        basis_ref = persisted_inference_basis_ref
        outcome = HTEIntervalOutcome(
            method_fqn=anchor.method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=method_profile_id,
            input_profile_id=capture.input_profile_id,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            selected_x_sha256=capture.selected_x_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            resolved_params_sha256=capture.resolved_params_sha256,
            n_selected_rows=capture.n_selected_rows,
            source_data_ref=source_ref,
            invocation_basis_ref=None,
            invocation_basis_status="not_established",
            invocation_basis_reason="no_invocation_basis_artifact_contract",
            owned_attempt_anchor_ref=anchor_ir_ref,
            resource_evidence=resource,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            **request_fields,
            target_relation=target_relation,
            limitations=tuple(
                dict.fromkeys((*writer.limitations, _SOURCE_VARIABLE_IDENTITY_LIMITATION))
            ),
            point_estimate=point_estimate,
            lower_bound=native.native_lower_bound,
            upper_bound=native.native_upper_bound,
            confidence_level=native.confidence_level,
            interval_semantics="native_mean_confidence_interval",
            inference_status="native_ate_inference_validated",
            hte_result_ref=persisted_hte_result_ref,
            inference_basis_ref=persisted_inference_basis_ref,
        )
        outcome_inputs = _numeric_outcome_inputs(
            result_ref=persisted_hte_result_ref,
            result_role="hte_result",
            inference_basis_ref=persisted_inference_basis_ref,
            base_inputs=point_inputs,
        )
    else:
        point_result = HTEPointResult(
            method_fqn=anchor.method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=method_profile_id,
            search_uncertainty_task_binding_ref=task_binding_ir_ref,
            resolved_params_sha256=capture.resolved_params_sha256,
            source_data_ref=source_ref,
            materialization_binding_ref=materialization_binding_ir_ref,
            source_data_sha256=capture.source_data_sha256,
            input_profile_id=capture.input_profile_id,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            selected_x_sha256=capture.selected_x_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            n_selected_rows=capture.n_selected_rows,
            point_estimate=writer.point_estimate,
            cate_values=tuple(writer.cate_values),
            owned_attempt_anchor_ref=anchor_ir_ref,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            resource_evidence=resource,
        )
        persisted_point_result_ref = _persist_and_check(
            store=store,
            ir_store=ir_store,
            model=point_result,
            persist=persist_hte_point_result,
            inputs=point_inputs,
            artifact_ref_type=CoreArtifactRef,
            limits=limits,
            schema_name=HTEPointResultRef.ARTIFACT_SCHEMA_NAME,
            schema_version=HTEPointResultRef.ARTIFACT_SCHEMA_VERSION,
            validator=HTEPointResult,
        )
        point_result_ref = persisted_point_result_ref
        native = writer.native_diagnostic
        if native is not None:
            disposition_reason: Literal[
                "point_not_contained_in_legacy_interval", "native_bounds_unordered"
            ] = (
                "native_bounds_unordered"
                if native.native_lower_bound > native.native_upper_bound
                else "point_not_contained_in_legacy_interval"
            )
            basis = _basis_for_native(
                writer,
                disposition="legacy_hte_result_unrepresentable",
                disposition_reason=disposition_reason,
                point_result_ref=persisted_point_result_ref,
            )
            basis_inputs = ((persisted_point_result_ref, "point_result"), *point_inputs)
            basis_ref = _persist_and_check(
                store=store,
                ir_store=ir_store,
                model=basis,
                persist=persist_ate_inference_basis,
                inputs=basis_inputs,
                artifact_ref_type=CoreArtifactRef,
                limits=limits,
                schema_name=ATEInferenceBasisRef.ARTIFACT_SCHEMA_NAME,
                schema_version=ATEInferenceBasisRef.ARTIFACT_SCHEMA_VERSION,
                validator=ATEInferenceBasis,
            )
        outcome = HTEPointOutcome(
            method_fqn=anchor.method_fqn,
            method_abi=anchor.method_version,
            method_abi_digest=anchor.method_abi_digest,
            method_profile_id=method_profile_id,
            input_profile_id=capture.input_profile_id,
            selected_input_sha256=capture.selected_input_sha256,
            selected_rows_sha256=capture.selected_rows_sha256,
            selected_x_sha256=capture.selected_x_sha256,
            selected_row_order_sha256=capture.selected_row_order_sha256,
            resolved_params_sha256=capture.resolved_params_sha256,
            n_selected_rows=capture.n_selected_rows,
            source_data_ref=source_ref,
            invocation_basis_ref=None,
            invocation_basis_status="not_established",
            invocation_basis_reason="no_invocation_basis_artifact_contract",
            owned_attempt_anchor_ref=anchor_ir_ref,
            point_result_ref=persisted_point_result_ref,
            inference_basis_ref=basis_ref,
            resource_evidence=resource,
            method_result_ref=point_ref,
            method_evidence_ref=evidence_ref,
            **request_fields,
            target_relation=target_relation,
            limitations=tuple(
                dict.fromkeys(
                    (
                        *writer.limitations,
                        *(
                            ("native_interval_not_representable_by_hte_result_v1",)
                            if native is not None
                            else ()
                        ),
                    )
                )
            ),
            point_estimate=point_estimate,
            inference_status=writer.inference_status,
            inference_reason=writer.inference_reason,
        )
        outcome_inputs = _numeric_outcome_inputs(
            result_ref=persisted_point_result_ref,
            result_role="point_result",
            inference_basis_ref=basis_ref,
            base_inputs=point_inputs,
        )
    outcome = _HTE_OUTCOME_ADAPTER.validate_python(outcome, strict=True)
    outcome_ref = _persist_and_check(
        store=store,
        ir_store=ir_store,
        model=outcome,
        persist=persist_hte_outcome,
        inputs=outcome_inputs,
        artifact_ref_type=CoreArtifactRef,
        limits=limits,
        schema_name=HTEOutcomeRef.ARTIFACT_SCHEMA_NAME,
        schema_version=HTEOutcomeRef.ARTIFACT_SCHEMA_VERSION,
        validator=_HTE_OUTCOME_ADAPTER,
    )
    refs = HTEFinalizedArtifactRefs(
        owned_attempt_anchor_ref=anchor_ir_ref,
        materialization_binding_ref=materialization_binding_ir_ref,
        hte_outcome_ref=outcome_ref,
        point_result_ref=point_result_ref,
        hte_result_ref=hte_result_ref,
        inference_basis_ref=basis_ref,
        refusal_diagnostic_ref=None,
        invocation_basis_ref=None,
    )
    summary = _bounded_summary(
        outcome=outcome,
        refs=refs,
        resource=resource,
        source_data_ref=source_ref,
        summary_model=DirectMethodExecutionHTESummary,
        relation_model=DirectMethodExecutionHTETargetRelation,
        resource_model=DirectMethodExecutionHTEResourceEvidence,
    )
    return HTEFinalizedRuntimeOutput(artifact_refs=refs, summary=summary)


__all__ = ["HTEFinalizedRuntimeOutput", "persist_runtime_hte_outcome"]
