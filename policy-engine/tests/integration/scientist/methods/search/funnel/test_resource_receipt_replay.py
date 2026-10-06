"""A real provider receipt replay cannot become a second funnel charge."""

import asyncio
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.methods.search.funnel.level3_medium import Level3MediumFidelity
from polisyos.scientist.methods.search.funnel.level4_full import Level4FullFidelity
from polisyos.scientist.methods.search.funnel.orchestrator import FunnelOrchestrator
from polisyos.scientist.methods.search.funnel.types import observe_funnel_resource_response
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine

_root = Path(__file__).resolve().parents[6]
_text = run_path(str(_root / "tests/integration/core/llm/test_gateway_response_text_cost.py"))


@pytest.mark.parametrize("split", [False, True])
def test_actual_same_provider_event_is_not_charged_again_at_next_stage(tmp_path, split):
    path = tmp_path / "budget.json"
    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(5))})
    owner = BudgetMiddleware(budget, ledger=FileBudgetLedger(path))
    gateway = _text["TextGateway"](_text["response_text"]("usage", "cost_usd", "1"))
    enforcer = LLMBudgetEnforcer(
        client=TracedLLMClient(gateway, model_name="test-model"),
        budget_state=budget,
        budget_keys=["run"],
        run_id="replay-run",
        model_name="test-model",
        budget_middleware=owner,
    )
    actual_responses = []

    def estimate(state):
        if not actual_responses:
            actual_responses.append(
                asyncio.run(
                    enforcer.generate(
                        user="actual request",
                        max_tokens=1,
                        _prompt_tokens_estimate=1,
                        _evaluation_id=state["_resource_evaluation_id"],
                    )
                )
            )
        # The actual D worker port consumes an authentic original receipt in
        # both stages. No second provider call or ledger event occurs.
        observe_funnel_resource_response(actual_responses[0])
        return {
            **state,
            "simulation_results": {
                "gdp_change": 1,
                "ate": 1,
                "bootstrap": {"ci_width": 0.01},
            },
        }

    engine = SimpleLoopEngine(
        [
            ("estimate", estimate),
            ("feedback", lambda state: {**state, "feedback": {"verdict": "APPROVE"}}),
        ],
        "feedback",
    )
    funnel = FunnelOrchestrator(
        [Level3MediumFidelity(engine), Level4FullFidelity(engine)],
        stage_a_max_level=3,
        budget_middleware=owner,
    )
    ticket = funnel.submit({"candidate_id": "candidate-replay"}, {"run_id": "replay-run"})
    if split:
        stage_a = funnel.advance(ticket, policy="stage_a")
        assert stage_a.provider_spend_usd == 1
    outcome = funnel.advance(ticket, policy="full")
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == 1 and len(snapshot.spend_receipts) == 1
    assert gateway.transport.calls == 1
    assert outcome.provider_spend_usd == 1
    assert len(outcome.resource_event_ids) == 1
    assert outcome.stage_results[3].provider_spend_usd == 1
    assert outcome.stage_results[4].provider_spend_usd == 0
    assert outcome.final_action == "reject"
    assert "resource_provider_event_replayed" in {
        card.failure_type for card in outcome.stage_results[4].failure_cards
    }
