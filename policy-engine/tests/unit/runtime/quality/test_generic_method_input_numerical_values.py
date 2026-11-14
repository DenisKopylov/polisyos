"""Real selected 1.4 intake and numerical facets, without running N5.

The source, certified derivation and Foundry binding owners produce the input.
These checks establish intake/value identity only, not a complete N5 witness.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import FoundryInputBindings, FoundrySelectedMethodInput
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.foundry.data_plane.bindings import reconcile_selected_method_input_bindings
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.acquisition_evaluation import (
    _selected_method_input_numerical_values,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationHorizonController,
    _require_program_graph_input_preflight,
)
from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import prepare_selected_method_input_case
from tests.unit.runtime.quality.test_joint_simulation_horizon import _request


def test_real_selected_method_values_distinguish_unchanged_prestate_and_ignore_ref_labels(tmp_path):
    """Changing the actual method value changes the key while ref-only changes do not."""
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        selected = materialize_selected_method_input_case(case, metadata)
        changed = materialize_selected_method_input_case(case, metadata, ratio_value=Decimal("0"))
        fresh = FileSystemCAS(case.store_root)
        first = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=selected.input_bindings_ref, effective_step=0
        )
        second = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=changed.input_bindings_ref, effective_step=0
        )
        assert first.bindings.bound_state_snapshot_ref == second.bindings.bound_state_snapshot_ref
        assert first.bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
        original_values = _selected_method_input_numerical_values(first)
        assert original_values != _selected_method_input_numerical_values(second)
        assert original_values[0][:3] == ("period_flow", "<f8", ())

        # A real selected binding artifact can change its non-numerical notes
        # and manifest identity while every actual parent/value is still read.
        original_manifest = fresh.get_manifest(selected.input_bindings_ref)
        relabelled_ref = fresh.put_json(
            first.bindings.model_copy(update={"notes": [*first.bindings.notes, "release:next"]}),
            PutOptions(
                kind=FoundryInputBindings.ARTIFACT_KIND,
                media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
                schema=original_manifest.artifact_schema,
                inputs=list(original_manifest.inputs),
                producer=original_manifest.producer,
            ),
            return_selected_profile=True,
        )
        assert relabelled_ref != selected.input_bindings_ref
        relabelled = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=relabelled_ref, effective_step=0
        )
        assert _selected_method_input_numerical_values(relabelled) == original_values

        # The actual canonical preflight now consumes the selected 1.4 ref;
        # it cannot proceed using the unchanged prestate reference alone.
        manifest = load_resolved_input_binding_manifest(
            fresh, selected.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            fresh, manifest.model_input_obligation_set_ref
        )
        preflight = ProgramGraphInputPreflight(
            obligation_refs=selected_set.obligation_refs,
            supplied_initial_slots=selected_set.supplied_initial_slots,
            parameter_override_bundle_ref=selected_set.invocation.parameter_override_bundle_ref,
            obligation_set_ref=manifest.model_input_obligation_set_ref,
            invocation=selected_set.invocation,
        )
        plan = EnginePlan(
            engine_kind="program_graph",
            objective_ref="objective://selected-method-intake",
            eligibility_conditions=("acyclic", "state_transition"),
            program_compilation_ref=case.compile_report_ref,
            program_semantic_input_bindings_ref=selected.input_bindings_ref,
            program_graph_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            program_store=fresh,
        )
        base = _request()
        request = base.model_copy(
            update={
                "horizon": HorizonSpec(start=0, end=0, step=1),
                "engine_plan": (plan,),
                "intervention_atoms": base.intervention_atoms[:1],
            }
        )
        decision = JointSimulationHorizonController()._select_engine(request).decision
        intake = _require_program_graph_input_preflight(
            request, plan, decision, lambda *_: preflight
        )
        assert intake is not None
        assert intake.request.input_bindings_ref == selected.input_bindings_ref
        assert intake.invocation == selected_set.invocation

        # A future binding or value field needs a deliberate role. Replacing
        # it on the already source-reconciled result must not be ignored.
        class FutureBindings(FoundryInputBindings):
            entity_axes: tuple[str, ...] = ("households",)

        class FutureInput(FoundrySelectedMethodInput):
            growth_option: bool = True

        with pytest.raises(ValueError, match="generic_method_bindings_field_role_census_mismatch"):
            _selected_method_input_numerical_values(
                replace(first, bindings=FutureBindings.model_validate(first.bindings.model_dump()))
            )
        with pytest.raises(ValueError, match="generic_method_input_field_role_census_mismatch"):
            _selected_method_input_numerical_values(
                replace(
                    first,
                    records=(FutureInput.model_validate(first.records[0].model_dump()),),
                )
            )

        record = first.records[0]
        digest = str(record.npy_value_ref.artifact_id).removeprefix("sha256:")
        blob = (
            case.store_root / "artifacts" / "sha256" / digest[:2] / digest[2:4] / f"{digest}.blob"
        )
        saved = blob.read_bytes()
        blob.unlink()
        try:
            with pytest.raises((OSError, ValueError)):
                reconcile_selected_method_input_bindings(
                    fresh, input_bindings_ref=relabelled_ref, effective_step=0
                )
        finally:
            blob.write_bytes(saved)
        restored = reconcile_selected_method_input_bindings(
            fresh, input_bindings_ref=relabelled_ref, effective_step=0
        )
        assert _selected_method_input_numerical_values(restored) == original_values
    finally:
        case.close()
