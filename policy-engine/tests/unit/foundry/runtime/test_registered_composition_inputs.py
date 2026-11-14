"""Registered unscored native inputs reach a real step and a cold reader."""

from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.artifacts import load_core_json_artifact, validate_core_model_json_artifact
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts import DataSnapshot, DerivedModelInputDataSnapshotLineage
from polisyos.core.contracts.foundry import ExecuteRequest
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_composition_binding import (
    RegisteredDerivedModelInputRequest,
    load_native_derivation_source_projection,
    load_registered_derived_input_correspondence,
)
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.contracts.variable_binding import SelectedVariableBindingRef
from polisyos.core.derivations import (
    load_composition_recipe_artifact,
    resolve_certified_composition,
)
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.model_input_routing import materialize_registered_derived_model_inputs
from tests._helpers.registered_derived_method_input import (
    materialize_registered_method_input_case,
    prepare_registered_method_input_preflight,
    prepare_registered_method_input_request,
)
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import _removed_blob
from tests.unit.foundry.runtime.test_selected_method_inputs import (
    _fresh_process_read,
    _independent_value_sha256,
)


def test_registered_candidate_sources_reach_actual_method_and_cold_reader(tmp_path):
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        materialized = materialize_registered_method_input_case(case, metadata)
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        assert bindings.schema_version == "1.4"
        assert bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        snapshot = validate_core_model_json_artifact(
            DataSnapshot, case.store, materialized.data_snapshot_ref
        )
        assert (
            case.store.get_manifest(materialized.data_snapshot_ref).artifact_schema.version
            == "0.3.0"
        )
        assert isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage)
        assert snapshot.source_lineage.base_data_snapshot_ref == case.data_snapshot_ref
        (record,) = bindings.selected_method_inputs
        assert record.canonical_value == Decimal("-6000000000")
        assert record.value_sha256 == _independent_value_sha256(-6_000_000_000.0)
        correspondence = load_registered_derived_input_correspondence(
            case.store, materialized.correspondence_ref
        )
        assert tuple(role.role for role in correspondence.roles) == ("rate_input", "scale_input")
        for role in correspondence.roles:
            source = load_core_json_artifact(case.store, role.source_series_ref)
            assert source["evidence_status"] == "not_established"
            assert source["observation_class"] == "candidate"
            assert "effective_score" not in source and "authority" not in source
            projection = load_native_derivation_source_projection(
                case.store, role.source_projection_ref
            )
            assert projection.source_value_correspondence == "recomputed"
            assert projection.source_basis_correspondence == "recomputed"
            assert projection.empirical_authority == "not_established"
            assert projection.source_variable_id.startswith("provider.")
        recipe = load_composition_recipe_artifact(case.store, metadata["recipe_ref"])
        resolved = resolve_certified_composition(
            case.store,
            certificate_ref=metadata["certificate_ref"],
            consumer_method_id="tests.registered-input-numeric-control",
        )
        assert recipe == resolved.certificate.recipe
        assert resolved.series.points[0].value == Decimal("-6000000000")
        assert resolved.series.effective_score is None
        assert all(
            item.effective_score is None for item in resolved.certificate.input_contributions
        )

        executed = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=materialized.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        assert executed.ok and executed.simulation_result_ref is not None
        independent_read = _fresh_process_read(case, executed.simulation_result_ref)
        assert independent_read["stock"] == 4_000_000_000.0
        assert independent_read["value_sha256"] == _independent_value_sha256(-6_000_000_000.0)
        fresh = FileSystemCAS(case.store_root)
        admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert (
            "external_empirical_context_not_established" in admitted.semantic_input_limitation_codes
        )
        assert "empirical_authority_not_established" in admitted.semantic_input_limitation_codes

        # Core's embedded recipe remains mathematically replayable. The actual
        # semantic consumer additionally requires the separately selected recipe.
        with _removed_blob(fresh, metadata["recipe_ref"]):
            assert (
                resolve_certified_composition(
                    fresh,
                    certificate_ref=metadata["certificate_ref"],
                    consumer_method_id="tests.embedded-recipe-is-not-selection",
                ).series
                == resolved.series
            )
            with pytest.raises(
                ValueError, match=r"^foundry_input_bindings_composition_recipe_unavailable$"
            ):
                admit_execution_source(fresh, executed.simulation_result_ref)
        for ref in (
            metadata["role_occurrences"][0].occurrence_ref,
            correspondence.roles[1].source_series_ref,
            correspondence.roles[0].source_projection_ref,
        ):
            with _removed_blob(fresh, ref), pytest.raises(ValueError):
                admit_execution_source(fresh, executed.simulation_result_ref)

        request = RegisteredDerivedModelInputRequest(
            model_input_obligation_ref=SelectedVariableBindingRef.model_validate(
                metadata["obligation_ref"].model_dump(mode="python")
            ),
            profile_ref=metadata["registered_profile_ref"],
            role_occurrences=metadata["role_occurrences"],
            binding_id="registered-period-flow",
        )
        with pytest.raises(
            ValueError, match=r"^registered_derived_model_input_complete_target_set_required$"
        ):
            materialize_registered_derived_model_inputs(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=metadata["preflight"].obligation_set_ref,
                inputs=(),
            )
        swapped = tuple(
            role.model_copy(
                update={"occurrence_ref": metadata["role_occurrences"][1 - index].occurrence_ref}
            )
            for index, role in enumerate(metadata["role_occurrences"])
        )
        with pytest.raises(ValueError, match="native_source_basis_mismatch"):
            materialize_registered_derived_model_inputs(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=metadata["preflight"].obligation_set_ref,
                inputs=(request.model_copy(update={"role_occurrences": swapped}),),
            )
        assert admit_execution_source(fresh, executed.simulation_result_ref).basis == admitted.basis
    finally:
        case.close()


def test_two_distinct_registered_inputs_materialize_one_complete_manifest(tmp_path):
    input_slots = ("ledger.a", "ledger.b")
    case, metadata = prepare_selected_method_input_case(
        tmp_path,
        method_class=PeriodFlowToStock,
        method_input_slots=input_slots,
        method_instances=2,
        mapped=True,
    )
    try:
        per_port = metadata["method_inputs_by_slot"]
        assert set(per_port) == set(input_slots)
        assert len({str(per_port[slot]["target_ref"].artifact_id) for slot in input_slots}) == 2
        preflight = prepare_registered_method_input_preflight(case)
        selected_set, obligations = load_model_input_obligation_set(
            case.store, preflight.obligation_set_ref
        )
        obligation_refs = {
            member.port.slot_id: ref
            for ref, member in zip(selected_set.obligation_refs, obligations, strict=True)
        }
        assert set(obligation_refs) == set(input_slots)
        ratios = {"ledger.a": Decimal("-0.03"), "ledger.b": Decimal("0.01")}
        expected_values = {"ledger.a": Decimal("-6000000000"), "ledger.b": Decimal("2000000000")}
        requests = tuple(
            prepare_registered_method_input_request(
                case,
                per_port[slot],
                preflight=preflight,
                model_input_obligation_ref=obligation_refs[slot],
                ratio_value=ratios[slot],
                binding_id=f"registered-{slot}",
            )
            for slot in input_slots
        )
        # One completed derivation does not complete the invocation's full AND set.
        with pytest.raises(
            ValueError, match=r"^registered_derived_model_input_complete_target_set_required$"
        ):
            materialize_registered_derived_model_inputs(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=preflight.obligation_set_ref,
                inputs=requests[:1],
            )
        with pytest.raises(
            ValueError, match=r"^registered_derived_model_input_binding_id_duplicate$"
        ):
            materialize_registered_derived_model_inputs(
                case.store,
                base_data_snapshot_ref=case.data_snapshot_ref,
                obligation_set_ref=preflight.obligation_set_ref,
                inputs=(
                    requests[0],
                    requests[1].model_copy(update={"binding_id": requests[0].binding_id}),
                ),
            )
        batch = materialize_registered_derived_model_inputs(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=preflight.obligation_set_ref,
            inputs=tuple(reversed(requests)),
        )
        manifest = load_resolved_input_binding_manifest(
            case.store, batch.resolved_binding_manifest_ref
        )
        assert len(manifest.derivations) == len(batch.correspondence_refs) == 2
        snapshot = validate_core_model_json_artifact(
            DataSnapshot, case.store, batch.data_snapshot_ref
        )
        assert isinstance(snapshot.source_lineage, DerivedModelInputDataSnapshotLineage)
        assert snapshot.source_lineage.selections == manifest.derivations
        bindings = load_input_bindings(case.store, batch.input_bindings_ref)
        assert bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        by_slot = {record.slot_id: record for record in bindings.selected_method_inputs}
        assert set(by_slot) == set(input_slots)
        expected_hashes = {
            "ledger.a": _independent_value_sha256(-6_000_000_000.0),
            "ledger.b": _independent_value_sha256(2_000_000_000.0),
        }
        assert len(set(expected_hashes.values())) == 2
        for slot, record in by_slot.items():
            assert record.canonical_value == expected_values[slot]
            assert record.dtype == "float64" and record.shape == ()
            assert record.value_sha256 == expected_hashes[slot]
        executed = execute_foundry(
            case.store,
            ExecuteRequest(
                exec_plan_ref=case.exec_plan_ref,
                registry_bundle_ref=case.registry_bundle_ref,
                input_bindings_ref=batch.input_bindings_ref,
                return_selected_profile=True,
            ),
        )
        assert executed.ok and executed.simulation_result_ref is not None
        fresh = _fresh_process_read(case, executed.simulation_result_ref)
        assert fresh["stock"] == 6_000_000_000.0
        assert fresh["occurrences"] == 2
        assert fresh["value_sha256_by_slot"] == expected_hashes
        fresh_store = FileSystemCAS(case.store_root)
        with (
            _removed_blob(fresh_store, manifest.derivations[1].recipe_ref),
            pytest.raises(
                ValueError, match=r"^foundry_input_bindings_composition_recipe_unavailable$"
            ),
        ):
            admit_execution_source(fresh_store, executed.simulation_result_ref)
        assert admit_execution_source(fresh_store, executed.simulation_result_ref).basis is not None
    finally:
        case.close()
