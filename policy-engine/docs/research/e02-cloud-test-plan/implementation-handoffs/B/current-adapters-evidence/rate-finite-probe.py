"""Read-only finite rate quantity admission and actual provider discriminator."""
import asyncio
import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from polisyos.fabric.connectors.resilience import rate_limiter as module

async def main():
    print(json.dumps({"target_sha":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"driver_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"module_file":module.__file__,"module_sha256":hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}),flush=True)
    accepted=[]
    for field in ("rate_limit_rps","burst_size","min_rate_rps","max_rate_rps"):
        for value in (float("nan"),float("inf")):
            try:
                module.RateLimiterConfig(**{"rate_limit_rps":1.0,field:value})
            except ValueError:
                continue
            accepted.append([field,str(value)])
    provider_calls=[]
    @module.with_rate_limit(float("inf"))
    async def actual_provider(handle):
        provider_calls.append(handle.connector_id)
    try:
        for _ in range(3):
            await asyncio.wait_for(actual_provider(SimpleNamespace(connector_id="non-finite")),0.2)
        provider_outcome="returned"
    except Exception as error:
        provider_outcome=type(error).__name__
    print(json.dumps({"accepted_nonfinite_config":accepted,"provider_outcome":provider_outcome,"physical_provider_calls":provider_calls}),flush=True)
    assert not accepted and provider_calls==[], "nonfinite service quantity must refuse before real provider admission"

asyncio.run(main())
