"""Exercise the real gateway factory, scoped cache, and durable settlement together."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.llm.cache_settlement import session_for_cache_client
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReuseRequest,
    CachingLLMClient,
)


@contextmanager
def _principal(tenant: str) -> Iterator[None]:
    token = set_current_access_scope(
        AccessScope.for_service(
            tenant_id=tenant,
            cell_id="cell-a",
            spiffe_id="spiffe://fixture/factory-cache-owner",
        )
    )
    try:
        with tenant_scope(None, tenant_id=tenant, cell_id="cell-a"):
            yield
    finally:
        reset_current_access_scope(token)


@contextmanager
def _local_gateway() -> Iterator[tuple[str, list[dict[str, Any]], threading.Lock]]:
    """Stub only the external HTTP provider while retaining the real client stack."""
    requests: list[dict[str, Any]] = []
    requests_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != "/v1/chat/completions":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            with requests_lock:
                requests.append(payload)
                request_number = len(requests)
            body = json.dumps(
                {
                    "id": f"fixture-completion-{request_number}",
                    "object": "chat.completion",
                    "model": "fixture-model",
                    "provider": "local-http-fixture",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "fixture answer"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 3,
                        "total_tokens": 5,
                        "cost_usd": 0.02,
                    },
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name="fixture-gateway", daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/v1", requests, requests_lock
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


class _SnapshotOwner:
    """Local currentness owner that independently reads each tenant's CAS bytes."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.active_tenants = {"tenant-a", "tenant-b"}
        self.epochs = {"tenant-a": "grant-a-1", "tenant-b": "grant-b-1"}
        self.snapshots: dict[tuple[str, str], tuple[FileSystemCAS, Any, bytes]] = {}
        self.requests: list[CacheReuseRequest] = []

    def metadata(self, tenant: str) -> dict[str, Any]:
        version = "snapshot-1"
        key = (tenant, version)
        if key not in self.snapshots:
            content = f"immutable policy inputs for {tenant}".encode()
            store = FileSystemCAS(self.root / tenant, ownership_enforced=True)
            ref = store.put_bytes(
                content,
                PutOptions(kind="factory.cache.scope.fixture", media_type="text/plain"),
            )
            self.snapshots[key] = store, ref, content
        _store, ref, content = self.snapshots[key]
        return {
            "tenant": tenant,
            "scope": "scope-a",
            "cache_reuse": {
                "tenant": tenant,
                "scope": "scope-a",
                "purpose": "policy-recommendation",
                "permission": {"tenant": tenant, "scope": "scope-a"},
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
        self.requests.append(request)
        if (
            request.tenant not in self.active_tenants
            or request.actor_id != "spiffe://fixture/factory-cache-owner"
            or request.scope != "scope-a"
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
            or evidence.immutable is not True
            or evidence.content != actual
            or evidence.content_hash != "sha256:" + hashlib.sha256(actual).hexdigest()
        ):
            return None
        return CacheReuseDecision(
            issuer="fixture-owner",
            epoch=self.epochs[request.tenant],
            actor_id=request.actor_id,
            tenant=request.tenant,
            scope=request.scope,
            purpose=request.purpose,
            model=request.model,
            parameters_digest=request.parameters_digest,
            evidence=request.evidence,
        )


class _Span:
    def set_attribute(self, _name: str, _value: object) -> None:
        return None

    def set_status(self, _status: object) -> None:
        return None

    def record_exception(self, _error: BaseException) -> None:
        return None


class _Tracer:
    @contextmanager
    def start_as_current_span(self, *_args: object, **_kwargs: object):
        yield _Span()


class _Metrics:
    def record_llm_call(self, **_kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_factory_cache_reuse_settlement_and_scope_currentness_composition(
    tmp_path: Path,
) -> None:
    """Reuse only current, tenant-bound entries and settle every logical call durably."""
    with _local_gateway() as (base_url, provider_requests, requests_lock):
        ledger_path = tmp_path / "producer-ledger.json"
        middleware = BudgetMiddleware(
            BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))}),
            ledger=FileBudgetLedger(ledger_path),
        )
        owner = _SnapshotOwner(tmp_path / "snapshot-cas")
        observations: list[dict[str, Any]] = []
        client = create_traced_gateway_client(
            model_name="fixture-model",
            provider_hint="local-http-fixture",
            run_id="factory-cache-composition-run",
            config=GatewayLLMConfig(
                base_url=base_url,
                api_key="sk-fixture-factory-cache-composition-key",
                timeout_s=2.0,
                max_retries=0,
                cache_ttl_s=60.0,
                cache_maxsize=8,
                enable_prompt_sanitizer=False,
            ),
            cache_reuse_authorizer=owner,
            producer_settlement_store=middleware,
            producer_budget_key="run",
            call_observer=observations.append,
            tracer=_Tracer(),
            metrics=_Metrics(),
        )
        assert client is not None
        cache_client = client._client
        assert type(cache_client) is CachingLLMClient
        cache_session = session_for_cache_client(cache_client)
        assert cache_session is not None and cache_session.owns(cache_client)
        assert client._cache_settlement_session is cache_session
        gateway = client.unwrap()
        assert type(gateway) is GatewayLLMClient

        async def generate_for(tenant: str) -> None:
            with _principal(tenant):
                await client.generate(
                    user="Compare the same policy option against the admitted snapshot.",
                    temperature=0.0,
                    metadata=owner.metadata(tenant),
                )

        try:
            await generate_for("tenant-a")
            with requests_lock:
                assert len(provider_requests) == 1
            await generate_for("tenant-a")
            with requests_lock:
                assert len(provider_requests) == 1

            owner.active_tenants.remove("tenant-a")
            owner.epochs["tenant-a"] = "grant-a-revoked"
            await generate_for("tenant-a")
            with requests_lock:
                assert len(provider_requests) == 2

            await generate_for("tenant-b")
            with requests_lock:
                assert len(provider_requests) == 3
            await generate_for("tenant-b")
            with requests_lock:
                assert len(provider_requests) == 3
        finally:
            await gateway.aclose()

    assert [request.tenant for request in owner.requests] == [
        "tenant-a",
        "tenant-a",
        "tenant-a",
        "tenant-b",
        "tenant-b",
    ]
    assert [event["provider_call"] for event in observations] == [True, False, True, True, False]
    assert [event["cache_hit"] for event in observations] == [False, True, False, False, True]
    assert all(event["settlement_status"] == "committed" for event in observations)

    snapshot = FileBudgetLedger(ledger_path).snapshot()
    records = tuple(snapshot.producer_settlements.values())
    assert len(records) == 5
    provider_records = tuple(row for row in records if row.cost_origin == "reported")
    reuse_records = tuple(row for row in records if row.cost_origin == "reuse")
    assert len(provider_records) == 3
    assert len(reuse_records) == 2
    assert all(row.status == "committed" for row in records)
    assert all(row.amount == Decimal("0.02") for row in provider_records)
    assert all(row.amount == Decimal(0) for row in reuse_records)
    assert all(
        row.origin_event_id in {item.event_id for item in provider_records} for row in reuse_records
    )
    assert snapshot.state.spent["run"] == Decimal("0.06")
    assert len({row.event_id for row in records}) == len(records)
