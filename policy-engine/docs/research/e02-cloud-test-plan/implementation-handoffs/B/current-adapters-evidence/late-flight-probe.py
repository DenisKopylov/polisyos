"""Read-only real producer timeout/publication discriminator."""
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

from polisyos.scientist.orchestration.llm import prompt_cache

HERE = Path(__file__).resolve()
ROOT = Path.cwd()
spec = importlib.util.spec_from_file_location("e02_llm_fixture", ROOT / "tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

class SuppressingGateway(fixture._Gateway):
    def __init__(self):
        super().__init__()
        self.cancel_observed = asyncio.Event()
    async def generate(self, **kwargs):
        self.calls += 1
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancel_observed.set()
            await self.release.wait()
        return fixture.GatewayLLMResponse(content="late physical response", model="e02", provider="synthetic", request_id="late-request", usage=fixture.GatewayUsage(prompt_tokens=7, completion_tokens=3, cost_usd=0.02))

async def main():
    print(json.dumps({"target_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "driver_sha256": hashlib.sha256(HERE.read_bytes()).hexdigest(), "pool_of_interest": {"file": prompt_cache.__file__, "sha256": hashlib.sha256(Path(prompt_cache.__file__).read_bytes()).hexdigest()}, "fixture_sha256": hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()}), flush=True)
    with tempfile.TemporaryDirectory(prefix="e02-late-flight-") as path:
        gateway = SuppressingGateway()
        _, cache, enforcer, middleware, events = fixture._durable_stack(Path(path), gateway=gateway)
        cache._inflight_timeout_s = 0.03
        caller = asyncio.create_task(enforcer.generate(user="shared producer deadline", temperature=0.0, _prompt_tokens_estimate=1))
        await asyncio.wait_for(gateway.cancel_observed.wait(), 1.0)
        gateway.release.set()
        try:
            result = await caller
            outcome = "returned"
            returned = result.content
        except Exception as error:
            outcome = type(error).__name__
            returned = None
        record = {"outcome": outcome, "returned": returned, "provider_calls": gateway.calls, "cache_size": cache._cache.size, "spent": str(middleware.budget_state.spent["run"]), "reserved": str(middleware.budget_state.reserved["run"]), "physical_cancellation_observed": gateway.cancel_observed.is_set(), "provider_events": len([event for event in events if event["provider_call"]]), "flights": len(cache._inflight)}
        print(json.dumps(record), flush=True)
        assert record["spent"] == "0.02" and record["provider_events"] == 1, "observed actual response still requires accounting"
        assert outcome == "TimeoutError" and record["cache_size"] == 0, "expired physical response must not publish or return as admitted success"

asyncio.run(main())
