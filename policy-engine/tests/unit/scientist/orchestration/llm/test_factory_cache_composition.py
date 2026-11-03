"""Exercise the real gateway factory, scoped cache, and durable settlement together."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.llm.cache_settlement import (
    CacheFlightRegistration,
    CacheSettlementSession,
    session_for_cache_client,
)
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerProducerRunBinding,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import (
    GatewayLLMConfig,
    _gateway_cache_reuse_scope,
    create_traced_gateway_client,
)
from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReusePrincipal,
    CacheReuseRequest,
    CachingLLMClient,
    InMemoryPromptCache,
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
def _local_gateway(
    *,
    request_entered: threading.Event | None = None,
    response_release: threading.Event | None = None,
    fail_request_numbers: frozenset[int] = frozenset(),
) -> Iterator[tuple[str, list[dict[str, Any]], threading.Lock]]:
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
            if request_entered is not None:
                request_entered.set()
            if response_release is not None and not response_release.wait(timeout=5.0):
                self.send_error(504)
                return
            if request_number in fail_request_numbers:
                body = b"fixture provider failure"
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
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


@pytest.mark.asyncio
async def test_factory_cache_scoped_singleflight_success_settles_each_waiter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Share one current CAS-authorized provider success and settle each logical caller."""
    request_entered = threading.Event()
    response_release = threading.Event()
    with _local_gateway(
        request_entered=request_entered,
        response_release=response_release,
    ) as (base_url, provider_requests, requests_lock):
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
            run_id="factory-cache-concurrent-success-run",
            config=GatewayLLMConfig(
                base_url=base_url,
                api_key="sk-fixture-factory-cache-concurrent-success-key",
                timeout_s=4.0,
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
        gateway = client.unwrap()

        actual_join = CacheSettlementSession.join
        joined_attempts: list[str] = []
        joined_cache_keys: list[str] = []
        all_waiting = asyncio.Event()

        def observe_flight_join(
            session: CacheSettlementSession,
            registration: CacheFlightRegistration,
            scope_key: tuple[str, ...],
            request_digest: str,
            cache_key: str,
            attempt_id: str,
        ) -> None:
            # Observe actual owner-admitted receivers, independent of whether
            # a waiter shields a producer task or a per-loop shared future.
            actual_join(session, registration, scope_key, request_digest, cache_key, attempt_id)
            if session is cache_session:
                joined_attempts.append(attempt_id)
                joined_cache_keys.append(cache_key)
                if len(joined_attempts) == 3:
                    all_waiting.set()

        monkeypatch.setattr(CacheSettlementSession, "join", observe_flight_join)

        async def generate_for_current_tenant() -> Any:
            with _principal("tenant-a"):
                return await client.generate(
                    user="Compare the same policy option against the admitted snapshot.",
                    temperature=0.0,
                    metadata=owner.metadata("tenant-a"),
                )

        tasks = [asyncio.create_task(generate_for_current_tenant()) for _ in range(4)]
        try:
            assert await asyncio.wait_for(asyncio.to_thread(request_entered.wait, 3.0), timeout=4.0)
            await asyncio.wait_for(all_waiting.wait(), timeout=3.0)
            assert len(set(joined_attempts)) == 3
            assert len(set(joined_cache_keys)) == 1
            assert len(cache_client._inflight) == 1
            with requests_lock:
                assert len(provider_requests) == 1
            assert len(owner.requests) == 4
            assert all(request == owner.requests[0] for request in owner.requests)

            response_release.set()
            concurrent_results = await asyncio.gather(*tasks)
            assert all(result.content == "fixture answer" for result in concurrent_results)
            assert len({id(result) for result in concurrent_results}) == 4
            assert cache_client._inflight == {}

            # A later request still resolves the current owner before using the cached bytes.
            sequential_result = await generate_for_current_tenant()
            assert sequential_result.content == "fixture answer"
            with requests_lock:
                assert len(provider_requests) == 1

            # A current-owner revocation turns the same request into a provider miss.
            owner.active_tenants.remove("tenant-a")
            owner.epochs["tenant-a"] = "grant-a-revoked"
            revoked_result = await generate_for_current_tenant()
            assert revoked_result.content == "fixture answer"
            with requests_lock:
                assert len(provider_requests) == 2
        finally:
            response_release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await gateway.aclose()

    assert len(observations) == 6
    reported_observations = [row for row in observations if row["cost_origin"] == "reported"]
    reuse_observations = [row for row in observations if row["cost_origin"] == "reuse"]
    assert len(reported_observations) == 2
    assert len(reuse_observations) == 4
    assert sum(row["provider_call"] is True for row in observations) == 2
    assert sum(row["provider_call"] is False for row in observations) == 4
    assert all(row["settlement_status"] == "committed" for row in observations)

    # Reopen through a fresh ledger reader; one physical event has four linked zero-cost reuses.
    snapshot = FileBudgetLedger(ledger_path).snapshot()
    records = tuple(snapshot.producer_settlements.values())
    provider_records = tuple(row for row in records if row.cost_origin == "reported")
    reuse_records = tuple(row for row in records if row.cost_origin == "reuse")
    assert len(records) == 6
    assert len(provider_records) == 2
    assert len(reuse_records) == 4
    assert all(row.status == "committed" for row in records)
    assert all(row.amount == Decimal("0.02") for row in provider_records)
    assert all(row.amount == Decimal(0) for row in reuse_records)
    reuse_origins = {row.origin_event_id for row in reuse_records}
    assert len(reuse_origins) == 1
    assert reuse_origins.issubset({row.event_id for row in provider_records})
    assert snapshot.state.spent["run"] == Decimal("0.04")


def _run_no_otel_scoped_cache_scenario(
    base_url: str,
    ledger_path: str,
    snapshot_root: str,
) -> None:
    """Run the real factory/ledger path after the facade selects its no-OTel fallback."""
    import asyncio
    from decimal import Decimal as ChildDecimal
    from pathlib import Path as ChildPath

    from polisyos.core.observability import get_tracer

    # The subprocess import blocker represents an installation with the optional
    # dependency absent. It leaves PolicyOS' real fallback method and signature intact.
    assert type(get_tracer()).__module__ == "polisyos.core.observability"

    run_id = "factory-cache-no-otel-run"
    budget_key = f"nl-run:{run_id}"
    ledger = FileBudgetLedger(ChildPath(ledger_path))
    middleware = BudgetMiddleware(
        BudgetState(limits={budget_key: BudgetLimit(key=budget_key, max_usd=ChildDecimal("1"))}),
        ledger=ledger,
    )
    binding = BudgetLedgerProducerRunBinding(
        run_id=run_id,
        control_job_id="job-factory-cache-no-otel",
        tenant_id="tenant-a",
        cell_id="cell-a",
        profile_id="fixture-profile",
    )
    owner = _SnapshotOwner(ChildPath(snapshot_root))
    with _principal("tenant-a"):
        context = owner.metadata("tenant-a")["cache_reuse"]

    async def exercise() -> None:
        with middleware.producer_run_binding_scope(binding, control_job_attempt=1):
            with _gateway_cache_reuse_scope(
                authorizer=owner,
                principal=CacheReusePrincipal(
                    "spiffe://fixture/factory-cache-owner", "tenant-a", "scope-a"
                ),
                context=context,
                cache=InMemoryPromptCache(),
                run_id=run_id,
                settlement_store=middleware,
                reuse_guard=lambda operation: operation(),
            ):
                client = create_traced_gateway_client(
                    model_name="fixture-model",
                    provider_hint="local-http-fixture",
                    config=GatewayLLMConfig(
                        base_url=base_url,
                        api_key="sk-fixture-no-otel-cache-test-key",
                        timeout_s=3.0,
                        max_retries=0,
                        cache_ttl_s=60.0,
                        cache_maxsize=8,
                        enable_prompt_sanitizer=False,
                    ),
                )
                assert client is not None
                assert type(client._client) is CachingLLMClient
                cache_session = session_for_cache_client(client._client)
                assert cache_session is not None and cache_session.owns(client._client)
                gateway = client.unwrap()

                async def generate() -> Any:
                    with _principal("tenant-a"):
                        return await client.generate(
                            user="Compare the same policy option against the admitted snapshot.",
                            temperature=0.0,
                            metadata=owner.metadata("tenant-a"),
                        )

                try:
                    first = await generate()
                    second = await generate()
                    assert first.content == second.content == "fixture answer"

                    owner.active_tenants.remove("tenant-a")
                    owner.epochs["tenant-a"] = "grant-a-revoked"
                    try:
                        await generate()
                    except RuntimeError as error:
                        assert "Gateway request failed (400)" in str(error)
                    else:
                        raise AssertionError("provider failure was hidden by the no-OTel fallback")
                finally:
                    await gateway.aclose()

    asyncio.run(exercise())

    assert len(owner.requests) == 3
    snapshot = FileBudgetLedger(ChildPath(ledger_path)).snapshot()
    records = tuple(snapshot.producer_settlements.values())
    assert len(records) == 3
    reported = tuple(row for row in records if row.cost_origin == "reported")
    reused = tuple(row for row in records if row.cost_origin == "reuse")
    failed = tuple(row for row in records if row.cost_origin == "unknown")
    assert len(reported) == len(reused) == len(failed) == 1
    assert reported[0].status == reused[0].status == "committed"
    assert reported[0].amount == ChildDecimal("0.02")
    assert reused[0].amount == ChildDecimal(0)
    assert reused[0].origin_event_id == reported[0].event_id
    assert failed[0].status == "unknown" and failed[0].amount is None
    assert failed[0].run_binding == binding
    assert snapshot.state.spent[budget_key] == ChildDecimal("0.02")


def test_factory_scoped_cache_and_ledger_use_real_no_otel_fallback(tmp_path: Path) -> None:
    """The optional-telemetry fallback preserves scoped cache and settlement semantics."""
    with _local_gateway(fail_request_numbers=frozenset({2})) as (
        base_url,
        provider_requests,
        requests_lock,
    ):
        script = """
from importlib.abc import MetaPathFinder
import runpy
import sys

class _WithoutOpenTelemetry(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "opentelemetry" or fullname.startswith("opentelemetry."):
            raise ModuleNotFoundError(
                "OpenTelemetry omitted for the optional-dependency profile", name=fullname
            )
        return None

sys.meta_path.insert(0, _WithoutOpenTelemetry())
sys.path.insert(0, sys.argv[4])
module = runpy.run_path(sys.argv[1])
module["_run_no_otel_scoped_cache_scenario"](sys.argv[2], sys.argv[3], sys.argv[5])
"""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                str(Path(__file__).resolve()),
                base_url,
                str(tmp_path / "no-otel-ledger.json"),
                str(Path(__file__).resolve().parents[5] / "src"),
                str(tmp_path / "no-otel-snapshot-cas"),
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        assert result.returncode == 0, f"no-OTel child failed:\n{result.stdout}\n{result.stderr}"

        with requests_lock:
            assert len(provider_requests) == 2
            assert provider_requests[0]["metadata"] == provider_requests[1]["metadata"]
