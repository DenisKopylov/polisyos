"""Real native sources are resealed under a new complete method context.

This component uses actual compiler, native occurrence, derivation, CAS and
Foundry owners. It does not construct a Runtime job, authorization, Generic N5
input, numerical result, or protected successor selection.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts import (
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import DataSnapshot, FoundryInputBindingsRef
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_composition_binding import RegisteredMeasurementRole
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.foundry.data_plane import (
    load_input_bindings,
    reconcile_selected_method_input_bindings,
    replay_selected_method_input_facts,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.model_input_requirements import (
    preflight_current_use_method_input_revalidation,
    preflight_program_graph_inputs,
)
from polisyos.runtime.quality.model_input_routing import (
    materialize_registered_derived_model_inputs,
    reseal_registered_method_input_bindings,
)
from tests._helpers.registered_derived_method_input import (
    prepare_registered_method_input_preflight,
    prepare_registered_method_input_request,
)
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.integration.core_runtime.test_candidate_experiment_generations_served import (
    _forbid_retained_generation_n5,
)


def test_registered_method_reseal_replays_fresh_context_and_exact_source_views(tmp_path):
    """Fresh proof refs preserve values, while a same-value source swap refuses."""
    slots = ("ledger.a", "ledger.b")
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slots=slots,
        method_instances=2,
        mapped=True,
    )
    try:
        with _forbid_retained_generation_n5() as n5_entries:
            original = prepare_registered_method_input_preflight(case)
            old_set, old_members = load_model_input_obligation_set(
                case.store, original.obligation_set_ref
            )
            old_refs = {
                member.port.slot_id: ref
                for ref, member in zip(old_set.obligation_refs, old_members, strict=True)
            }
            requests = tuple(
                prepare_registered_method_input_request(
                    case,
                    metadata["method_inputs_by_slot"][slot],
                    preflight=original,
                    model_input_obligation_ref=old_refs[slot],
                    ratio_value=Decimal("-0.03") if index == 0 else Decimal("0.01"),
                    binding_id=f"registered-{slot}",
                )
                for index, slot in enumerate(slots)
            )
            source = materialize_registered_derived_model_inputs(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=original.obligation_set_ref,
                inputs=requests,
            )
            source_bindings = load_input_bindings(case.store, source.input_bindings_ref)
            context = old_set.invocation.context.model_copy(
                update={"run_id": "registered-method-reseal-component-current"}
            )
            arguments = {
                "interface_ref": old_set.invocation.interface_ref,
                "program_graph_ref": old_set.invocation.program_graph_ref,
                "exec_plan_ref": old_set.invocation.exec_plan_ref,
                "registry_bundle_ref": old_set.invocation.registry_bundle_ref,
                "input_bindings_ref": FoundryInputBindingsRef.model_validate(
                    source.input_bindings_ref.model_dump(mode="python")
                ),
                "context": context,
                "steps": (0,),
            }
            with pytest.raises(
                ValueError, match=r"^model_input_method_selected_obligation_mismatch$"
            ):
                preflight_program_graph_inputs(case.store, **arguments)
            current = preflight_current_use_method_input_revalidation(case.store, **arguments)
            fresh_set, fresh_members = load_model_input_obligation_set(
                case.store, current.obligation_set_ref
            )
            assert fresh_set.schema_version == "1.3"
            assert fresh_set.purpose == "current_use_method_input_revalidation"
            assert fresh_set.authority_purpose == "candidate_execution_input_revalidation_only"
            assert {member.port.slot_id for member in fresh_members} == set(slots)
            assert fresh_set.invocation.context == context
            assert fresh_set.invocation.context != old_set.invocation.context
            assert artifact_ref_identity_key(fresh_set.invocation.input_bindings_ref) == (
                artifact_ref_identity_key(source.input_bindings_ref)
            )
            fresh = reseal_registered_method_input_bindings(
                case.store,
                source_input_bindings_ref=source.input_bindings_ref,
                obligation_set_ref=current.obligation_set_ref,
                expected_invocation=current.invocation,
            )
            old_snapshot = validate_core_model_json_artifact(
                DataSnapshot, case.store, source.data_snapshot_ref
            )
            new_snapshot = validate_core_model_json_artifact(
                DataSnapshot, case.store, fresh.data_snapshot_ref
            )
            # The actual writer must support the selected-view DAG. An equal
            # payload is not given a nonce or disconnected from its old parent.
            assert old_snapshot.data_ref.artifact_id == new_snapshot.data_ref.artifact_id
            assert artifact_ref_identity_key(old_snapshot.data_ref) != artifact_ref_identity_key(
                new_snapshot.data_ref
            )
            assert artifact_ref_identity_key(source.data_snapshot_ref) != artifact_ref_identity_key(
                fresh.data_snapshot_ref
            )
            parent = next(
                edge
                for edge in case.store.get_manifest(new_snapshot.data_ref).inputs
                if edge.role == "context.base_payload"
            )
            assert parent.artifact_id == old_snapshot.data_ref.artifact_id
            assert parent.manifest_profile_sha256 == old_snapshot.data_ref.manifest_profile_sha256
            fresh_store = FileSystemCAS(case.store_root)
            old_facts = replay_selected_method_input_facts(
                fresh_store,
                input_bindings_ref=source.input_bindings_ref,
                expected_invocation=old_set.invocation,
            )
            fresh_facts = replay_selected_method_input_facts(
                fresh_store,
                input_bindings_ref=fresh.input_bindings_ref,
                expected_invocation=current.invocation,
            )
            assert fresh_facts.bindings.bound_state_snapshot_ref == (
                source_bindings.bound_state_snapshot_ref
            )
            assert set(fresh_facts.values) == set(slots)
            for slot in slots:
                before, after = old_facts.values[slot], fresh_facts.values[slot]
                assert (after.dtype.str, after.shape, after.tobytes(order="C")) == (
                    before.dtype.str,
                    before.shape,
                    before.tobytes(order="C"),
                )
            old_manifest = load_resolved_input_binding_manifest(
                fresh_store, source.resolved_binding_manifest_ref
            )
            new_manifest = load_resolved_input_binding_manifest(
                fresh_store, fresh.resolved_binding_manifest_ref
            )
            for before, after in zip(
                old_manifest.derivations, new_manifest.derivations, strict=True
            ):
                assert before.model_port_id == after.model_port_id
                assert artifact_ref_identity_key(before.recipe_ref) != artifact_ref_identity_key(
                    after.recipe_ref
                )
                assert artifact_ref_identity_key(
                    before.certificate_ref
                ) != artifact_ref_identity_key(after.certificate_ref)
            # Both actual scale observations are 200B with the same registered
            # meaning. Their distinct selected receipts cannot be substituted.
            scales = tuple(
                next(role for role in request.role_occurrences if role.role == "scale_input")
                for request in requests
            )
            assert artifact_ref_identity_key(scales[0].occurrence_ref) != artifact_ref_identity_key(
                scales[1].occurrence_ref
            )
            fresh_refs = {
                member.port.slot_id: ref
                for ref, member in zip(fresh_set.obligation_refs, fresh_members, strict=True)
            }
            reissued = tuple(
                request.model_copy(
                    update={
                        "model_input_obligation_ref": SelectedVariableBindingRef.model_validate(
                            fresh_refs[slot].model_dump(mode="python")
                        )
                    }
                )
                for request, slot in zip(requests, slots, strict=True)
            )
            changed_roles = tuple(
                RegisteredMeasurementRole(role=role.role, occurrence_ref=scales[1].occurrence_ref)
                if role.role == "scale_input"
                else role
                for role in reissued[0].role_occurrences
            )
            with pytest.raises(
                ValueError, match=r"^registered_method_reseal_source_selection_mismatch$"
            ):
                materialize_registered_derived_model_inputs(
                    case.store,
                    base_data_snapshot_ref=source.data_snapshot_ref,
                    obligation_set_ref=current.obligation_set_ref,
                    inputs=(
                        reissued[0].model_copy(update={"role_occurrences": changed_roles}),
                        reissued[1],
                    ),
                )
            restored = reconcile_selected_method_input_bindings(
                fresh_store,
                input_bindings_ref=fresh.input_bindings_ref,
                expected_invocation=current.invocation,
                effective_step=0,
            )
            assert set(restored.values) == set(slots)
            assert n5_entries == []
    finally:
        case.close()
