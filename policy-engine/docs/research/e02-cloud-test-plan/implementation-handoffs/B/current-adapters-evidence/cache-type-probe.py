"""Read-only typed provider consumer: names cannot grant billing provenance."""
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from polisyos.core.llm import response as module

spec=importlib.util.spec_from_file_location("e02_llm_type_fixture",Path.cwd()/"tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py")
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
FakeReuse = type("_CacheReuseGatewayResponse", (fixture.GatewayLLMResponse,), {"__module__":"provider_claim.prompt_cache","_polisyos_cache_hit":True,"_polisyos_reuse_event_id":"claimed-reuse","_polisyos_cache_key":"claimed-key"})
class Provider(fixture._Gateway):
    async def generate(self,**kwargs):
        self.calls+=1
        return FakeReuse(content="actual paid typed provider response",model="e02",provider="synthetic",request_id="physical-paid",usage=fixture.GatewayUsage(prompt_tokens=7,completion_tokens=3,cost_usd=0.02))
async def main():
    print(json.dumps({"target_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"driver_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"module_file":module.__file__,"module_sha256":hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),"fixture_sha256":hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()}),flush=True)
    with tempfile.TemporaryDirectory(prefix="e02-billing-type-") as path:
        provider=Provider()
        _,cache,enforcer,middleware,events=fixture._durable_stack(Path(path),gateway=provider)
        result=await enforcer.generate(user="physical paid provider",temperature=0.0,_prompt_tokens_estimate=1)
        settled=fixture.producer_settlement(result)
        value={"physical_provider_calls":provider.calls,"spent":str(middleware.budget_state.spent.get("run",Decimal(0))),"cache_size":cache._cache.size,"event_kind":settled.event.kind,"ack_status":settled.ack.status,"ack_durability":settled.ack.durability,"receipt_count":len(settled.ack.receipts),"provider_metrics_events":sum(bool(event["provider_call"]) for event in events)}
        print(json.dumps(value),flush=True)
        assert value["spent"]=="0.02" and value["event_kind"]=="provider" and value["receipt_count"]==1, "a type name supplied by a paid provider is not cache-owned billing authority"
asyncio.run(main())
