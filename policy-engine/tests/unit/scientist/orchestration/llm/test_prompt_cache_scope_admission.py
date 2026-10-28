"""Actual CAS-backed cache scope and logical-flight controls.

The fixture owner below is a local operational input, not deployment authority.
This module supplements the maintained cache consumers; it never replaces their
permission, producer settlement, cancellation or publication assertions.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMResponse, GatewayUsage
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReusePrincipal,
    CacheReuseRequest,
    CachingLLMClient,
    InMemoryPromptCache,
    prepare_cached_request,
)


@contextmanager
def _principal(tenant: str = "tenant-a"):
    token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id=tenant, cell_id="cell-a", spiffe_id="spiffe://fixture/cache-owner"
        )
    )
    try:
        with tenant_scope(None, tenant_id=tenant, cell_id="cell-a"):
            yield
    finally:
        reset_current_access_scope(token)


class _LocalOwner:
    """Current fixture grant plus independent reads of the exact CAS references."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.epoch = "grant-1"
        self.snapshots: dict[tuple[str, str], tuple[Any, Any, bytes]] = {}
        self.decisions: list[CacheReuseRequest] = []

    def snapshot(self, tenant: str, version: str) -> dict[str, Any]:
        key = (tenant, version)
        if key not in self.snapshots:
            content = f"immutable {version} evidence".encode()
            store = FileSystemCAS(self.root / tenant, ownership_enforced=True)
            ref = store.put_bytes(
                content, PutOptions(kind="cache.scope.fixture", media_type="text/plain")
            )
            self.snapshots[key] = store, ref, content
        _, ref, content = self.snapshots[key]
        return {
            "tenant": tenant,
            "scope": "scope-a",
            "cache_reuse": {
                "tenant": tenant,
                "scope": "scope-a",
                "purpose": "decision-a",
                "snapshot": {
                    "ref": str(ref.artifact_id),
                    "version": version,
                    "immutable": True,
                    "content": content,
                    "content_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
                },
            },
        }

    def authorize_reuse(self, request: CacheReuseRequest) -> CacheReuseDecision | None:
        self.decisions.append(request)
        if (
            request.actor_id != "spiffe://fixture/cache-owner"
            or request.scope not in {"scope-a", "scope-b"}
            or request.purpose != "llm_snapshot_reuse"
            or len(request.evidence) != 1
        ):
            return None
        evidence = request.evidence[0]
        selected = self.snapshots.get((request.tenant, evidence.version))
        if selected is None:
            return None
        store, ref, content = selected
        actual = store.get_bytes(ref)
        if (
            evidence.ref != str(ref.artifact_id)
            or actual != content
            or evidence.content != actual
            or evidence.content_hash != "sha256:" + hashlib.sha256(actual).hexdigest()
        ):
            return None
        return CacheReuseDecision(
            issuer="local-owner-fixture",
            epoch=self.epoch,
            actor_id=request.actor_id,
            tenant=request.tenant,
            scope=request.scope,
            purpose=request.purpose,
            model=request.model,
            parameters_digest=request.parameters_digest,
            evidence=request.evidence,
        )


class _PhysicalProvider:
    """A gated real file effect, with an explicit known synthetic price."""

    def __init__(self, path: Path, *, terminal: str = "success") -> None:
        self.path = path
        self.terminal = terminal
        self.calls = 0
        self.first_entered = asyncio.Event()
        self.second_entered = asyncio.Event()
        self.release = asyncio.Event()

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, **kwargs: Any) -> GatewayLLMResponse:
        self.calls += 1
        operation = self.calls
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"operation": operation, "user": kwargs.get("user")}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.first_entered.set()
        if operation == 2:
            self.second_entered.set()
        await self.release.wait()
        if self.terminal == "error" and operation == 1:
            raise RuntimeError("actual fixture provider error")
        return GatewayLLMResponse(
            content=f"physical-{operation}",
            model="fixture",
            provider="local-filesystem-fixture",
            request_id=f"physical-{operation}",
            usage=GatewayUsage(cost_usd=0.02),
        )

    def effects(self) -> list[dict[str, Any]]:
        return [json.loads(line) for line in self.path.read_text().splitlines()]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "difference",
    ["seed", "instruction", "snapshot", "tenant", "scope", "purpose", "epoch", "independent"],
)
async def test_distinct_admissible_requests_do_not_join_actual_flight(
    tmp_path: Path, difference: str
) -> None:
    owner = _LocalOwner(tmp_path / "cas")
    provider = _PhysicalProvider(tmp_path / "provider.jsonl")
    cache = InMemoryPromptCache()
    client = CachingLLMClient(provider, cache=cache, model="fixture", reuse_authorizer=owner)
    tasks: list[asyncio.Task[Any]] = []
    try:
        with _principal():
            first_metadata = owner.snapshot("tenant-a", "v1")
            tasks.append(
                asyncio.create_task(
                    client.generate(
                        user="https://fixture.invalid/report",
                        metadata=first_metadata,
                        temperature=0.0,
                        seed=1,
                    )
                )
            )
        await asyncio.wait_for(provider.first_entered.wait(), timeout=2.0)
        tenant = "tenant-b" if difference == "tenant" else "tenant-a"
        with _principal(tenant):
            metadata = owner.snapshot(tenant, "v2" if difference == "snapshot" else "v1")
            request: dict[str, Any] = {
                "user": "https://fixture.invalid/report",
                "metadata": metadata,
                "temperature": 0.0,
                "seed": 2 if difference == "seed" else 1,
            }
            if difference == "instruction":
                request["system"] = "a different scientific instruction"
            elif difference == "scope":
                metadata["scope"] = metadata["cache_reuse"]["scope"] = "scope-b"
            elif difference == "purpose":
                metadata["cache_reuse"]["purpose"] = "decision-b"
            elif difference == "epoch":
                owner.epoch = "grant-2"
            elif difference == "independent":
                metadata["cacheable"] = False
            tasks.append(asyncio.create_task(client.generate(**request)))
        # Observe the second physical entry while the first is still gated.
        await asyncio.wait_for(provider.second_entered.wait(), timeout=2.0)
        assert provider.calls == len(provider.effects()) == 2
    finally:
        provider.release.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(result, GatewayLLMResponse) for result in results)
    assert provider.calls == len(provider.effects()) == 2
    assert client._inflight == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("terminal", ["error", "deadline"])
async def test_cas_admitted_flight_cleanup_allows_fresh_physical_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: str
) -> None:
    owner = _LocalOwner(tmp_path / "cas")
    provider = _PhysicalProvider(tmp_path / "provider.jsonl", terminal=terminal)
    client = CachingLLMClient(
        provider,
        cache=InMemoryPromptCache(),
        model="fixture",
        reuse_authorizer=owner,
        inflight_timeout_s=0.2 if terminal == "deadline" else None,
    )
    actual_shield = asyncio.shield
    shielded: list[asyncio.Task[Any]] = []
    all_waiting = asyncio.Event()

    def observe_real_wait(future: Any) -> Any:
        protected = actual_shield(future)
        if any(flight.task is future for flight in client._inflight.values()):
            shielded.append(future)
            if len(shielded) == 4:
                all_waiting.set()
        return protected

    monkeypatch.setattr(asyncio, "shield", observe_real_wait)
    with _principal():
        metadata = owner.snapshot("tenant-a", "v1")
        tasks = [
            asyncio.create_task(
                client.generate(
                    user="https://fixture.invalid/report", metadata=metadata, temperature=0.0
                )
            )
            for _ in range(4)
        ]
        try:
            await asyncio.wait_for(all_waiting.wait(), timeout=2.0)
            await asyncio.wait_for(provider.first_entered.wait(), timeout=2.0)
            assert len(set(shielded)) == 1
            assert provider.calls == len(provider.effects()) == 1
            tasks[1].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[1]
            assert not shielded[0].cancelled()
            if terminal == "error":
                provider.release.set()
            results = await asyncio.gather(tasks[0], tasks[2], tasks[3], return_exceptions=True)
            expected = RuntimeError if terminal == "error" else TimeoutError
            assert all(isinstance(result, expected) for result in results)
            assert client._inflight == {} and client._cache.size == 0
        finally:
            provider.release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
        response = await client.generate(
            user="https://fixture.invalid/report", metadata=metadata, temperature=0.0
        )
        assert response.content == "physical-2"
        assert provider.calls == len(provider.effects()) == 2
        assert client._inflight == {} and client._cache.size == 1


@pytest.mark.asyncio
async def test_factory_without_snapshot_authorizer_preserves_ordinary_provider_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import nullcontext

    class Span:
        def set_attribute(self, *args: Any) -> None:
            pass

        def set_status(self, *args: Any) -> None:
            pass

        def record_exception(self, *args: Any) -> None:
            pass

    class Tracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            return nullcontext(Span())

    owner = _LocalOwner(tmp_path / "cas")
    provider = _PhysicalProvider(tmp_path / "provider.jsonl")
    provider.release.set()
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.GatewayLLMClient",
        lambda **kwargs: provider,
    )
    events: list[dict[str, Any]] = []
    client = create_traced_gateway_client(
        model_name="fixture",
        config=GatewayLLMConfig(
            base_url="https://unused-fixture.invalid",
            api_key="fixture",
            enable_prompt_sanitizer=False,
        ),
        call_observer=events.append,
        tracer=Tracer(),
        metrics=SimpleNamespace(record_llm_call=lambda **kwargs: None),
    )
    assert client is not None
    with _principal():
        metadata = owner.snapshot("tenant-a", "v1")
        for _ in range(2):
            result = await client.generate(
                user="https://fixture.invalid/report", metadata=metadata, temperature=0.0
            )
            assert result.content.startswith("physical-")
    assert provider.calls == len(provider.effects()) == 2
    assert len(events) == 2 and all(event["provider_call"] for event in events)


@pytest.mark.asyncio
async def test_prebound_snapshot_compares_raw_invocation_before_current_owner_authorization(
    tmp_path: Path,
) -> None:
    owner = _LocalOwner(tmp_path / "cas")
    provider = _PhysicalProvider(tmp_path / "provider.jsonl")
    provider.release.set()
    cache = InMemoryPromptCache()
    principal = CacheReusePrincipal(
        actor_id="spiffe://fixture/cache-owner", tenant="tenant-a", scope="scope-a"
    )

    def bound(values: dict[str, Any]) -> Any:
        plan = prepare_cached_request(provider, model="fixture", kwargs=values)
        return CachingLLMClient(
            provider,
            cache=cache,
            model="fixture",
            prepared_request=plan,
            reuse_authorizer=owner,
            reuse_principal=principal,
        )

    with _principal():
        valid = {
            "user": "Use https://fixture.invalid/report with uncertainty_notes",
            "temperature": 0.0,
            "metadata": owner.snapshot("tenant-a", "v1"),
        }
        first = await bound(valid).generate(**valid)
        assert provider.calls == 1 and len(owner.decisions) == 1
        assert owner.decisions[0].evidence[0].content == owner.snapshots[("tenant-a", "v1")][2]

        second = bound(valid)
        invalid = {**valid, "metadata": owner.snapshot("tenant-a", "v1")}
        invalid["metadata"]["cache_reuse"]["snapshot"]["content"] = b"changed raw evidence"
        # The declared digest and every adjacent permission/provenance value stay A.
        assert (
            invalid["metadata"]["cache_reuse"]["snapshot"]["content_hash"]
            == (valid["metadata"]["cache_reuse"]["snapshot"]["content_hash"])
        )
        with pytest.raises(ValueError, match="call_mismatch"):
            await second.generate(**invalid)
        assert provider.calls == 1 and len(owner.decisions) == 1
        hit = await second.generate(**valid)
        assert first.content == hit.content and hit.raw["_polisyos_cache"]["status"] == "hit"
        assert provider.calls == 1 and len(owner.decisions) == 2

        reverse = bound(invalid)
        with pytest.raises(ValueError, match="call_mismatch"):
            await reverse.generate(**valid)
        assert provider.calls == 1 and len(owner.decisions) == 2
        invalid_result = await reverse.generate(**invalid)
        assert invalid_result.content == "physical-2"
        assert provider.calls == 2 and len(owner.decisions) == 2

        changed_hash = {**valid, "metadata": owner.snapshot("tenant-a", "v1")}
        changed_hash["metadata"]["cache_reuse"]["snapshot"]["content"] = b"changed raw evidence"
        changed_hash["metadata"]["cache_reuse"]["snapshot"]["content_hash"] = (
            "sha256:" + hashlib.sha256(b"changed raw evidence").hexdigest()
        )
        with pytest.raises(ValueError, match="call_mismatch"):
            await bound(valid).generate(**changed_hash)
        assert provider.calls == 2 and len(owner.decisions) == 2
        assert len(provider.effects()) == 2
