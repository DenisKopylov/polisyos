from __future__ import annotations

import hashlib
import json
from typing import TypedDict

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.owned_attempt_anchor import SelectedArtifactRef
from polisyos.core.contracts.runtime import ContentAdmittedObservationalRunIntent


class ArtifactRefPayload(TypedDict):
    artifact_id: str
    kind: str
    media_type: str
    manifest_profile_sha256: str


def _ref(
    kind: str,
    marker: str,
    profile_marker: str | None = None,
    *,
    artifact_id: str | None = None,
    manifest_profile_sha256: str | None = None,
) -> ArtifactRefPayload:
    profile = profile_marker or marker
    return ArtifactRefPayload(
        artifact_id=artifact_id or "sha256:" + marker * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=(manifest_profile_sha256 or "sha256:" + profile * 64),
    )


def _admitted_payload(
    *,
    context_binding_artifact_id: str | None = None,
    context_binding_profile: str | None = None,
    context_binding_kind: str = "scientist.search.uncertainty_task_binding",
    selected_input_marker: str = "c",
    search_binding_tenant_id: str = "tenant-a",
    search_binding_cell_id: str = "cell-a",
) -> dict[str, object]:
    binding_ref = _ref("scientist.search.uncertainty_task_binding", "a", "b")
    request_binding_ref = _ref(
        context_binding_kind,
        "a",
        "b",
        artifact_id=context_binding_artifact_id or binding_ref["artifact_id"],
        manifest_profile_sha256=(context_binding_profile or binding_ref["manifest_profile_sha256"]),
    )
    input_ref = _ref("ir.observation_method_input", "c", "d")
    selected_input_ref = (
        input_ref
        if selected_input_marker == "c"
        else _ref("ir.observation_method_input", selected_input_marker, "d")
    )
    params = {"alpha": 0.05}
    params_sha = hashlib.sha256(
        json.dumps(
            params,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    snapshot = {
        "binding_ref": binding_ref,
        "binding_content_sha256": "a" * 64,
        "ticket_id": "ticket-1",
        "ticket_generation": 1,
        "owner_revision": 1,
        "projection_revision": 1,
        "projection_ref": _ref("scientist.search.uncertainty_ticket_projection", "e"),
        "task_admission_ref": _ref("scientist.search.uncertainty_task_admission", "f"),
        "task_epoch_ref": _ref("scientist.search.uncertainty_task_epoch", "1"),
        "owner_context_ref": _ref("scientist.search.uncertainty_owner_task_context", "2"),
        "basis_ref": _ref("scientist.search.uncertainty_basis", "3"),
        "dependency_inventory_ref": _ref("scientist.search.uncertainty_input_inventory", "4"),
        "dependency_inventory_sha256": "5" * 64,
        "source_projection_ref": _ref("scientist.search.uncertainty_ticket_projection", "6"),
        "selected_method_fqn": "causal.hte.forest_dr@2.0.0",
        "selected_method_abi_version": "2.0.0",
        "selected_method_abi_digest": "7" * 64,
        "selected_method_params": params,
        "selected_method_params_sha256": params_sha,
        "selected_method_seed": 17,
        "selected_inference_profile_id": "econml.forest_dr.native_mean@2.0",
        "selected_method_input_ref": selected_input_ref,
        "selected_method_input_content_sha256": selected_input_marker * 64,
        "tenant_id": "tenant-a",
        "cell_id": "cell-a",
        "resolved_at": "2026-10-23T00:00:00+00:00",
        "resolution_status": "current",
        "closure_status": "recomputed",
    }
    request_context = {
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
        "requested_guarantee_status": "not_established",
        "requested_guarantee": None,
        "search_uncertainty_task_binding_ref": request_binding_ref,
    }
    return {
        "schema_version": "polisyos.runtime.content_admitted_observational_run_intent.v2",
        "job_id": "job-1",
        "run_id": "run-1",
        "attempt": 1,
        "requested_intent_ref": _ref("runtime.observational_run_intent", "8"),
        "requested_source_ref": input_ref,
        "source_manifest_sha256": "9" * 64,
        "resource_policy_ref": _ref("runtime.observational_input_resource_policy", "a"),
        "submitted_input_ref": input_ref,
        "effective_input_ref": input_ref,
        "contract_target_id": "foundry.causal.hte_observational_data.v1",
        "contract_target": "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
        "method_fqn": "causal.hte.forest_dr@2.0.0",
        "owned_hte_request_context": request_context,
        "search_binding_admission": snapshot,
        "search_binding_tenant_id": search_binding_tenant_id,
        "search_binding_cell_id": search_binding_cell_id,
        "source_protocol": "method_input_envelope_v1",
        "normalization": "canonical_passthrough",
        "limitations": [
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
        ],
        "source_governance": {"classification": "public"},
        "source_tenant_context": None,
        "observed_manifest_bytes": 100,
        "observed_manifest_selection_bytes": 100,
        "observed_manifest_verification_bytes": 10,
        "observed_payload_bytes": 20,
        "observed_source_bytes": 130,
        "payload_integrity_verified": True,
        "observed_bytes": 20,
        "observed_depth": 2,
        "observed_elements": 7,
        "resource_policy_digest": "e" * 64,
    }


def _validate_wire_payload(
    payload: dict[str, object],
) -> ContentAdmittedObservationalRunIntent:
    return ContentAdmittedObservationalRunIntent.model_validate_json(
        json.dumps(payload, ensure_ascii=False, allow_nan=False),
        strict=True,
    )


def test_content_admitted_binding_join_uses_full_identity_across_ref_subtypes() -> None:
    parsed = _validate_wire_payload(_admitted_payload())

    assert parsed.search_binding_admission is not None
    assert parsed.owned_hte_request_context is not None
    admission_ref = parsed.search_binding_admission.binding_ref
    request_ref = parsed.owned_hte_request_context.search_uncertainty_task_binding_ref
    assert type(admission_ref) is ArtifactRef
    assert type(request_ref) is SelectedArtifactRef
    assert artifact_ref_identity_key(admission_ref) == artifact_ref_identity_key(request_ref)


def test_content_admitted_binding_join_rejects_changed_artifact_identity() -> None:
    payload = _admitted_payload(context_binding_artifact_id="sha256:" + "0" * 64)

    with pytest.raises(
        ValidationError,
        match="content_admitted_search_snapshot_selection_mismatch",
    ):
        _validate_wire_payload(payload)


def test_content_admitted_binding_join_rejects_changed_selected_profile() -> None:
    payload = _admitted_payload(context_binding_profile="sha256:" + "f" * 64)

    with pytest.raises(
        ValidationError,
        match="content_admitted_search_snapshot_selection_mismatch",
    ):
        _validate_wire_payload(payload)


def test_content_admitted_binding_join_rejects_wrong_binding_kind() -> None:
    payload = _admitted_payload(context_binding_kind="scientist.search.other_binding")

    with pytest.raises(
        ValidationError,
        match="owned_attempt_search_binding_ref_kind_mismatch",
    ):
        _validate_wire_payload(payload)


def test_content_admitted_binding_join_rejects_changed_selected_source() -> None:
    payload = _admitted_payload(selected_input_marker="d")

    with pytest.raises(
        ValidationError,
        match="content_admitted_search_snapshot_selection_mismatch",
    ):
        _validate_wire_payload(payload)


@pytest.mark.parametrize(
    ("search_binding_tenant_id", "search_binding_cell_id"),
    [("tenant-other", "cell-a"), ("tenant-a", "cell-other")],
)
def test_content_admitted_binding_join_rejects_changed_owner_context(
    search_binding_tenant_id: str, search_binding_cell_id: str
) -> None:
    payload = _admitted_payload(
        search_binding_tenant_id=search_binding_tenant_id,
        search_binding_cell_id=search_binding_cell_id,
    )

    with pytest.raises(
        ValidationError,
        match="content_admitted_search_snapshot_selection_mismatch",
    ):
        _validate_wire_payload(payload)
