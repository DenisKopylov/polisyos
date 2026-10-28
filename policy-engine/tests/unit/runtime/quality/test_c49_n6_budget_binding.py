"""Real canonical caller binds one run owner; no substitute budget receipt."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from decimal import Decimal

import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.methods.catalog.causal.ncm_engine import NCMEngineMethod
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleError,
    JointSimulationPort,
    load_joint_simulation_result,
)
from polisyos.runtime.quality.joint_simulation_horizon import JointSimulationHorizonController
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


@pytest.mark.asyncio
@pytest.mark.parametrize("supply_port", [False, True])
async def test_real_n6_default_and_supplied_same_owner_stop_on_a_between_native_seeds(
    tmp_path,
    monkeypatch,
    supply_port,
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
                        score=0.9,
                        voi_estimate=4.0,
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
            assert controller._simulation_port._controller._producer_budget_observer is owner
            assert owner.last_checked.remaining_usd <= Decimal(0)
            refs = [
                cycle.simulation.simulation_result_ref
                for cycle in run.cycles
                if cycle.simulation.simulation_result_ref is not None
            ]
            assert refs
            result = load_joint_simulation_result(refs[0], store=store)
            assert result.diagnostics["physical_work_interruption"] == "n5_current_budget_exhausted"
            assert len(result.physical_work_observations) == 1
            assert result.physical_work_observations[0].budget_status == "current_owner_checked"
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
