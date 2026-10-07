"""Prove the default N6 scheduler's information-value choice reaches real N5."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    JointSimulationPort,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tests.integration.core_runtime.test_e02_hard_feasibility_before_voi import (
    _FixtureGrounding,
    _owner_fixture,
)


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[object, ...]
    surrogate_rankings: tuple[_Ranking, ...]


class _LowProxyInformationGenerator:
    """Set N4 ranking evidence while preserving the real downstream owners."""

    def __init__(self, candidate: object) -> None:
        self._candidate = candidate

    async def __call__(self, problem: object, *, cycle_index: int) -> _GenerationResult:
        del problem
        assert cycle_index == 0
        candidate_id = str(getattr(self._candidate, "candidate_id"))
        return _GenerationResult(
            status="generated",
            candidates=(self._candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate_id, score=0.0, voi_estimate=0.4),
            ),
        )


def _bounded_budget(max_usd: str) -> BudgetState:
    """Build the existing scheduler budget input for this bounded fixture."""

    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def _controller(
    *,
    store: Any,
    problem: object,
    context: object,
    candidate: object,
    repo_root: Path,
) -> GenerationCycleController:
    """Use production N6 composition with the default scheduler and N5 port."""

    return GenerationCycleController(
        generation_port=_LowProxyInformationGenerator(candidate),
        grounding_port=_FixtureGrounding(),
        repo_root=repo_root,
        cycle_substrate_context=context,
        promotion_runtime=PromotionRuntime(store=store),
        authority_scope="production",
    )


@pytest.mark.asyncio
async def test_default_information_value_advance_executes_real_n5_and_budget_blocks_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Low proxy plus positive information advances; an exhausted cap blocks N5."""

    repo_root = Path(__file__).resolve().parents[3]
    positive_store, positive_problem, positive_context, _high, positive_candidate = (
        _owner_fixture(tmp_path / "positive")
    )
    exhausted_store, exhausted_problem, exhausted_context, _high, exhausted_candidate = (
        _owner_fixture(tmp_path / "exhausted")
    )
    stores = (positive_store, exhausted_store)
    n5_calls: list[str] = []
    original_n5_call = JointSimulationPort.__call__

    def observe_real_n5_call(self: JointSimulationPort, **kwargs: Any) -> Any:
        candidate = kwargs["candidate"]
        n5_calls.append(str(getattr(candidate, "candidate_id")))
        return original_n5_call(self, **kwargs)

    monkeypatch.setattr(JointSimulationPort, "__call__", observe_real_n5_call)

    try:
        with tenant_scope(None, tenant_id="tenant-n5-owner", cell_id="cell-n5-owner"):
            positive_controller = _controller(
                store=positive_store,
                problem=positive_problem,
                context=positive_context,
                candidate=positive_candidate,
                repo_root=repo_root,
            )
            positive_budget = _bounded_budget("1.0")
            assert type(positive_controller._voi_scheduler) is SimpleVOIScheduler
            assert positive_controller._candidate_simulation_handoff is None
            assert type(positive_controller._simulation_port) is JointSimulationPort
            assert positive_controller._simulation_port.supports_applicability_preflight(
                positive_problem
            )

            # This budget is a scheduler cap fixture. The synthetic local NCM
            # execution does not report or settle provider charges.
            positive_run = await positive_controller.run(
                positive_problem,
                budget_state=positive_budget,
                min_cycles=1,
                max_cycles=1,
            )
            positive_cycle = positive_run.cycles[0]
            positive_summary = next(
                summary
                for summary in positive_run.candidate_summaries
                if summary.candidate_id == positive_candidate.candidate_id
            )
            assert positive_summary.proxy_score == 0.0
            assert positive_summary.voi_estimate == 0.4
            assert positive_summary.n5_applicability is not None
            assert positive_summary.n5_applicability.status == "eligible"
            assert positive_cycle.voi_decision.scheduler_action == "advance"
            assert positive_cycle.voi_decision.scheduler_reason == (
                "advance_by_information_value"
            )
            assert positive_cycle.simulation.status == "joint_simulated"
            assert positive_cycle.simulation.simulation_result_ref is not None
            assert positive_cycle.value_port.status == "value_conditional"
            assert positive_cycle.value_port.value_ref == str(
                positive_cycle.simulation.simulation_result_ref.artifact_id
            )
            assert n5_calls == [positive_candidate.candidate_id]

            exhausted_controller = _controller(
                store=exhausted_store,
                problem=exhausted_problem,
                context=exhausted_context,
                candidate=exhausted_candidate,
                repo_root=repo_root,
            )
            exhausted_budget = _bounded_budget("0.0")
            assert type(exhausted_controller._voi_scheduler) is SimpleVOIScheduler
            assert exhausted_controller._candidate_simulation_handoff is None
            assert type(exhausted_controller._simulation_port) is JointSimulationPort
            assert exhausted_controller._simulation_port.supports_applicability_preflight(
                exhausted_problem
            )

            exhausted_run = await exhausted_controller.run(
                exhausted_problem,
                budget_state=exhausted_budget,
                min_cycles=1,
                max_cycles=1,
            )
            exhausted_cycle = exhausted_run.cycles[0]
            exhausted_summary = next(
                summary
                for summary in exhausted_run.candidate_summaries
                if summary.candidate_id == exhausted_candidate.candidate_id
            )
            assert exhausted_summary.n5_applicability is not None
            assert exhausted_summary.n5_applicability.status == "eligible"
            assert exhausted_cycle.voi_decision.scheduler_action == "defer"
            assert exhausted_cycle.voi_decision.scheduler_reason == (
                "budget_exhausted_for_next_level"
            )
            assert exhausted_cycle.simulation.status == "simulation_blocked"
            assert exhausted_cycle.simulation.simulation_result_ref is None
            assert exhausted_cycle.simulation.authority_blockers == (
                "budget_exhausted_for_next_level",
            )
            assert n5_calls == [positive_candidate.candidate_id]
    finally:
        for store in stores:
            store.close()
