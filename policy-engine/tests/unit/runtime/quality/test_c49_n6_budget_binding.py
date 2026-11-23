"""Real canonical caller binds one run owner; no substitute budget receipt."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from decimal import Decimal

import pytest

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleError,
    JointSimulationPort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationResult,
    verify_simulation_receipt,
)
from polisyos.scientist.orchestration.engine.producer_budget import ProducerBudgetObserver
from tests.unit.runtime.quality.test_c49_native_stopping_budget import (
    _producer_owner,
    _real_provider_charge,
)
from tests.unit.runtime.quality.test_generation_cycle import (
    _GenerationResult,
    _owner_n5_case_with_selected_ncm_ref,
    _problem,
    _Ranking,
    _runtime_ncm_fixture_store,
)


def _observer(tmp_path, *, run_suffix=""):
    middleware, binding, state = _producer_owner(tmp_path, cap="10")
    binding = binding.model_copy(
        update={
            "run_id": binding.run_id + run_suffix,
            "tenant_id": "tenant-n5-owner",
            "cell_id": "cell-n5-owner",
        }
    )
    observer = ProducerBudgetObserver(
        settlement_store=middleware,
        producer_run_binding=binding,
        budget_state=state,
    )
    return middleware, binding, state, observer


def _charge_from_sync_boundary(middleware, binding, amount, label):
    # Only an accounting wire call runs in the bounded extra thread. The real
    # native method and every numerical thread remain the configured owner path.
    context = copy_context()
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            context.run,
            _real_provider_charge,
            middleware,
            binding,
            amount,
            label,
        ).result()


@pytest.mark.parametrize("supplied", ["foreign", "absent"])
def test_supplied_canonical_port_refuses_foreign_or_absent_expected_owner(tmp_path, supplied):
    _, _, _, owner_a = _observer(tmp_path / "a")
    _, _, _, owner_b = _observer(tmp_path / "b", run_suffix="-b")
    port = JointSimulationPort(
        controller=JointSimulationHorizonController(
            producer_budget_observer=owner_b if supplied == "foreign" else None,
        )
    )
    with pytest.raises(GenerationCycleError, match="n5_producer_budget_owner_mismatch"):
        GenerationCycleController(
            simulation_port=port,
            _producer_budget_reconciler=owner_a,
            authority_scope="contract_testing",
        )


@pytest.mark.asyncio
async def test_actual_run_refuses_detached_budget_state_before_generation(tmp_path):
    _, _, state, owner = _observer(tmp_path)
    calls = []

    async def must_not_generate(*args, **kwargs):
        calls.append(True)
        raise AssertionError("generation began with another run state")

    controller = GenerationCycleController(
        generation_port=must_not_generate,
        _producer_budget_reconciler=owner,
        authority_scope="contract_testing",
    )
    with pytest.raises(GenerationCycleError, match="n5_producer_budget_state_binding_mismatch"):
        # The join precedes problem/source construction; no synthetic problem is admitted.
        await controller.run(_problem(), budget_state=state.model_copy(deep=True))
    assert calls == []


# Keep the low proxy numeric; it does not stand in for an unknown value.
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("supply_port", "proxy_score", "voi_estimate", "expected_scheduler_reason"),
    [
        pytest.param(False, 0.9, 4.0, "advance_by_voi", id="default-port-high-score"),
        pytest.param(True, 0.9, 4.0, "advance_by_voi", id="supplied-port-high-score"),
        pytest.param(
            False,
            0.1,
            0.8,
            "advance_by_information_value",
            id="default-port-low-score-positive-information",
        ),
    ],
)
async def test_real_n6_default_and_supplied_same_owner_stop_on_a_between_native_seeds(
    tmp_path,
    monkeypatch,
    supply_port,
    proxy_score,
    voi_estimate,
    expected_scheduler_reason,
):
    store, _, ncm_ref = _runtime_ncm_fixture_store(tmp_path / "source")
    problem, context, candidate = _owner_n5_case_with_selected_ncm_ref(
        ncm_ref,
        artifact_store=store,
        tmp_path=tmp_path / "source",
        runtime_hints={
            "joint_simulation_horizon": {"start": 0, "end": 0, "step": 1},
            "joint_simulation_baseline_state": {"firm_survival": 0.0},
            "joint_simulation_replications": 2,
        },
    )
    middleware, binding, state, owner = _observer(tmp_path / "money")

    class ControlledN4:
        async def __call__(self, generated_problem, *, cycle_index):
            assert generated_problem.design_problem_id == problem.design_problem_id
            assert cycle_index == 0
            return _GenerationResult(
                status="generated",
                candidates=(candidate,),
                surrogate_rankings=(
                    _Ranking(
                        candidate_id=candidate.candidate_id,
                        score=proxy_score,
                        voi_estimate=voi_estimate,
                    ),
                ),
            )

    def limited_grounding(*, candidate, **kwargs):
        return CandidateGroundingObservation(
            candidate_id=candidate.candidate_id,
            status="grounding_unavailable",
            grounding_score=0.2,
            issue_codes=("controlled_profile_grounding_unavailable",),
            grounding_source="grounding_unavailable",
        )

    port = (
        JointSimulationPort(
            controller=JointSimulationHorizonController(producer_budget_observer=owner),
            repo_root=tmp_path / "source",
            artifact_store=store,
            cycle_substrate_context=context,
        )
        if supply_port
        else None
    )
    controller = GenerationCycleController(
        generation_port=ControlledN4(),
        grounding_port=limited_grounding,
        simulation_port=port,
        repo_root=tmp_path / "source",
        artifact_store=store,
        cycle_substrate_context=context,
        authority_scope="contract_testing",
        _producer_budget_reconciler=owner,
    )
    scheduled = []
    schedule_candidate = controller._schedule_candidate_for_execution

    def observe_schedule(**kwargs):
        decision = schedule_candidate(**kwargs)
        scheduled.append(
            (
                kwargs["candidate_id"],
                kwargs["proxy_score"],
                kwargs["voi_estimate"],
                decision,
                owner.last_checked.remaining_usd,
            )
        )
        return decision

    monkeypatch.setattr(controller, "_schedule_candidate_for_execution", observe_schedule)
    original = NCMEngineMethod.pure_step
    native_calls = []

    def actual_native_method_then_current_a_spend(method_state, params):
        output = original(method_state, params)
        native_calls.append(params["__seed__"])
        if len(native_calls) == 1:
            _charge_from_sync_boundary(middleware, binding, 9.8, "A exhausted between native seeds")
        return output

    monkeypatch.setattr(
        NCMEngineMethod, "pure_step", staticmethod(actual_native_method_then_current_a_spend)
    )
    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            _charge_from_sync_boundary(middleware, binding, 0.2, "A before real N6")
            run = await controller.run(problem, budget_state=state, min_cycles=1, max_cycles=1)
            assert len(native_calls) == 1
            assert scheduled
            (
                scheduled_candidate_id,
                scheduled_proxy_score,
                scheduled_voi_estimate,
                initial_schedule,
                initial_remaining_usd,
            ) = scheduled[0]
            assert scheduled_candidate_id == candidate.candidate_id
            assert scheduled_proxy_score == proxy_score
            assert scheduled_voi_estimate == voi_estimate
            assert initial_schedule.candidate_id == candidate.candidate_id
            assert initial_schedule.next_level == 3
            assert initial_schedule.recommended_action == "advance"
            assert initial_schedule.reason == expected_scheduler_reason
            assert initial_schedule.economics.expected_improvement_per_usd == pytest.approx(
                proxy_score / 0.5
            )
            assert initial_schedule.economics.estimated_cost_usd == 0.5
            assert initial_remaining_usd == Decimal("9.8")
            assert controller._simulation_port._controller._producer_budget_observer is owner
            assert owner.last_checked.remaining_usd <= Decimal(0)
            refs = [
                cycle.simulation.simulation_result_ref
                for cycle in run.cycles
                if cycle.simulation.simulation_result_ref is not None
            ]
            assert refs
            ref = refs[0]
            with pytest.raises(
                GenerationCycleError,
                match="joint_simulation_result_trajectory_missing",
            ):
                # The consumer remains strict: an interrupted run is not a
                # successful numerical result.
                load_joint_simulation_result(ref, store=store)

            selected = read_core_json_artifact(store, ref)
            assert selected.status == "declared_bytes_conformant"
            assert ref.manifest_profile_sha256 is not None
            assert selected.selected_manifest_profile_sha256 == ref.manifest_profile_sha256
            payload = selected.value
            assert isinstance(payload, dict)
            result = JointSimulationResult.model_validate(payload)
            verify_simulation_receipt(
                result.receipt,
                {key: value for key, value in payload.items() if key != "receipt"},
            )

            selected_decisions = [
                decision for decision in result.engine_decisions if decision.decision == "selected"
            ]
            assert len(selected_decisions) == 1
            assert selected_decisions[0].engine_kind == "ncm_parallel_worlds"
            assert selected_decisions[0].method_fqn == NCMEngineMethod.signature.fqn
            assert result.receipt.engine_kind == "ncm_parallel_worlds"
            assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
            assert result.trajectories == ()
            assert result.receipt.trajectory_count == 0
            observations = result.physical_work_observations
            assert len(observations) == result.diagnostics["physical_work_units"] == 1
            observation = observations[0]
            assert observation.status == "completed"
            assert observation.work_units == 1
            assert observation.budget_status == "current_owner_checked"
            assert observation.usd_cost is None
            assert observation.usd_cost_status == "not_established"
            assert state.spent["run"] == Decimal("10.0")
    finally:
        close = getattr(store, "close", None)
        if callable(close):
            close()


@pytest.mark.asyncio
async def test_actual_run_rechecks_supplied_port_owner_before_any_generation(tmp_path):
    _, _, state, owner_a = _observer(tmp_path / "a")
    _, _, _, owner_b = _observer(tmp_path / "b", run_suffix="-b")
    calls = []

    async def must_not_generate(*args, **kwargs):
        calls.append(True)
        raise AssertionError("generation began after port owner drift")

    controller = GenerationCycleController(
        generation_port=must_not_generate,
        _producer_budget_reconciler=owner_a,
        authority_scope="contract_testing",
    )
    controller._simulation_port = JointSimulationPort(
        controller=JointSimulationHorizonController(
            producer_budget_observer=owner_b,
        )
    )
    with pytest.raises(GenerationCycleError, match="n5_producer_budget_owner_mismatch"):
        await controller.run(_problem(), budget_state=state)
    assert calls == []
