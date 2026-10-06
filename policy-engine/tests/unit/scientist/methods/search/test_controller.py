"""Controller supplier evaluation and persisted resource-owner consumption."""

from copy import deepcopy
from decimal import Decimal

import pytest

from polisyos.scientist.methods.search.controller import SearchConfig, SearchController
from polisyos.scientist.methods.search.objective import CompositeObjective, GDPGrowthObjective
from polisyos.scientist.methods.search.service import _NativeSearchServiceDriver
from polisyos.scientist.methods.search.stopping import CostBudgetStopping, MaxIterations
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage


class Generator:
    def generate(self, history, current_best, context):
        return {"candidate_id": "candidate-1", "semantic": {"interventions": []}}


def controller(stage_b, stopping=None, owner=None):
    return SearchController(
        config=SearchConfig(
            stopping=stopping or MaxIterations(1),
            objective=CompositeObjective([GDPGrowthObjective()]),
            budget_middleware=owner,
        ),
        candidate_generator=Generator(),
        stage_a_evaluator=lambda candidate, context: (0.0, True),
        stage_b_evaluator=stage_b,
    )


def test_evaluation_supplier_does_not_accept_state_and_real_tell_accepts_once():
    search = controller(
        lambda candidate, context: {
            "simulation_results": {"gdp_change": 2},
            "feedback": {"verdict": "APPROVE"},
        }
    )
    service = _NativeSearchServiceDriver(search)
    proposal = service.ask(None, None, {})[0]
    before = search._run_state.snapshot()
    evaluation = search._evaluate_for_tell(proposal.payload, iteration=0, context={})
    assert search._run_state == before
    assert evaluation.objective_value == -2
    service.tell(proposal.candidate_id, evaluation)
    state = search._run_state.snapshot()
    assert state.evaluation_iterations == 1
    assert state.stage_a_evaluations == state.stage_b_evaluations == 1
    assert len(state.history) == 1
    with pytest.raises(ValueError, match="duplicate"):
        service.tell(proposal.candidate_id, evaluation)
    assert search._run_state == state


@pytest.mark.parametrize("malformed", [None, {"unexpected": "typed"}, False, []])
def test_present_malformed_typed_result_never_uses_legacy_scalar(malformed):
    search = controller(
        lambda candidate, context: {
            "simulation_results": {"gdp_change": 10},
            "feedback": {"verdict": "APPROVE"},
            "policy_evaluation": malformed,
        }
    )
    result = search.run({})
    assert result.best_candidate is None
    assert result.history[0].objective_value == float("inf")
    assert result.history[0].policy_evaluation_status == "invalid"
    assert result.telemetry["policy_evaluation_errors"] == 1


def test_measured_provider_charge_drives_stopping_and_detached_report(tmp_path):
    path = tmp_path / "budget.json"
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5"))})
    owner = BudgetMiddleware(state, ledger=FileBudgetLedger(path))

    class Transport:
        def invoke(self, prompt, **kwargs):
            return GatewayLLMResponse(
                content="response",
                provider="provider-a",
                request_id="request-1",
                usage=GatewayUsage(cost_usd=1.0),
            )

    llm = LLMBudgetEnforcer(
        client=Transport(),
        budget_state=state,
        budget_keys=["run"],
        budget_middleware=owner,
        run_id="run-1",
    )

    def stage_b(candidate, context):
        llm.invoke("hello", _prompt_tokens_estimate=1, max_tokens=1)
        return {"simulation_results": {"gdp_change": 2}, "feedback": {"verdict": "APPROVE"}}

    search = controller(stage_b, stopping=CostBudgetStopping(max_cost_usd=1), owner=owner)
    result = search.run({"cumulative_cost_usd": -999})
    assert result.iterations_completed == 1
    assert result.telemetry["budget_snapshot"] == {"cumulative_cost_usd": 1.0}
    assert result.telemetry["budget_snapshot_source"] == "persisted_owner"
    assert result.telemetry["budget_ledger_revision"] == FileBudgetLedger(path).snapshot().revision
    assert FileBudgetLedger(path).load().remaining("run") == Decimal("4")
    frozen = deepcopy(result)
    owner.record_spend_safe("run", Decimal("1"))
    assert result == frozen
