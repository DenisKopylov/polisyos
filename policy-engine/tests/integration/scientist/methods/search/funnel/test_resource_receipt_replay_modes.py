"""The existing local event boundary applies to reported and estimated inputs."""

import asyncio
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from runpy import run_path

import pytest

from polisyos.core.llm.settlement import producer_settlement
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
@pytest.mark.parametrize("profile", ["estimated", "mixed"])
@pytest.mark.parametrize("positive_terminal", [False, True])
def test_actual_estimated_and_mixed_replay_projects_only_fresh_local_events(
    tmp_path, split, profile, positive_terminal
):
    path = tmp_path / "budget.json"
    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal(5))})
    owner = BudgetMiddleware(budget, ledger=FileBudgetLedger(path))
    gateways, enforcers = [], []
    for cost in ["null"] if profile == "estimated" else ["1", "null"]:
        gateway = _text["TextGateway"](
            _text["response_text"]("usage", "cost_usd", cost), model="gpt-3.5-turbo"
        )
        gateways.append(gateway)
        enforcers.append(
            LLMBudgetEnforcer(
                client=TracedLLMClient(gateway, model_name="gpt-3.5-turbo"),
                budget_state=budget,
                budget_keys=["run"],
                run_id="replay-run",
                model_name="gpt-3.5-turbo",
                budget_middleware=owner,
            )
        )
    actual_responses = []

    def estimate(state):
        if not actual_responses:
            for enforcer in enforcers:
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
        for response in actual_responses:
            observe_funnel_resource_response(response)
            observe_funnel_resource_response(response)  # Exact in-stage redelivery.
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

    class TerminalResultProfile(Level4FullFidelity):
        def evaluate(self, candidate, context):
            actual = super().evaluate(candidate, context)
            # The ordinary public stage result supports a terminal action.
            # This is a consumer profile, not a permission or L6 writer claim.
            return replace(actual, terminal_action="complete") if positive_terminal else actual

    funnel = FunnelOrchestrator(
        [Level3MediumFidelity(engine), TerminalResultProfile(engine)],
        stage_a_max_level=3,
        budget_middleware=owner,
    )
    ticket = funnel.submit({"candidate_id": "candidate-replay"}, {"run_id": "replay-run"})
    if split:
        funnel.advance(ticket, policy="stage_a")
    outcome = funnel.advance(ticket, policy="full")
    events = [producer_settlement(response).event for response in actual_responses]
    recorded = sum((event.amount for event in events), Decimal(0))
    estimated = [event for event in events if event.cost_origin == "estimated"]
    assert len(estimated) == 1 and estimated[0].amount > 0
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == recorded
    assert (
        len(snapshot.spend_receipts)
        == len(events)
        == sum(gateway.transport.calls for gateway in gateways)
    )
    assert outcome.compute_actual_usd == float(recorded)
    assert outcome.provider_spend_usd == (Decimal(1) if profile == "mixed" else None)
    assert outcome.stage_results[4].compute_actual_usd == 0
    assert outcome.stage_results[4].provider_spend_usd == (
        Decimal(0) if profile == "mixed" else None
    )
    assert outcome.stage_results[4].feedback["resource_local_recorded_spend_usd"] == "0"
    assert outcome.compute_cost_source == ("mixed" if profile == "mixed" else "estimated")
    assert outcome.final_action == "reject"
    assert "resource_provider_event_replayed" in {
        card.failure_type for card in outcome.stage_results[4].failure_cards
    }
