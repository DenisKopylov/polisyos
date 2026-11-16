"""Prepare selected annual method inputs through the registered derivation owner.

The per-port native projection and arithmetic producer remains owned by
``model_input_routing``.  This adapter owns the temporal batch and artifact
assembly only.  It produces candidate staging, including incomplete coverage;
Foundry separately replays physical values and admits a complete horizon.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    validate_core_model_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import (
    DERIVED_MODEL_INPUT_PAYLOAD_KIND,
    DataSnapshot,
    DataSnapshotOwnerBound,
    DerivedInputCorrespondenceRef,
    DerivedModelInputStepDataSnapshotLineage,
    ModelInputStepCoverage,
    ModelInputStepScope,
    ModelInputStepSubject,
    RegisteredDerivedModelInputRequest,
    ResolvedDerivedInputAtStep,
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    SelectedVariableBindingRef,
    data_snapshot_owner_input_requirements,
    persist_resolved_input_binding_manifest,
    resolve_model_input_step_subjects,
)


class RegisteredDerivedModelInputStepRequest(BaseModel):
    """Native role selections for one required port and absolute model step."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    step_scope: ModelInputStepScope
    request: RegisteredDerivedModelInputRequest


@dataclass(frozen=True)
class DerivedModelInputStepPreparation:
    """Persisted candidate selections and computed coverage, without execution."""

    data_snapshot_ref: ArtifactRef
    resolved_binding_manifest_ref: ResolvedInputBindingManifestRef
    correspondence_refs: tuple[DerivedInputCorrespondenceRef, ...]
    coverage: ModelInputStepCoverage


def prepare_registered_derived_model_input_steps(
    store: FileSystemCAS,
    *,
    base_data_snapshot_ref: ArtifactRef,
    obligation_set_ref: ArtifactRef,
    inputs: tuple[RegisteredDerivedModelInputStepRequest, ...],
) -> DerivedModelInputStepPreparation:
    """Replay selected native rows into a temporal candidate input batch.

    Every request is checked against the original immutable full-horizon set
    before any arithmetic runs.  Repeating an existing request reopens its same
    selected occurrences; it does not acquire data or dispatch N5.  Input order
    is canonicalized by model port and step.  Incomplete coverage remains
    candidate staging and is never an execution admission.

    Args:
        store: Existing local store containing the selected model and native rows.
        base_data_snapshot_ref: Exact original predecessor snapshot, not a staged output.
        obligation_set_ref: Original selected-model full-horizon obligation set.
        inputs: Actual registered source selections for the supplied step subset.

    Returns:
        Typed snapshot and manifest refs with computed supplied/missing scopes.

    Raises:
        ValueError: If identity, original base, source facts or supported profile differs.
    """
    from polisyos.foundry.data_plane import load_input_bindings
    from polisyos.runtime.quality.model_input_routing import (
        _prepare_registered_derived_port_output,
    )

    if (
        type(inputs) is not tuple
        or len(inputs) > 32
        or any(type(row) is not RegisteredDerivedModelInputStepRequest for row in inputs)
    ):
        raise ValueError("registered_derived_step_input_requests_invalid")
    if not inputs:
        raise ValueError("registered_derived_step_input_no_verified_rows")
    ordered = tuple(sorted(inputs, key=lambda row: (row.step_scope.port_id, row.step_scope.step)))
    binding_ids = tuple(row.request.binding_id for row in ordered)
    if len(set(binding_ids)) != len(binding_ids):
        raise ValueError("registered_derived_step_input_binding_id_duplicate")
    resolved = resolve_model_input_step_subjects(
        store,
        obligation_set_ref=obligation_set_ref,
        subjects=tuple(
            ModelInputStepSubject(
                model_input_obligation_ref=row.request.model_input_obligation_ref,
                step_scope=row.step_scope,
            )
            for row in ordered
        ),
    )
    selected_set = resolved.obligation_set
    if (
        selected_set.schema_version != "1.2"
        or selected_set.authority_purpose != "candidate_acquisition_routing_only"
    ):
        raise ValueError("registered_derived_step_input_original_set_required")
    if len(resolved.coverage.required_step_scopes) > 32:
        raise ValueError("registered_derived_step_input_horizon_profile_unrepresentable")
    predecessor = load_input_bindings(store, selected_set.invocation.input_bindings_ref)
    if (
        predecessor.schema_version == "1.5"
        or artifact_ref_identity_key(predecessor.data_snapshot_ref)
        != artifact_ref_identity_key(base_data_snapshot_ref)
        or artifact_ref_identity_key(predecessor.registry_bundle_ref)
        != artifact_ref_identity_key(selected_set.invocation.registry_bundle_ref)
        or artifact_ref_identity_key(predecessor.bound_state_snapshot_ref)
        != artifact_ref_identity_key(selected_set.prestate_ref)
    ):
        raise ValueError("registered_derived_step_input_original_base_mismatch")
    base = validate_core_model_json_artifact(DataSnapshot, store, base_data_snapshot_ref)
    if isinstance(base.source_lineage, DerivedModelInputStepDataSnapshotLineage):
        raise ValueError("registered_derived_step_input_original_base_mismatch")
    members = {
        artifact_ref_identity_key(ref): member
        for ref, member in zip(selected_set.obligation_refs, resolved.obligations, strict=True)
    }
    outputs = tuple(
        _prepare_registered_derived_port_output(
            store,
            obligation_set_ref=obligation_set_ref,
            request=row.request,
            obligation=members[artifact_ref_identity_key(row.request.model_input_obligation_ref)],
            expected_step_scope=row.step_scope,
        )
        for row in ordered
    )
    if any(output.projection != "scalar" for output in outputs):
        raise ValueError("registered_derived_step_input_scalar_profile_required")
    selections = tuple(
        ResolvedDerivedInputAtStep(step_scope=row.step_scope, selection=output.selection)
        for row, output in zip(ordered, outputs, strict=True)
    )
    if tuple(row.step_scope for row in selections) != resolved.coverage.supplied_step_scopes:
        raise ValueError("registered_derived_step_input_output_scope_mismatch")

    values: dict[str, dict[str, object]] = {}
    payload_inputs = [input_ref_from_artifact_ref(base.data_ref, role="context.base_payload")]
    for row, output in zip(selections, outputs, strict=True):
        selection = row.selection
        key = hashlib.sha256(selection.binding_id.encode()).hexdigest()[:20]
        if key in values or selection.source_path != f"derived_inputs.{key}.value":
            raise ValueError("registered_derived_step_input_source_path_collision")
        values[key] = {"value": output.value}
        payload_inputs.extend(
            (
                input_ref_from_artifact_ref(
                    selection.output_ref, role=selection.payload_output_role()
                ),
                input_ref_from_artifact_ref(
                    selection.correspondence_ref, role="derived.correspondence"
                ),
            )
        )
    payload_ref = store.put_json(
        {"derived_inputs": values},
        PutOptions(
            kind=DERIVED_MODEL_INPUT_PAYLOAD_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.runtime.quality.DerivedModelInputPayload", version="1.1"
            ),
            inputs=payload_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    snapshot = DataSnapshotOwnerBound(
        data_ref=payload_ref,
        source_lineage=DerivedModelInputStepDataSnapshotLineage(
            base_data_snapshot_ref=base_data_snapshot_ref,
            model_input_obligation_set_ref=obligation_set_ref,
            selections=selections,
        ),
        stats={"snapshot_id": "derived-model-input-steps-" + payload_ref.artifact_id.hex[:20]},
        notes=[
            "candidate_simulation_input_only",
            "derived_input_not_acquired_observation",
            "external_empirical_context_not_established",
            "execution_admission_not_established",
        ],
    )
    snapshot_ref = store.put_json(
        snapshot,
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=snapshot.ARTIFACT_SCHEMA_NAME, version=snapshot.ARTIFACT_SCHEMA_VERSION
            ),
            inputs=[
                input_ref_from_artifact_ref(ref, role=role)
                for ref, role in data_snapshot_owner_input_requirements(snapshot)
            ],
        ),
        return_selected_profile=True,
    )
    manifest_ref = persist_resolved_input_binding_manifest(
        store,
        ResolvedInputBindingManifest(
            schema_version="3.0",
            data_snapshot_ref=SelectedVariableBindingRef.model_validate(
                snapshot_ref.model_dump(mode="python")
            ),
            model_input_obligation_set_ref=SelectedVariableBindingRef.model_validate(
                obligation_set_ref.model_dump(mode="python")
            ),
            retained_binding_ids=tuple(
                rule.binding_id
                for rule in predecessor.rules
                if rule.target_slot_id in selected_set.supplied_initial_slots
            ),
            method_input_steps=selections,
        ),
    )
    return DerivedModelInputStepPreparation(
        data_snapshot_ref=snapshot_ref,
        resolved_binding_manifest_ref=manifest_ref,
        correspondence_refs=tuple(row.selection.correspondence_ref for row in selections),
        coverage=resolved.coverage,
    )
