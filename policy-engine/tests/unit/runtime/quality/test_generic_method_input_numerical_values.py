"""Real selected 1.4 intake and numerical facets, without running N5.

The source, certified derivation and Foundry binding owners produce the input.
These checks establish intake/value identity only, not a complete N5 witness.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import FoundryInputBindings, FoundrySelectedMethodInput
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.core.registry import load_registry_bundle_content
from polisyos.foundry.data_plane.bindings import (
    reconcile_selected_method_input_bindings,
    replay_selected_method_input_facts,
)
from polisyos.foundry.execute import load_state_snapshot
from polisyos.foundry.execute._internal.graph import prepare_program_graph_method_calls
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.acquisition_evaluation import (
    _generic_method_call_content,
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


def test_real_selected_method_facts_and_preflight_preserve_numeric_and_ref_roles(tmp_path):
    """Prove facts/preflight only; unavailable provider content is a separate control.

    Development r1/r2 failed later at preflight/provider respectively. Their
    outputs remain deciding failure evidence, not full witness acceptance.
    """
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
        obligation_set_ref = ArtifactRef.model_validate(
            manifest.model_input_obligation_set_ref.model_dump(mode="python")
        )
        assert artifact_ref_identity_key(obligation_set_ref) == artifact_ref_identity_key(
            manifest.model_input_obligation_set_ref
        )
        preflight = ProgramGraphInputPreflight(
            obligation_refs=selected_set.obligation_refs,
            supplied_initial_slots=selected_set.supplied_initial_slots,
            parameter_override_bundle_ref=selected_set.invocation.parameter_override_bundle_ref,
            obligation_set_ref=obligation_set_ref,
            invocation=selected_set.invocation,
        )
        facts = replay_selected_method_input_facts(
            fresh,
            input_bindings_ref=selected.input_bindings_ref,
            expected_invocation=selected_set.invocation,
        )
        assert _selected_method_input_numerical_values(facts) == original_values
        assert "semantic_input_limitation:method_nominal_abi_not_checked" in facts.notes
        assert (
            "semantic_input_limitation:method_provider_completeness_not_established" in facts.notes
        )
        base_state = load_state_snapshot(fresh, snapshot_ref=case.bound_state_snapshot_ref)
        registry = load_registry_bundle_content(fresh, case.registry_bundle_ref)
        plan = EnginePlan(
            engine_kind="program_graph",
            objective_ref="objective://selected-method-intake",
            eligibility_conditions=("acyclic", "state_transition"),
            program_compilation_ref=case.compile_report_ref,
            program_semantic_input_bindings_ref=selected.input_bindings_ref,
            program_graph_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            program_store=fresh,
            program_base_state=base_state,
            program_base_ref=case.bound_state_snapshot_ref,
            mechanism_registry=registry.mechanism_registry,
            slot_registry=registry.slot_registry,
            merge_registry=registry.merge_registry,
            selector_field_registry=registry.selector_field_registry,
            constraint_registry=registry.constraint_registry,
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


def test_ordinary_method_provider_without_retained_provenance_is_not_established(tmp_path):
    """A real prepared native call is insufficient for a current content witness."""
    from polisyos.runtime.quality.confidence_ledger import _retained_n5_host_capture

    assert _retained_n5_host_capture() is None
    case, metadata = prepare_selected_method_input_case(tmp_path, method_class=PeriodFlowToStock)
    try:
        selected = materialize_selected_method_input_case(case, metadata)
        fresh = FileSystemCAS(case.store_root)
        manifest = load_resolved_input_binding_manifest(
            fresh, selected.resolved_binding_manifest_ref
        )
        selected_set, _ = load_model_input_obligation_set(
            fresh, manifest.model_input_obligation_set_ref
        )
        base_state = load_state_snapshot(fresh, snapshot_ref=case.bound_state_snapshot_ref)
        calls = prepare_program_graph_method_calls(
            fresh,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=selected.input_bindings_ref,
            base_state=base_state,
            steps=(0,),
            expected_invocation=selected_set.invocation,
            seed=0,
        )
        assert len(calls) == 1
        assert calls[0].input_slot_sources == {"period_flow": "period_flow"}
        assert float(calls[0].input_values["period_flow"]) == -6_000_000_000.0
        with pytest.raises(
            ValueError, match=r"^generic_method_call_provider_not_established:default_rng$"
        ):
            _generic_method_call_content(calls[0])
    finally:
        case.close()
