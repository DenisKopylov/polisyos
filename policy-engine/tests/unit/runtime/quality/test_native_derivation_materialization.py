"""Selected N7 leaf collections feed the actual registered semantic producer."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import load_resolved_input_binding_manifest
from polisyos.core.contracts.semantic_composition_binding import (
    persist_registered_derived_input_profile,
)
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality import acquisition_planner as planner
from polisyos.runtime.quality import acquisition_world_growth as owner
from polisyos.runtime.quality.model_input_routing import materialize_registered_derived_model_inputs
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.runtime.quality.test_n7_derivation_bundle import (
    _marker,
    _pending_source,
    _profile,
    _target_gap,
)


def test_native_n7_roles_reach_registered_batch_and_incomplete_inputs_stay_pending(
    tmp_path: Path,
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
