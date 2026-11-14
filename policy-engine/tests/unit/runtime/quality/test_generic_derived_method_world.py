"""Real derived method input reaches WMR and the generic N5 intake without N5.

Sources, registered arithmetic, selected bindings, candidate-world publishers,
compiler and N4 atom are real controlled producers. No simulation, retained
number, current source authority or publication claim is established here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.core.contracts.semantic_input_binding import load_resolved_input_binding_manifest
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContextOwnerError
from polisyos.runtime.quality.data_state_substrate import (
    build_derived_model_input_candidate_world,
)
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationHorizonController,
    JointSimulationRequest,
    _require_program_graph_input_preflight,
)
from polisyos.runtime.quality.model_input_requirements import ProgramGraphInputPreflight
from polisyos.runtime.quality.world_model_record import world_model_artifact_views
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests._helpers.derived_input_world import build_selected_method_base_world
from tests._helpers.registered_derived_method_input import materialize_registered_method_input_case
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.integration.core_runtime.test_candidate_experiment_generations_served import (
    _forbid_retained_generation_n5,
)
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
    _n4_atom,
    _with_hash,
)


def test_registered_derived_method_world_reaches_actual_generic_port_before_n5(
    tmp_path: Path,
) -> None:
    """Keep the exact selected method inputs through real world/plan/state owners."""
    from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock

    case, metadata = prepare_selected_method_input_case(
        tmp_path / "selected",
        method_class=PeriodFlowToStock,
        mapped=True,
        method_input_slot="ledger.flow",
        snapshot_id="selected-generic-derived-method-base",
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=(2**26, 2**27),
    )
    foreign_case = None
    try:
        with _forbid_retained_generation_n5() as n5_entries:
            base, registry, registry_ref = build_selected_method_base_world(
                case,
                tmp_path / "base-world",
                region_or_jurisdiction="UA",
                population_scope="population:government",
            )
            materialized = materialize_registered_method_input_case(case, metadata)
            built = build_derived_model_input_candidate_world(
                case.store,
                base_world_model=base.record,
                substrate_registry=registry,
                substrate_registry_artifact_ref=registry_ref,
                materialization=metadata["batch_materialization"],
                workspace_dir=tmp_path / "derived-world",
                transaction_time=datetime(2026, 11, 14, 12, tzinfo=UTC),
            )
            world = built.world_model.record
            views = world_model_artifact_views(world)
            for actual, expected in (
                (views.input_bindings_ref, built.world_model.input_bindings_ref),
                (views.bound_state_snapshot_ref, case.bound_state_snapshot_ref),
                (views.data_snapshot_ref, materialized.data_snapshot_ref),
            ):
                assert artifacts.artifact_ref_identity_key(
                    actual
                ) == artifacts.artifact_ref_identity_key(expected)
            trinity = load_trinity_bundle_artifact(
                artifacts.ensure_ir_artifact_store(case.store), case.trinity_ref
            )
            profile = _with_hash(
                GenericCycleSimulationProfileV1.model_construct(
                    profile_id="test-registered-derived-method-world",
                    profile_selection_ref="sha256:" + "a" * 64,
                    world_model_record_ref=built.world_model.record_ref,
                    substrate_registry_ref=registry_ref,
                    context_inputs=CandidateSimulationContextInputs(
                        substrate_registry=registry,
                        selected_registry_entry_hashes=tuple(
                            entry.entry_content_hash for entry in registry.entries
                        ),
                        world_model_record=world,
                    ),
                    n5=GenericCycleN5ProgramGraphRequestProfileV4(
                        budget_ref="budget://test/registered-derived-method-world",
                        horizon=HorizonSpec(start=0, end=0, step=1),
                        baseline_state={"government.balance": 10_000_000_000.0},
                        compile_report_ref=artifacts.ArtifactRef.model_validate(
                            case.compile_report_ref.model_dump(mode="python")
                        ),
                        invocation_quota_policy=BudgetInvocationQuotaPolicy(
                            allocation_id="test-registered-derived-method-world",
                            total_units=2,
                            protected_units=0,
                        ),
                    ),
                    limitations=(
                        "controlled_inputs_only",
                        "currentness_not_established",
                        "n5_simulation_not_world_evidence",
                        "n9_not_admitted",
                        "s8_blocked",
                        "source_truth_not_established",
                    ),
                )
            )
            atom = _n4_atom(trinity, world, trinity.policy_spec.interventions[0])
            owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=case.store)
            (plan,) = owner.build_engine_plans(
                profile=profile,
                world_record=world,
                outcome="government.balance",
                variable_map={"agents.income": "agents.income"},
                atoms=(atom,),
            )
            assert artifacts.artifact_ref_identity_key(
                plan.program_semantic_input_bindings_ref
            ) == artifacts.artifact_ref_identity_key(views.input_bindings_ref)
            request = JointSimulationRequest(
                world_model_record_ref=world.world_model_record_id,
                world_model_record=world,
                intervention_atoms=(atom,),
                selected_outcomes=("government.balance",),
                horizon=profile.n5.horizon,
                engine_plan=(plan,),
                baseline_state=profile.n5.baseline_state,
                budget_ref=profile.n5.budget_ref,
            )
            controller = JointSimulationHorizonController()
            port = JointSimulationPort(controller=controller, artifact_store=case.store)
            bound, consumptions, failures = port._request_with_bound_program_state(request)
            assert not failures
            assert consumptions[0].input_bindings_ref == str(views.input_bindings_ref.artifact_id)
            (bound_plan,) = bound.engine_plan
            manifest = load_resolved_input_binding_manifest(
                case.store, materialized.resolved_binding_manifest_ref
            )
            selected, _ = load_model_input_obligation_set(
                case.store, manifest.model_input_obligation_set_ref
            )
            preflight = ProgramGraphInputPreflight(
                obligation_refs=selected.obligation_refs,
                supplied_initial_slots=selected.supplied_initial_slots,
                parameter_override_bundle_ref=selected.invocation.parameter_override_bundle_ref,
                obligation_set_ref=artifacts.ArtifactRef.model_validate(
                    manifest.model_input_obligation_set_ref.model_dump(mode="python")
                ),
                invocation=selected.invocation,
            )
            selected_engine = controller._select_engine(bound)
            assert selected_engine.plan is bound_plan
            assert selected_engine.decision.decision == "selected", selected_engine.decision
            intake = _require_program_graph_input_preflight(
                bound, bound_plan, selected_engine.decision, lambda *_: preflight
            )
            assert intake is not None
            assert artifacts.artifact_ref_identity_key(
                intake.request.input_bindings_ref
            ) == artifacts.artifact_ref_identity_key(views.input_bindings_ref)

            # These controls reach the same owner used by the successful read.
            # They perturb selected refs or the original compiled model, never
            # replace the real producer with a constructor-only world fixture.
            subject = {
                "world": world,
                "model": built.model_spec,
                "source_model": trinity.model_spec,
                "program_ref": plan.program_graph_ref,
                "exec_plan_ref": plan.exec_plan_ref,
                "registry_ref": case.registry_bundle_ref,
            }
            foreign_case, _ = prepare_selected_method_input_case(
                tmp_path / "foreign",
                method_class=PeriodFlowToStock,
                mapped=True,
                method_input_slot="ledger.flow",
                method_instances=2,
            )
            with pytest.raises(CycleSubstrateContextOwnerError) as foreign_graph:
                owner._require_selected_derived_program_graph_model(
                    **{**subject, "program_ref": foreign_case.program_graph_ref}
                )
            assert (
                foreign_graph.value.code
                == "generic_cycle_program_graph_derived_model_subject_mismatch"
            )
            graft = world.model_copy(
                update={
                    "artifact_views": views.model_copy(
                        update={"data_snapshot_ref": case.data_snapshot_ref}
                    )
                }
            )
            with pytest.raises(CycleSubstrateContextOwnerError) as foreign_snapshot:
                owner._require_selected_derived_program_graph_model(**{**subject, "world": graft})
            assert (
                foreign_snapshot.value.code
                == "generic_cycle_program_graph_derived_model_subject_mismatch"
            )
            for changed in (
                {"calibrated": True},
                {"calibration_ref": str(case.compile_report_ref.artifact_id)},
            ):
                with pytest.raises(CycleSubstrateContextOwnerError) as calibration:
                    owner._require_selected_derived_program_graph_model(
                        **{**subject, "source_model": trinity.model_spec.model_copy(update=changed)}
                    )
                assert (
                    calibration.value.code == "derived_model_input_calibration_recompile_required"
                )
            owner._require_selected_derived_program_graph_model(**subject)
            assert n5_entries == []
    finally:
        if foreign_case is not None:
            foreign_case.close()
        case.close()
