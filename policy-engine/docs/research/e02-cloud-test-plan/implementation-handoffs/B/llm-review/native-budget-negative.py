"""Read-only received-usage/budget cancellation witness against pinned adapters."""
import asyncio
import importlib.util
import json
from decimal import Decimal
from pathlib import Path

from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.llm.budget_enforcer import LLMBudgetEnforcer
from polisyos.scientist.orchestration.llm.prompt_cache import CachingLLMClient, InMemoryPromptCache

SOURCE = "d0eb247a2dff81f0a3ca48ea844c9ce3b8559b83"
FIXTURE = Path("tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py")
spec = importlib.util.spec_from_file_location("published_llm_fixture", FIXTURE)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


async def main():
    provider = fixture._Provider(gated=True)
    metrics = fixture._Metrics()
    events = []
    cached = CachingLLMClient(provider, cache=InMemoryPromptCache(), model="gpt-4o")
    traced = TracedLLMClient(
        cached, model_name="gpt-4o", metrics=metrics,
        run_id="independent-run", required_accounting=events.append,
    )
    budget = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
    client = LLMBudgetEnforcer(
        client=traced, budget_state=budget, budget_keys=["run"],
        model_name="gpt-4o", run_id="independent-run",
    )
    inputs = dict(user="hello", max_tokens=2, _prompt_tokens_estimate=3, _run_id="independent-run")
    owner = asyncio.create_task(client.generate(**inputs))
    await provider.started.wait()
    follower = asyncio.create_task(client.generate(**inputs))
    await asyncio.sleep(0)
    before = str(budget.reserved.get("run", Decimal(0)))
    owner.cancel()
    try:
        await owner
    except asyncio.CancelledError:
        pass
    after = str(budget.reserved.get("run", Decimal(0)))
    provider.proceed.set()
    response = await follower
    result = dict(
        source_sha=SOURCE, fixture=str(FIXTURE), provider_calls=provider.calls,
        received_provider_usage_cost_usd=response.usage.cost_usd,
        budget_spent_run=str(budget.spent.get("run", Decimal(0))),
        budget_reserved_before_cancel=before, budget_reserved_after_cancel=after,
        budget_reserved_final=str(budget.reserved.get("run", Decimal(0))),
        mandatory_accounting_events=events,
        optional_trace_cost_total=sum(event.get("cost_usd") or 0 for event in metrics.events),
        inflight_count_final=len(cached._inflight),
    )
    assert provider.calls == 1 and response.usage.cost_usd == 0.02
    assert budget.spent.get("run", Decimal(0)) == 0
    assert len(events) == 1 and events[0]["provider_call"] is False
    print(json.dumps(result, indent=2))


asyncio.run(main())
