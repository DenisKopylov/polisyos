"""An unbound mapped method remains a real pre-numerical input gap.

The world, graph, atom, obligation set and routing report use their real owners.
This component does not construct a Runtime job, Generic N5 input, protected
selection, invocation reservation or numerical result.
"""

from __future__ import annotations

import pytest

from polisyos.core import artifacts
from polisyos.core.contracts import load_model_input_obligation_set
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    ProgramGraphInputsRequiredError,
    _require_program_graph_input_preflight,
)
from polisyos.runtime.quality.model_input_requirements import SelectedProgramGraphInputBasis
from polisyos.runtime.quality.model_input_routing import (
    plan_selected_model_input_routing,
    read_model_input_routing_report,
)
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests._helpers.acquisition_production import _resolver
from tests._helpers.derived_input_world import build_selected_method_base_world
from tests._helpers.registered_derived_method_input import prepare_registered_method_input_preflight
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.integration.core_runtime.test_candidate_experiment_generations_served import (
    _forbid_retained_generation_n5,
)
from tests.integration.runtime_quality.test_program_graph_model_input_served import _fiscal_problem
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
    _n4_atom,
    _with_hash,
)


def test_structural_base_without_method_values_routes_gap_but_unknown_abi_refuses(
    tmp_path, monkeypatch
):
    """Structural admission does not invent an argument or hide an ABI refusal."""
    case, _ = prepare_selected_method_input_case(
        tmp_path / "selected",
        method_class=PeriodFlowToStock,
        mapped=True,
        method_input_slot="ledger.flow",
        snapshot_id="generic-unresolved-method-base",
        policy_spec=selected_method_tax_subsidy_policy(),
        income_values=(2**26, 2**27),
    )
    try:
        with _forbid_retained_generation_n5() as n5_entries:
            world, registry, registry_ref = build_selected_method_base_world(
                case, tmp_path / "world"
            )
            problem = _fiscal_problem()
            profile = _with_hash(
                GenericCycleSimulationProfileV1.model_construct(
                    profile_id="generic-unresolved-method",
                    profile_selection_ref=cycle_job_profile_selection_ref(problem),
                    world_model_record_ref=world.record_ref,
                    substrate_registry_ref=registry_ref,
                    context_inputs=CandidateSimulationContextInputs(
                        substrate_registry=registry,
                        selected_registry_entry_hashes=tuple(
                            entry.entry_content_hash for entry in registry.entries
                        ),
                        world_model_record=world.record,
                    ),
                    n5=GenericCycleN5ProgramGraphRequestProfileV4(
                        budget_ref="budget://test/generic-unresolved-method",
                        horizon=HorizonSpec(start=0, end=0, step=1),
                        baseline_state={"government.balance": 10_000_000_000.0},
                        compile_report_ref=artifacts.ArtifactRef.model_validate(
                            case.compile_report_ref.model_dump(mode="python")
                        ),
                        invocation_quota_policy=BudgetInvocationQuotaPolicy(
                            allocation_id="generic-unresolved-method",
                            total_units=5,
                            protected_units=1,
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
            trinity = load_trinity_bundle_artifact(
                artifacts.ensure_ir_artifact_store(case.store), case.trinity_ref
            )
            atom = _n4_atom(trinity, world.record, trinity.policy_spec.interventions[0])
            owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=case.store)
            (plan,) = owner.build_engine_plans(
                profile=profile,
                world_record=world.record,
                outcome="government.balance",
                variable_map={"agents.income": "agents.income"},
                atoms=(atom,),
            )
            assert plan.program_semantic_input_bindings_ref is None
            assert "program_semantic_input_bindings_ref" not in plan.model_dump(mode="json")
            request = JointSimulationRequest(
                world_model_record_ref=world.record.world_model_record_id,
                world_model_record=world.record,
                intervention_atoms=(atom,),
                selected_outcomes=("government.balance",),
                horizon=profile.n5.horizon,
                engine_plan=(plan,),
                baseline_state=profile.n5.baseline_state,
                budget_ref=profile.n5.budget_ref,
            )
            controller = JointSimulationHorizonController()
            port = JointSimulationPort(controller=controller, artifact_store=case.store)
            bound, _, failures = port._request_with_bound_program_state(request)
            assert not failures
            selected = controller._select_engine(bound)
            assert selected.decision.decision == "selected"

            def canonical_preflight(*_args):
                return prepare_registered_method_input_preflight(case)

            with pytest.raises(ProgramGraphInputsRequiredError) as gap:
                _require_program_graph_input_preflight(
                    bound, selected.plan, selected.decision, canonical_preflight
                )
            selected_set, members = load_model_input_obligation_set(
                case.store, gap.value.obligation_set_ref
            )
            assert len(members) == 1
            assert members[0].port.slot_id == "ledger.flow"
            assert members[0].port.carrier == "method_input"
            invocation = selected_set.invocation
            basis = SelectedProgramGraphInputBasis(
                context=invocation.context,
                program_graph_ref=invocation.program_graph_ref,
                exec_plan_ref=invocation.exec_plan_ref,
                registry_bundle_ref=invocation.registry_bundle_ref,
                input_bindings_ref=invocation.input_bindings_ref,
                steps=invocation.steps,
            )
            authority, _ = _resolver(tmp_path / "catalog")
            routed = plan_selected_model_input_routing(
                case.store,
                obligation_set_ref=gap.value.obligation_set_ref,
                selected_basis=basis,
                catalog_authority=authority,
                report_version="2.0",
            )
            assert routed.report == read_model_input_routing_report(case.store, routed.report_ref)
            assert len(routed.report.routes) == 1
            assert routed.report.routes[0].obligation_ref == selected_set.obligation_refs[0]
            assert routed.report.fetch_status == "not_attempted"
            assert "publication" in routed.report.may_not_use_for

            def unavailable_method(*_args, **_kwargs):
                raise KeyError("test removed the actual registered method")

            with monkeypatch.context() as changed:
                changed.setattr(MethodRegistry.get_instance(), "get", unavailable_method)
                with pytest.raises(JointSimulationControllerError) as refused:
                    _require_program_graph_input_preflight(
                        bound, selected.plan, selected.decision, canonical_preflight
                    )
            assert refused.value.code == "program_graph_input_preflight_not_established"
            assert isinstance(refused.value.__cause__, ValueError)
            assert str(refused.value.__cause__) == "model_input_method_registry_unresolved"
            assert n5_entries == []
    finally:
        case.close()
