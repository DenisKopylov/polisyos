"""Measured sentinel resources and the native controller's distinct counters."""

from decimal import Decimal

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.stopping import CostBudgetStopping
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.policy_design.adversary import (
    ScenarioAdversaryConfig,
    ScenarioAdversaryWorker,
    ScenarioAttackSurface,
)


def test_native_paid_sentinel_stops_on_cost_without_training_or_new_evaluation_count(
    tmp_path, monkeypatch
):
    path = tmp_path / "budget.json"
    owner = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))}),
        ledger=FileBudgetLedger(path),
    )
    calls = []

    class Transport:
        async def generate(self, **kwargs):
            calls.append(kwargs)
            return GatewayLLMResponse(
                content='{"scenarios":[{"scenario_id":"s1","scenario_type":"bounded_shift"}]}',
                provider="provider-a",
                request_id="sentinel-request-1",
                usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, cost_usd=1.0),
            )

    monkeypatch.setattr(
        "polisyos.scientist.policy_design.adversary.create_traced_gateway_client",
        lambda **kwargs: Transport(),
    )
    worker = ScenarioAdversaryWorker(
        ScenarioAdversaryConfig(budget_keys=["run"], fallback_on_error=False),
        budget_middleware=owner,
    )

    def stage_b(candidate, context):
        proposal = worker.propose(
            ScenarioAttackSurface(candidate_id="sentinel-1"),
            run_id="run-1",
            evaluation_id="sentinel-1",
        )
        assert not proposal.fallback_used
        return {"simulation_results": {"gdp_change": 2}, "feedback": {"verdict": "APPROVE"}}

    class Generator:
        def generate(self, history, current_best, context):
            raise AssertionError("Measured cost must stop the run before another generation.")

    search = SearchController(
        config=SearchConfig(
            stopping=CostBudgetStopping(max_cost_usd=1),
            objective=CompositeObjective([GDPGrowthObjective()]),
            budget_middleware=owner,
            initial_evaluations=[
                {"candidate": {"candidate_id": "warm-1"}, "objective_value": -1},
                {"candidate": {"candidate_id": "warm-2"}, "objective_value": -2},
            ],
        ),
        candidate_generator=Generator(),
        stage_a_evaluator=lambda candidate, context: (0, True),
        stage_b_evaluator=stage_b,
    )
    result = search.run(
        {}, initial_candidate={"candidate_id": "sentinel-1", "__sentinel__": {"sentinel_id": "s1"}}
    )
    assert len(calls) == 1
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("1")
    assert snapshot.state.remaining("run") == Decimal("4")
    assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": 1.0}
    assert result.telemetry["training_evaluations"] == 2
    assert result.telemetry["new_evaluations"] == result.iterations_completed == 0
    assert result.telemetry["sentinel_evaluations"] == 1
    assert result.telemetry["scientific_evaluations"] == 0
    assert result.stage_a_evaluations == result.stage_b_evaluations == 1
    assert len(result.history) == 2
    assert all(record.iteration == -1 for record in result.history)
