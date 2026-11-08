"""Selected ProgramGraph input preflight under a signed simulate-only lease."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    WarningRecord,
    ensure_ir_artifact_store,
)
from polisyos.core.contracts.foundry import ExecPlanRef, FoundryInputBindingsRef, ProgramGraphRef
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ProgramGraphInputInvocation,
    load_model_input_obligation_set,
)
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute.model_input_requirements import verify_program_graph_input_preflight
from polisyos.ir.trinity import load_trinity_bundle_artifact
from polisyos.runtime.quality.candidate_simulation import CandidateSimulationContextInputs
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContextArtifactOwner,
    CycleSubstrateContextOwnerError,
    VerifiedNLJobBudgetScope,
    VerifiedNLJobScope,
    cycle_job_profile_selection_ref,
)
from polisyos.runtime.quality.design_problem import DESIGN_PROBLEM_V3_SCHEMA_VERSION, DesignProblem
from polisyos.runtime.quality.generation_cycle import (
    JointSimulationPort,
    _bind_scoped_n5_invocation_policy,
    _resolve_n4_program_graph_link_context,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5ProgramGraphRequestProfileV4,
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationProfileV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    EngineDecision,
    EnginePlan,
    HorizonSpec,
    JointSimulationHorizonController,
    JointSimulationRequest,
    ProgramGraphInputsRequiredError,
)
from polisyos.runtime.quality.model_input_requirements import (
    ProgramGraphInputPreflight,
    derive_program_graph_input_interface,
    preflight_program_graph_inputs,
)
from polisyos.runtime.quality.substrate_registry import persist_substrate_registry
from polisyos.runtime.quality.world_model_record import (
    build_world_model_record,
    world_model_artifact_views,
)
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from polisyos.scientist.policy_design.schema import load_policy_candidate_schema
from tests._helpers import world_model_record as world_fixture
from tests._helpers.controlled_candidate_profile import _problem
from tests._helpers.program_graph_tax_subsidy_input import (
    ProgramGraphTaxSubsidyInputCase,
    prepare_program_graph_tax_subsidy_input_case,
)
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
    _n4_atom,
    _with_hash,
)
from tests.unit.runtime.quality.test_model_input_requirements import _stock_declaration
from tests.unit.runtime.quality.test_n5_physical_budget_scope import _issued_owner, _with_scope

if TYPE_CHECKING:
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationContextHandoffV1,
    )

_OUTCOME = "government.balance"
_INCOME = "agents.income"


def _fiscal_problem() -> DesignProblem:
    payload = _problem("program_graph_model_input").model_dump(mode="json")
    payload["schema_version"] = DESIGN_PROBLEM_V3_SCHEMA_VERSION
    payload["domain"] = "fiscal_credit"
    payload["problem_statement"] = "Assess the modeled government balance for a bounded subsidy."
    payload["nl_provenance"]["raw_request"] = "Evaluate a bounded candidate simulation."
    payload["outcome_of_interest"]["target_variable"] = _OUTCOME
    payload["outcome_of_interest"]["metric_id"] = "opening_balance"
    payload["outcome_of_interest"]["measurement_unit"] = "usd"
    payload["objectives"][0]["metric_id"] = "opening_balance"
    payload["objectives"][0]["description"] = "Assess modeled government balance in USD."
    payload["candidate_lever_space"] = {
        "allowed_operator_kinds": ["tax_subsidy"],
        "candidate_levers": [
            {
                "lever_id": "subsidy",
                "operator_kind": "tax_subsidy",
                "instrument": "Income subsidy",
                "target_slot": _INCOME,
            }
        ],
    }
    payload["jurisdiction_time"]["region"] = "UA-30"
    return DesignProblem.model_validate(payload)


def _selected_profile(
    case: ProgramGraphTaxSubsidyInputCase,
    trinity: TrinityBundle,
    problem: DesignProblem,
    world_root: Path,
) -> GenericCycleSimulationProfileV1:
    store = case.store
    world_root.mkdir()
    world_fixture._write_fabric_world_snapshot(world_root)
    substrate = world_fixture._substrate_registry()
    substrate_ref = persist_substrate_registry(store, substrate)
    world = build_world_model_record(
        store,
        fabric_world_ref=world_fixture._fabric_ref(world_root),
        data_forge_snapshot_binding_path=world_fixture._write_data_forge_binding(world_root),
        data_snapshot_ref=case.data_snapshot_ref,
        model_spec=trinity.model_spec,
        skg_causal_prior_ref=world_fixture._skg_ref(world_root),
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        registry_bundle_artifact_ref=case.registry_bundle_ref,
        foundry_binding_rules=load_input_bindings(store, case.input_bindings_ref).rules,
        region_or_jurisdiction="UA-30",
        population_scope="wartime_msme",
        policy_domain=problem.domain,
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=world_fixture.BranchMode.OBSERVED,
        policy_slot_ids=(_INCOME, _OUTCOME),
        producer_ref="test.program_graph_model_input_signed",
        program_graph_refs=(str(case.program_graph_ref.artifact_id),),
        program_graph_view_refs=(case.program_graph_ref,),
        return_selected_profile=True,
    )
    return _with_hash(
        GenericCycleSimulationProfileV1.model_construct(
            profile_id="test-selected-model-input",
            profile_selection_ref=cycle_job_profile_selection_ref(problem),
            world_model_record_ref=world.record_ref,
            substrate_registry_ref=substrate_ref,
            context_inputs=CandidateSimulationContextInputs(
                substrate_registry=substrate,
                selected_registry_entry_hashes=tuple(
                    entry.entry_content_hash for entry in substrate.entries
                ),
                world_model_record=world.record,
            ),
            n5=GenericCycleN5ProgramGraphRequestProfileV4(
                budget_ref="budget://test/selected-model-input",
                horizon=HorizonSpec(start=0, end=2, step=1),
                baseline_state={_OUTCOME: 0.0},
                compile_report_ref=case.compile_report_ref,
                invocation_quota_policy=BudgetInvocationQuotaPolicy(
                    allocation_id="test-selected-model-input", total_units=3, protected_units=1
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


def _reopen_signed_scopes(
    service: ControlPlaneService,
) -> tuple[VerifiedNLJobScope, VerifiedNLJobBudgetScope]:
    admission = service._control_store.current_execution_job_admission()
    job, execution_scope = admission.job, admission.scope
    payload = service._payload_for_execution_scope(
        service._load_control_nl_job_payload(job), job=job, execution_scope=execution_scope
    )
    manifest_ref, manifest = service._resolve_capability_manifest_for_execution(
        job=job, admission=admission, execution_scope=execution_scope
    )
    binding = service._require_nl_job_execution_intent_binding(
        job=job,
        admission=admission,
        execution_scope=execution_scope,
        payload=payload,
        capability_manifest_ref=manifest_ref,
        capability_manifest=manifest,
    )
    scope = binding["_verified_nl_job_scope"]
    budget_scope = binding["_verified_nl_job_budget_scope"]
    assert type(scope) is VerifiedNLJobScope
    assert type(budget_scope) is VerifiedNLJobBudgetScope
    return scope, budget_scope


def _assert_selected_n4_linkage(
    *,
    owner: GenericCycleSimulationAdmissionOwner,
    context_owner: CycleSubstrateContextArtifactOwner,
    scope: VerifiedNLJobScope,
    handoff: GenericCycleSimulationContextHandoffV1,
    problem: DesignProblem,
    case: ProgramGraphTaxSubsidyInputCase,
) -> None:
    linked = _resolve_n4_program_graph_link_context(
        problem=problem,
        handoff=handoff,
        owner=owner,
        scope=scope,
        context_owner=context_owner,
        repo_root=None,
    )
    assert linked is not None
    linkage = linked.linkage
    assert linkage.profile_ref == handoff.profile_ref
    assert linkage.profile_content_hash == handoff.profile.content_hash
    assert linkage.profile_selection_ref == handoff.profile.profile_selection_ref
    assert linkage.compile_report_ref == case.compile_report_ref
    assert linkage.registry_bundle_ref == case.registry_bundle_ref
    assert linked.registry_content.bundle_ref == linkage.registry_bundle_ref
    mechanism = linked.registry_content.mechanism_registry.mechanisms["tax_subsidy"]
    assert tuple(mechanism.reads_slots) == (_INCOME,)
    assert tuple(mechanism.writes_slots) == (_INCOME, _OUTCOME)

    replay = {
        "profile_ref": linkage.profile_ref,
        "expected_profile_content_hash": linkage.profile_content_hash,
        "expected_profile_selection_ref": linkage.profile_selection_ref,
        "expected_compile_report_ref": linkage.compile_report_ref,
        "expected_registry_bundle_ref": linkage.registry_bundle_ref,
        "context_job_ref": handoff.context_job_ref,
        "expected_context": handoff.context,
        "problem": problem,
        "job_id": scope.job_id,
        "run_id": scope.run_id,
        "tenant_id": scope.tenant_id,
        "cell_id": scope.cell_id,
    }
    historical = owner.resolve_selected_program_graph_linkage_historical(**replay)
    assert historical.registry_bundle_content == linked.registry_content
    assert historical.compile_report_ref == linkage.compile_report_ref

    store = case.store
    manifest = store.get_manifest(linkage.registry_bundle_ref)
    sibling_ref = store.put_bytes(
        store.get_bytes(linkage.registry_bundle_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=manifest.inputs,
            warnings=[WarningRecord(code="fixture.sibling_registry_view", msg="Distinct view.")],
        ),
        return_selected_profile=True,
    )
    assert sibling_ref.artifact_id == linkage.registry_bundle_ref.artifact_id
    assert (
        sibling_ref.manifest_profile_sha256 != linkage.registry_bundle_ref.manifest_profile_sha256
    )
    with pytest.raises(
        CycleSubstrateContextOwnerError,
        match="generic_cycle_program_graph_historical_registry_binding_mismatch",
    ):
        owner.resolve_selected_program_graph_linkage_historical(
            **{**replay, "expected_registry_bundle_ref": sibling_ref}
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_signed_program_graph_preflight_preserves_complete_selected_obligations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the scoped N5 boundary with a controlled, linked policy candidate."""
    service, middleware, observer, job = await _issued_owner(
        tmp_path, mode="metered_paid_producers_and_bounded_candidate"
    )
    try:
        store = service._artifact_store
        assert type(store) is FileSystemCAS
        with service._control_store.job_execution_fence(
            job_id=job.job_id, worker_id=job.lease_owner, attempt=job.attempt
        ):
            admission = service._control_store.current_execution_job_admission()
            with service._install_execution_scope(admission.scope):
                scope, budget_scope = _reopen_signed_scopes(service)
                case = prepare_program_graph_tax_subsidy_input_case(
                    tmp_path / "graph",
                    opening_balance_usd=None,
                    mechanism_start_step=2,
                    model_input_port_declaration_builder=_stock_declaration,
                    store=store,
                    snapshot_id=world_fixture.SNAPSHOT_ID,
                )
                trinity = load_trinity_bundle_artifact(
                    ensure_ir_artifact_store(store), case.trinity_ref
                )
                problem = _fiscal_problem()
                profile = _selected_profile(case, trinity, problem, tmp_path / "world")
                owner = GenericCycleSimulationAdmissionOwner(profiles=(profile,), store=store)
                context_owner = CycleSubstrateContextArtifactOwner(
                    store=store, control_store=service._control_store
                )
                identity = {
                    "problem": problem,
                    "job_id": scope.job_id,
                    "run_id": scope.run_id,
                    "tenant_id": scope.tenant_id,
                    "cell_id": scope.cell_id,
                    "verified_nl_job_scope": scope,
                }
                offer = owner.admit_context(
                    generic_simulation_profile_id=profile.profile_id, **identity
                )
                handoff = owner.persist_handoff(
                    offer=offer, context_owner=context_owner, **identity
                )
                assert (
                    owner.resolve_handoff(
                        handoff=handoff,
                        problem=problem,
                        verified_nl_job_scope=scope,
                        context_owner=context_owner,
                    )
                    == handoff
                )
                _assert_selected_n4_linkage(
                    owner=owner,
                    context_owner=context_owner,
                    scope=scope,
                    handoff=handoff,
                    problem=problem,
                    case=case,
                )
                world = handoff.context.world_model_record
                n5 = handoff.profile.n5
                assert type(n5) is GenericCycleN5ProgramGraphRequestProfileV4
                (intervention,) = trinity.policy_spec.interventions
                atom = _n4_atom(trinity, world, intervention)
                plans = owner.build_engine_plans(
                    profile=handoff.profile,
                    world_record=world,
                    outcome=_OUTCOME,
                    variable_map={_INCOME: _INCOME},
                    atoms=(atom,),
                )
                request = JointSimulationRequest(
                    world_model_record_ref=world.world_model_record_id,
                    world_model_record=world,
                    intervention_atoms=(atom,),
                    selected_outcomes=(_OUTCOME,),
                    horizon=n5.horizon,
                    engine_plan=plans,
                    baseline_state=n5.baseline_state,
                    budget_ref=n5.budget_ref,
                )
                observer = _with_scope(observer, budget_scope)
                controller = JointSimulationHorizonController(
                    producer_budget_observer=observer, physical_n5_budget_scope=budget_scope
                )
                port = JointSimulationPort(
                    controller=controller,
                    artifact_store=store,
                    physical_n5_budget_scope=budget_scope,
                    cycle_substrate_context=handoff.context,
                    generic_cycle_simulation_admission_owner=owner,
                    generic_cycle_simulation_handoff=handoff,
                )
                bound_request, consumptions, failures = port._request_with_bound_program_state(
                    request
                )
                assert not failures
                assert consumptions[0].program_graph_ref == str(case.program_graph_ref.artifact_id)
                candidate = load_policy_candidate_schema(store, case.policy_candidate_ref)
                context = ModelInputContext(
                    run_id=scope.run_id,
                    candidate_id=candidate.candidate_id,
                    candidate_content_hash=str(case.policy_candidate_ref.artifact_id),
                    design_problem_ref=handoff.context.design_problem_ref,
                    candidate_source_ref=case.policy_candidate_ref,
                    context_job_ref=handoff.context_job_ref,
                )
                views = world_model_artifact_views(world)
                assert views.input_bindings_ref.manifest_profile_sha256 is not None
                assert views.bound_state_snapshot_ref.manifest_profile_sha256 is not None
                assert views.input_binding_report_ref.manifest_profile_sha256 is not None
                graph_ref = ProgramGraphRef.model_validate(case.program_graph_ref.model_dump())
                exec_plan_ref = ExecPlanRef.model_validate(case.exec_plan_ref.model_dump())
                interface_ref = derive_program_graph_input_interface(
                    store,
                    program_graph_ref=graph_ref,
                    exec_plan_ref=exec_plan_ref,
                    registry_bundle_ref=case.registry_bundle_ref,
                )
                assert interface_ref is not None
                invocation = ProgramGraphInputInvocation(
                    context=context,
                    interface_ref=interface_ref,
                    program_graph_ref=graph_ref,
                    exec_plan_ref=exec_plan_ref,
                    registry_bundle_ref=case.registry_bundle_ref,
                    input_bindings_ref=FoundryInputBindingsRef.model_validate(
                        views.input_bindings_ref.model_dump()
                    ),
                    steps=(0, 1, 2),
                )

                def preflight(
                    selected_request: JointSimulationRequest,
                    selected_plan: EnginePlan,
                    decision: EngineDecision,
                ) -> ProgramGraphInputPreflight:
                    context_owner.require_current_job_scope(verified_nl_job_scope=scope)
                    assert decision.engine_kind == "program_graph"
                    assert selected_plan.program_graph_ref == graph_ref
                    assert selected_plan.exec_plan_ref == exec_plan_ref
                    assert selected_plan.program_compilation_ref == case.compile_report_ref
                    return preflight_program_graph_inputs(
                        store,
                        interface_ref=interface_ref,
                        program_graph_ref=graph_ref,
                        exec_plan_ref=exec_plan_ref,
                        registry_bundle_ref=case.registry_bundle_ref,
                        input_bindings_ref=invocation.input_bindings_ref,
                        context=context,
                        steps=selected_request.horizon.steps(),
                    )

                dispatches = []
                actual_runners = controller._engine_runners

                def record_dispatch():
                    dispatches.append("dispatch")
                    return actual_runners()

                monkeypatch.setattr(controller, "_engine_runners", record_dispatch)
                before = middleware._ledger.snapshot()
                with (
                    _bind_scoped_n5_invocation_policy(
                        observer, n5_profile=n5, physical_n5_budget_scope=budget_scope
                    ),
                    pytest.raises(ProgramGraphInputsRequiredError) as raised,
                ):
                    controller.run(bound_request, _program_graph_input_preflight=preflight)
                after = middleware._ledger.snapshot()
                assert dispatches == []
                assert before.invocation_reservations == after.invocation_reservations
                assert before.producer_settlements == after.producer_settlements

                fresh = FileSystemCAS(store.root).for_tenant(scope.tenant_id, scope.cell_id)
                obligation_ref = raised.value.obligation_set_ref
                selected_set, (obligation,) = load_model_input_obligation_set(fresh, obligation_ref)
                assert (
                    verify_program_graph_input_preflight(
                        fresh, obligation_set_ref=obligation_ref, expected_invocation=invocation
                    )
                    == selected_set
                )
                assert selected_set.supplied_initial_slots == (_INCOME,)
                assert obligation.port.slot_id == _OUTCOME
                assert obligation.missing_reason == "required_port_input_not_bound"
                (dependency,) = obligation.dependencies
                assert (dependency.node_id, dependency.kind, dependency.first_required_step) == (
                    "fixture_subsidy",
                    "additive_prestate",
                    2,
                )
    finally:
        service.close()
