"""Selected N7 leaf collections feed the actual registered semantic producer."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import (
    SelectedVariableBindingRef,
    load_resolved_input_binding_manifest,
)
from polisyos.core.contracts.semantic_composition_binding import (
    persist_registered_derived_input_profile,
)
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import acquisition_world_growth as owner
from polisyos.runtime.quality.model_input_requirements import SelectedProgramGraphInputBasis
from polisyos.runtime.quality.model_input_routing import (
    materialize_registered_derived_model_inputs,
    plan_selected_model_input_routing,
)
from tests._helpers.acquisition_production import _resolver
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.data_forge.domains.catalog.knowledge.test_acquisition_authority_model_input_discovery import (
    _authority_entry,
)
from tests.unit.runtime.quality.test_n7_derivation_bundle import (
    _marker,
    _pending_source,
    _profile,
    _target_gap,
)


@pytest.mark.parametrize("registered_bundle", [False, True], ids=("historical-v1", "registered-v2"))
def test_native_n7_roles_reach_registered_batch_and_incomplete_inputs_stay_pending(
    tmp_path: Path,
    registered_bundle: bool,
) -> None:
    """Opaque native names and registered roles travel through persisted owners."""
    case, metadata = prepare_selected_method_input_case(
        tmp_path / "method", method_class=PeriodFlowToStock
    )
    try:
        materialize_registered_method_input_case(case, metadata)
        profile = metadata["registered_profile"]
        obligation = metadata["obligation"]
        selected_set_ref = metadata["preflight"].obligation_set_ref
        budget, budget_ref = _profile(case.store)
        supplier = _marker(case.store, "selected-native-semantic-supplier")
        selected_parents = {}
        if registered_bundle:
            invocation = metadata["preflight"].invocation
            authority, _entry = _resolver(
                tmp_path / "catalog-authority",
                authority_entry=_authority_entry(
                    obligation.port.semantic_definition_ref,
                    obligation.port.representation_ref,
                    suffix="registered-native-materialization",
                ),
            )
            routing = plan_selected_model_input_routing(
                case.store,
                obligation_set_ref=selected_set_ref,
                selected_basis=SelectedProgramGraphInputBasis(
                    context=invocation.context,
                    program_graph_ref=invocation.program_graph_ref,
                    exec_plan_ref=invocation.exec_plan_ref,
                    registry_bundle_ref=invocation.registry_bundle_ref,
                    input_bindings_ref=invocation.input_bindings_ref,
                    steps=invocation.steps,
                    parameter_override_bundle_ref=invocation.parameter_override_bundle_ref,
                ),
                catalog_authority=authority,
                report_version="2.0",
            )
            selected_parents = {
                "schema_version": "policyos.runtime.n7_derivation_bundle.v2",
                "registered_profile_ref": artifacts.ArtifactRef.model_validate(
                    metadata["registered_profile_ref"].model_dump(mode="python")
                ),
                "model_input_routing_report_ref": routing.report_ref,
            }

        def basis(value):
            return planner.N7DerivationBasis.model_validate(value.model_dump(mode="python"))

        sources = tuple(
            _pending_source(
                "leaf-" + str(index),
                basis(row.basis),
                _target_gap(obligation.context, f"test.native.external.{index}"),
                alternatives=(supplier,),
            )
            for index, row in enumerate(profile.inputs)
        )
        bundle = planner.N7DerivationBundle(
            obligation_set_ref=selected_set_ref,
            model_input_obligation_ref=metadata["obligation_ref"],
            target_basis=basis(profile.output),
            dag_budget_profile_ref=budget_ref,
            dag_budget_profile=budget,
            source_nodes=sources,
            operation_nodes=(
                planner.N7DerivationOperationNode(
                    node_id="selected-root",
                    operator_ref=profile.registry_ref,
                    family_id=profile.family_id,
                    method_version=profile.method_version,
                    output_basis=basis(profile.output),
                    role_inputs=tuple(
                        planner.N7DerivationRoleInput(
                            role=row.role,
                            input_node_id=source.node_id,
                            source_basis=source.source_basis,
                        )
                        for row, source in zip(profile.inputs, sources, strict=True)
                    ),
                ),
            ),
            root_node_id="selected-root",
            input_closure_status="partial",
            **selected_parents,
        )
        bundle_ref = planner.persist_n7_derivation_bundle(case.store, bundle)
        original_bundle_bytes = case.store.get_bytes(bundle_ref)
        collected = tuple(
            owner.NativeDerivationCollectedInput(
                source_node_id=source.node_id,
                source_basis=source.source_basis,
                supplier_ref=supplier,
                occurrence_ref=metadata["native_sources"][row.role]["occurrence_ref"],
                source_receipt_ref=metadata["native_sources"][row.role]["source_receipt_ref"],
                source_passport_ref=metadata["native_sources"][row.role]["source_passport_ref"],
            )
            for row, source in zip(profile.inputs, sources, strict=True)
        )
        complete = owner.NativeDerivationInputCollection(
            derivation_bundle_ref=bundle_ref,
            source_node_ids=tuple(source.node_id for source in sources),
            source_inputs=collected,
            pending_actions=(),
            input_closure_status="inputs_complete",
        )
        complete_ref = owner.persist_native_derivation_input_collection(case.store, complete)
        request = owner.prepare_native_derivation_materialization_request(
            case.store,
            collection_ref=complete_ref,
            profile_ref=metadata["registered_profile_ref"],
            binding_id="native-n7-selected-flow",
        )
        assert tuple(
            (row.role, str(row.occurrence_ref.artifact_id)) for row in request.role_occurrences
        ) == tuple(
            (row.role, str(metadata["native_sources"][row.role]["occurrence_ref"].artifact_id))
            for row in profile.inputs
        )
        batch = materialize_registered_derived_model_inputs(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=selected_set_ref,
            inputs=(request,),
        )
        (selection,) = load_resolved_input_binding_manifest(
            case.store, batch.resolved_binding_manifest_ref
        ).derivations
        assert artifacts.artifact_ref_identity_key(selection.derivation_bundle_ref) == (
            artifacts.artifact_ref_identity_key(bundle_ref)
        )
        assert selection.binding_id == request.binding_id
        assert case.store.get_bytes(bundle_ref) == original_bundle_bytes
        assert complete.target_satisfaction_status == "unsatisfied"
        assert complete.semantic_admissibility == "not_established"
        bindings = load_input_bindings(case.store, batch.input_bindings_ref)
        assert bindings.selected_method_inputs is not None
        (foundry_input,) = bindings.selected_method_inputs
        assert foundry_input.canonical_value == Decimal("-6000000000")
        assert "warning:n7_derivation_bundle_structure_only" in bindings.notes
        pending_phase_ref = _marker(
            case.store,
            "pending-world-commit",
            kind="runtime_quality.acquisition_route_phase_receipt",
        )
        current_inputs = {
            "collection_refs": (complete_ref,),
            "configured_port_source_ref": supplier,
            "registered_profile_refs": (request.profile_ref,),
            "base_data_snapshot_ref": case.data_snapshot_ref,
            "pending_action_phase_ref": pending_phase_ref,
        }
        checkpoint = owner.NativeDerivationWorldCheckpoint(
            **current_inputs,
            data_snapshot_ref=batch.data_snapshot_ref,
            resolved_binding_manifest_ref=batch.resolved_binding_manifest_ref,
            correspondence_refs=(selection.correspondence_ref,),
            input_bindings_ref=batch.input_bindings_ref,
            world_model_ref=_marker(case.store, "candidate-world"),
            action_phase_ref=str(pending_phase_ref.artifact_id),
            tenant_id="native-tests",
            cell_id="runtime",
            run_id="native-n7",
            source_job_id="source",
            action_job_id="action",
            route_id=str(supplier.artifact_id),
            transaction_time=datetime(2026, 11, 20, tzinfo=UTC),
        )
        checkpoint_ref = case.store.put_json(
            checkpoint.model_dump(mode="json"),
            artifacts.PutOptions(
                kind="runtime_quality.acquisition_candidate_world_checkpoint",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        recovered = owner.NativeDerivationWorldCheckpoint.model_validate(
            artifacts.load_core_json_artifact(case.store, checkpoint_ref)
        )
        assert type(recovered.registered_profile_refs[0]) is artifacts.ArtifactRef
        assert recovered._matches_input_selection(**current_inputs)

        wrong_profile = request.profile_ref.model_copy(
            update={"manifest_profile_sha256": supplier.manifest_profile_sha256}
        )
        assert not recovered._matches_input_selection(
            **(current_inputs | {"registered_profile_refs": (wrong_profile,)})
        )
        unselected_profile = request.profile_ref.model_copy(
            update={"manifest_profile_sha256": None}
        )
        with pytest.raises(ValueError, match="native_derivation_source_ref_unselected"):
            recovered._matches_input_selection(
                **(current_inputs | {"registered_profile_refs": (unselected_profile,)})
            )

        if registered_bundle:
            # Preserve the profile content ID, graph, roles, and wire schema
            # while substituting an unselected manifest profile. Make the
            # forged bundle internally agree with its own substituted edge.
            selected_profile = metadata["registered_profile_ref"]
            wrong_profile = selected_profile.model_copy(
                update={"manifest_profile_sha256": "sha256:" + "1" * 64}
            )
            bundle_manifest = case.store.get_manifest(bundle_ref)
            wrong_profile_edges = [
                artifacts.input_ref_from_artifact_ref(wrong_profile, role=edge.role)
                if edge.role == "selected_registered_semantic_profile"
                else edge
                for edge in bundle_manifest.inputs
            ]
            for patch, edges, reason in (
                (
                    {"registered_profile_ref": wrong_profile.model_dump(mode="json")},
                    wrong_profile_edges,
                    "foundry_input_bindings_composition_bundle_profile_mismatch",
                ),
                (
                    {"authority_purpose": "measurement_admission"},
                    bundle_manifest.inputs,
                    "foundry_input_bindings_composition_bundle_authority_mismatch",
                ),
            ):
                wrong_bundle = case.store.put_json(
                    bundle.model_dump(mode="json") | patch,
                    artifacts.PutOptions(
                        kind=bundle_ref.kind,
                        media_type=bundle_ref.media_type,
                        schema=bundle_manifest.artifact_schema,
                        producer=bundle_manifest.producer,
                        canon=bundle_manifest.canon,
                        inputs=edges,
                    ),
                    canon_spec=planner._n7_derivation_bundle_write_profile(bundle)[1],
                    return_selected_profile=True,
                )
                assert case.store.verify(wrong_bundle).ok
                wrong_bundle_selection = SelectedVariableBindingRef.model_validate(
                    wrong_bundle.model_dump(mode="python")
                )
                with pytest.raises(ValueError, match=reason):
                    materialize_registered_derived_model_inputs(
                        case.store,
                        base_data_snapshot_ref=case.data_snapshot_ref,
                        obligation_set_ref=selected_set_ref,
                        inputs=(
                            request.model_copy(
                                update={"derivation_bundle_ref": wrong_bundle_selection}
                            ),
                        ),
                    )

        partial = complete.model_copy(
            update={
                "source_inputs": collected[:1],
                "pending_actions": (
                    owner.NativeDerivationPendingAction(
                        source_node_id=sources[1].node_id,
                        source_basis=sources[1].source_basis,
                        action="request_native_acquisition",
                        requirement_gap=sources[1].requirement_gap,
                    ),
                ),
                "input_closure_status": "partial",
            }
        )
        partial_ref = owner.persist_native_derivation_input_collection(case.store, partial)
        ordered = (complete_ref, partial_ref)
        plural_checkpoint = recovered.model_copy(update={"collection_refs": ordered})
        assert plural_checkpoint._matches_input_selection(
            **(current_inputs | {"collection_refs": ordered})
        )
        assert not plural_checkpoint._matches_input_selection(
            **(current_inputs | {"collection_refs": ordered[::-1]})
        )
        before_partial = case.store.manifest_inventory_snapshot(kind="foundry.input_bindings")
        assert before_partial.verdict == "pass"
        with pytest.raises(ValueError, match="native_derivation_inputs_incomplete"):
            owner.prepare_native_derivation_materialization_request(
                case.store,
                collection_ref=partial_ref,
                profile_ref=metadata["registered_profile_ref"],
                binding_id="native-n7-partial-refused",
            )
        after_partial = case.store.manifest_inventory_snapshot(kind="foundry.input_bindings")
        assert after_partial.verdict == "pass"
        assert after_partial.entries == before_partial.entries
        foreign_profile_ref = persist_registered_derived_input_profile(
            case.store, profile.model_copy(update={"family_id": "different.selected.operator"})
        )
        with pytest.raises(ValueError, match="registered_operator_binding_mismatch"):
            owner.prepare_native_derivation_materialization_request(
                case.store,
                collection_ref=complete_ref,
                profile_ref=foreign_profile_ref,
                binding_id="native-n7-foreign-operator-refused",
            )
    finally:
        case.close()
