"""Execute immutable source with one explicit in-memory property removal overlay."""
from __future__ import annotations
import hashlib
import inspect
import json
import subprocess
import sys
import textwrap
from contextlib import contextmanager
from pathlib import Path
import pytest

mode = sys.argv[1]
from polisyos.fabric.connectors import pool
from polisyos.fabric.connectors.resilience import _bounded_registry as registry
from polisyos.fabric.connectors.resilience import rate_limiter
from polisyos.scientist.orchestration.engine.runner import serialization as wire
from polisyos.scientist.orchestration.llm import prompt_cache
from polisyos.core.llm import traced_client, settlement, response

modules = (pool, registry, rate_limiter, wire, prompt_cache, traced_client, settlement, response)
origins = {m.__name__: {"path": m.__file__, "sha256": hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()} for m in modules}
print(json.dumps({"target_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(), "mode": mode, "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "module_origins": origins, "python": sys.version}, sort_keys=True), flush=True)

selectors = {
 "issuer": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "receiver_binds or unconfigured_receiver"],
 "physical": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "actual_physical_completion"],
 "pool": ["tests/unit/fabric/connectors/test_pool_e02.py", "-k", "whole_acquisition_budget or cancelled_caller"],
 "registry": ["tests/unit/fabric/connectors/test_resilience_e02.py", "-k", "neutral_refilled or available_protected"],
 "wire": ["tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py", "-k", "rejects_untyped"],
 "settlement": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "actual_cache_publication"],
 "permission": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "metadata_permission"],
 "deadline": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "expired_suppressed or deadline_covers"],
 "emission": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "cached_emission"],
 "rate": ["tests/unit/fabric/connectors/test_resilience_e02.py", "-k", "nonfinite or each_rate or fractional_service or receiver_binds or unconfigured_receiver or actual_physical_completion"],
 "mandatory": ["tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "-k", "unknown_mandatory"],
}

def replace_method(owner, name, before, after):
    original = getattr(owner, name)
    source = textwrap.dedent(inspect.getsource(original))
    assert source.count(before) == 1, (name, "overlay must bind exactly one immutable source site")
    namespace = {}
    exec(compile(source.replace(before, after), f"<e02-{mode}-in-memory-overlay>", "exec"), original.__globals__, namespace)
    setattr(owner, name, namespace[name])

if mode == "issuer":
    settlement._cache_reuse_provenance = lambda value: getattr(value, "_polisyos_cache_reuse_provenance", None)
elif mode == "physical":
    replace_method(prompt_cache.CachingLLMClient, "_produce", "completion.complete(response, True)", "completion.complete(response, False)")
elif mode == "pool":
    pool.ConnectionPool._require_acquire_budget = lambda self, deadline, cancellation_count: None
elif mode == "registry":
    @contextmanager
    def unowned_lookup(self, key, factory):
        yield self.get_or_create(key, factory)
    registry.BoundedResourceRegistry.lease = unowned_lookup
elif mode == "wire":
    wire._typed_state_payload = lambda payload: None
elif mode == "settlement":
    replace_method(prompt_cache.CachingLLMClient, "_produce", "completion = _current_producer_completion()", "completion = None")
elif mode == "permission":
    replace_method(prompt_cache.CachingLLMClient, "generate", '''if isinstance(metadata, Mapping) and "cache_reuse" in metadata and admission is None:
        reason = reason or "permission_owner_unavailable_or_denied"''', "# owner admission removed; declarations and typed decision markers retained")
elif mode == "mandatory":
    traced_client.TracedLLMClient._require_accounting_ready = lambda self: None
elif mode == "deadline":
    prompt_cache.CachingLLMClient._require_producer_budget = staticmethod(lambda deadline: None)
elif mode == "emission":
    prompt_cache.CachingLLMClient._require_current_reuse = lambda self, admission: None
elif mode == "rate":
    rate_limiter._require_positive_finite = lambda value, name: None
elif mode != "control":
    raise ValueError(mode)

selected = selectors.get(mode)
if selected is None:
    selected = ["tests/unit/fabric/connectors/test_pool_e02.py", "tests/unit/fabric/connectors/test_resilience_e02.py", "tests/unit/scientist/orchestration/llm/test_prompt_cache_e02.py", "tests/unit/scientist/orchestration/engine/runner/test_serialization_e02.py", "-k", "whole_acquisition_budget or cancelled_caller or neutral_refilled or available_protected or rejects_untyped or actual_cache_publication or metadata_permission or unknown_mandatory or expired_suppressed or deadline_covers or cached_emission or nonfinite or each_rate or fractional_service or receiver_binds or unconfigured_receiver or actual_physical_completion"]
code = pytest.main([*selected, "-o", "addopts=", "-q", "--tb=short"])
after = {m.__name__: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in modules}
assert all(after[name] == identity["sha256"] for name, identity in origins.items())
print(json.dumps({"mode": mode, "pytest_exit": int(code), "file_bytes_unchanged": True}, sort_keys=True), flush=True)
raise SystemExit(int(code))
