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


def test_two_paid_runs_on_same_controller_match_fresh_controllers_with_scoped_sentinels(
    tmp_path, monkeypatch
):
    from copy import deepcopy

    from polisyos.scientist.methods.search.stopping import (
        CompositeStoppingCriterion,
        MaxIterations,
    )

    class Transport:
        async def generate(self, **kwargs):
            return GatewayLLMResponse(
                content='{"scenarios":[{"scenario_id":"s1","scenario_type":"bounded_shift"}]}',
                provider="provider-a",
                request_id="paid-controller-control",
                usage=GatewayUsage(prompt_tokens=1, completion_tokens=1, cost_usd=1.0),
            )

    monkeypatch.setattr(
        "polisyos.scientist.policy_design.adversary.create_traced_gateway_client",
        lambda **kwargs: Transport(),
    )

    class Batch:
        def generate(self, history, current_best, context):
            raise AssertionError("The configured two-row native batch is required")

        def generate_batch(self, history, current_best, context, batch_size):
            label = context["run_label"]
            return [
                {
                    "candidate_id": f"sentinel-{label}",
                    "semantic": {"interventions": []},
                    "__sentinel__": {"sentinel_id": f"control-{label}"},
                },
                {"candidate_id": f"ordinary-{label}", "semantic": {"interventions": []}},
            ]

    def execute(profile, reuse_controller):
        path = tmp_path / profile / "budget.json"
        owner = BudgetMiddleware(
            BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("20"))}),
            ledger=FileBudgetLedger(path),
        )
        worker = ScenarioAdversaryWorker(
            ScenarioAdversaryConfig(budget_keys=["run"], fallback_on_error=False),
            budget_middleware=owner,
        )
        physical = []

        def new_controller():
            search = None

            def stage_b(candidate, context):
                run_id = search._run_state.search_id
                candidate_id = candidate["candidate_id"]
                proposal = worker.propose(
                    ScenarioAttackSurface(candidate_id=candidate_id),
                    run_id=run_id,
                    evaluation_id=candidate_id,
                )
                assert not proposal.fallback_used
                physical.append((run_id, candidate_id))
                return {
                    # The sentinel is deliberately more attractive than every
                    # ordinary/warm value; admitting it changes best/frontier.
                    "simulation_results": {"gdp_change": 100 if "__sentinel__" in candidate else 1},
                    "feedback": {"verdict": "APPROVE"},
                }

            search = SearchController(
                config=SearchConfig(
                    stopping=CompositeStoppingCriterion([MaxIterations(1), CostBudgetStopping(10)]),
                    objective=CompositeObjective([GDPGrowthObjective()]),
                    batch_size=2,
                    budget_middleware=owner,
                    initial_evaluations=[
                        {"candidate": {"candidate_id": "warm-1"}, "objective_value": -1},
                        {"candidate": {"candidate_id": "warm-2"}, "objective_value": -2},
                    ],
                ),
                candidate_generator=Batch(),
                stage_a_evaluator=lambda candidate, context: (0, True),
                stage_b_evaluator=stage_b,
            )
            return search

        search = new_controller()
        results, projections, snapshots = [], [], []
        for index, label in enumerate(("one", "two"), start=1):
            if index > 1 and not reuse_controller:
                search = new_controller()
            result = search.run({"run_label": label})
            results.append(result)
            snapshot = FileBudgetLedger(path).snapshot()
            snapshots.append(snapshot)
            assert snapshot.state.spent == {"run": Decimal(2 * index)}
            assert len(snapshot.spend_receipts) == 2 * index
            assert all(
                row.amount == 1 and row.provider == "provider-a"
                for row in snapshot.spend_receipts.values()
            )
            assert all(amount == 0 for amount in snapshot.state.reserved.values())
            assert not snapshot.completion_obligations
            assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": float(2 * index)}
            assert result.telemetry["training_evaluations"] == 2
            assert result.telemetry["sentinel_evaluations"] == 1
            assert result.telemetry["new_evaluations"] == result.iterations_completed == 1
            assert result.stage_a_evaluations == result.stage_b_evaluations == 2
            assert result.best_candidate == {"candidate_id": "warm-2"}
            assert result.best_objective == -2
            assert [row.candidate["candidate_id"] for row in result.history] == [
                "warm-1",
                "warm-2",
                f"ordinary-{label}",
            ]
            assert [row["candidate"]["candidate_id"] for row in result.pareto_front] == [
                f"ordinary-{label}"
            ]
            assert physical[-2:] == [
                (result.search_id, f"sentinel-{label}"),
                (result.search_id, f"ordinary-{label}"),
            ]
            projections.append(
                {
                    "history": [
                        (row.iteration, row.candidate, row.objective_value)
                        for row in result.history
                    ],
                    "best": result.best_candidate,
                    "best_objective": result.best_objective,
                    "frontier": result.pareto_front,
                    "training": result.telemetry["training_evaluations"],
                    "sentinels": result.telemetry["sentinel_evaluations"],
                    "new": result.iterations_completed,
                    "stage_a": result.stage_a_evaluations,
                    "stage_b": result.stage_b_evaluations,
                    "spend": result.telemetry["budget_snapshot"],
                }
            )
            if index == 1:
                retained_first = deepcopy(result)
        assert results[0] == retained_first
        assert results[0].search_id != results[1].search_id
        assert set(snapshots[0].spend_receipts) < set(snapshots[1].spend_receipts)
        assert all(
            snapshots[1].spend_receipts[key] == receipt
            for key, receipt in snapshots[0].spend_receipts.items()
        )
        print(
            "actual_paid_run_comparison",
            profile,
            projections,
            [row.search_id for row in results],
            [sorted(row.spend_receipts) for row in snapshots],
        )
        return projections

    assert execute("one-mutable-controller", True) == execute("two-fresh-controllers", False)
