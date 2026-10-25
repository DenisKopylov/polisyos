from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.scientist.methods.search.uncertainty import (
    SearchOwnedHistoricalAttemptAssociationResolver,
    SearchUncertaintyTaskBinding,
    SearchUncertaintyTaskBindingResolution,
    SearchUncertaintyTicketState,
    load_search_uncertainty_task_binding,
    resolve_admitted_search_uncertainty_task_binding,
    resolve_current_search_uncertainty_task_binding,
)
from tests.unit.scientist.methods.search.funnel.test_configured_observations import (
    _ready_current_projection_packet,
)


def _resolve(
    store: FileSystemCAS,
    binding_ref: ArtifactRef,
    binding: SearchUncertaintyTaskBinding,
    *,
    tenant_id: str | None = None,
) -> SearchUncertaintyTaskBindingResolution:
    return resolve_current_search_uncertainty_task_binding(
        store=store,
        binding_ref=binding_ref,
        tenant_id=binding.tenant_id if tenant_id is None else tenant_id,
        cell_id=binding.cell_id,
        request_projection=binding.request_projection,
        selected_method_fqn=binding.selected_method_fqn,
        selected_method_abi_version=binding.selected_method_abi_version,
        selected_method_abi_digest=binding.selected_method_abi_digest,
        selected_method_params_sha256=binding.selected_method_params_sha256,
        selected_method_params=binding.selected_method_params,
        selected_method_seed=binding.selected_method_seed,
        selected_inference_profile_id=binding.selected_inference_profile_id,
        selected_input_ref=binding.selected_method_input_ref,
        selected_input_sha256=binding.selected_method_input_content_sha256,
    )


def test_current_binding_roundtrip_resolves_selected_persisted_content_and_refuses_substitution(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    state, ticket_id = _ready_current_projection_packet(
        store,
        run_id="run-binding-resolution-roundtrip",
    )
    row = state._read_row(ticket_id)
    assert row is not None
    binding_ref = state.publish_task_binding(
        ticket_id,
        expected_generation=row.ticket_generation,
        expected_projection_revision=row.projection_revision,
    )
    assert binding_ref is not None

    fresh_state = SearchUncertaintyTicketState(store)
    current = fresh_state.read_current_snapshot(ticket_id)
    assert current is not None
    assert current.status == "available_as_of_task_epoch"
    assert current.projection is not None
    assert current.projection.live_currentness_status == "not_established"
    persisted = load_search_uncertainty_task_binding(store, binding_ref)
    resolution = _resolve(store, binding_ref, persisted)
    assert resolution.resolution_status == "current"
    assert resolution.closure_status == "recomputed"
    assert resolution.binding_ref == binding_ref
    assert resolution.binding == persisted
    assert resolution.binding_content_sha256 == binding_ref.artifact_id.hex

    wrong_digest = resolution.model_dump(mode="python")
    wrong_digest["binding_content_sha256"] = (
        "0" * 64 if resolution.binding_content_sha256 != "0" * 64 else "1" * 64
    )
    with pytest.raises(ValidationError, match="content digest differs from its ref"):
        SearchUncertaintyTaskBindingResolution.model_validate(wrong_digest, strict=True)

    wrong_profile_payload = binding_ref.model_dump(mode="json")
    wrong_profile_payload["manifest_profile_sha256"] = "sha256:" + "0" * 64
    foreign_profile_ref = ArtifactRef.model_validate(wrong_profile_payload, strict=True)
    with pytest.raises((TypeError, ValueError)):
        _resolve(store, foreign_profile_ref, persisted)

    with pytest.raises(ValueError, match="differs from the actual Runtime request"):
        _resolve(store, binding_ref, persisted, tenant_id="foreign-" + persisted.tenant_id)


def _resolve_admitted(
    store: FileSystemCAS,
    binding_ref: ArtifactRef,
    binding: SearchUncertaintyTaskBinding,
    *,
    tenant_id: str | None = None,
    task_epoch_ref: ArtifactRef | None = None,
    owned_historical_attempt_association_resolver: (
        SearchOwnedHistoricalAttemptAssociationResolver | None
    ) = None,
) -> SearchUncertaintyTaskBindingResolution:
    return resolve_admitted_search_uncertainty_task_binding(
        store=store,
        binding_ref=binding_ref,
        expected_ticket_id=binding.ticket_id,
        expected_ticket_generation=binding.ticket_generation,
        expected_owner_revision=binding.owner_revision,
        expected_projection_revision=binding.projection_revision,
        expected_projection_ref=binding.source_projection_ref,
        expected_task_admission_ref=binding.task_admission_ref,
        expected_task_epoch_ref=binding.task_epoch_ref
        if task_epoch_ref is None
        else task_epoch_ref,
        expected_owner_context_ref=binding.owner_context_ref,
        expected_tenant_id=binding.tenant_id if tenant_id is None else tenant_id,
        expected_cell_id=binding.cell_id,
        owned_historical_attempt_association_resolver=(
            owned_historical_attempt_association_resolver
        ),
    )


def test_admitted_binding_handoff_accepts_same_generation_history_and_rejects_revocation(
    tmp_path: Path,
) -> None:
    """Only the exact pre-admitted task epoch can survive a same-generation pointer move."""
    store = FileSystemCAS(tmp_path / "cas")
    state, ticket_id = _ready_current_projection_packet(
        store,
        run_id="run-admitted-binding-handoff",
    )
    row = state._read_row(ticket_id)
    assert row is not None
    binding_ref = state.publish_task_binding(
        ticket_id,
        expected_generation=row.ticket_generation,
        expected_projection_revision=row.projection_revision,
    )
    assert binding_ref is not None
    binding = load_search_uncertainty_task_binding(store, binding_ref)
    row = state._read_row(ticket_id)
    assert row is not None

    current = _resolve_admitted(store, binding_ref, binding)
    assert current.resolution_status == "current"
    assert current.closure_status == "recomputed"

    with pytest.raises(ValueError, match="differs from the selected task epoch"):
        _resolve_admitted(store, binding_ref, binding, task_epoch_ref=binding.owner_context_ref)
    with pytest.raises(ValueError, match="differs from the selected task scope"):
        _resolve_admitted(store, binding_ref, binding, tenant_id="foreign-tenant")

    selected = state._read_projection_for_row(row)
    assert selected is not None
    advanced = state._publish_locked(
        row,
        expected_generation=row.ticket_generation,
        projection=selected.model_copy(
            update={
                "limitations": tuple(sorted((*selected.limitations, "same_epoch_owner_advance")))
            }
        ),
    )
    assert advanced.ticket_generation == binding.ticket_generation
    assert advanced.current_binding_ref is None
    assert binding_ref in advanced.historical_binding_refs

    historical_resolver_calls: list[ArtifactRef] = []

    def record_historical_lookup(
        *,
        anchor_ref: ArtifactRef,
        expected_job_id: str,
        expected_completed_event_id: int,
        expected_tenant_id: str,
        expected_cell_id: str | None | object = None,
    ) -> None:
        del expected_job_id, expected_completed_event_id, expected_tenant_id, expected_cell_id
        historical_resolver_calls.append(anchor_ref)

    historical = _resolve_admitted(
        store,
        binding_ref,
        binding,
        owned_historical_attempt_association_resolver=record_historical_lookup,
    )
    assert historical_resolver_calls == []
    assert historical.resolution_status == "historical"
    assert historical.binding == binding

    revoked = state.bump_ticket_generation(ticket_id, expected_generation=binding.ticket_generation)
    assert revoked.ticket_generation == binding.ticket_generation + 1
    with pytest.raises(ValueError, match="generation differs"):
        _resolve_admitted(store, binding_ref, binding)
