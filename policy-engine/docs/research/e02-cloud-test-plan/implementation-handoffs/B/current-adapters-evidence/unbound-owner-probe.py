"""Read-only actual raw provider cannot appoint itself as a cache owner."""
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from polisyos.core.llm import settlement
from polisyos.core.llm.traced_client import TracedLLMClient

spec=importlib.util.spec_from_file_location("e02_unbound_owner_fixture",Path.cwd()/"tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py")
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
class ProviderResponse(fixture.GatewayLLMResponse):
    pass
class RawProvider(fixture._Gateway):
    async def generate(self,**kwargs):
        self.calls+=1
        response=ProviderResponse(content="actual raw physical response",model="e02",provider="synthetic",request_id="raw-paid",usage=fixture.GatewayUsage(prompt_tokens=7,completion_tokens=3,cost_usd=0.02))
        response._polisyos_cache_reuse_provenance=settlement._CacheReuseOwner().issue("self-appointed-key")
        return response
async def main():
    print(json.dumps({"target_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"driver_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"module_file":settlement.__file__,"module_sha256":hashlib.sha256(Path(settlement.__file__).read_bytes()).hexdigest(),"fixture_sha256":hashlib.sha256(Path(spec.origin).read_bytes()).hexdigest()}),flush=True)
    with tempfile.TemporaryDirectory(prefix="e02-unbound-owner-") as path:
        raw=RawProvider();events=[]
        traced=TracedLLMClient(raw,model_name="e02",tracer=fixture._Tracer(),metrics=SimpleNamespace(record_llm_call=lambda **kwargs:None),required_accounting=events.append)
        _,unused_cache,enforcer,middleware,_=fixture._durable_stack(Path(path),gateway=raw,client=traced)
        result=await enforcer.generate(user="raw physical call",temperature=0.0,_prompt_tokens_estimate=1)
        recorded=fixture.producer_settlement(result)
        value={"physical_provider_calls":raw.calls,"actual_cache_clients_in_provider_route":0,"spent":str(middleware.budget_state.spent.get("run",Decimal(0))),"event_kind":recorded.event.kind,"ack_status":recorded.ack.status,"receipt_count":len(recorded.ack.receipts),"provider_metrics_events":sum(bool(e["provider_call"]) for e in events)}
        print(json.dumps(value),flush=True)
        assert value["spent"]=="0.02" and value["event_kind"]=="provider" and value["receipt_count"]==1, "a self-appointed typed owner is not an admitted cache emitter"
asyncio.run(main())
