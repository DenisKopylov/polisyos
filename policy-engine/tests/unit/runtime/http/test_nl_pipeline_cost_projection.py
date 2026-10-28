from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, cast

import duckdb
import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
)
from polisyos.core.contracts.control import (
    CatalogRunProfile,
    ControlJobResponse,
    DataResolveRequest,
)
from polisyos.core.contracts.execution_plan import (
    MethodCatalogSnapshot,
    MethodCatalogSnapshotRef,
)
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.fabric.retrieval import RetrievalService as _CanonicalRetrievalService
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.nl_pipeline import (
    NaturalLanguagePipelineRefusalError,
    _artifact_ref_from_ref_payload,
)
from polisyos.runtime.http.services.control_registry_providers import (
    ControlRegistryProviders,
)
from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)
from polisyos.scientist.orchestration.llm.simulated_gateway import (
    SimulatedGatewayLLMClient,
)
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.runtime_http import (
    build_runtime_api_env,
    close_runtime_api_env,
    submit_ordinary_nl_post,
)


class _EmptyRegistry:
    def query_entries(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def get(self, profile_id: str) -> None:
        return None

    def list_all(self) -> list[Any]:
        return []

    def list_by_family(self, connector_family: str) -> list[Any]:
        return []


class _FakeMetric:
    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        return {"metric": "macro.gdp", "value": 1.0}


class _FakeRetrievalService(_CanonicalRetrievalService):
    instances: ClassVar[list[_FakeRetrievalService]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.resolve_profile_calls: list[
            tuple[CatalogRunProfile | None, CatalogRunProfile | None]
        ] = []
        self.instances.append(self)

    def resolve(
        self,
        request: DataResolveRequest,
        *,
        run_profile: CatalogRunProfile | None = None,
    ) -> Any:
        self.resolve_profile_calls.append((request.catalog_run_profile, run_profile))
        return SimpleNamespace(
            fetch_plans=[{"id": "plan-1"}],
            telemetry={
                "lane_used": "fastlane",
                "metadata_docs_fetched": 1,
                "local_index_size_bytes": 10,
                "local_index_docs_total": 1,
                "candidates_filtered": 0,
                "phases": [],
            },
            mode="hybrid",
        )

    def execute_fetch_plans(
        self,
        plans: list[dict[str, Any]],
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> Any:
        return SimpleNamespace(
            previews=[SimpleNamespace(preview=SimpleNamespace(coverage_ok=True))],
            fallback_triggered_count=0,
            promoted_count=1,
            data_context=SimpleNamespace(
                metrics=[_FakeMetric()],
                metadata_docs_fetched=1,
                index_docs_total=1,
                index_size_bytes=10,
            ),
        )


def test_runtime_api_env_builder_closes_worker_when_fixture_setup_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tests._helpers.runtime_http as runtime_http_module

    services: list[dict[str, Any]] = []
    real_control_service = runtime_http_module.ControlPlaneService

    def _capture_control_service(*args: Any, **kwargs: Any) -> Any:
        service = real_control_service(*args, **kwargs)
        services.append(
            {
                "service": service,
                "control_store": getattr(service._control_store, "_target", service._control_store),
            }
        )
        return service

    def _raise_during_fixture_materialization(**_kwargs: Any) -> None:
        raise RuntimeError("controlled_fixture_setup_failure")

    monkeypatch.setattr(runtime_http_module, "ControlPlaneService", _capture_control_service)
    monkeypatch.setattr(
        runtime_http_module,
        "PromotionCandidate",
        _raise_during_fixture_materialization,
    )
    registered_before = tuple(runtime_http_module._RUNTIME_API_ENVS)

    with pytest.raises(RuntimeError, match="controlled_fixture_setup_failure"):
        runtime_http_module.build_runtime_api_env(tmp_path, include_test_client=False)

    assert len(services) == 1
    service = services[0]["service"]
    control_store = services[0]["control_store"]
    worker = service._worker
    assert worker is not None
    assert worker._thread is not None
    assert not worker._thread.is_alive()
    worker_leases = [
        lease
        for lease in control_store.list_worker_leases(active_only=False)
        if lease.worker_id == worker.worker_id
    ]
    assert len(worker_leases) == 1
    assert worker_leases[0].state == "stopped"
    assert worker_leases[0].active_job_id is None
    assert tuple(runtime_http_module._RUNTIME_API_ENVS) == registered_before


def test_runtime_api_env_closes_published_client_when_registration_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import tests._helpers.runtime_http as runtime_http_module

    real_test_client = runtime_http_module.TestClient
    if real_test_client is None:
        pytest.skip("FastAPI test client dependencies are not installed")

    registered_before = tuple(runtime_http_module._RUNTIME_API_ENVS)
    clients: list[Any] = []

    class _TrackedClient:
        def __init__(self, app: Any, **kwargs: Any) -> None:
            self._client = real_test_client(app, **kwargs)
            self.close_calls = 0

        def close(self) -> None:
            self.close_calls += 1
            self._client.close()

    def _build_tracked_client(app: Any, **kwargs: Any) -> _TrackedClient:
        client = _TrackedClient(app, **kwargs)
        clients.append(client)
        return client

    class _FailingRegistry(list[dict[str, object]]):
        def append(self, _env: dict[str, object]) -> None:
            raise RuntimeError("controlled_runtime_api_env_registration_failure")

    failing_registry = _FailingRegistry(registered_before)
    monkeypatch.setattr(runtime_http_module, "TestClient", _build_tracked_client)
    monkeypatch.setattr(runtime_http_module, "_RUNTIME_API_ENVS", failing_registry)

    with pytest.raises(RuntimeError, match="controlled_runtime_api_env_registration_failure"):
        build_runtime_api_env(tmp_path, include_test_client=True)

    assert len(clients) == 1
    assert clients[0].close_calls == 1
    assert tuple(failing_registry) == registered_before


def _forbid_real_gateway_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked_gateway_constructor(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("simulated LLM test must not construct a real gateway client")

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.GatewayLLMClient",
        _blocked_gateway_constructor,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.FallbackRouter",
        _blocked_gateway_constructor,
    )


def _cost_event_rows(payload: object) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}

    def _visit(value: object) -> None:
        if isinstance(value, dict):
            for key in ("cost_events", "nl_preflight_cost_events"):
                raw_events = value.get(key)
                if isinstance(raw_events, list):
                    for row in raw_events:
                        if isinstance(row, dict) and isinstance(row.get("event_id"), str):
                            prior = rows_by_id.setdefault(row["event_id"], row)
                            if prior != row:
                                raise AssertionError("pipeline cost event identity conflict")
            for nested in value.values():
                _visit(nested)
        elif isinstance(value, list):
            for nested in value:
                _visit(nested)

    _visit(payload)
    return list(rows_by_id.values())


def test_workflow_report_ref_preserves_selected_profile_and_rejects_mismatch() -> None:
    artifact_id = "sha256:" + "1" * 64
    selected_ref = ArtifactRef(
        artifact_id=artifact_id,
        kind="scientist.workflow_report",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    assert (
        _artifact_ref_from_ref_payload(
            selected_ref,
            artifact_id=artifact_id,
            kind="scientist.workflow_report",
        )
        is selected_ref
    )
    assert (
        _artifact_ref_from_ref_payload(
            selected_ref.model_dump(mode="json"),
            artifact_id=artifact_id,
            kind="scientist.workflow_report",
        ).manifest_profile_sha256
        == selected_ref.manifest_profile_sha256
    )
    with pytest.raises(ValueError, match="artifact_ref_does_not_match_expected_selection"):
        _artifact_ref_from_ref_payload(
            selected_ref,
            artifact_id=artifact_id,
            kind="runtime.payload",
        )


class _MonetarySimulatedProvider:
    """Use valid simulated outputs while varying only raw provider cost evidence."""

    provider = "simulated_gateway"

    def __init__(self, model: str) -> None:
        self._client = SimulatedGatewayLLMClient(
            model=model,
            supported_model_ids=(model, "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8"),
        )
        self._costs: tuple[float | None, ...] = (0.0, None, -1.0)
        self.calls = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.release.set()
        self._block_next = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    def block_next(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self._block_next = True

    def prepare_cache_request(self, *args, **kwargs):
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

    async def generate(self, **kwargs: Any) -> Any:
        call_number = self.calls
        self.calls += 1
        if self._block_next:
            self._block_next = False
            self.entered.set()
            await self.release.wait()
        response = await self._client.generate(**kwargs)
        cost = self._costs[call_number % len(self._costs)]
        response.usage.cost_usd = cost
        response.usage.cost_status = (
            "missing" if cost is None else "invalid" if cost < 0 else "known"
        )
        return response


class _CancelCacheOwnerOnce(TracedLLMClient):
    """Cancel the first cache waiter while a same-key follower owns the result."""

    def __init__(
        self,
        cache: CachingLLMClient,
        provider: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(cache, **kwargs)
        self._cache = cache
        self._provider = provider
        self._used = False

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        # The synthetic monetary provider is configured for explicit deterministic requests.
        kwargs.setdefault("temperature", 0.0)
        metadata = kwargs.get("metadata")
        if (
            self._used
            or kwargs.get("tools")
            or kwargs.get("tool_choice")
            or kwargs.get("stream")
            or (isinstance(metadata, dict) and metadata.get("cacheable") is False)
        ):
            return await TracedLLMClient.generate(self, *args, **kwargs)
        self._used = True
        self._provider.block_next()
        owner = asyncio.create_task(TracedLLMClient.generate(self, *args, **kwargs))
        await self._provider.entered.wait()
        flight = next(iter(self._cache._inflight.values()))
        follower = asyncio.create_task(TracedLLMClient.generate(self, *args, **kwargs))
        for _ in range(100):
            if len(flight.registrations) == 2:
                break
            await asyncio.sleep(0)
        assert len(flight.registrations) == 2
        owner.cancel()
        with suppress(asyncio.CancelledError):
            await owner
        self._provider.release.set()
        return await follower


def test_simulated_nl_producer_costs_settle_and_capture_four_origins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.common import async_tools
    from polisyos.fabric import retrieval as retrieval_module
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import (
        BudgetMiddleware,
    )

    captured: dict[str, Any] = {}
    monetary_clients: list[_CancelCacheOwnerOnce] = []

    def _capture_state(payload: dict[str, Any], **kwargs: Any) -> None:
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    real_retrieval_service = retrieval_module.RetrievalService
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)

    def _build_monetary_client(**kwargs: Any) -> _CancelCacheOwnerOnce:
        model = str(kwargs["model_name"])
        provider = _MonetarySimulatedProvider(model)
        cache = CachingLLMClient(
            provider,
            cache=InMemoryPromptCache(maxsize=8, default_ttl_s=30),
            model=model,
            ttl_s=30,
            inflight_timeout_s=10,
        )
        client = _CancelCacheOwnerOnce(
            cache,
            provider,
            model_name=model,
            run_id=kwargs.get("run_id"),
            model_variant_id=kwargs.get("model_variant_id"),
            call_observer=kwargs.get("call_observer"),
            tracer=kwargs.get("tracer"),
            metrics=kwargs.get("metrics"),
            producer_settlement_store=kwargs.get("producer_settlement_store"),
            producer_budget_key=str(kwargs.get("producer_budget_key", "run")),
        )
        monetary_clients.append(client)
        return client

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline.create_traced_gateway_client",
        _build_monetary_client,
    )
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    from polisyos.foundry.methods import (
        persist_method_catalog_snapshot as _canonical_persist_method_catalog_snapshot,
    )

    catalog_snapshot_writes: list[tuple[MethodCatalogSnapshotRef, MethodCatalogSnapshot]] = []

    def _persist_catalog_snapshot_with_typed_tenant(
        store: Any,
        snapshot: MethodCatalogSnapshot,
        *,
        inputs: list[InputRef] | None = None,
        tenant_context: ArtifactTenantContextInfo | None = None,
    ) -> MethodCatalogSnapshotRef:
        assert isinstance(snapshot, MethodCatalogSnapshot)
        assert inputs is None
        assert type(tenant_context) is ArtifactTenantContextInfo
        assert tenant_context == ArtifactTenantContextInfo(
            tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            cell_id="cell-a",
        )
        selected_ref = _canonical_persist_method_catalog_snapshot(
            store,
            snapshot,
            inputs=inputs,
            tenant_context=tenant_context,
        )
        assert selected_ref.manifest_profile_sha256 is not None
        catalog_snapshot_writes.append((selected_ref, snapshot))
        return selected_ref

    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        _persist_catalog_snapshot_with_typed_tenant,
    )

    real_run_coro_sync = async_tools.run_coro_sync

    def _run_coro_sync_with_load_budget(coro, *, timeout_seconds=None):
        timeout = 120.0 if timeout_seconds is None else timeout_seconds
        return real_run_coro_sync(coro, timeout_seconds=timeout)

    monkeypatch.setattr(async_tools, "run_coro_sync", _run_coro_sync_with_load_budget)

    run_id = "R_core_api_001"
    cas_root = tmp_path / ".polisyos"
    ledger_path = cas_root / "runs" / ".runtime" / "llm-cost-ledger.json"
    ledger = FileBudgetLedger(ledger_path)
    settlement_store = BudgetMiddleware(BudgetState(), ledger=ledger)
    empty_registry = _EmptyRegistry()
    service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        llm_producer_settlement_store=settlement_store,
        policy_resolver=RuntimeExecutionPolicyResolver(
            default_profile="dev",
            worker_backend="external",
            state_store_backend="sqlite",
            sqlite_path=str(tmp_path / "control-progress.sqlite3"),
            postgres_dsn=None,
        ),
        registry_providers=ControlRegistryProviders(
            connectors=empty_registry,
            source_profiles=empty_registry,
            binding_profiles=empty_registry,
            model_profiles=empty_registry,
            catalog_run_profile="prod_full",
        ),
    )
    _FakeRetrievalService.instances.clear()
    import hashlib

    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.runtime.http.services.control import nl_pipeline as nl_pipeline_module
    from polisyos.runtime.http.services.control.artifacts import (
        AUTHORITY_ENVELOPE_ARTIFACT_KIND,
        DIAGNOSTIC_EVENT_ARTIFACT_KIND,
        verify_runtime_authority_artifact_identity,
    )
    from polisyos.runtime.quality.authority import (
        AUTHORITY_ENVELOPE_CONTRACT_NAME,
        AUTHORITY_ENVELOPE_CONTRACT_VERSION,
    )
    from polisyos.runtime.quality.diagnostic_events import (
        DIAGNOSTIC_EVENT_SCHEMA_NAME,
        DIAGNOSTIC_EVENT_SCHEMA_VERSION,
    )

    artifact_store = service._artifact_store
    original_put_json = artifact_store.put_json
    original_get_bytes = artifact_store.get_bytes
    original_get_manifest = artifact_store.get_manifest
    original_run_blocking_async = nl_pipeline_module.run_blocking_async
    authority_envelope_pairs: list[tuple[ArtifactRef, ArtifactRef]] = []
    authority_envelope_reads: list[object] = []
    authority_envelope_puts: list[ArtifactRef] = []
    authority_envelope_default_views: list[ArtifactRef] = []
    authority_write_options = []
    production_authority_envelope_reads: list[object] = []
    authority_envelope_read_digests: list[tuple[object, str]] = []
    production_authority_envelope_read_digests: list[tuple[object, str]] = []
    writer_authority_envelope_readbacks: list[object] = []
    writer_authority_envelope_readback_digests: list[tuple[object, str]] = []
    writer_authority_readback_id: str | None = None
    observed_authority_ids: set[str] = set()

    def _put_json_with_sibling_default(
        obj, write_options, canon_spec=None, *, return_selected_profile=False
    ):
        if (
            write_options.kind == "runtime_quality.evidence_authority_envelope"
            and not authority_envelope_default_views
        ):
            sibling_options = replace(
                write_options,
                schema=SchemaInfo(
                    name=write_options.schema.name,
                    version=f"{write_options.schema.version}.sibling",
                ),
            )
            authority_envelope_default_views.append(
                original_put_json(obj, sibling_options, canon_spec)
            )
        ref = original_put_json(
            obj,
            write_options,
            canon_spec,
            return_selected_profile=return_selected_profile,
        )
        if write_options.kind == "runtime_quality.evidence_authority_envelope":
            authority_envelope_puts.append(ref)
        return ref

    monkeypatch.setattr(artifact_store, "put_json", _put_json_with_sibling_default)

    def _recording_get_bytes(artifact_ref):
        artifact_id = str(getattr(artifact_ref, "artifact_id", artifact_ref))
        is_authority_envelope_ref = (
            isinstance(artifact_ref, ArtifactRef)
            and artifact_ref.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND
        )
        raw_payload = original_get_bytes(artifact_ref)
        read_receipt = (artifact_ref, hashlib.sha256(raw_payload).hexdigest())
        if writer_authority_readback_id is not None:
            if is_authority_envelope_ref or artifact_id == writer_authority_readback_id:
                writer_authority_envelope_readbacks.append(artifact_ref)
                writer_authority_envelope_readback_digests.append(read_receipt)
        elif is_authority_envelope_ref or artifact_id in observed_authority_ids:
            authority_envelope_reads.append(artifact_ref)
            authority_envelope_read_digests.append(read_receipt)
        return raw_payload

    artifact_store.get_bytes = _recording_get_bytes

    async def _run_blocking_with_sibling_manifest(function, *args, **kwargs):
        nonlocal writer_authority_readback_id
        result = await original_run_blocking_async(function, *args, **kwargs)
        if function is nl_pipeline_module.write_runtime_authority_artifact:
            writer_store, _event_log, _payload, writer_options = args
            assert writer_store is artifact_store
            selected_ref = result.authority_envelope_ref
            selected_id = str(selected_ref.artifact_id)
            writer_authority_readback_id = selected_id
            try:
                readback = verify_runtime_authority_artifact_identity(
                    writer_store,
                    artifact_id=result.cas_ref,
                    opts=writer_options,
                    expected_context=result.identity_context,
                )
            finally:
                writer_authority_readback_id = None
            assert readback.cas_ref == result.cas_ref
            assert readback.authority_envelope_ref == result.authority_envelope_ref
            assert readback.identity_context == result.identity_context
            authority_write_options.append((result, writer_options))
            if selected_id not in observed_authority_ids:
                manifest = original_get_manifest(selected_ref)
                payload_bytes = original_get_bytes(selected_ref)
                sibling_ref = artifact_store.put_bytes(
                    payload_bytes,
                    PutOptions(
                        kind=manifest.kind,
                        media_type=manifest.media_type,
                        schema=SchemaInfo(
                            name=manifest.artifact_schema.name,
                            version=f"{manifest.artifact_schema.version}.sibling",
                        ),
                        tenant_context=ArtifactTenantContextInfo(
                            tenant_id="tenant-sibling",
                            cell_id="cell-sibling",
                        ),
                    ),
                )
                authority_envelope_pairs.append((selected_ref, sibling_ref))
                observed_authority_ids.add(selected_id)
        return result

    monkeypatch.setattr(
        nl_pipeline_module,
        "run_blocking_async",
        _run_blocking_with_sibling_manifest,
    )

    try:
        execution_context = {
            "tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "cell_id": "cell-a",
            "jurisdiction": "UA",
            "target_population": "wartime MSMEs",
            "policy_time": "2026-05-15",
            "data_time": "2024-2026",
            "policy_problem": "Wartime MSMEs face liquidity constraints.",
            "desired_outcome": "MSME survival",
            "proposed_intervention": "targeted credit support",
            "requested_authority_level": "dev",
        }
        pipeline_kwargs = {
            "run_id": run_id,
            "nl_request": "Develop an optimal policy for wartime MSMEs in Ukraine.",
            "context": execution_context,
            "domain_hint": "Ukraine wartime MSME support policy",
            "data_source": None,
            "max_iterations": 1,
            "llm_models": ["simulated-qwen"],
            "max_parallel_models": 1,
            "run_budget_usd": None,
            "per_model_budget_usd": None,
            "checkpoint_policy": "strict",
            "execution_plan_ref": None,
            "execution_plan_payload": None,
            "stop_criteria_payload": {},
            "governance_constraints_payload": [],
            "expected_outputs_payload": [],
            "allow_mock_fallback": False,
        }
        with pytest.raises(
            NaturalLanguagePipelineRefusalError,
            match="control_job_execution_scope_not_established",
        ):
            service._execute_nl_pipeline(**pipeline_kwargs)
        assert captured == {}
        assert monetary_clients == []

        job_id = "job-nl-producer-cost-projection"
        payload_ref = "sha256:" + "f" * 64
        execution_scope = {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": "established",
            "tenant_id": execution_context["tenant_id"],
            "cell_id": execution_context["cell_id"],
            "actor_subject": "test-nl-producer-worker",
            "actor_authenticated": True,
            "actor_roles": ["analyst"],
        }
        creation_payload = {
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": "natural_language_run",
            "pipeline_id": None,
            "payload_ref": payload_ref,
            "submitted_by": execution_scope["actor_subject"],
            "requested_execution_profile": "dev",
            "effective_execution_profile": "dev",
            "policy_flags": {},
            "capability_manifest_ref": None,
            "execution_scope": execution_scope,
        }
        service._control_store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="dev",
            effective_execution_profile="dev",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=payload_ref,
            submitted_by=execution_scope["actor_subject"],
            initial_progress={"state": "pending", "phase": "job_admission"},
            creation_event_payload=creation_payload,
        )

        def _run_pipeline_under_live_job(_job: object) -> None:
            captured["pipeline_result"] = service._execute_nl_pipeline(
                **pipeline_kwargs,
                control_job_id=job_id,
                execution_profile="dev",
            )
            service._control_store.complete_job(
                job_id=job_id,
                run_id=run_id,
                progress={"state": "completed", "phase": "nl_pipeline_contract"},
            )

        dispatch_one_control_job(
            store=service._control_store,  # noqa: SLF001
            handler=_run_pipeline_under_live_job,
            expected_job_id=job_id,
        )
        completed_job = service._control_store.get_job(job_id)
        assert completed_job is not None and completed_job.state == "completed"
        assert completed_job.progress["execution_owner_binding"]["job_id"] == job_id
        actual_retrieval_services = [
            retrieval
            for retrieval in _FakeRetrievalService.instances
            if retrieval.resolve_profile_calls
        ]
        assert actual_retrieval_services
        assert all(
            request_profile == keyword_profile == "prod_full"
            for retrieval in actual_retrieval_services
            for request_profile, keyword_profile in retrieval.resolve_profile_calls
        )
        production_authority_envelope_reads[:] = authority_envelope_reads
        production_authority_envelope_read_digests[:] = authority_envelope_read_digests
        assert authority_write_options and authority_envelope_pairs
        first_result, first_options = authority_write_options[0]
        first_selected_ref, first_sibling_ref = authority_envelope_pairs[0]
        assert first_result.authority_envelope_ref == first_selected_ref
        assert first_selected_ref.manifest_profile_sha256 is not None
        assert first_sibling_ref.manifest_profile_sha256 is not None
        assert (
            first_selected_ref.manifest_profile_sha256 != first_sibling_ref.manifest_profile_sha256
        )
        default_ref = authority_envelope_default_views[0]
        assert default_ref.artifact_id == first_selected_ref.artifact_id
        assert default_ref.manifest_profile_sha256 is None
        wrong_default_manifest = original_get_manifest(default_ref)
        assert wrong_default_manifest.artifact_schema is not None
        assert wrong_default_manifest.artifact_schema.version.endswith(".sibling")

        def _verify_with_linked_profile(
            result,
            options,
            profile_sha256,
            *,
            default_manifest_override=None,
        ):
            payload_manifest = original_get_manifest(result.cas_ref)
            authority = payload_manifest.authority
            assert authority is not None
            linked_authority = authority.model_copy(
                update={"authority_envelope_manifest_profile_sha256": profile_sha256}
            )
            linked_payload_manifest = payload_manifest.model_copy(
                update={"authority": linked_authority}
            )
            envelope_id = str(result.authority_envelope_ref.artifact_id)

            class _ManifestLinkStore:
                def __getattr__(self, name):
                    return getattr(artifact_store, name)

                def get_manifest(self, selector):
                    selector_id = str(getattr(selector, "artifact_id", selector))
                    if selector_id == str(result.cas_ref.artifact_id):
                        return linked_payload_manifest
                    if (
                        profile_sha256 is None
                        and default_manifest_override is not None
                        and selector_id == envelope_id
                    ):
                        return default_manifest_override
                    return original_get_manifest(selector)

            return verify_runtime_authority_artifact_identity(
                _ManifestLinkStore(),
                artifact_id=result.cas_ref.artifact_id,
                opts=options,
                expected_context=result.identity_context,
            )

        with pytest.raises(ValueError):
            _verify_with_linked_profile(
                first_result,
                first_options,
                first_sibling_ref.manifest_profile_sha256,
            )
        with pytest.raises(ValueError):
            _verify_with_linked_profile(
                first_result,
                first_options,
                None,
                default_manifest_override=wrong_default_manifest,
            )
    finally:
        service.close()
        monkeypatch.setattr(
            "polisyos.fabric.retrieval.RetrievalService",
            real_retrieval_service,
        )

    payload = captured["payload"]
    assert captured["kwargs"]["store"] is not None
    actual_rows = _cost_event_rows(payload)
    assert len(actual_rows) >= 2
    variant_rows = payload["params"]["llm_model_variants"][0]["cost_events"]
    preflight_rows = payload["params"]["nl_preflight_cost_events"]
    assert preflight_rows

    reopened = FileBudgetLedger(ledger_path).snapshot().producer_settlements
    variant_ids = {row["event_id"] for row in variant_rows}
    preflight_ids = {row["event_id"] for row in preflight_rows}
    assert variant_ids.isdisjoint(preflight_ids)
    assert variant_ids | preflight_ids == set(reopened)
    assert {row["event_id"] for row in actual_rows} == set(reopened), (
        "the persisted NL payload must retain every provider event emitted for the run; "
        f"captured={sorted(row['event_id'] for row in actual_rows)}, "
        f"ledger={sorted(reopened)}, "
        f"preflight={payload['params'].get('nl_preflight_cost_events')}"
    )
    assert all(record.key == f"nl-run:{run_id}" for record in reopened.values())
    assert {record.cost_origin for record in reopened.values()} == {
        "reported",
        "estimated",
        "unknown",
        "reuse",
    }
    assert all(
        record.status == ("unknown" if record.cost_origin == "unknown" else "committed")
        for record in reopened.values()
    )
    assert all(
        record.amount is None if record.cost_origin == "unknown" else record.amount is not None
        for record in reopened.values()
    )
    provider_rows = [row for row in actual_rows if row["cost_origin"] != "reuse"]
    reuse_rows = [row for row in actual_rows if row["cost_origin"] == "reuse"]
    assert any(
        row["cost_origin"] == "reported" and Decimal(str(row["amount"])) == Decimal(0)
        for row in provider_rows
    )
    assert any(
        row["cost_origin"] == "estimated" and Decimal(row["amount"]) > 0 for row in provider_rows
    )
    assert any(row["cost_origin"] == "unknown" and row["amount"] is None for row in provider_rows)
    assert reuse_rows and all(
        Decimal(str(row["amount"])) == Decimal(0) and row["origin_event_id"] for row in reuse_rows
    )
    assert payload["params"]["run_cost_usd"] is None

    assert len(variant_rows) + len(preflight_rows) == len(reopened)
    assert {row["cost_origin"] for row in actual_rows} == {
        "reported",
        "estimated",
        "unknown",
        "reuse",
    }
    assert authority_envelope_pairs
    assert authority_envelope_default_views
    assert authority_envelope_puts
    selected_envelope_refs = [selected for selected, _sibling in authority_envelope_pairs]
    assert selected_envelope_refs == authority_envelope_puts

    def _authority_envelope_identity(
        ref: ArtifactRef,
    ) -> tuple[str, str | None, str, str]:
        return (
            str(ref.artifact_id),
            ref.manifest_profile_sha256,
            ref.kind,
            ref.media_type,
        )

    expected_envelope_identities = {
        _authority_envelope_identity(ref) for ref in selected_envelope_refs
    }
    assert len(expected_envelope_identities) == len(selected_envelope_refs)
    assert all(
        ref.manifest_profile_sha256 is not None
        and ref.kind == AUTHORITY_ENVELOPE_ARTIFACT_KIND
        and ref.media_type == "application/json"
        for ref in selected_envelope_refs
    )

    # The owner re-resolves linked authority ancestors through the selected Core
    # refs. Repeated reads are valid; identity/profile and resolved bytes are not
    # allowed to drift to a default or sibling view.
    assert all(isinstance(ref, ArtifactRef) for ref in production_authority_envelope_reads)
    assert {
        _authority_envelope_identity(cast("ArtifactRef", ref))
        for ref in production_authority_envelope_reads
    } == expected_envelope_identities
    assert len(production_authority_envelope_read_digests) == len(
        production_authority_envelope_reads
    )
    assert {
        (
            _authority_envelope_identity(cast("ArtifactRef", ref)),
            digest,
        )
        for ref, digest in production_authority_envelope_read_digests
    } == {
        (_authority_envelope_identity(ref), ref.artifact_id.hex) for ref in selected_envelope_refs
    }

    assert all(isinstance(ref, ArtifactRef) for ref in writer_authority_envelope_readbacks)
    assert {
        _authority_envelope_identity(cast("ArtifactRef", ref))
        for ref in writer_authority_envelope_readbacks
    } == expected_envelope_identities
    assert len(writer_authority_envelope_readback_digests) == len(
        writer_authority_envelope_readbacks
    )
    assert {
        (
            _authority_envelope_identity(cast("ArtifactRef", ref)),
            digest,
        )
        for ref, digest in writer_authority_envelope_readback_digests
    } == {
        (_authority_envelope_identity(ref), ref.artifact_id.hex) for ref in selected_envelope_refs
    }
    assert all(
        selected.artifact_id == sibling.artifact_id
        and selected.kind == sibling.kind == "runtime_quality.evidence_authority_envelope"
        and selected.media_type == sibling.media_type == "application/json"
        and selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
        for selected, sibling in authority_envelope_pairs
    )
    assert authority_envelope_default_views[0].manifest_profile_sha256 is None
    # The original service-owned CAS is intentionally closed above. Reopen the
    # same filesystem namespace with a real reader and bind every selected view
    # back to the tenant/cell declared by this controlled producer input.
    fresh_artifact_store = FileSystemCAS(cas_root)
    expected_tenant_context = ArtifactTenantContextInfo(
        tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        cell_id="cell-a",
    )
    assert fresh_artifact_store.root == cas_root.resolve()
    assert fresh_artifact_store is not artifact_store
    assert catalog_snapshot_writes
    catalog_schema = SchemaInfo(name="polisyos.core.MethodCatalogSnapshot", version="2.0")
    for catalog_ref, expected_snapshot in catalog_snapshot_writes:
        assert catalog_ref.manifest_profile_sha256 is not None
        assert catalog_ref.kind == "foundry.method_catalog_snapshot"
        assert catalog_ref.media_type == "application/json"
        catalog_manifest = fresh_artifact_store.get_manifest(catalog_ref)
        catalog_bytes = fresh_artifact_store.get_bytes(catalog_ref)
        catalog_profile = artifact_manifest_profile_sha256(catalog_manifest)
        assert catalog_manifest.artifact_id == catalog_ref.artifact_id
        assert catalog_manifest.kind == catalog_ref.kind
        assert catalog_manifest.media_type == catalog_ref.media_type
        assert catalog_manifest.artifact_schema == catalog_schema
        assert catalog_manifest.tenant_context == expected_tenant_context
        assert catalog_ref.manifest_profile_sha256 == catalog_profile
        assert catalog_manifest.byte_size == len(catalog_bytes)
        assert hashlib.sha256(catalog_bytes).hexdigest() == catalog_ref.artifact_id.hex
        catalog_read = read_core_json_artifact(
            fresh_artifact_store,
            catalog_ref,
            raw_payload_bytes=catalog_bytes,
        )
        assert catalog_read.status == "declared_bytes_conformant"
        assert catalog_read.selected_artifact_id == str(catalog_ref.artifact_id)
        assert catalog_read.selected_manifest_profile_sha256 == catalog_profile
        assert catalog_read.raw_payload_bytes == catalog_bytes
        assert isinstance(catalog_read.value, dict)
        persisted_catalog = MethodCatalogSnapshot.model_validate(catalog_read.value)
        # Rich metadata uses CAN.2 sequence normalization; compare every wire value.
        assert persisted_catalog.model_dump(mode="json") == expected_snapshot.model_dump(
            mode="json"
        )
        assert persisted_catalog.run_id == run_id
    for result, writer_options in authority_write_options:
        payload_schema = writer_options.schema
        assert payload_schema is not None
        selected_specs = (
            (
                result.cas_ref,
                writer_options.kind,
                writer_options.media_type,
                payload_schema,
            ),
            (
                result.authority_envelope_ref,
                AUTHORITY_ENVELOPE_ARTIFACT_KIND,
                "application/json",
                SchemaInfo(
                    name=AUTHORITY_ENVELOPE_CONTRACT_NAME,
                    version=AUTHORITY_ENVELOPE_CONTRACT_VERSION,
                ),
            ),
            (
                result.diagnostic_event_ref,
                DIAGNOSTIC_EVENT_ARTIFACT_KIND,
                "application/json",
                SchemaInfo(
                    name=DIAGNOSTIC_EVENT_SCHEMA_NAME,
                    version=DIAGNOSTIC_EVENT_SCHEMA_VERSION,
                ),
            ),
        )
        selected_manifests = []
        for ref, expected_kind, expected_media_type, expected_schema in selected_specs:
            assert isinstance(ref, ArtifactRef)
            assert ref.manifest_profile_sha256 is not None
            assert ref.kind == expected_kind
            assert ref.media_type == expected_media_type
            manifest = fresh_artifact_store.get_manifest(ref)
            raw_payload = fresh_artifact_store.get_bytes(ref)
            profile_sha256 = artifact_manifest_profile_sha256(manifest)
            assert manifest.artifact_id == ref.artifact_id
            assert manifest.kind == expected_kind
            assert manifest.media_type == expected_media_type
            assert manifest.artifact_schema == expected_schema
            assert manifest.tenant_context == expected_tenant_context
            assert ref.manifest_profile_sha256 == profile_sha256
            assert manifest.byte_size == len(raw_payload)
            assert hashlib.sha256(raw_payload).hexdigest() == ref.artifact_id.hex
            core_read = read_core_json_artifact(
                fresh_artifact_store,
                ref,
                raw_payload_bytes=raw_payload,
            )
            assert core_read.status == "declared_bytes_conformant"
            assert core_read.selected_artifact_id == str(ref.artifact_id)
            assert core_read.selected_manifest_profile_sha256 == profile_sha256
            assert core_read.raw_payload_bytes == raw_payload
            assert isinstance(core_read.value, dict)
            selected_manifests.append(manifest)

        payload_authority = selected_manifests[0].authority
        assert payload_authority is not None
        assert payload_authority.authority_envelope_ref == str(
            result.authority_envelope_ref.artifact_id
        )
        assert (
            payload_authority.authority_envelope_manifest_profile_sha256
            == result.authority_envelope_ref.manifest_profile_sha256
        )
        assert payload_authority.diagnostic_event_ref == str(
            result.diagnostic_event_ref.artifact_id
        )
        assert (
            payload_authority.diagnostic_event_manifest_profile_sha256
            == result.diagnostic_event_ref.manifest_profile_sha256
        )


@pytest.mark.usefixtures("canary_diagnostic_output_root")
def test_ordinary_nl_post_persists_and_serves_durable_cost_events_after_reopen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import json

    from polisyos.core.contracts.runtime import AgentPipelineResponse
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        BudgetLedgerProducerRunBinding,
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import (
        BudgetMiddleware,
    )
    from polisyos.scientist.orchestration.llm.gateway_client import GatewayLLMClient

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    monetary_providers: list[_MonetarySimulatedProvider] = []
    monetary_clients: list[_CancelCacheOwnerOnce] = []

    def _build_monetary_client(**kwargs: Any) -> _CancelCacheOwnerOnce:
        model = str(kwargs["model_name"])
        provider = _MonetarySimulatedProvider(model)
        monetary_providers.append(provider)
        cache = CachingLLMClient(
            provider,
            cache=InMemoryPromptCache(maxsize=8, default_ttl_s=30),
            model=model,
            ttl_s=30,
            inflight_timeout_s=10,
        )
        client = _CancelCacheOwnerOnce(
            cache,
            provider,
            model_name=model,
            run_id=kwargs.get("run_id"),
            model_variant_id=kwargs.get("model_variant_id"),
            call_observer=kwargs.get("call_observer"),
            tracer=kwargs.get("tracer"),
            metrics=kwargs.get("metrics"),
            producer_settlement_store=kwargs.get("producer_settlement_store"),
            producer_budget_key=str(kwargs.get("producer_budget_key", "run")),
        )
        monetary_clients.append(client)
        return client

    n4_producer_clients: list[_CancelCacheOwnerOnce] = []

    def _build_n4_producer_client(**kwargs: Any) -> _CancelCacheOwnerOnce:
        client = _build_monetary_client(**kwargs)
        n4_producer_clients.append(client)
        return client

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline.create_traced_gateway_client",
        _build_monetary_client,
    )
    monkeypatch.setattr(
        "polisyos.scientist.orchestration.llm.factory.create_traced_gateway_client",
        _build_n4_producer_client,
    )
    catalog_snapshot_root = tmp_path / "candidate-catalog"
    catalog_path = catalog_snapshot_root / "datasets/graph/dataset_catalog.duckdb"
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as catalog:
        catalog.execute("CREATE TABLE ds_metric_bindings(metric_id VARCHAR)")
        catalog.execute("CREATE TABLE ds_observations(canonical_var VARCHAR)")
        catalog.execute("CREATE TABLE ds_datasets(polisyos_metrics VARCHAR[])")
        catalog.execute("INSERT INTO ds_metric_bindings VALUES ('employment_rate')")
    catalog_selection = CatalogServingSourceSelection(
        snapshot_root=catalog_snapshot_root,
        catalog_run_profile="prod_full",
    )
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"catalog_source_selection": catalog_selection},
    )
    control_service = cast("Any", env["app"]).state._control_service
    control_store = control_service._control_store
    assert control_service._catalog_run_profile == "prod_full"
    assert control_service._catalog_serving_source.selection_basis == "explicit_path_candidate_only"
    owner_projection_writes: list[tuple[str, object, dict[str, object]]] = []
    original_update_progress_state = control_store.update_progress_state

    def _capture_owner_projection_write(**kwargs: Any) -> None:
        progress = kwargs.get("progress")
        owner = progress.get("execution_owner_binding") if isinstance(progress, dict) else None
        if isinstance(owner, dict):
            owner_projection_writes.append(
                (str(kwargs.get("job_id")), progress.get("phase"), dict(owner))
            )
        original_update_progress_state(**kwargs)

    monkeypatch.setattr(control_store, "update_progress_state", _capture_owner_projection_write)
    client_context = cast("Any", env["client"])
    assert client_context is not None
    client_entered = False
    try:
        client_context.__enter__()
        client_entered = True
        client = client_context
        ordinary_run = submit_ordinary_nl_post(env)
        from polisyos.runtime.http.services import run_index as run_index_module

        monkeypatch.setattr(
            run_index_module,
            "time",
            SimpleNamespace(monotonic=lambda: 100.0, perf_counter=lambda: 100.0),
        )
        runtime_context = cast("Any", ordinary_run["runtime_context"])
        run_index = runtime_context.run_index
        run_index.refresh(force=True)
        prewarmed_run = run_index.get_run(str(ordinary_run["run_id"]))
        assert prewarmed_run.run_id == ordinary_run["run_id"]
        ordinary_progress = ordinary_run["job"].progress
        assert ordinary_progress["execution_intent_band"] == "candidate_only"
        assert ordinary_progress["stage"] == "n4_proposal_only"
        assert ordinary_progress["n5_status"] == "not_run"
        assert ordinary_progress["n9_status"] == "not_run"
        job = ordinary_run["job"]
        job_id = str(ordinary_run["job_id"])
        creation_payload = ordinary_run["creation_payload"]
        creation_outbox = ordinary_run["creation_outbox"]
        assert creation_outbox.payload == creation_payload
        execution_scope = creation_payload.get("execution_scope")
        assert isinstance(execution_scope, dict)
        assert execution_scope.get("status") == "established"
        assert execution_scope.get("actor_subject") == job.submitted_by

        job_response = client.get(f"/api/v1/control/jobs/{job_id}")
        assert job_response.status_code == 200, job_response.text
        received_job = ControlJobResponse.model_validate(job_response.json())
        app = cast("Any", env["app"])
        runtime_container = app.state.runtime_container
        runtime_context = runtime_container.runtime_api_context
        assert runtime_context is not None
        from copy import deepcopy

        from polisyos.runtime.quality.scorecard import build_quality_scorecard

        received_payload = received_job.model_dump(mode="json")
        persisted_job = control_store.get_job(job_id)
        assert persisted_job is not None and persisted_job.state == "completed"
        assert received_job.state == "completed"
        persisted_owner = persisted_job.progress.get("execution_owner_binding")
        assert isinstance(persisted_owner, dict)
        assert received_job.requested_execution_profile is None
        assert persisted_job.requested_execution_profile is None
        assert persisted_owner["requested_execution_profile"] is None
        assert "run_intent_binding" not in persisted_job.progress
        completion_outbox = control_store.get_job_completed_outbox_event(job_id)
        assert completion_outbox is not None
        completion_progress = completion_outbox.payload["progress"]
        assert completion_progress["execution_owner_binding"] == persisted_owner
        assert completion_progress == persisted_job.progress
        received_disposition = received_job.progress.get("normative_disposition")
        assert isinstance(received_disposition, dict)
        assert received_disposition.get("authorization_status") == "blocked"
        assert received_disposition.get("reason_codes") == [
            "normative_evidence_owned_run_source_mismatch"
        ]
        assert received_disposition.get("source_status") == "not_established"
        assert (job_id, "job_admission", persisted_owner) in owner_projection_writes
        received_owner = received_job.progress.get("execution_owner_binding")
        assert isinstance(received_owner, dict)
        assert received_owner == persisted_owner
        assert received_owner["job_id"] == job_id
        assert received_owner["run_id"] == str(job.run_id)
        assert received_owner["requested_execution_profile"] is None
        assert "run_intent_binding" not in received_job.progress
        assert completion_outbox.payload["progress"]["execution_owner_binding"] == received_owner

        def _owner_gate(payload: dict[str, Any]) -> dict[str, Any]:
            scorecard = build_quality_scorecard(
                canary_kind="production",
                job_id=job_id,
                run_id=received_job.run_id,
                execution_status=received_job.state,
                job_payload=payload,
                run_payload=None,
                provider_preflight=None,
                quality_evidence={},
            )
            return next(
                gate
                for gate in scorecard["quality_gates"]
                if gate["name"] == "serious_phase_barrier_owner_scope"
            )

        fresh_gate = _owner_gate(received_payload)
        assert fresh_gate["status"] == "fail"
        assert fresh_gate["code"] == "phase_barrier_owner_scope_not_established"

        def _source_scorecard(
            payload: dict[str, Any],
            *,
            source_job_id: str = job_id,
            source_run_id: str | None = None,
            quality_evidence: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            from tools.ops_runners.runtime.canary_evidence import (
                _build_canary_scorecard,
            )

            return _build_canary_scorecard(
                owner_source_context=(app, client),
                canary_kind="production",
                job_id=source_job_id,
                run_id=received_job.run_id if source_run_id is None else source_run_id,
                execution_status=received_job.state,
                job_payload=payload,
                run_payload=None,
                provider_preflight=None,
                quality_evidence=quality_evidence or {},
                quality_scorecard_ref="quality_evidence/quality_scorecard.json",
                quality_evidence_bundle_path=".canary/owner-source-integration-test",
            )

        from tools.ops_runners.runtime import canary_evidence as canary_evidence_module

        source_scorecards: list[dict[str, Any]] = []
        original_canary_scorecard_builder = canary_evidence_module._build_canary_scorecard

        def _capture_assembled_scorecard(**kwargs: Any) -> dict[str, Any]:
            scorecard = original_canary_scorecard_builder(**kwargs)
            source_scorecards.append(scorecard)
            return scorecard

        monkeypatch.setattr(
            canary_evidence_module,
            "_build_canary_scorecard",
            _capture_assembled_scorecard,
        )
        assembled_bundle = canary_evidence_module.assemble_canary_evidence(
            output_root=tmp_path,
            output_dir=tmp_path / "owner-source-assembled",
            canary_kind="production",
            command_metadata={"argv": ["policyos-canary", "--real"]},
            job_payload=received_payload,
            quality_evidence={},
            provider_preflight={"status": "skipped"},
            _scorecard_owner_source=(app, client),
        )
        assert assembled_bundle.is_dir()
        assert len(source_scorecards) == 2
        source_scorecard = source_scorecards[0]
        for repeated_scorecard in source_scorecards:
            repeated_owner_gate = next(
                gate
                for gate in repeated_scorecard["quality_gates"]
                if gate["name"] == "serious_phase_barrier_owner_scope"
            )
            assert repeated_owner_gate["status"] == "pass"
            assert repeated_owner_gate["code"] == "phase_barrier_owner_scope_reconciled"
        source_owner_gate = next(
            gate
            for gate in source_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        source_intent_gate = next(
            gate
            for gate in source_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_intent_binding"
        )
        assert source_owner_gate["status"] == "pass"
        assert source_owner_gate["code"] == "phase_barrier_owner_scope_reconciled"
        assert source_intent_gate["status"] == "fail"
        assert source_intent_gate["code"] == "run_intent_binding_incomplete"
        assert source_scorecard["quality_status"] == "fail"

        # The valid terminal outbox contains the complete producer-owned identity
        # envelope. Every member must reconcile to the completed job row, while
        # extra fields remain a refusal rather than being ignored.
        from polisyos.runtime.http.services.control_plane_store import (
            _control_job_outbox_identity_envelope,
        )

        expected_outbox_envelope = {
            "job_id": persisted_job.job_id,
            "job_kind": persisted_job.kind,
            "run_id": persisted_job.run_id,
            "pipeline_id": persisted_job.pipeline_id,
            "effective_execution_profile": persisted_job.effective_execution_profile,
        }
        assert _control_job_outbox_identity_envelope(persisted_job) == expected_outbox_envelope
        assert {
            field: completion_outbox.payload[field] for field in expected_outbox_envelope
        } == expected_outbox_envelope
        debug_service = runtime_context.debug
        original_control_job_store = debug_service._producer_control_job_store
        assert original_control_job_store is control_store
        assert debug_service._producer_control_job_store is control_service._control_store

        def _assert_completion_outbox_refused(payload: dict[str, Any]) -> None:
            reader_calls: list[str] = []
            original_completed_outbox_reader = (
                original_control_job_store.get_job_completed_outbox_event
            )

            def _read_overridden_completed_outbox(requested_job_id: str) -> Any:
                reader_calls.append(requested_job_id)
                outbox = original_completed_outbox_reader(requested_job_id)
                if requested_job_id != job_id or outbox is None:
                    return outbox
                assert outbox.event_id == completion_outbox.event_id
                assert outbox.payload == completion_outbox.payload
                assert payload != completion_outbox.payload
                return replace(outbox, payload=deepcopy(payload))

            with monkeypatch.context() as outbox_override:
                # Keep the installed service graph intact and override only the
                # real store's response so the owner join reads this mutation.
                outbox_override.setattr(
                    original_control_job_store,
                    "get_job_completed_outbox_event",
                    _read_overridden_completed_outbox,
                )
                assert debug_service._producer_control_job_store is control_service._control_store
                rejected_scorecard = _source_scorecard(received_payload)

            assert reader_calls == [job_id]
            assert debug_service._producer_control_job_store is control_service._control_store
            rejected_owner_gate = next(
                gate
                for gate in rejected_scorecard["quality_gates"]
                if gate["name"] == "serious_phase_barrier_owner_scope"
            )
            assert rejected_owner_gate["status"] == "fail"
            assert rejected_owner_gate["code"] == "phase_barrier_owner_scope_not_established"
            assert (
                "runtime_owner_source_service_graph_mismatch" not in rejected_owner_gate["message"]
            )

        for field, expected_value in expected_outbox_envelope.items():
            missing_envelope_payload = deepcopy(completion_outbox.payload)
            missing_envelope_payload.pop(field)
            _assert_completion_outbox_refused(missing_envelope_payload)

            mismatched_envelope_payload = deepcopy(completion_outbox.payload)
            mismatched_envelope_payload[field] = (
                "forged-envelope-value" if expected_value is None else f"{expected_value}:forged"
            )
            _assert_completion_outbox_refused(mismatched_envelope_payload)

        mismatched_progress_payload = deepcopy(completion_outbox.payload)
        mismatched_progress_owner = mismatched_progress_payload["progress"][
            "execution_owner_binding"
        ]
        assert isinstance(mismatched_progress_owner, dict)
        mismatched_progress_owner["lease_owner"] = "forged-terminal-progress-owner"
        _assert_completion_outbox_refused(mismatched_progress_payload)

        unexpected_envelope_payload = deepcopy(completion_outbox.payload)
        unexpected_envelope_payload["unrecognized_owner_envelope_field"] = "forged"
        _assert_completion_outbox_refused(unexpected_envelope_payload)

        # A completed owner projection can carry the declared request omission,
        # but neither effective-profile barrier records nor an intent reconstructed
        # from that effective profile may turn the omission into authority.
        from polisyos.runtime.quality.phase_barriers import (
            PhaseBarrierId,
            PhaseBarrierRecord,
        )

        effective_profile = received_job.effective_execution_profile
        assert isinstance(effective_profile, str) and effective_profile
        omitted_profile_barriers = [
            PhaseBarrierRecord.pass_record(
                barrier_id=barrier_id,
                run_id=str(received_job.run_id),
                tenant_id=str(persisted_owner["tenant_id"]),
                profile=effective_profile,
                evidence_refs=(f"event://effective-profile/{barrier_id.value}",),
            ).model_dump(mode="json")
            for barrier_id in PhaseBarrierId.scorecard_required()
        ]
        omitted_profile_scorecard = _source_scorecard(
            received_payload,
            quality_evidence={"phase_barrier_records": omitted_profile_barriers},
        )
        omitted_profile_barrier_gate = next(
            gate
            for gate in omitted_profile_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barriers_closed"
        )
        omitted_profile_owner_gate = next(
            gate
            for gate in omitted_profile_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        omitted_profile_intent_gate = next(
            gate
            for gate in omitted_profile_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_intent_binding"
        )
        assert omitted_profile_barrier_gate["status"] == "fail"
        assert omitted_profile_barrier_gate["code"] == "phase_barrier_scope_mismatch"
        assert omitted_profile_owner_gate["status"] == "pass"
        assert omitted_profile_intent_gate["status"] == "fail"
        assert omitted_profile_intent_gate["code"] == "run_intent_binding_incomplete"

        forged_intent_payload = deepcopy(received_payload)
        forged_intent_payload["progress"]["run_intent_binding"] = {
            "run_id": str(received_job.run_id),
            "tenant_id": str(persisted_owner["tenant_id"]),
            "requested_profile": effective_profile,
            "policy_intent_ref": "sha256:" + "c" * 64,
            "time_context_ref": "sha256:" + "d" * 64,
            "same_input_closure_ref": "sha256:" + "e" * 64,
        }
        forged_intent_scorecard = _source_scorecard(forged_intent_payload)
        forged_intent_gate = next(
            gate
            for gate in forged_intent_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_intent_binding"
        )
        assert forged_intent_gate["status"] == "fail"
        assert forged_intent_gate["code"] == "run_intent_binding_incomplete"

        with monkeypatch.context() as missing_terminal_reader:
            # Keep the bound store object and service graph; make the required
            # reader unavailable on that exact owner so its typed refusal runs.
            missing_terminal_reader.setattr(
                original_control_job_store,
                "get_job_terminal_source_event_record",
                None,
            )
            assert debug_service._producer_control_job_store is control_service._control_store
            missing_reader_scorecard = _source_scorecard(received_payload)
        assert debug_service._producer_control_job_store is control_service._control_store
        missing_reader_gate = next(
            gate
            for gate in missing_reader_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert missing_reader_gate["status"] == "fail"
        assert missing_reader_gate["code"] == "phase_barrier_owner_scope_not_established"
        assert (
            "control_job_source_reader_unavailable:get_job_terminal_source_event_record"
            in missing_reader_gate["message"]
        )
        assert "runtime_owner_source_service_graph_mismatch" not in missing_reader_gate["message"]

        forged_payload = deepcopy(received_payload)
        forged_owner = forged_payload["progress"]["execution_owner_binding"]
        forged_owner["lease_owner"] = "worker-forged-after-terminal-read"
        forged_gate = _owner_gate(forged_payload)
        assert forged_gate["status"] == "fail"
        assert forged_gate["code"] == "phase_barrier_owner_scope_not_established"
        forged_source_scorecard = _source_scorecard(forged_payload)
        forged_source_gate = next(
            gate
            for gate in forged_source_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert forged_source_gate["status"] == "fail"
        assert forged_source_gate["code"] == "phase_barrier_owner_scope_not_established"

        stale_run_index_misses: list[str] = []

        def _assert_completed_sibling_is_missing_before_refresh(
            completed_job: Any, candidate_run_index: Any, core_run_id: str
        ) -> None:
            assert completed_job.state == "completed"
            assert str(completed_job.progress["core_run_id"]) == core_run_id
            assert candidate_run_index is run_index
            assert core_run_id != str(ordinary_run["run_id"])
            run_dir = candidate_run_index._core_runs_root / core_run_id
            trace_path = run_dir / "trace.jsonl"
            assert trace_path.is_file() and trace_path.stat().st_size > 0
            with pytest.raises(KeyError):
                candidate_run_index.get_run(core_run_id)
            stale_run_index_misses.append(core_run_id)

        sibling_run = submit_ordinary_nl_post(
            env,
            request="Compare a sibling liquidity-support execution.",
            before_run_index_refresh=_assert_completed_sibling_is_missing_before_refresh,
        )
        assert stale_run_index_misses == [str(sibling_run["run_id"])]
        assert sibling_run["run"].run_id == sibling_run["run_id"]
        sibling_job_id = str(sibling_run["job_id"])
        sibling_record = control_store.get_job(sibling_job_id)
        sibling_outbox = control_store.get_job_completed_outbox_event(sibling_job_id)
        assert sibling_record is not None and sibling_outbox is not None
        sibling_response = client.get(f"/api/v1/control/jobs/{sibling_job_id}")
        assert sibling_response.status_code == 200, sibling_response.text
        sibling_job = ControlJobResponse.model_validate(sibling_response.json())
        # Durable completion state remains the exact progress snapshot written by
        # the terminal event. The outward GET independently replays current normative
        # source binding and may add a typed refusal projection without mutating either
        # durable source.
        assert sibling_record.progress == sibling_outbox.payload["progress"]
        sibling_normative_projection_fields = {
            "normative_head_limitation",
            "normative_disposition",
            "normative_disposition_ref",
        }
        assert sibling_normative_projection_fields.isdisjoint(sibling_record.progress)
        assert (
            set(sibling_job.progress) - set(sibling_record.progress)
            == sibling_normative_projection_fields
        )
        assert set(sibling_job.progress) == (
            set(sibling_record.progress) | sibling_normative_projection_fields
        )
        assert {
            key: sibling_job.progress[key] for key in sibling_record.progress
        } == sibling_record.progress
        assert (
            sibling_job.progress["normative_head_limitation"]
            == "normative_evidence_owned_run_source_mismatch"
        )
        sibling_disposition = sibling_job.progress["normative_disposition"]
        assert isinstance(sibling_disposition, dict)
        assert sibling_disposition["authorization_status"] == "blocked"
        assert sibling_disposition["source_status"] == "not_established"
        assert sibling_disposition["reason_codes"] == [
            "normative_evidence_owned_run_source_mismatch"
        ]
        assert sibling_disposition["ranked_recommendations"] == []
        assert sibling_disposition["candidate_fronts"] is None
        assert sibling_job.progress["normative_disposition_ref"] == (
            sibling_disposition.get("refusal_disposition_ref")
        )

        sibling_record_after_get = control_store.get_job(sibling_job_id)
        sibling_outbox_after_get = control_store.get_job_completed_outbox_event(sibling_job_id)
        assert sibling_record_after_get is not None and sibling_outbox_after_get is not None
        assert sibling_record_after_get.progress == sibling_record.progress
        assert sibling_outbox_after_get.payload["progress"] == sibling_outbox.payload["progress"]
        assert sibling_record_after_get.progress == sibling_outbox_after_get.payload["progress"]
        assert sibling_job.progress["stage"] == "n4_proposal_only"
        assert "runtime_quality_refs" not in sibling_job.progress
        sibling_payload = sibling_job.model_dump(mode="json")
        from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs

        sibling_authority_refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
            job_payload=sibling_payload
        )
        assert not sibling_authority_refs.rejections
        assert sibling_authority_refs.refs == {}
        assert sibling_authority_refs.selected_refs == {}

        # A sibling job paired with the first run ID must remain refused.
        sibling_mismatched_run_scorecard = _source_scorecard(
            sibling_payload,
            source_job_id=sibling_job_id,
        )
        sibling_mismatched_run_gate = next(
            gate
            for gate in sibling_mismatched_run_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert sibling_mismatched_run_gate["status"] == "fail"
        assert sibling_mismatched_run_gate["code"] == "phase_barrier_owner_scope_not_established"

        assert isinstance(sibling_job.run_id, str) and sibling_job.run_id
        sibling_source_scorecard = _source_scorecard(
            sibling_payload,
            source_job_id=sibling_job_id,
            source_run_id=sibling_job.run_id,
        )
        sibling_source_gate = next(
            gate
            for gate in sibling_source_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        sibling_source_intent_gate = next(
            gate
            for gate in sibling_source_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_intent_binding"
        )
        assert sibling_source_gate["status"] == "pass"
        assert sibling_source_gate["code"] == "phase_barrier_owner_scope_reconciled"
        assert sibling_source_intent_gate["status"] == "fail"
        assert sibling_source_intent_gate["code"] == "run_intent_binding_incomplete"

        tampered_outbox_payload = {
            **completion_outbox.payload,
            "lease_owner": "worker-forged-in-outbox",
        }
        control_store._execute(
            "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
            (
                json.dumps(tampered_outbox_payload, sort_keys=True),
                completion_outbox.event_id,
            ),
        )
        try:
            tampered_outbox_scorecard = _source_scorecard(received_payload)
        finally:
            control_store._execute(
                "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
                (
                    json.dumps(completion_outbox.payload, sort_keys=True),
                    completion_outbox.event_id,
                ),
            )
        tampered_outbox_gate = next(
            gate
            for gate in tampered_outbox_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert tampered_outbox_gate["status"] == "fail"
        assert tampered_outbox_gate["code"] == "phase_barrier_owner_scope_not_established"

        terminal_row = control_store.get_job(job_id)
        assert terminal_row is not None
        original_attempt = terminal_row.attempt
        control_store._execute(
            "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
            (original_attempt + 1, job_id),
        )
        changed_attempt_row = control_store.get_job(job_id)
        assert changed_attempt_row is not None
        assert changed_attempt_row.attempt == original_attempt + 1
        try:
            tampered_attempt_scorecard = _source_scorecard(received_payload)
        finally:
            control_store._execute(
                "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
                (original_attempt, job_id),
            )
        tampered_attempt_gate = next(
            gate
            for gate in tampered_attempt_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert tampered_attempt_gate["status"] == "fail"
        assert tampered_attempt_gate["code"] == "phase_barrier_owner_scope_not_established"

        original_lease_owner = terminal_row.lease_owner
        control_store._execute(
            "UPDATE control_jobs SET lease_owner = ? WHERE job_id = ?",
            ("worker-forged-in-terminal-row", job_id),
        )
        changed_lease_row = control_store.get_job(job_id)
        assert changed_lease_row is not None
        assert changed_lease_row.lease_owner == "worker-forged-in-terminal-row"
        try:
            tampered_lease_scorecard = _source_scorecard(received_payload)
        finally:
            control_store._execute(
                "UPDATE control_jobs SET lease_owner = ? WHERE job_id = ?",
                (original_lease_owner, job_id),
            )
        tampered_lease_gate = next(
            gate
            for gate in tampered_lease_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert tampered_lease_gate["status"] == "fail"
        assert tampered_lease_gate["code"] == "phase_barrier_owner_scope_not_established"

        terminal_event = control_store.get_job_terminal_source_event_record(job_id)
        assert terminal_event is not None
        tampered_event_payload = {
            **terminal_event.payload,
            "lease_owner": "worker-forged-in-event",
        }
        control_store._execute(
            "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
            (
                json.dumps(tampered_event_payload, sort_keys=True),
                terminal_event.event_id,
            ),
        )
        try:
            tampered_event_scorecard = _source_scorecard(received_payload)
        finally:
            control_store._execute(
                "UPDATE control_job_events SET payload_json = ? WHERE event_id = ?",
                (
                    json.dumps(terminal_event.payload, sort_keys=True),
                    terminal_event.event_id,
                ),
            )
        tampered_event_gate = next(
            gate
            for gate in tampered_event_scorecard["quality_gates"]
            if gate["name"] == "serious_phase_barrier_owner_scope"
        )
        assert tampered_event_gate["status"] == "fail"
        assert tampered_event_gate["code"] == "phase_barrier_owner_scope_not_established"

        progress = received_job.progress
        assert progress["execution_intent_band"] == "candidate_only"
        assert progress["status"] == "candidate_limited"
        assert progress["stage"] == "n4_proposal_only"
        assert progress["candidate_computation_status"] == "completed"
        assert progress["limitation_code"] == "cycle_substrate_context_unavailable"
        assert progress["candidate_proposal_limitation_code"] == (
            "cycle_substrate_context_unavailable"
        )
        candidate_proposal_ref = progress.get("candidate_proposal_ref")
        assert isinstance(candidate_proposal_ref, dict)
        candidate_artifact_ref = candidate_proposal_ref.get("artifact_ref")
        assert isinstance(candidate_artifact_ref, dict)
        assert candidate_artifact_ref.get("kind") == "runtime.quality.n4_candidate_proposal"
        assert candidate_artifact_ref.get("manifest_profile_sha256") is not None
        proposal_read = progress["generation_source_read_provenance"]
        assert proposal_read["selected_artifact_id"] == candidate_artifact_ref["artifact_id"]
        assert (
            proposal_read["selected_manifest_profile_sha256"]
            == candidate_artifact_ref["manifest_profile_sha256"]
        )
        assert proposal_read["source_materialization"] == "reader_materialized"
        assert proposal_read["producer_attestation_status"] == "not_established"
        assert progress["n5_status"] == "not_run"
        assert progress["n9_status"] == "not_run"
        assert progress["target_world_scope_currentness"] == "not_established"

        from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs

        authority_refs = RuntimeQualityAuthorityRefs.from_runtime_payloads(
            job_payload=received_job.model_dump(mode="json")
        )
        assert authority_refs.get_selected_ref("security_assurance_report_ref") is None
        core_run_id = str(ordinary_run["run_id"])
        runtime_context = ordinary_run["runtime_context"]
        run = ordinary_run["run"]
        details = run.details
        binding = ordinary_run["binding"]
        assert details.control_job_id == job_id
        assert details.run_id == core_run_id
        assert binding.run_id == str(job.run_id)
        assert binding.run_id != details.run_id
        assert details.execution_profile == job.effective_execution_profile
        settlement_store = env["app"].state.runtime_container.llm_producer_settlement_store
        records = settlement_store.list_producer_events_for_run_safe(binding)
        assert records
        assert all(record.key == f"nl-run:{job.run_id}" for record in records)
        assert all(record.run_binding == binding for record in records)
        assert binding.run_id == str(job.run_id)
        assert binding.control_job_id == job_id
        assert binding.profile_id == details.execution_profile == job.effective_execution_profile
        assert binding.tenant_id == execution_scope.get("tenant_id")
        assert binding.cell_id == execution_scope.get("cell_id")
        record_ids = [record.event_id for record in records]
        assert len(record_ids) == len(set(record_ids))
        assert n4_producer_clients
        assert any(client._used for client in n4_producer_clients)
        assert monetary_providers
        actual_origins = {record.cost_origin for record in records}
        assert actual_origins == {"reported", "estimated", "unknown", "reuse"}
        assert all(
            record.status == ("unknown" if record.cost_origin == "unknown" else "committed")
            for record in records
        )
        assert all(
            record.amount is None if record.cost_origin == "unknown" else record.amount is not None
            for record in records
        )
        provider_event_ids = {
            record.event_id for record in records if record.cost_origin != "reuse"
        }
        reuse_records = [record for record in records if record.cost_origin == "reuse"]
        assert reuse_records
        assert all(
            record.amount == Decimal(0) and record.origin_event_id in provider_event_ids
            for record in reuse_records
        )
        assert any(
            record.cost_origin == "reported" and record.amount == Decimal(0) for record in records
        )
        assert any(
            record.cost_origin == "estimated"
            and record.amount is not None
            and record.amount > Decimal(0)
            for record in records
        )
        assert any(record.cost_origin == "unknown" and record.amount is None for record in records)
        assert details.root_artifacts

        ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
        reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))

        # This synthetic HTTP transport exercises the configured Gateway client's local retry
        # path. Its reported amount is a test candidate, not provider invoice evidence.
        class _FakeResponse:
            def __init__(self, status: int, body: str, headers: dict[str, str]) -> None:
                self.status = status
                self._body = body
                self.headers = headers

            async def text(self) -> str:
                return self._body

        class _AsyncResponseContext:
            def __init__(self, response: _FakeResponse) -> None:
                self._response = response

            async def __aenter__(self) -> _FakeResponse:
                return self._response

            async def __aexit__(self, *_args: object) -> bool:
                return False

        class _RetrySession:
            def __init__(self) -> None:
                self.closed = False
                self.requests: list[dict[str, Any]] = []
                self._responses = [
                    _FakeResponse(
                        429,
                        json.dumps({"error": {"code": "rate_limit_exceeded"}}),
                        {"Retry-After": "0"},
                    ),
                    _FakeResponse(
                        200,
                        json.dumps(
                            {
                                "model": "provider-self-model",
                                "provider": "provider-self-label",
                                "choices": [
                                    {
                                        "message": {
                                            "role": "assistant",
                                            "content": "retry completed",
                                        }
                                    }
                                ],
                                "usage": {
                                    "prompt_tokens": 3,
                                    "completion_tokens": 2,
                                    "total_tokens": 5,
                                    "total_cost_usd": "0.125",
                                },
                            }
                        ),
                        {"x-request-id": "synthetic-retry-success"},
                    ),
                ]

            def post(self, *_args: object, **kwargs: Any) -> _AsyncResponseContext:
                self.requests.append(kwargs)
                return _AsyncResponseContext(self._responses[len(self.requests) - 1])

            async def close(self) -> None:
                self.closed = True

        retry_gateway = GatewayLLMClient(
            base_url="http://synthetic-provider.test/v1",
            api_key="synthetic-test-key",
            model="simulated-qwen",
            max_retries=1,
            provider_hint="synthetic_gateway",
        )
        retry_session = _RetrySession()
        retry_gateway._session = retry_session
        retry_observations: list[dict[str, Any]] = []
        retry_traced_client = TracedLLMClient(
            retry_gateway,
            model_name="simulated-qwen",
            run_id=str(job.run_id),
            provider_name="synthetic_gateway",
            call_observer=retry_observations.append,
            producer_settlement_store=reopened,
            producer_budget_key=f"nl-run:{job.run_id}",
        )

        async def _run_synthetic_retry() -> Any:
            try:
                with reopened.producer_run_binding_scope(binding, control_job_attempt=job.attempt):
                    return await retry_traced_client.generate(
                        user="Local synthetic retry candidate for the persisted run."
                    )
            finally:
                await retry_gateway.aclose()

        retry_response = asyncio.run(_run_synthetic_retry())
        retry_event = retry_response.settlement.event
        retry_ack = retry_response.settlement.ack
        retry_idempotency_keys = [
            str(request["headers"]["x-idempotency-key"]) for request in retry_session.requests
        ]
        assert len(retry_idempotency_keys) == 2
        assert retry_idempotency_keys[0] and retry_idempotency_keys[0] == retry_idempotency_keys[1]
        assert len(retry_observations) == 1
        assert retry_observations[0]["event_id"] == retry_event.event_id
        assert retry_event.cost_origin == "reported"
        assert retry_event.amount == Decimal("0.125")
        assert retry_event.model == "simulated-qwen"
        assert retry_event.provider == "synthetic_gateway"
        assert retry_ack.status == "committed"
        assert retry_ack.durability == "ledger"
        assert retry_ack.receipts == (retry_event.event_id,)
        records_after_retry = reopened.list_producer_events_for_run_safe(binding)
        assert {record.event_id for record in records_after_retry} - set(record_ids) == {
            retry_event.event_id
        }

        # This durable begin is the exact crash boundary: the provider intent
        # is written under the admitted run owner and no terminal settlement
        # follows before the ledger is reopened and read by a fresh GET.
        with reopened.producer_run_binding_scope(binding, control_job_attempt=job.attempt):
            pending = reopened.begin_producer_event_safe(
                "crash-after-begin:ordinary-nl-route",
                "a" * 64,
                key=f"nl-run:{job.run_id}",
                model="simulated-qwen",
                provider="simulated_gateway",
            )
        assert pending.status == "pending" and pending.amount is None

        # Exercise a real TTL cache producer after the ordinary route has issued
        # this exact run binding. Expiry must create a second provider settlement,
        # then survive a fresh reader of the same durable ledger.
        expiry_provider = _MonetarySimulatedProvider("simulated-qwen")
        expiry_cache = InMemoryPromptCache(maxsize=8, default_ttl_s=0.5)
        expiry_cached_client = CachingLLMClient(
            expiry_provider,
            cache=expiry_cache,
            model="simulated-qwen",
            ttl_s=0.5,
            inflight_timeout_s=10,
        )
        expiry_traced_client = TracedLLMClient(
            expiry_cached_client,
            model_name="simulated-qwen",
            run_id=str(job.run_id),
            provider_name="simulated_gateway",
            producer_settlement_store=reopened,
            producer_budget_key=f"nl-run:{job.run_id}",
        )

        async def _run_cache_expiry() -> tuple[Any, Any, Any]:
            with reopened.producer_run_binding_scope(binding, control_job_attempt=job.attempt):
                request = {"user": "R3 TTL expiry witness for the selected ordinary run."}
                first = await expiry_traced_client.generate(**request)
                reuse = await expiry_traced_client.generate(**request)
                await asyncio.sleep(0.6)
                expired = await expiry_traced_client.generate(**request)
            return first, reuse, expired

        expiry_first, expiry_reuse, expiry_second_provider = asyncio.run(_run_cache_expiry())
        expiry_first_event = expiry_first.settlement.event
        expiry_reuse_event = expiry_reuse.settlement.event
        expiry_second_event = expiry_second_provider.settlement.event
        assert expiry_provider.calls == 2
        expiry_stats = expiry_cache.stats()
        assert expiry_stats["hits"] == 1
        assert expiry_stats["misses"] == 2
        assert expiry_stats["expired"] == 1
        assert expiry_stats["puts"] == 2
        assert expiry_first_event.cost_origin == "reported"
        assert expiry_first_event.amount == Decimal(0)
        assert expiry_reuse_event.cost_origin == "reuse"
        assert expiry_reuse_event.amount == Decimal(0)
        assert expiry_reuse_event.origin_event_id == expiry_first_event.event_id
        assert expiry_second_event.cost_origin == "estimated"
        assert expiry_second_event.amount is not None
        assert expiry_second_event.amount > Decimal(0)
        assert expiry_second_event.event_id != expiry_first_event.event_id
        assert expiry_second_event.request_digest == expiry_first_event.request_digest
        assert expiry_first_event.model == expiry_second_event.model == "simulated-qwen"
        assert expiry_first_event.provider == expiry_second_event.provider == "simulated_gateway"
        assert all(
            response.settlement.ack.status == "committed"
            and response.settlement.ack.durability == "ledger"
            for response in (expiry_first, expiry_reuse, expiry_second_provider)
        )
        expiry_event_ids = {
            expiry_first_event.event_id,
            expiry_reuse_event.event_id,
            expiry_second_event.event_id,
        }
        assert len(expiry_event_ids) == 3
        expiry_rows = reopened.list_producer_events_for_run_safe(binding)
        expiry_rows_by_id = {row.event_id: row for row in expiry_rows}
        assert expiry_event_ids <= set(expiry_rows_by_id)
        assert all(
            expiry_rows_by_id[event_id].run_binding == binding for event_id in expiry_event_ids
        )

        fresh_reader = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        assert fresh_reader is not reopened
        assert fresh_reader.settlement_owner_identity == reopened.settlement_owner_identity
        fresh_rows = fresh_reader.list_producer_events_for_run_safe(binding)
        assert expiry_event_ids <= {row.event_id for row in fresh_rows}
        runtime_context.debug.bind_producer_settlement_store(fresh_reader)
        tampered_run = replace(
            run,
            details=run.details.model_copy(update={"control_job_id": "foreign-job"}),
        )
        rejected_steps, rejection = runtime_context.debug._agent_steps_from_producer_ledger(
            tampered_run
        )
        assert rejected_steps == []
        assert rejection == ["llm_producer_control_job_owner_not_established"]

        selected_binding, selected_binding_note = (
            runtime_context.debug._producer_run_binding_for_indexed_run(run)
        )
        assert selected_binding_note is None
        assert selected_binding is not None
        assert selected_binding == binding

        # Same run, tenant, cell and profile; only the persisted ControlJob owner differs.
        # Its amount aliases a real reported row, so the API must select by full ownership.
        assert retry_event.amount is not None
        foreign_binding = BudgetLedgerProducerRunBinding(
            run_id=selected_binding.run_id,
            tenant_id=selected_binding.tenant_id,
            cell_id=selected_binding.cell_id,
            profile_id=selected_binding.profile_id,
            control_job_id="foreign-job",
        )
        foreign_event_id = "llm-provider:r3-foreign-owner-same-cost"
        foreign_request_digest = "b" * 64
        foreign_payload_digest = "c" * 64
        foreign_key = f"nl-run:{foreign_binding.run_id}"
        with reopened.producer_run_binding_scope(foreign_binding):
            foreign_intent = reopened.begin_producer_event_safe(
                foreign_event_id,
                foreign_request_digest,
                key=foreign_key,
                model="simulated-qwen",
                provider="synthetic_gateway",
            )
            foreign_record = reopened.settle_producer_event_safe(
                foreign_event_id,
                foreign_request_digest,
                foreign_payload_digest,
                key=foreign_key,
                model="simulated-qwen",
                provider="synthetic_gateway",
                amount=retry_event.amount,
                cost_origin="reported",
            )
        assert foreign_intent.status == "pending"
        assert foreign_record.status == "committed"
        assert foreign_record.amount == retry_event.amount
        assert foreign_record.model == retry_event.model == "simulated-qwen"
        assert foreign_record.provider == retry_event.provider == "synthetic_gateway"
        assert foreign_record.run_binding == foreign_binding

        # An owner-bound row from a writer without lease-attempt context remains unassigned.
        with reopened.producer_run_binding_scope(binding):
            legacy_event = reopened.settle_producer_event_safe(
                "llm-provider:r3-unattributed-legacy-row",
                "d" * 64,
                "e" * 64,
                key=f"nl-run:{selected_binding.run_id}",
                model="simulated-qwen",
                provider="synthetic_gateway",
                amount=Decimal("0.01"),
                cost_origin="reported",
            )
        assert legacy_event.run_binding == selected_binding
        assert legacy_event.control_job_attempt is None
        assert legacy_event.pre_admission_attempt_id is None

        pre_admission_attempt_id = "b" * 32
        with reopened.producer_run_binding_scope(
            binding,
            pre_admission_attempt_id=pre_admission_attempt_id,
        ):
            pre_admission_record = reopened.settle_producer_event_safe(
                "llm-provider:r3-pre-admission-attempt",
                "1" * 64,
                "2" * 64,
                key=f"nl-run:{selected_binding.run_id}",
                model="simulated-qwen",
                provider="synthetic_gateway",
                amount=Decimal("0.02"),
                cost_origin="estimated",
            )
        assert pre_admission_record.run_binding == selected_binding
        assert pre_admission_record.control_job_attempt is None
        assert pre_admission_record.pre_admission_attempt_id == pre_admission_attempt_id

        # Two writes share the stable run binding but carry different persisted lease attempts.
        second_attempt_event = "llm-provider:r3-control-job-attempt-two"
        second_attempt_request = "f" * 64
        second_attempt_payload = "a" * 64
        with reopened.producer_run_binding_scope(binding, control_job_attempt=2):
            reopened.begin_producer_event_safe(
                second_attempt_event,
                second_attempt_request,
                key=f"nl-run:{binding.run_id}",
                model="simulated-qwen",
                provider="synthetic_gateway",
            )
            second_attempt_record = reopened.settle_producer_event_safe(
                second_attempt_event,
                second_attempt_request,
                second_attempt_payload,
                key=f"nl-run:{binding.run_id}",
                model="simulated-qwen",
                provider="synthetic_gateway",
                amount=Decimal("0.03"),
                cost_origin="reported",
            )
        assert second_attempt_record.control_job_attempt == 2
        assert second_attempt_record.run_binding == selected_binding

        original_state_loader = runtime_context.debug._load_experiment_state_payload

        def _load_state_with_malformed_variant_details(ref: Any) -> dict[str, Any]:
            payload = deepcopy(original_state_loader(ref))
            params = payload.setdefault("params", {})
            assert isinstance(params, dict)
            variants = params.setdefault("llm_model_variants", [])
            assert isinstance(variants, list)
            variants.append(
                {
                    "model": "diagnostic-only",
                    "model_variant_id": "diagnostic-only",
                    "status": "completed",
                    "steps": [
                        {
                            "agent": "diagnostic",
                            "action": "inspection",
                            "details": False,
                        }
                    ],
                }
            )
            return payload

        monkeypatch.setattr(
            runtime_context.debug,
            "_load_experiment_state_payload",
            _load_state_with_malformed_variant_details,
        )
        try:
            response = client.get(f"/api/v1/runs/{core_run_id}/agents")
        finally:
            monkeypatch.setattr(
                runtime_context.debug,
                "_load_experiment_state_payload",
                original_state_loader,
            )
        assert response.status_code == 200, response.text
        response_payload = response.json()
        wire_pipeline = response_payload["pipeline"]
        accepted = AgentPipelineResponse.model_validate(response_payload)
        pipeline = accepted.pipeline
        assert pipeline.owner_control_job_attempt == job.attempt
        assert pipeline.cost_usd == wire_pipeline["cost_usd"]
        assert pipeline.reported_cost_usd == pytest.approx(wire_pipeline["reported_cost_usd"])
        assert pipeline.estimated_cost_usd == pytest.approx(wire_pipeline["estimated_cost_usd"])
        assert dict(pipeline.cost_origin_counts) == wire_pipeline["cost_origin_counts"]
        assert dict(pipeline.settlement_status_counts) == wire_pipeline["settlement_status_counts"]
        assert pipeline._verified_owner_control_job_attempt is None
        assert pipeline._verified_cost_event_basis_sha256 is None
        served_events = [
            event
            for attempt in pipeline.attempts
            for step in attempt.steps
            for event in step.cost_events
        ]
        served_by_id = {event.event_id: event for event in served_events}
        assert len(served_by_id) == len(served_events)
        owner_records = fresh_reader.list_producer_events_for_run_safe(selected_binding)
        owner_records_by_id = {record.event_id: record for record in owner_records}
        assert len(owner_records_by_id) == len(owner_records)
        assert all(record.run_binding == selected_binding for record in owner_records)
        assert foreign_record.event_id not in owner_records_by_id
        assert foreign_record.event_id not in served_by_id
        assert pending.event_id in served_by_id
        current_records = [
            record
            for record in owner_records
            if record.control_job_attempt == job.attempt and record.pre_admission_attempt_id is None
        ]
        unattributed_records = [
            record for record in owner_records if record.control_job_attempt is None
        ]
        other_attempt_records = [
            record
            for record in owner_records
            if record.control_job_attempt is not None and record.control_job_attempt != job.attempt
        ]
        unassigned_by_id = {event.event_id: event for event in pipeline.unattributed_cost_events}
        assert set(served_by_id) == {record.event_id for record in current_records}
        assert set(unassigned_by_id) == {record.event_id for record in unattributed_records}
        assert second_attempt_record in other_attempt_records
        assert legacy_event.event_id in unassigned_by_id
        assert pre_admission_record.event_id in unassigned_by_id
        assert (
            unassigned_by_id[pre_admission_record.event_id].pre_admission_attempt_id
            == pre_admission_attempt_id
        )
        assert unassigned_by_id[legacy_event.event_id].amount == Decimal("0.01")
        assert second_attempt_event not in served_by_id
        assert "llm_producer_events_from_other_control_job_attempts_excluded_from_core_run" in (
            pipeline.notes
        )
        assert (
            "llm_producer_events_with_unknown_or_pre_admission_attempt_unassigned" in pipeline.notes
        )
        assert "llm_model_variant_step_details_invalid_type_not_projected" in pipeline.notes

        # A fresh GET must not project durable cost as current when the persisted
        # ControlJob owner pointer omits its lease attempt.
        diagnostic_job = control_store.get_job(job_id)
        assert diagnostic_job is not None
        diagnostic_progress_before = dict(diagnostic_job.progress)
        diagnostic_progress_without_attempt = dict(diagnostic_progress_before)
        del diagnostic_progress_without_attempt["core_run_attempt"]
        control_store.upsert_progress(
            job_id=job_id,
            progress=diagnostic_progress_without_attempt,
        )
        try:
            missing_attempt_response = client.get(f"/api/v1/runs/{core_run_id}/agents")
        finally:
            control_store.upsert_progress(
                job_id=job_id,
                progress=diagnostic_progress_before,
            )
        assert missing_attempt_response.status_code == 200, missing_attempt_response.text
        missing_attempt_wire_pipeline = missing_attempt_response.json()["pipeline"]
        assert missing_attempt_wire_pipeline["owner_control_job_attempt"] is None
        assert (
            "llm_producer_control_job_owner_not_established"
            in missing_attempt_wire_pipeline["notes"]
        )
        attributed_ledger_events_without_owner = [
            event
            for attempt in missing_attempt_wire_pipeline["attempts"]
            for step in attempt["steps"]
            for event in step["cost_events"]
            if event.get("durability") == "ledger" and event.get("control_job_attempt") is not None
        ]
        assert attributed_ledger_events_without_owner == []

        assert all(event.durability == "ledger" for event in served_events)
        for record in current_records:
            served_record = served_by_id[record.event_id]
            assert served_record.origin_event_id == record.origin_event_id
            assert served_record.cost_origin == record.cost_origin
            assert served_record.settlement_status == record.status
            assert served_record.durability == "ledger"
            assert served_record.receipts == (
                (record.event_id,) if record.status == "committed" else ()
            )
            assert served_record.amount == record.amount
            assert served_record.payload_digest == record.payload_digest
            assert served_record.model == record.model
            assert served_record.provider == record.provider
            assert served_record.control_job_attempt == job.attempt
        for record in unattributed_records:
            assert unassigned_by_id[record.event_id].control_job_attempt is None
            assert unassigned_by_id[record.event_id].pre_admission_attempt_id == (
                record.pre_admission_attempt_id
            )
        pending_view = served_by_id[pending.event_id]
        assert pending_view.settlement_status == "pending"
        assert pending_view.cost_origin == "unknown"
        assert pending_view.amount is None
        assert pending_view.durability == "ledger"
        assert pending_view.receipts == ()
        assert wire_pipeline["cost_usd"] is None
        expected_origin_counts: dict[str, int] = {}
        expected_status_counts: dict[str, int] = {}
        reported_amount = Decimal(0)
        estimated_amount = Decimal(0)
        known_total = Decimal(0)
        total_is_unknown = False
        visible_records = current_records
        for record in visible_records:
            expected_origin_counts[record.cost_origin] = (
                expected_origin_counts.get(record.cost_origin, 0) + 1
            )
            expected_status_counts[record.status] = expected_status_counts.get(record.status, 0) + 1
            if record.cost_origin == "reported" and record.amount is not None:
                reported_amount += record.amount
            if record.cost_origin == "estimated" and record.amount is not None:
                estimated_amount += record.amount
            if (
                record.cost_origin == "unknown"
                or record.status in {"pending", "unknown"}
                or record.amount is None
            ):
                total_is_unknown = True
            elif record.cost_origin in {"reported", "estimated", "reuse"}:
                known_total += record.amount
        assert expected_origin_counts == wire_pipeline["cost_origin_counts"]
        assert expected_status_counts == wire_pipeline["settlement_status_counts"]
        assert wire_pipeline["reported_cost_usd"] == pytest.approx(float(reported_amount), abs=1e-9)
        assert wire_pipeline["estimated_cost_usd"] == pytest.approx(
            float(estimated_amount), abs=1e-9
        )
        if total_is_unknown:
            assert wire_pipeline["cost_usd"] is None
        else:
            assert wire_pipeline["cost_usd"] == pytest.approx(float(known_total), abs=1e-9)
        assert expected_origin_counts["reported"] > 0
        assert expected_origin_counts["estimated"] > 0
        assert expected_origin_counts["unknown"] > 0
        assert expected_origin_counts["reuse"] > 0
        assert any(
            record.cost_origin == "reported" and record.amount == Decimal(0)
            for record in owner_records
        )
        assert any(
            record.cost_origin == "unknown" and record.status == "unknown" and record.amount is None
            for record in visible_records
        )
        assert pending_view.model == "simulated-qwen"

        # A scalar from the persisted model-variant source must survive when its
        # step identity merges with an audit/timeline step.
        existing_step = next(
            step
            for attempt in pipeline.attempts
            for step in attempt.steps
            if step.agent != "llm_producer_settlement"
        )
        original_load_state_for_merge = runtime_context.debug._load_experiment_state_payload
        variant_index = existing_step.attempt - 1
        duplicate_step_state = [None] * variant_index + [
            {
                "model": existing_step.model or "legacy-model",
                "model_variant_id": existing_step.model_variant_id,
                "status": "completed",
                "steps": [
                    {
                        "action": existing_step.action,
                        "agent": existing_step.agent,
                        "attempt": existing_step.attempt,
                        "cost_usd": 0.91,
                        "model": existing_step.model,
                        "model_variant_id": existing_step.model_variant_id,
                        "timestamp": (
                            existing_step.timestamp.isoformat()
                            if existing_step.timestamp is not None
                            else None
                        ),
                    }
                ],
            }
        ]

        def _load_state_with_duplicate_step(ref: Any) -> dict[str, Any]:
            payload = deepcopy(original_load_state_for_merge(ref))
            params = payload.setdefault("params", {})
            assert isinstance(params, dict)
            params["llm_model_variants"] = duplicate_step_state
            return payload

        monkeypatch.setattr(
            runtime_context.debug,
            "_load_experiment_state_payload",
            _load_state_with_duplicate_step,
        )
        try:
            duplicate_step_response = client.get(f"/api/v1/runs/{core_run_id}/agents")
        finally:
            monkeypatch.setattr(
                runtime_context.debug,
                "_load_experiment_state_payload",
                original_load_state_for_merge,
            )
        assert duplicate_step_response.status_code == 200, duplicate_step_response.text
        duplicate_step_pipeline = AgentPipelineResponse.model_validate(
            duplicate_step_response.json()
        ).pipeline
        assert any(
            row.claimed_value_usd == pytest.approx(0.91)
            and row.agent == existing_step.agent
            and row.attempt == existing_step.attempt
            and row.scope == "not_established"
            for row in duplicate_step_pipeline.unattributed_cost_scalars
        )

        from polisyos.core.contracts.runtime import AgentPipelineView

        unassigned_only_summary = AgentPipelineView.model_validate(
            {
                "run_id": core_run_id,
                "source_kind": run.source_kind,
                "attempts": [],
                "unattributed_cost_events": [
                    unassigned_by_id[legacy_event.event_id].model_dump(mode="json")
                ],
                "cost_usd": 0.01,
                "reported_cost_usd": 0.01,
                "estimated_cost_usd": 0.0,
                "cost_origin_counts": {"reported": 1},
                "settlement_status_counts": {"committed": 1},
            }
        )
        assert unassigned_only_summary.cost_usd is None
        assert unassigned_only_summary.reported_cost_usd is None
        assert unassigned_only_summary.cost_origin_counts == {}
        assert {
            (row.source_field, row.claimed_value_usd, row.scope)
            for row in unassigned_only_summary.unattributed_cost_scalars
        } == {
            ("cost_usd", 0.01, "not_established"),
            ("reported_cost_usd", 0.01, "not_established"),
            ("estimated_cost_usd", 0.0, "not_established"),
        }

        from polisyos.runtime.http.services.adapters.core_run import (
            derive_control_job_core_run_id,
        )

        persisted_job = control_store.get_job(job_id)
        assert persisted_job is not None
        original_progress = dict(persisted_job.progress)
        original_attempt = persisted_job.attempt
        attempt_two_core_run_id = derive_control_job_core_run_id(
            job_id=job_id,
            control_run_id=str(persisted_job.run_id),
            attempt=2,
        )
        attempt_two_run = replace(
            run,
            run_id=attempt_two_core_run_id,
            details=run.details.model_copy(update={"run_id": attempt_two_core_run_id}),
        )
        run_index = runtime_context.run_index
        original_get_run = run_index.get_run
        progress_for_attempt_two = {
            **original_progress,
            "core_run_id": attempt_two_core_run_id,
            "core_run_attempt": 2,
        }
        try:
            control_store._execute(
                "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
                (2, job_id),
            )
            control_store.upsert_progress(job_id=job_id, progress=progress_for_attempt_two)

            def _get_attempt_two_run(requested_id: str) -> Any:
                if requested_id == attempt_two_core_run_id:
                    return attempt_two_run
                return original_get_run(requested_id)

            monkeypatch.setattr(run_index, "get_run", _get_attempt_two_run)
            stale_attempt_record = next(
                record
                for record in current_records
                if record.control_job_attempt == original_attempt
                and record.pre_admission_attempt_id is None
            )
            stale_event_payload = served_by_id[stale_attempt_record.event_id].model_dump(
                mode="json"
            )
            original_load_state = runtime_context.debug._load_experiment_state_payload

            def _load_state_with_same_label_stale_attempt(ref: Any) -> dict[str, Any]:
                payload = deepcopy(original_load_state(ref))
                params = payload.setdefault("params", {})
                assert isinstance(params, dict)
                params["llm_model_variants"] = [
                    {
                        "model": "legacy-top-level-model",
                        "model_variant_id": "legacy-top-level-variant",
                        "status": "completed",
                        "cost_usd": 0.41,
                    },
                    {
                        "model": "legacy-nested-model",
                        "model_variant_id": "legacy-nested-variant",
                        "cost_usd": 0.53,
                        "reported_cost_usd": 0.52,
                        "estimated_cost_usd": 0.51,
                        "steps": [
                            {
                                "agent": "llm_producer_settlement",
                                "action": "durable_ledger",
                                "status": "info",
                                "cost_events": [stale_event_payload],
                            },
                            {
                                "agent": "model_variant",
                                "action": "legacy_scalar",
                                "status": "info",
                                "cost_usd": 0.29,
                                "details": {
                                    "nested": {
                                        "cost_usd": 0.73,
                                        "annotation": "diagnostic $9 only",
                                    }
                                },
                            },
                        ],
                    },
                ]
                return payload

            monkeypatch.setattr(
                runtime_context.debug,
                "_load_experiment_state_payload",
                _load_state_with_same_label_stale_attempt,
            )
            try:
                attempt_two_response = client.get(f"/api/v1/runs/{attempt_two_core_run_id}/agents")
            finally:
                monkeypatch.setattr(
                    runtime_context.debug,
                    "_load_experiment_state_payload",
                    original_load_state,
                )
            assert stale_attempt_record.control_job_attempt == original_attempt
            assert stale_attempt_record.control_job_attempt != 2
            assert attempt_two_response.status_code == 200, attempt_two_response.text
            attempt_two_payload = attempt_two_response.json()
            attempt_two_wire_pipeline = attempt_two_payload["pipeline"]
            attempt_two_pipeline = AgentPipelineResponse.model_validate(
                attempt_two_payload
            ).pipeline
            attempt_two_served_ids = {
                event.event_id
                for attempt in attempt_two_pipeline.attempts
                for step in attempt.steps
                for event in step.cost_events
            }
            assert attempt_two_served_ids == {second_attempt_event}
            assert stale_attempt_record.event_id not in attempt_two_served_ids
            assert second_attempt_record.control_job_attempt == 2
            assert attempt_two_wire_pipeline["owner_control_job_attempt"] == 2
            assert {
                attempt.attempt
                for attempt in attempt_two_pipeline.attempts
                if any(
                    event.event_id == second_attempt_event
                    for step in attempt.steps
                    for event in step.cost_events
                )
            } == {1}
            assert not (attempt_two_served_ids & {record.event_id for record in current_records})
            assert {
                legacy_event.event_id,
                pre_admission_record.event_id,
            } <= {event.event_id for event in attempt_two_pipeline.unattributed_cost_events}
            assert (
                "llm_producer_events_from_other_control_job_attempts_excluded_from_core_run"
                in attempt_two_pipeline.notes
            )
            assert attempt_two_wire_pipeline["cost_usd"] == pytest.approx(0.03, abs=1e-9)
            assert attempt_two_wire_pipeline["reported_cost_usd"] == pytest.approx(0.03, abs=1e-9)
            assert attempt_two_wire_pipeline["cost_origin_counts"] == {"reported": 1}
            nested_parent_claims = {
                (row.source_field, row.claimed_value_usd, row.source_index, row.scope)
                for row in attempt_two_pipeline.unattributed_cost_scalars
                if row.source_kind == "performance_summary_variant_row"
            }
            assert nested_parent_claims == {
                ("cost_usd", 0.53, 1, "not_established"),
                ("reported_cost_usd", 0.52, 1, "not_established"),
                ("estimated_cost_usd", 0.51, 1, "not_established"),
            }
            unassigned_scalars = {
                (
                    row.source_kind,
                    row.model_variant_id,
                    row.claimed_value_usd,
                    row.scope,
                )
                for row in attempt_two_pipeline.unattributed_cost_scalars
            }
            assert (
                "step_summary",
                "legacy-top-level-variant",
                0.41,
                "not_established",
            ) in unassigned_scalars
            assert (
                "step_summary",
                "legacy-nested-variant",
                0.29,
                "not_established",
            ) in unassigned_scalars
            nested_details_step = next(
                step
                for attempt in attempt_two_pipeline.attempts
                for step in attempt.steps
                if step.model_variant_id == "legacy-nested-variant"
                and step.action == "legacy_scalar"
            )
            assert nested_details_step.details_cost_scope == "not_established"
            assert nested_details_step.details == {
                "nested": {"cost_usd": 0.73, "annotation": "diagnostic $9 only"}
            }
            assert nested_details_step.cost_usd is None
            assert {row.scope for row in attempt_two_pipeline.unattributed_cost_scalars} == {
                "not_established"
            }
            owner_rows_after_second_attempt = fresh_reader.list_producer_events_for_run_safe(
                selected_binding
            )
            assert {record.event_id for record in current_records} <= {
                record.event_id for record in owner_rows_after_second_attempt
            }
            assert second_attempt_event in {
                record.event_id for record in owner_rows_after_second_attempt
            }

            progress_without_attempt = dict(progress_for_attempt_two)
            del progress_without_attempt["core_run_attempt"]
            control_store.upsert_progress(job_id=job_id, progress=progress_without_attempt)
            rejected_projection = runtime_context.debug._producer_ledger_projection_for_indexed_run(
                attempt_two_run
            )
            assert rejected_projection[0] == []
            assert rejected_projection[1] == []
            assert rejected_projection[3] is None
            assert rejected_projection[4] == ["llm_producer_control_job_owner_not_established"]

            assert rejected_projection[4] == ["llm_producer_control_job_owner_not_established"]
        finally:
            control_store._execute(
                "UPDATE control_jobs SET attempt = ? WHERE job_id = ?",
                (original_attempt, job_id),
            )
            control_store.upsert_progress(job_id=job_id, progress=original_progress)
            monkeypatch.setattr(run_index, "get_run", original_get_run)

        # A terminal unknown physical amount may still have a separately recorded
        # zero-increment cache reuse. Append that pair to the selected run's durable
        # ledger, reopen its owner, and prove the fresh API projection keeps the
        # physical total unknown.
        from polisyos.runtime.http.services.control.run_lifecycle import (
            _build_control_nl_producer_budget_reconciler,
        )
        from polisyos.runtime.quality.generation_cycle import (
            GenerationCycleController,
            GenerationCycleError,
        )
        from polisyos.scientist.methods.search.voi_scheduler import SimpleVOIScheduler
        from polisyos.scientist.orchestration.engine.budget import (
            BudgetLimit,
            BudgetState,
        )

        unknown_store = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        unknown_provider = _MonetarySimulatedProvider("simulated-qwen")
        unknown_provider._costs = (-1.0,)
        unknown_cache = CachingLLMClient(
            unknown_provider,
            cache=InMemoryPromptCache(maxsize=4, default_ttl_s=30),
            model="simulated-qwen",
            ttl_s=30,
            inflight_timeout_s=10,
        )
        unknown_client = TracedLLMClient(
            unknown_cache,
            model_name="simulated-qwen",
            run_id=str(job.run_id),
            provider_name="simulated_gateway",
            producer_settlement_store=unknown_store,
            producer_budget_key=f"nl-run:{job.run_id}",
        )

        async def _run_unknown_origin_reuse() -> tuple[Any, Any]:
            request = {
                "user": "R3 terminal-unknown origin cache reuse witness.",
                "temperature": 0,
            }
            with unknown_store.producer_run_binding_scope(binding, control_job_attempt=job.attempt):
                physical = await unknown_client.generate(**request)
                reuse = await unknown_client.generate(**request)
            return physical, reuse

        unknown_physical, unknown_reuse = asyncio.run(_run_unknown_origin_reuse())
        unknown_physical_event = unknown_physical.settlement.event
        unknown_reuse_event = unknown_reuse.settlement.event
        unknown_reader = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        unknown_records = unknown_reader.list_producer_events_for_run_safe(binding)
        unknown_records_by_id = {record.event_id: record for record in unknown_records}
        assert {unknown_physical_event.event_id, unknown_reuse_event.event_id} <= set(
            unknown_records_by_id
        )
        assert unknown_records_by_id[unknown_physical_event.event_id].status == "unknown"
        assert unknown_records_by_id[unknown_physical_event.event_id].cost_origin == "unknown"
        assert unknown_records_by_id[unknown_physical_event.event_id].amount is None
        assert unknown_records_by_id[unknown_reuse_event.event_id].status == "committed"
        assert unknown_records_by_id[unknown_reuse_event.event_id].cost_origin == "reuse"
        assert unknown_records_by_id[unknown_reuse_event.event_id].amount == Decimal(0)
        assert unknown_reuse_event.origin_event_id == unknown_physical_event.event_id

        runtime_context.debug.bind_producer_settlement_store(unknown_reader)
        unknown_get = client.get(f"/api/v1/runs/{core_run_id}/agents")
        assert unknown_get.status_code == 200, unknown_get.text
        unknown_pipeline = AgentPipelineResponse.model_validate(unknown_get.json()).pipeline
        unknown_served_events = [
            event
            for attempt in unknown_pipeline.attempts
            for step in attempt.steps
            for event in step.cost_events
        ]
        unknown_served_by_id = {event.event_id: event for event in unknown_served_events}
        unknown_current_ids = {
            record.event_id
            for record in unknown_records
            if record.control_job_attempt == job.attempt and record.pre_admission_attempt_id is None
        }
        unknown_unattributed_ids = {
            record.event_id for record in unknown_records if record.control_job_attempt is None
        }
        assert set(unknown_served_by_id) == unknown_current_ids
        assert {event.event_id for event in unknown_pipeline.unattributed_cost_events} == (
            unknown_unattributed_ids
        )
        assert second_attempt_event not in unknown_served_by_id
        assert unknown_served_by_id[unknown_physical_event.event_id].amount is None
        assert unknown_served_by_id[unknown_physical_event.event_id].cost_origin == "unknown"
        assert unknown_served_by_id[unknown_reuse_event.event_id].amount == Decimal(0)
        assert unknown_served_by_id[unknown_reuse_event.event_id].cost_origin == "reuse"
        assert unknown_served_by_id[unknown_reuse_event.event_id].origin_event_id == (
            unknown_physical_event.event_id
        )
        assert unknown_pipeline.cost_usd is None

        n6_state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("1"))})
        n6_controller = GenerationCycleController(
            model_id="n6-unknown-origin-cache-reuse",
            authority_scope="contract_testing",
            voi_scheduler=SimpleVOIScheduler(stage_costs={3: 0.01}, min_roi_threshold=0.0),
            _producer_budget_reconciler=_build_control_nl_producer_budget_reconciler(
                settlement_store=unknown_reader,
                producer_run_binding=binding,
                budget_state=n6_state,
            ),
        )
        with pytest.raises(
            GenerationCycleError, match="control_nl_budget_producer_event_not_settled"
        ):
            n6_controller._schedule_candidate_for_execution(
                candidate_id="unknown-origin-cache-reuse",
                proxy_score=1.0,
                voi_estimate=1.0,
                budget_state=n6_state,
            )
        assert n6_state.spent == {}
    finally:
        if client_entered:
            client_context.__exit__(None, None, None)
        close_runtime_api_env(env)


def test_terminal_progress_carries_only_current_fenced_source_projections(
    tmp_path: Path,
) -> None:
    from polisyos.runtime.http.services.control_plane_store import (
        ControlJobLeaseLostError,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.phase_barriers import (
        _execution_owner_binding_from_admission,
    )
    from polisyos.runtime.quality.refs import RuntimeQualityAuthorityRefs

    store = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "owner-terminal.sqlite3")

    def _assert_no_completed_outbox(job_id: str) -> None:
        events = store.list_outbox_events(state=None, limit=500)
        assert len(events) < 500, "absence query would be truncated at the reader page cap"
        event_key = f"{job_id}:job_completed"
        assert not any(
            event.topic == "control.job.completed"
            and event.event_key == event_key
            and event.job_id == job_id
            for event in events
        )

    def _lease_job(job_id: str, *, scope_status: str = "established") -> tuple[Any, str]:
        run_id = f"run-{job_id}"
        worker_id = f"worker-{job_id}"
        submitted_by = f"actor-{job_id}"
        tenant_id = f"tenant-{job_id}"
        cell_id = f"cell-{job_id}"
        assert scope_status in {"established", "not_established"}
        established = scope_status == "established"
        scope = {
            "schema_version": "polisyos.runtime.control_execution_scope.v1",
            "status": scope_status,
            "tenant_id": tenant_id if established else None,
            "cell_id": cell_id if established else None,
            "actor_subject": submitted_by if established else None,
            "actor_authenticated": established,
            "actor_roles": ["analyst"] if established else [],
        }
        payload_ref = "sha256:" + "a" * 64
        creation_payload = {
            "job_id": job_id,
            "run_id": run_id,
            "job_kind": "natural_language_run",
            "pipeline_id": None,
            "payload_ref": payload_ref,
            "submitted_by": submitted_by,
            "requested_execution_profile": "research",
            "effective_execution_profile": "research",
            "policy_flags": {},
            "capability_manifest_ref": None,
            "execution_scope": scope,
        }
        job = store.create_job(
            job_id=job_id,
            kind="natural_language_run",
            run_id=run_id,
            pipeline_id=None,
            requested_execution_profile="research",
            effective_execution_profile="research",
            policy_flags={},
            capability_manifest_ref=None,
            payload_ref=payload_ref,
            submitted_by=submitted_by,
            creation_event_payload=creation_payload,
        )
        leased = store.lease_next_job(worker_id=worker_id, lease_seconds=30)
        assert leased is not None
        assert leased.job_id == job.job_id
        return leased, worker_id

    def _current_owner_binding_or_none(job_id: str) -> dict[str, object] | None:
        admission = store.current_execution_job_admission()
        return _execution_owner_binding_from_admission(
            admission,
            expected_job_id=job_id,
            expected_run_id=f"run-{job_id}",
            expected_effective_profile="research",
            expected_scope={
                "tenant_id": f"tenant-{job_id}",
                "cell_id": f"cell-{job_id}",
            },
        )

    def _current_owner_binding(job_id: str) -> dict[str, object]:
        binding = _current_owner_binding_or_none(job_id)
        assert binding is not None
        return binding

    def _current_projection(owner: dict[str, object]) -> dict[str, Any]:
        policy_intent_ref = "sha256:" + "b" * 64
        assurance_ref = "sha256:" + "d" * 64
        artifact_ref = ArtifactRef(
            artifact_id="sha256:" + "c" * 64,
            kind="runtime.quality.assurance_report",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "e" * 64,
        ).model_dump(mode="json")
        return {
            "state": "running",
            "phase": "quality_projection",
            "details": {"stale_phase_payload": True},
            "execution_owner_binding": owner,
            "run_intent_binding": {
                "run_id": str(owner["run_id"]),
                "tenant_id": str(owner["tenant_id"]),
                "requested_profile": str(owner["requested_execution_profile"]),
                "policy_intent_ref": policy_intent_ref,
                "time_context_ref": None,
                "same_input_closure_ref": None,
            },
            "runtime_quality_refs": {
                "policy_intent_envelope_ref": policy_intent_ref,
                "security_assurance_report_ref": assurance_ref,
                "phase": "sha256:" + "a" * 64,
            },
            "runtime_quality_artifact_refs": {
                "security_assurance_report_ref": artifact_ref,
            },
            "runtime_quality_projection": {
                "authority_role": "projection_only",
                "provenance_kind": "runtime_projection",
                "surface": "runtime.progress",
                "authoritative_surface": "runtime_quality_refs",
            },
            "security_assurance_report_ref": assurance_ref,
            "policy_intent_envelope_ref": policy_intent_ref,
            "trust_boundary_attestations": [],
            "diagnostic_event_log_ref": "candidate-diagnostic-log",
            "diagnostic_events": [{"event_id": "candidate-diagnostic-event"}],
            "runtime_quality_diagnostic_events": ["obsolete local-only key"],
            "runtime_diagnostic_event_status": "not_persisted",
            "diagnostic_event_scope_status": "established",
            "runtime_diagnostic_event_limitation_code": "last_phase_only",
            "diagnostic_event_ids": ["phase-event-id"],
            "diagnostic_event_authority": "progress_reference_only",
            "scientist_workflow": {"event_count": 1},
        }

    def _runtime_quality_ref_aliases(projection: dict[str, Any]) -> dict[str, str]:
        resolution = RuntimeQualityAuthorityRefs.from_runtime_payloads(
            job_payload={"runtime_quality_refs": projection.get("runtime_quality_refs")}
        )
        assert not resolution.rejections
        return resolution.refs

    def _assert_runtime_quality_aliases(
        projection: dict[str, Any],
        *terminal_progress_views: dict[str, Any],
    ) -> None:
        aliases = _runtime_quality_ref_aliases(projection)
        assert "phase" not in aliases
        for terminal_progress in terminal_progress_views:
            for key, value in aliases.items():
                assert terminal_progress[key] == value

    completed, completed_worker = _lease_job("job-owner-complete")
    with store.job_execution_fence(
        job_id=completed.job_id,
        worker_id=completed_worker,
        attempt=completed.attempt,
    ):
        completed_owner = _current_owner_binding(completed.job_id)
        completed_projection = _current_projection(completed_owner)
        store.upsert_progress(job_id=completed.job_id, progress=completed_projection)
        store.complete_job(
            job_id=completed.job_id,
            progress={"phase": "terminal", "details": {"terminal_detail": True}},
        )
    completed_record = store.get_job(completed.job_id)
    completed_outbox = store.get_job_completed_outbox_event(completed.job_id)
    assert completed_record is not None
    for field in (
        "execution_owner_binding",
        "run_intent_binding",
        "runtime_quality_refs",
        "runtime_quality_artifact_refs",
        "runtime_quality_projection",
        "trust_boundary_attestations",
        "diagnostic_event_log_ref",
        "diagnostic_events",
    ):
        assert completed_record.progress[field] == completed_projection[field]
        assert completed_outbox.payload["progress"][field] == completed_projection[field]
    _assert_runtime_quality_aliases(
        completed_projection,
        completed_record.progress,
        completed_outbox.payload["progress"],
    )
    assert completed_record.progress["phase"] == "terminal"
    assert completed_record.progress["runtime_quality_refs"]["phase"] == "sha256:" + "a" * 64
    assert completed_record.progress["details"] == {"terminal_detail": True}
    for field in (
        "runtime_quality_diagnostic_events",
        "runtime_diagnostic_event_status",
        "diagnostic_event_scope_status",
        "runtime_diagnostic_event_limitation_code",
        "diagnostic_event_ids",
        "diagnostic_event_authority",
        "scientist_workflow",
    ):
        assert field not in completed_record.progress
    assert completed_record.progress["run_intent_binding"]["time_context_ref"] is None
    assert completed_record.progress["run_intent_binding"]["same_input_closure_ref"] is None

    failed, failed_worker = _lease_job("job-owner-fail")
    with store.job_execution_fence(
        job_id=failed.job_id,
        worker_id=failed_worker,
        attempt=failed.attempt,
    ):
        failed_owner = _current_owner_binding(failed.job_id)
        failed_projection = _current_projection(failed_owner)
        store.upsert_progress(job_id=failed.job_id, progress=failed_projection)
        conflicting_owner = {**failed_owner, "lease_owner": "worker-forged"}
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_owner_binding_conflict",
        ):
            store.complete_job(
                job_id=failed.job_id,
                progress={
                    "phase": "terminal",
                    "execution_owner_binding": conflicting_owner,
                },
            )
        selected_aliases = _runtime_quality_ref_aliases(failed_projection)
        selected_ref_key, selected_ref_value = next(iter(selected_aliases.items()))
        conflicting_refs = {
            **failed_projection["runtime_quality_refs"],
            selected_ref_key: selected_ref_value + "-forged",
        }
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_source_projection_conflict",
        ):
            store.complete_job(
                job_id=failed.job_id,
                progress={
                    "phase": "terminal",
                    "runtime_quality_refs": conflicting_refs,
                },
            )
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_source_projection_conflict",
        ):
            store.complete_job(
                job_id=failed.job_id,
                progress={
                    "phase": "terminal",
                    selected_ref_key: selected_ref_value + "-forged",
                },
            )
        current = store.current_execution_job_record()
        assert current.state == "running"
        store.fail_job(
            job_id=failed.job_id,
            error_message="controlled owner-preservation failure",
            progress={"phase": "failed"},
        )
    failed_record = store.get_job(failed.job_id)
    failed_outbox = store._get_outbox_event_by_key(
        topic="control.job.failed",
        event_key=f"{failed.job_id}:job_failed",
    )
    assert failed_record is not None
    assert failed_outbox is not None
    for field in (
        "execution_owner_binding",
        "run_intent_binding",
        "runtime_quality_refs",
        "runtime_quality_artifact_refs",
        "runtime_quality_projection",
        "diagnostic_event_log_ref",
        "diagnostic_events",
    ):
        assert failed_record.progress[field] == failed_projection[field]
        assert failed_outbox.payload["progress"][field] == failed_projection[field]
    _assert_runtime_quality_aliases(
        failed_projection,
        failed_record.progress,
        failed_outbox.payload["progress"],
    )
    assert failed_record.progress["phase"] == "failed"
    assert "details" not in failed_record.progress

    delegated, delegated_worker = _lease_job("job-owner-delegated-failure")
    with store.job_execution_fence(
        job_id=delegated.job_id,
        worker_id=delegated_worker,
        attempt=delegated.attempt,
    ):
        delegated_owner = _current_owner_binding(delegated.job_id)
        delegated_projection = _current_projection(delegated_owner)
        store.upsert_progress(job_id=delegated.job_id, progress=delegated_projection)
        store.complete_job(
            job_id=delegated.job_id,
            progress={"phase": "terminal", "status": "fail"},
        )
    delegated_record = store.get_job(delegated.job_id)
    assert delegated_record is not None
    assert delegated_record.state == "failed"
    assert delegated_record.progress["execution_owner_binding"] == delegated_owner
    assert (
        delegated_record.progress["runtime_quality_refs"]
        == delegated_projection["runtime_quality_refs"]
    )
    delegated_outbox = store._get_outbox_event_by_key(
        topic="control.job.failed",
        event_key=f"{delegated.job_id}:job_failed",
    )
    assert delegated_outbox is not None
    _assert_runtime_quality_aliases(
        delegated_projection,
        delegated_record.progress,
        delegated_outbox.payload["progress"],
    )
    assert delegated_record.progress["phase"] == "terminal"
    assert "details" not in delegated_record.progress

    missing, missing_worker = _lease_job("job-owner-missing-intent")
    with store.job_execution_fence(
        job_id=missing.job_id,
        worker_id=missing_worker,
        attempt=missing.attempt,
    ):
        missing_owner = _current_owner_binding(missing.job_id)
        store.upsert_progress(
            job_id=missing.job_id,
            progress={"phase": "running", "execution_owner_binding": missing_owner},
        )
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_source_projection_conflict",
        ):
            store.complete_job(
                job_id=missing.job_id,
                progress={
                    "phase": "terminal",
                    "run_intent_binding": {
                        "run_id": str(missing_owner["run_id"]),
                        "tenant_id": str(missing_owner["tenant_id"]),
                        "requested_profile": str(missing_owner["requested_execution_profile"]),
                    },
                },
            )
        store.complete_job(job_id=missing.job_id, progress={"phase": "terminal"})
    missing_record = store.get_job(missing.job_id)
    assert missing_record is not None
    assert missing_record.progress["execution_owner_binding"] == missing_owner
    assert "run_intent_binding" not in missing_record.progress
    assert "runtime_quality_refs" not in missing_record.progress
    assert "policy_intent_envelope_ref" not in missing_record.progress
    assert missing_record.progress["phase"] == "terminal"

    unprojected_owner, unprojected_owner_worker = _lease_job("job-owner-terminal-rederived")
    with store.job_execution_fence(
        job_id=unprojected_owner.job_id,
        worker_id=unprojected_owner_worker,
        attempt=unprojected_owner.attempt,
    ):
        current_owner = _current_owner_binding(unprojected_owner.job_id)
        assert "execution_owner_binding" not in store.current_execution_job_record().progress
        store.complete_job(
            job_id=unprojected_owner.job_id,
            progress={"phase": "terminal"},
        )
    unprojected_record = store.get_job(unprojected_owner.job_id)
    unprojected_outbox = store.get_job_completed_outbox_event(unprojected_owner.job_id)
    assert unprojected_record is not None
    assert unprojected_outbox is not None
    unprojected_response = unprojected_record.to_response()
    unprojected_views = (
        unprojected_record.progress,
        unprojected_outbox.payload["progress"],
        unprojected_response.progress,
    )
    assert unprojected_record.progress == unprojected_outbox.payload["progress"]
    assert unprojected_response.progress == unprojected_record.progress
    for terminal_progress in unprojected_views:
        assert terminal_progress["execution_owner_binding"] == current_owner
        assert "runtime_quality_refs" not in terminal_progress
        assert "policy_intent_envelope_ref" not in terminal_progress

    absent_alias, absent_alias_worker = _lease_job("job-owner-missing-flat-ref")
    with store.job_execution_fence(
        job_id=absent_alias.job_id,
        worker_id=absent_alias_worker,
        attempt=absent_alias.attempt,
    ):
        absent_alias_owner = _current_owner_binding(absent_alias.job_id)
        absent_alias_projection = _current_projection(absent_alias_owner)
        consumer_aliases = _runtime_quality_ref_aliases(absent_alias_projection)
        missing_flat_key, missing_flat_value = next(iter(consumer_aliases.items()))
        assert (
            absent_alias_projection["runtime_quality_refs"][missing_flat_key] == missing_flat_value
        )
        del absent_alias_projection[missing_flat_key]
        assert missing_flat_key not in absent_alias_projection
        remaining_aliases = {
            key: value for key, value in consumer_aliases.items() if key != missing_flat_key
        }
        store.upsert_progress(
            job_id=absent_alias.job_id,
            progress=absent_alias_projection,
        )
        store.complete_job(
            job_id=absent_alias.job_id,
            progress={"phase": "terminal"},
        )
    absent_alias_record = store.get_job(absent_alias.job_id)
    absent_alias_outbox = store.get_job_completed_outbox_event(absent_alias.job_id)
    assert absent_alias_record is not None
    assert absent_alias_outbox is not None
    absent_alias_response = absent_alias_record.to_response()
    assert absent_alias_record.progress == absent_alias_outbox.payload["progress"]
    assert absent_alias_response.progress == absent_alias_record.progress
    for terminal_progress in (
        absent_alias_record.progress,
        absent_alias_outbox.payload["progress"],
        absent_alias_response.progress,
    ):
        assert (
            terminal_progress["runtime_quality_refs"]
            == absent_alias_projection["runtime_quality_refs"]
        )
        assert missing_flat_key not in terminal_progress
        for key, value in remaining_aliases.items():
            assert terminal_progress[key] == value
    assert absent_alias_record.progress["phase"] == "terminal"

    mismatched, mismatched_worker = _lease_job("job-owner-nested-flat-ref-mismatch")
    with store.job_execution_fence(
        job_id=mismatched.job_id,
        worker_id=mismatched_worker,
        attempt=mismatched.attempt,
    ):
        mismatched_owner = _current_owner_binding(mismatched.job_id)
        mismatched_projection = _current_projection(mismatched_owner)
        selected_aliases = _runtime_quality_ref_aliases(mismatched_projection)
        selected_ref_key, selected_ref_value = next(iter(selected_aliases.items()))
        mismatched_projection[selected_ref_key] = selected_ref_value + "-forged"
        store.upsert_progress(job_id=mismatched.job_id, progress=mismatched_projection)
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_source_projection_conflict",
        ):
            store.complete_job(
                job_id=mismatched.job_id,
                progress={"phase": "terminal"},
            )
        current = store.current_execution_job_record()
        assert current.state == "running"

        malformed_projection = _current_projection(mismatched_owner)
        malformed_refs = dict(malformed_projection["runtime_quality_refs"])
        malformed_refs[selected_ref_key] = None
        malformed_projection["runtime_quality_refs"] = malformed_refs
        store.upsert_progress(job_id=mismatched.job_id, progress=malformed_projection)
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_progress_source_projection_conflict",
        ):
            store.complete_job(
                job_id=mismatched.job_id,
                progress={"phase": "terminal"},
            )
        current = store.current_execution_job_record()
        assert current.state == "running"

    def _well_formed_owner_guess(
        job: Any, current_owner: dict[str, object] | None
    ) -> dict[str, object]:
        if current_owner is not None:
            return dict(current_owner)
        return {
            "job_id": job.job_id,
            "run_id": str(job.run_id),
            "tenant_id": f"guessed-tenant-{job.job_id}",
            "cell_id": f"guessed-cell-{job.job_id}",
            "requested_execution_profile": "research",
            "effective_execution_profile": "research",
            "attempt": job.attempt,
            "lease_owner": job.lease_owner,
        }

    def _intent_for_matrix(job: Any, current_owner: dict[str, object] | None) -> dict[str, object]:
        return {
            "run_id": str(job.run_id),
            "tenant_id": (
                str(current_owner["tenant_id"])
                if current_owner is not None
                else f"guessed-tenant-{job.job_id}"
            ),
            "requested_profile": (
                str(current_owner["requested_execution_profile"])
                if current_owner is not None
                else "research"
            ),
            "policy_intent_ref": "sha256:" + "b" * 64,
            "time_context_ref": None,
            "same_input_closure_ref": None,
        }

    owner_state_cases: set[tuple[bool, str, bool]] = set()
    for owner_available in (True, False):
        for row_owner_state in ("absent", "valid", "malformed", "mismatch"):
            for intent_present in (False, True):
                case_id = f"{owner_available}-{row_owner_state}-{intent_present}"
                matrix_job, matrix_worker = _lease_job(
                    f"job-owner-matrix-{case_id}",
                    scope_status="established" if owner_available else "not_established",
                )
                with store.job_execution_fence(
                    job_id=matrix_job.job_id,
                    worker_id=matrix_worker,
                    attempt=matrix_job.attempt,
                ):
                    current_owner = _current_owner_binding_or_none(matrix_job.job_id)
                    assert (current_owner is not None) is owner_available
                    row_progress = dict(store.current_execution_job_record().progress)
                    row_progress.pop("execution_owner_binding", None)
                    row_progress.pop("run_intent_binding", None)
                    if row_owner_state == "valid":
                        row_progress["execution_owner_binding"] = _well_formed_owner_guess(
                            matrix_job, current_owner
                        )
                    elif row_owner_state == "malformed":
                        row_progress["execution_owner_binding"] = {"job_id": matrix_job.job_id}
                    elif row_owner_state == "mismatch":
                        mismatch = _well_formed_owner_guess(matrix_job, current_owner)
                        if current_owner is not None:
                            mismatch["tenant_id"] = f"foreign-tenant-{matrix_job.job_id}"
                        else:
                            mismatch["job_id"] = f"foreign-{matrix_job.job_id}"
                        row_progress["execution_owner_binding"] = mismatch
                    if intent_present:
                        row_progress["run_intent_binding"] = _intent_for_matrix(
                            matrix_job, current_owner
                        )
                    store.upsert_progress(job_id=matrix_job.job_id, progress=row_progress)

                    terminal_progress = {
                        "phase": "terminal",
                        "matrix_case": case_id,
                    }
                    owner_state_cases.add((owner_available, row_owner_state, intent_present))
                    should_reject = (
                        not owner_available and (row_owner_state != "absent" or intent_present)
                    ) or (owner_available and row_owner_state in {"malformed", "mismatch"})
                    if should_reject:
                        with pytest.raises(
                            ControlJobLeaseLostError,
                            match="control_job_terminal_owner_binding_not_current",
                        ):
                            store.complete_job(
                                job_id=matrix_job.job_id,
                                progress=terminal_progress,
                            )
                        current = store.current_execution_job_record()
                        assert current.state == "running"
                        assert current.progress == row_progress
                        _assert_no_completed_outbox(matrix_job.job_id)
                        continue

                    store.complete_job(
                        job_id=matrix_job.job_id,
                        progress=terminal_progress,
                    )
                completed_record = store.get_job(matrix_job.job_id)
                completed_outbox = store.get_job_completed_outbox_event(matrix_job.job_id)
                assert completed_record is not None and completed_record.state == "completed"
                assert completed_outbox is not None
                assert completed_record.progress == completed_outbox.payload["progress"]
                assert completed_record.progress["matrix_case"] == case_id
                if current_owner is None:
                    assert "execution_owner_binding" not in completed_record.progress
                    assert "run_intent_binding" not in completed_record.progress
                else:
                    assert completed_record.progress["execution_owner_binding"] == current_owner
                    if intent_present:
                        assert (
                            completed_record.progress["run_intent_binding"]
                            == row_progress["run_intent_binding"]
                        )
                    else:
                        assert "run_intent_binding" not in completed_record.progress

    assert owner_state_cases == {
        (owner_available, row_owner_state, intent_present)
        for owner_available in (True, False)
        for row_owner_state in ("absent", "valid", "malformed", "mismatch")
        for intent_present in (False, True)
    }

    unknown_supplied, unknown_supplied_worker = _lease_job(
        "job-owner-unknown-supplied-fields", scope_status="not_established"
    )
    with store.job_execution_fence(
        job_id=unknown_supplied.job_id,
        worker_id=unknown_supplied_worker,
        attempt=unknown_supplied.attempt,
    ):
        supplied_owner = _well_formed_owner_guess(unknown_supplied, None)
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_owner_binding_not_current",
        ):
            store.complete_job(
                job_id=unknown_supplied.job_id,
                progress={
                    "phase": "terminal",
                    "execution_owner_binding": supplied_owner,
                },
            )
        with pytest.raises(
            ControlJobLeaseLostError,
            match="control_job_terminal_owner_binding_not_current",
        ):
            store.complete_job(
                job_id=unknown_supplied.job_id,
                progress={
                    "phase": "terminal",
                    "run_intent_binding": _intent_for_matrix(unknown_supplied, None),
                },
            )
        current = store.current_execution_job_record()
        assert current.state == "running"
        assert "execution_owner_binding" not in current.progress
        assert "run_intent_binding" not in current.progress
        _assert_no_completed_outbox(unknown_supplied.job_id)

    # P31/P40 widened control: every actual source-availability path shares the
    # same owner/intent intake, and the finite state set comes from the helper's
    # live-fence/admission/source derivation branches.
    import json

    availability_states = (
        "no_fence",
        "mismatched_fence",
        "invalid_admission",
        "unknown_scope",
        "valid_fence",
    )
    projection_placements = ("none", "current", "supplied", "both")
    availability_cases: set[tuple[str, str]] = set()

    def _invalidate_created_admission(job_id: str) -> None:
        outbox = store.get_job_created_outbox_event(job_id)
        assert outbox is not None
        payload = dict(outbox.payload)
        scope = dict(payload["execution_scope"])
        scope["tenant_id"] = f"foreign-{scope['tenant_id']}"
        payload["execution_scope"] = scope
        store._execute(  # noqa: SLF001
            "UPDATE control_outbox_events SET payload_json = ? WHERE event_id = ?",
            (json.dumps(payload, sort_keys=True), outbox.event_id),
        )

    for availability in availability_states:
        for placement in projection_placements:
            case_id = f"{availability}-{placement}"
            job, worker = _lease_job(
                f"job-terminal-availability-{case_id}",
                scope_status=(
                    "not_established" if availability == "unknown_scope" else "established"
                ),
            )
            with store.job_execution_fence(
                job_id=job.job_id,
                worker_id=worker,
                attempt=job.attempt,
            ):
                derived_owner = _current_owner_binding_or_none(job.job_id)
                owner = derived_owner or _well_formed_owner_guess(job, None)
                intent = _intent_for_matrix(job, owner)
                row_progress = dict(store.current_execution_job_record().progress)
                row_progress.pop("execution_owner_binding", None)
                row_progress.pop("run_intent_binding", None)
                if placement in {"current", "both"}:
                    row_progress["execution_owner_binding"] = owner
                    row_progress["run_intent_binding"] = intent
                store.upsert_progress(job_id=job.job_id, progress=row_progress)

                if availability == "invalid_admission":
                    _invalidate_created_admission(job.job_id)

                terminal_progress = {"phase": "terminal", "matrix_case": case_id}
                if placement in {"supplied", "both"}:
                    terminal_progress["execution_owner_binding"] = owner
                    terminal_progress["run_intent_binding"] = intent

                availability_cases.add((availability, placement))
                should_reject = (availability != "valid_fence" and placement != "none") or (
                    availability == "valid_fence" and placement == "supplied"
                )

                if availability == "mismatched_fence":
                    # A live handler lease exists, but this invocation's fence
                    # does not match it. The public lifecycle API rejects this
                    # before projection; exercise the shared helper's defensive
                    # mismatch branch against the actual active admission.
                    mismatched_fence = (f"foreign-{worker}", job.attempt)
                    if should_reject:
                        with pytest.raises(
                            ControlJobLeaseLostError,
                            match="control_job_terminal_owner_binding_not_current",
                        ):
                            store._terminal_progress_with_current_source_projection(  # noqa: SLF001
                                job_id=job.job_id,
                                progress=terminal_progress,
                                fence=mismatched_fence,
                            )
                    else:
                        assert (
                            store._terminal_progress_with_current_source_projection(  # noqa: SLF001
                                job_id=job.job_id,
                                progress=terminal_progress,
                                fence=mismatched_fence,
                            )
                            == terminal_progress
                        )
                    current = store.current_execution_job_record()
                    assert current.state == "running"
                    assert current.progress == row_progress
                    _assert_no_completed_outbox(job.job_id)
                    continue

                if availability == "no_fence":
                    # The owner/intent intake still runs after the handler
                    # context ends; an unbound terminal snapshot remains valid.
                    pass
                elif should_reject:
                    with pytest.raises(
                        ControlJobLeaseLostError,
                        match=(
                            "control_job_terminal_progress_source_projection_conflict"
                            if availability == "valid_fence"
                            else "control_job_terminal_owner_binding_not_current"
                        ),
                    ):
                        store.complete_job(
                            job_id=job.job_id,
                            progress=terminal_progress,
                        )
                    current = store.current_execution_job_record()
                    assert current.state == "running"
                    assert current.progress == row_progress
                    _assert_no_completed_outbox(job.job_id)
                    continue
                else:
                    store.complete_job(
                        job_id=job.job_id,
                        progress=terminal_progress,
                    )
                    completed_record = store.get_job(job.job_id)
                    completed_outbox = store.get_job_completed_outbox_event(job.job_id)
                    assert completed_record is not None and completed_record.state == "completed"
                    assert completed_outbox is not None
                    assert completed_record.progress == completed_outbox.payload["progress"]
                    assert completed_record.progress["matrix_case"] == case_id
                    if availability == "valid_fence":
                        assert completed_record.progress["execution_owner_binding"] == owner
                        if placement in {"current", "both"}:
                            assert completed_record.progress["run_intent_binding"] == intent
                        else:
                            assert "run_intent_binding" not in completed_record.progress
                    else:
                        assert "execution_owner_binding" not in completed_record.progress
                        assert "run_intent_binding" not in completed_record.progress
                    continue

            if availability == "no_fence":
                if should_reject:
                    with pytest.raises(
                        ControlJobLeaseLostError,
                        match="control_job_terminal_owner_binding_not_current",
                    ):
                        store.complete_job(
                            job_id=job.job_id,
                            progress=terminal_progress,
                        )
                    current = store.get_job(job.job_id)
                    assert current is not None and current.state == "running"
                    assert current.progress == row_progress
                    _assert_no_completed_outbox(job.job_id)
                else:
                    store.complete_job(
                        job_id=job.job_id,
                        progress=terminal_progress,
                    )
                    completed_record = store.get_job(job.job_id)
                    completed_outbox = store.get_job_completed_outbox_event(job.job_id)
                    assert completed_record is not None and completed_record.state == "completed"
                    assert completed_outbox is not None
                    assert completed_record.progress == terminal_progress
                    assert completed_outbox.payload["progress"] == terminal_progress

    assert availability_cases == {
        (availability, placement)
        for availability in availability_states
        for placement in projection_placements
    }

    # Present malformed current values are not defaulted to absence.
    malformed_current_states = (
        ("null_owner", "execution_owner_binding", None, "owner"),
        ("malformed_owner", "execution_owner_binding", {"job_id": "partial"}, "owner"),
        ("null_intent", "run_intent_binding", None, "intent"),
        ("malformed_intent", "run_intent_binding", {"run_id": "partial"}, "intent"),
        (
            "mismatched_intent",
            "run_intent_binding",
            {
                "run_id": "foreign-run",
                "tenant_id": "foreign-tenant",
                "requested_profile": "research",
            },
            "intent",
        ),
    )
    for case_id, key, malformed_value, kind in malformed_current_states:
        job, worker = _lease_job(f"job-terminal-malformed-{case_id}")
        with store.job_execution_fence(
            job_id=job.job_id,
            worker_id=worker,
            attempt=job.attempt,
        ):
            owner = _current_owner_binding(job.job_id)
            projection = {"phase": "running", "execution_owner_binding": owner}
            if key == "run_intent_binding":
                projection["run_intent_binding"] = _intent_for_matrix(job, owner)
            projection[key] = malformed_value
            store.upsert_progress(job_id=job.job_id, progress=projection)
            error = (
                "control_job_terminal_owner_binding_not_current"
                if kind == "owner"
                else "control_job_terminal_progress_source_projection_conflict"
            )
            with pytest.raises(ControlJobLeaseLostError, match=error):
                store.complete_job(
                    job_id=job.job_id,
                    progress={"phase": "terminal", "matrix_case": case_id},
                )
            current = store.current_execution_job_record()
            assert current.state == "running"
            assert current.progress == projection
            _assert_no_completed_outbox(job.job_id)
    malformed_supplied_states = (
        (
            "null_owner",
            "execution_owner_binding",
            None,
            "control_job_terminal_progress_owner_binding_conflict",
        ),
        (
            "malformed_owner",
            "execution_owner_binding",
            {"job_id": "partial"},
            "control_job_terminal_progress_owner_binding_conflict",
        ),
        (
            "null_intent",
            "run_intent_binding",
            None,
            "control_job_terminal_progress_source_projection_conflict",
        ),
        (
            "malformed_intent",
            "run_intent_binding",
            {"run_id": "partial"},
            "control_job_terminal_progress_source_projection_conflict",
        ),
        (
            "mismatched_intent",
            "run_intent_binding",
            {
                "run_id": "foreign-run",
                "tenant_id": "foreign-tenant",
                "requested_profile": "research",
            },
            "control_job_terminal_progress_source_projection_conflict",
        ),
    )
    for case_id, key, malformed_value, error in malformed_supplied_states:
        job, worker = _lease_job(f"job-terminal-malformed-supplied-{case_id}")
        with store.job_execution_fence(
            job_id=job.job_id,
            worker_id=worker,
            attempt=job.attempt,
        ):
            owner = _current_owner_binding(job.job_id)
            intent = _intent_for_matrix(job, owner)
            row_progress = {
                "phase": "running",
                "execution_owner_binding": owner,
                "run_intent_binding": intent,
            }
            store.upsert_progress(job_id=job.job_id, progress=row_progress)
            terminal_progress = {
                "phase": "terminal",
                "execution_owner_binding": owner,
                "run_intent_binding": intent,
            }
            terminal_progress[key] = malformed_value
            with pytest.raises(ControlJobLeaseLostError, match=error):
                store.complete_job(job_id=job.job_id, progress=terminal_progress)
            current = store.current_execution_job_record()
            assert current.state == "running"
            assert current.progress == row_progress
            _assert_no_completed_outbox(job.job_id)

    # P40 whole-schema control: the nullable requested-profile slot is valid
    # only when it is the exact admitted value. Missing, malformed, empty, and
    # foreign values fail at both current-row intake and supplied terminal intake.
    missing_profile = object()
    invalid_requested_profiles: tuple[tuple[str, object], ...] = (
        ("absent", missing_profile),
        ("null", None),
        ("wrong_type", 7),
        ("empty", ""),
        ("foreign", "governed"),
    )
    for placement in ("current", "supplied"):
        for case_id, requested_profile in invalid_requested_profiles:
            job, worker = _lease_job(f"job-terminal-requested-profile-{placement}-{case_id}")
            with store.job_execution_fence(
                job_id=job.job_id,
                worker_id=worker,
                attempt=job.attempt,
            ):
                current_owner = _current_owner_binding(job.job_id)
                malformed_owner = dict(current_owner)
                if requested_profile is missing_profile:
                    malformed_owner.pop("requested_execution_profile")
                else:
                    malformed_owner["requested_execution_profile"] = requested_profile
                original_progress = dict(store.current_execution_job_record().progress)
                terminal_progress: dict[str, Any] = {
                    "phase": "terminal",
                    "matrix_case": f"{placement}-{case_id}",
                }
                if placement == "current":
                    row_progress = dict(original_progress)
                    row_progress.pop("execution_owner_binding", None)
                    row_progress.pop("run_intent_binding", None)
                    row_progress["execution_owner_binding"] = malformed_owner
                    store.upsert_progress(job_id=job.job_id, progress=row_progress)
                    expected_error = "control_job_terminal_owner_binding_not_current"
                    expected_progress = row_progress
                else:
                    terminal_progress["execution_owner_binding"] = malformed_owner
                    expected_error = "control_job_terminal_progress_owner_binding_conflict"
                    expected_progress = original_progress
                with pytest.raises(ControlJobLeaseLostError, match=expected_error):
                    store.complete_job(job_id=job.job_id, progress=terminal_progress)
                current = store.current_execution_job_record()
                assert current.state == "running"
                assert current.progress == expected_progress
                _assert_no_completed_outbox(job.job_id)

    store.close()


def test_agent_pipeline_cost_scalar_without_eligible_events_is_unassigned() -> None:
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import (
        AgentPipelineAttempt,
        AgentPipelineStep,
        AgentPipelineView,
    )

    current_event = {
        "event_id": "llm-provider:current-attempt-claim-control",
        "cost_origin": "reported",
        "amount": "0.07",
        "cost_usd": 0.07,
        "settlement_status": "committed",
        "durability": "ledger",
        "control_job_attempt": 2,
        "pre_admission_attempt_id": None,
    }
    event_step = AgentPipelineStep.model_validate(
        {
            "attempt": 2,
            "agent": "model_variant",
            "action": "completed",
            "cost_usd": 0.99,
            "reported_cost_usd": 0.99,
            "cost_events": [current_event],
        }
    )
    assert event_step.cost_usd is None
    assert event_step.reported_cost_usd is None
    assert event_step.cost_origin_counts == {}
    assert event_step.settlement_event_ids == ()
    assert {
        (row.source_field, row.claimed_value_usd) for row in event_step.unattributed_cost_scalars
    } == {("cost_usd", 0.99), ("reported_cost_usd", 0.99)}

    attempt = AgentPipelineAttempt.model_validate(
        {
            "attempt": 1,
            "cost_usd": 0.8,
            "steps": [
                {
                    "agent": "model_variant",
                    "action": "legacy",
                    "cost_usd": 0.3,
                }
            ],
        }
    )
    assert attempt.cost_usd is None
    assert attempt.steps[0].cost_usd is None
    assert {row.source_kind for row in attempt.unattributed_cost_scalars} == {
        "step_summary",
        "attempt_summary",
    }

    view = AgentPipelineView.model_validate(
        {
            "run_id": "run-scalar-only",
            "source_kind": "core_run",
            "cost_usd": 0.9,
            "attempts": [],
            "performance_summary": {
                "llm": {"cost_usd": 0.7},
                "variant_rows": [{"model_variant_id": "legacy-variant", "cost_usd": 0.4}],
            },
        }
    )
    assert view.cost_usd is None
    assert view.performance_summary is not None
    assert view.performance_summary["llm"]["cost_usd"] is None
    assert view.performance_summary["variant_rows"][0]["cost_usd"] is None
    assert {row.source_kind for row in view.unattributed_cost_scalars} == {
        "pipeline_summary",
        "performance_summary_llm",
        "performance_summary_variant_row",
    }

    for invalid in (True, float("nan"), -0.01):
        with pytest.raises(ValidationError):
            AgentPipelineStep.model_validate(
                {
                    "agent": "model_variant",
                    "action": "legacy",
                    "cost_usd": invalid,
                }
            )

    with pytest.raises(ValidationError):
        AgentPipelineStep.model_validate(
            {
                "agent": "model_variant",
                "action": "completed",
                "cost_usd": True,
                "cost_events": [{**current_event, "amount": "1.00", "cost_usd": 1.0}],
            }
        )


@pytest.mark.parametrize("source", ["audit", "timeline", "variant", "reflexion"])
def test_agent_pipeline_details_are_bounded_unestablished_claims(source: str) -> None:
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import AgentPipelineStep
    from polisyos.runtime.http.services.debug import (
        _agent_step_from_reflexion_payload,
        _agent_steps_from_audit_trail,
        _agent_steps_from_model_variants,
        _agent_steps_from_timeline,
    )

    nested_detail = {"cost_usd": 0.73, "annotation": "diagnostic $9 only"}
    if source == "audit":
        expected_details = {"nested": nested_detail}
        steps = _agent_steps_from_audit_trail(
            [
                {
                    "node": "critic",
                    "action": "approved",
                    "details": {"nested": nested_detail},
                }
            ],
            sensitive_keys=(),
        )
    elif source == "timeline":
        expected_details = {"nested": nested_detail}
        steps = _agent_steps_from_timeline(
            [
                SimpleNamespace(
                    phase="scientist.agent.critic",
                    event="approved",
                    metrics={"nested": nested_detail},
                    timestamp=None,
                )
            ],
            sensitive_keys=(),
        )
    elif source == "variant":
        expected_details = {"nested": nested_detail}
        steps, variant_notes = _agent_steps_from_model_variants(
            {
                "params": {
                    "llm_model_variants": [
                        {
                            "steps": [
                                {
                                    "agent": "critic",
                                    "action": "approved",
                                    "details": {"nested": nested_detail},
                                }
                            ]
                        }
                    ]
                }
            },
            sensitive_keys=(),
        )
        assert variant_notes == []
    else:
        reflexion_details = {"cost_usd": 0.73, "nested": nested_detail}
        expected_details = {"card": reflexion_details}
        reflexion_step = _agent_step_from_reflexion_payload(
            {
                "decision": "retry",
                "card": reflexion_details,
            },
            sensitive_keys=(),
        )
        assert reflexion_step is not None
        steps = [reflexion_step]

    assert len(steps) == 1
    step = steps[0]
    assert step.details_cost_scope == "not_established"
    assert step.cost_usd is None
    assert step.details == expected_details

    with pytest.raises(ValidationError):
        AgentPipelineStep.model_validate(
            {
                "agent": "critic",
                "action": "approved",
                "details_cost_scope": "current",
            }
        )


@pytest.mark.parametrize("invalid", [True, -0.01, float("nan"), "0.01"])
@pytest.mark.parametrize("source", ["audit", "timeline", "variant", "reflexion"])
def test_agent_pipeline_scalar_adapters_refuse_malformed_amounts(
    invalid: object, source: str
) -> None:
    from polisyos.runtime.http.services.debug import (
        _agent_step_from_reflexion_payload,
        _agent_steps_from_audit_trail,
        _agent_steps_from_model_variants,
        _agent_steps_from_timeline,
    )

    def _build_steps() -> object:
        if source == "audit":
            return _agent_steps_from_audit_trail(
                [
                    {
                        "node": "critic",
                        "action": "approved",
                        "details": {"cost_usd": invalid},
                    }
                ],
                sensitive_keys=(),
            )
        if source == "timeline":
            return _agent_steps_from_timeline(
                [
                    SimpleNamespace(
                        phase="scientist.agent.critic",
                        event="approved",
                        metrics={"cost_usd": invalid},
                        timestamp=None,
                    )
                ],
                sensitive_keys=(),
            )
        if source == "variant":
            return _agent_steps_from_model_variants(
                {"params": {"llm_model_variants": [{"status": "completed", "cost_usd": invalid}]}},
                sensitive_keys=(),
            )
        return _agent_step_from_reflexion_payload(
            {"decision": "retry", "card": {"cost_usd": invalid}},
            sensitive_keys=(),
        )

    with pytest.raises(ValueError):
        _build_steps()


def test_agent_pipeline_owner_control_attempt_is_distinct_from_group_ordinal() -> None:
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import AgentPipelineView

    event = {
        "event_id": "provider:owner-attempt-two",
        "cost_origin": "reported",
        "amount": "0.03",
        "cost_usd": 0.03,
        "settlement_status": "committed",
        "durability": "ledger",
        "control_job_attempt": 2,
        "pre_admission_attempt_id": None,
        "receipts": ["provider:owner-attempt-two"],
    }
    view = AgentPipelineView._from_verified_owner_context(
        run_id="run-owner-attempt-two",
        source_kind="core_run",
        owner_control_job_attempt=2,
        attempts=[
            {
                "attempt": 1,
                "steps": [
                    {
                        "agent": "llm_producer_settlement",
                        "action": "durable_ledger",
                        "cost_events": [event],
                    }
                ],
            }
        ],
    )
    assert view.owner_control_job_attempt == 2
    assert view.attempts[0].attempt == 1
    assert view.cost_usd == pytest.approx(0.03)

    for malformed in (True, 0):
        with pytest.raises(ValidationError):
            AgentPipelineView.model_validate(
                {
                    "run_id": "run-malformed-owner-attempt",
                    "source_kind": "core_run",
                    "owner_control_job_attempt": malformed,
                    "attempts": [],
                }
            )

    with pytest.raises(ValidationError, match="agent_pipeline_event_owner_attempt_mismatch"):
        AgentPipelineView._from_verified_owner_context(
            run_id="run-mismatched-owner-event",
            source_kind="core_run",
            owner_control_job_attempt=2,
            attempts=[
                {
                    "attempt": 1,
                    "steps": [
                        {
                            "agent": "llm_producer_settlement",
                            "action": "durable_ledger",
                            "cost_events": [{**event, "control_job_attempt": 1}],
                        }
                    ],
                }
            ],
        )


def test_agent_pipeline_projection_requires_explicit_root_owner_context() -> None:
    from pydantic import ValidationError

    from polisyos.core.contracts.runtime import (
        AgentPipelineAttempt,
        AgentPipelineStep,
        AgentPipelineView,
    )

    event = {
        "event_id": "provider:root-owner-context",
        "cost_origin": "reported",
        "amount": "0.03",
        "cost_usd": 0.03,
        "settlement_status": "committed",
        "durability": "ledger",
        "control_job_attempt": 2,
        "pre_admission_attempt_id": None,
        "receipts": ["provider:root-owner-context"],
    }
    raw_step = {
        "agent": "llm_producer_settlement",
        "action": "durable_ledger",
        "cost_usd": 0.03,
        "reported_cost_usd": 0.03,
        "estimated_cost_usd": 0.05,
        "cost_events": [event],
    }
    raw_attempt = {
        "attempt": 1,
        "cost_usd": 0.03,
        "reported_cost_usd": 0.03,
        "estimated_cost_usd": 0.07,
        "steps": [raw_step],
    }

    direct_step = AgentPipelineStep.model_validate(raw_step)
    direct_attempt = AgentPipelineAttempt.model_validate(raw_attempt)
    assert direct_step.cost_usd is None
    assert direct_step.reported_cost_usd is None
    assert direct_step.estimated_cost_usd is None
    assert direct_step.cost_origin_counts == {}
    assert direct_step.settlement_event_ids == ()
    assert direct_attempt.cost_usd is None
    assert direct_attempt.reported_cost_usd is None
    assert direct_attempt.estimated_cost_usd is None
    assert direct_attempt.steps[0].cost_usd is None
    assert direct_attempt.steps[0].reported_cost_usd is None
    assert direct_attempt.steps[0].estimated_cost_usd is None

    ownerless = AgentPipelineView.model_validate(
        {
            "run_id": "run-owner-not-established",
            "source_kind": "core_run",
            "owner_control_job_attempt": 2,
            "cost_usd": 0.03,
            "reported_cost_usd": 0.03,
            "estimated_cost_usd": 0.03,
            "attempts": [raw_attempt],
        }
    )
    assert ownerless.owner_control_job_attempt is None
    assert ownerless.cost_usd is None
    assert ownerless.reported_cost_usd is None
    assert ownerless.estimated_cost_usd is None
    assert ownerless.cost_origin_counts == {}
    assert ownerless.attempts[0].cost_usd is None
    assert ownerless.attempts[0].reported_cost_usd is None
    assert ownerless.attempts[0].estimated_cost_usd is None
    assert ownerless.attempts[0].steps[0].cost_usd is None
    assert ownerless.attempts[0].steps[0].reported_cost_usd is None
    assert ownerless.attempts[0].steps[0].estimated_cost_usd is None
    assert any(
        row.source_kind == "pipeline_summary" and row.claimed_value_usd == 0.03
        for row in ownerless.unattributed_cost_scalars
    )

    # A v1.3-style payload has scalar summaries but no owner or event ledger.
    # Its three summary levels remain claims, regardless of numeric values.
    legacy_v13 = AgentPipelineView.model_validate(
        {
            "run_id": "run-legacy-v13",
            "source_kind": "core_run",
            "cost_usd": 0.31,
            "reported_cost_usd": 0.21,
            "estimated_cost_usd": 0.11,
            "attempts": [
                {
                    "attempt": 1,
                    "cost_usd": 0.31,
                    "reported_cost_usd": 0.21,
                    "estimated_cost_usd": 0.11,
                    "steps": [
                        {
                            "agent": "model_variant",
                            "action": "legacy-v13",
                            "cost_usd": 0.31,
                            "reported_cost_usd": 0.21,
                            "estimated_cost_usd": 0.11,
                        }
                    ],
                }
            ],
        }
    )
    assert legacy_v13.owner_control_job_attempt is None
    assert legacy_v13.cost_usd is None
    assert legacy_v13.reported_cost_usd is None
    assert legacy_v13.estimated_cost_usd is None
    legacy_levels = [
        legacy_v13,
        legacy_v13.attempts[0],
        legacy_v13.attempts[0].steps[0],
    ]
    assert all(
        value is None
        for level in legacy_levels
        for value in (level.cost_usd, level.reported_cost_usd, level.estimated_cost_usd)
    )
    assert {row.source_kind for row in legacy_v13.unattributed_cost_scalars} == {
        "pipeline_summary",
        "attempt_summary",
        "step_summary",
    }
    assert {row.source_field for row in legacy_v13.unattributed_cost_scalars} == {
        "cost_usd",
        "reported_cost_usd",
        "estimated_cost_usd",
    }

    # The payload owner field is only a claim: malformed context cannot promote it.
    for malformed_context in (True, 0, 1.5, "2"):
        rejected_owner = AgentPipelineView.model_validate(
            {
                "run_id": "run-unverified-owner-context",
                "source_kind": "core_run",
                "owner_control_job_attempt": 2,
                "cost_usd": 0.03,
                "attempts": [raw_attempt],
            },
            context={"verified_control_job_attempt": malformed_context},
        )
        assert rejected_owner.owner_control_job_attempt is None
        assert rejected_owner.cost_usd is None
        assert rejected_owner.attempts[0].cost_usd is None
        assert rejected_owner.attempts[0].steps[0].cost_usd is None

    # The route builds child DTOs before its verified owner has been assembled.
    # The root reprojects those complete nested rows under its explicit context.
    verified = AgentPipelineView._from_verified_owner_context(
        run_id="run-owner-established",
        source_kind="core_run",
        owner_control_job_attempt=2,
        attempts=[direct_attempt],
    )
    assert verified.owner_control_job_attempt == 2
    assert verified.cost_usd == pytest.approx(0.03)
    assert verified.reported_cost_usd == pytest.approx(0.03)
    assert verified.attempts[0].attempt == 1
    assert verified.attempts[0].cost_usd == pytest.approx(0.03)
    assert verified.attempts[0].steps[0].cost_usd == pytest.approx(0.03)
    assert verified.attempts[0].steps[0].settlement_event_ids == ("provider:root-owner-context",)
    assert {
        (row.source_kind, row.source_field, row.claimed_value_usd, row.scope)
        for row in verified.unattributed_cost_scalars
    } == {
        ("step_summary", "estimated_cost_usd", 0.05, "not_established"),
        ("attempt_summary", "estimated_cost_usd", 0.07, "not_established"),
    }

    reprojected_values = verified.model_dump(mode="python")
    reprojected_values.pop("owner_control_job_attempt")
    reprojected = AgentPipelineView._from_verified_owner_context(
        owner_control_job_attempt=2,
        **reprojected_values,
    )
    assert reprojected.cost_usd == pytest.approx(0.03)
    assert reprojected.reported_cost_usd == pytest.approx(0.03)
    assert {
        (row.source_kind, row.source_field, row.claimed_value_usd, row.scope)
        for row in reprojected.unattributed_cost_scalars
    } == {
        ("step_summary", "estimated_cost_usd", 0.05, "not_established"),
        ("attempt_summary", "estimated_cost_usd", 0.07, "not_established"),
    }

    # Identical child labels and amounts are ambiguous unless every possible child
    # is reconciled. One unsupported sibling keeps the shared claim unassigned.
    sibling_attempt = AgentPipelineAttempt.model_validate(
        {"attempt": 1, "steps": [raw_step, {**raw_step, "cost_events": []}]}
    )
    sibling_view = AgentPipelineView._from_verified_owner_context(
        run_id="run-owner-identical-sibling",
        source_kind="core_run",
        owner_control_job_attempt=2,
        attempts=[sibling_attempt],
    )
    assert sibling_view.cost_usd == pytest.approx(0.03)
    assert sibling_view.attempts[0].steps[0].cost_usd == pytest.approx(0.03)
    assert sibling_view.attempts[0].steps[1].cost_usd is None
    sibling_claims = {
        (row.source_field, row.claimed_value_usd, row.scope)
        for row in sibling_view.unattributed_cost_scalars
        if row.source_kind == "step_summary"
    }
    assert sibling_claims == {
        ("cost_usd", 0.03, "not_established"),
        ("reported_cost_usd", 0.03, "not_established"),
        ("estimated_cost_usd", 0.05, "not_established"),
    }
    sibling_reprojected_values = sibling_view.model_dump(mode="python")
    sibling_reprojected_values.pop("owner_control_job_attempt")
    sibling_reprojected = AgentPipelineView._from_verified_owner_context(
        owner_control_job_attempt=2,
        **sibling_reprojected_values,
    )
    assert sibling_reprojected.cost_usd == pytest.approx(0.03)
    assert sibling_reprojected.unattributed_cost_scalars == sibling_view.unattributed_cost_scalars

    # A summary without any eligible event remains a claim, even if the owner exists.
    no_event_rows = AgentPipelineView._from_verified_owner_context(
        run_id="run-owner-no-events",
        source_kind="core_run",
        owner_control_job_attempt=2,
        cost_usd=0.91,
        attempts=[],
    )
    assert no_event_rows.cost_usd is None
    assert any(
        row.source_kind == "pipeline_summary"
        and row.source_field == "cost_usd"
        and row.claimed_value_usd == pytest.approx(0.91)
        and row.scope == "not_established"
        for row in no_event_rows.unattributed_cost_scalars
    )

    with pytest.raises(ValidationError, match="agent_pipeline_owner_context_mismatch"):
        AgentPipelineView.model_validate(
            {
                "run_id": "run-owner-context-conflict",
                "source_kind": "core_run",
                "owner_control_job_attempt": 2,
                "attempts": [],
            },
            context={"verified_control_job_attempt": 1},
        )


def test_model_variant_details_distinguish_absent_null_and_malformed() -> None:
    from polisyos.runtime.http.services.debug import _agent_steps_from_model_variants

    def _steps(
        nested_step: dict[str, Any],
    ) -> tuple[list[Any], list[str]]:
        return _agent_steps_from_model_variants(
            {"params": {"llm_model_variants": [{"steps": [nested_step]}]}},
            sensitive_keys=(),
        )

    absent_steps, absent_notes = _steps({"agent": "critic", "action": "approved"})
    null_steps, null_notes = _steps({"agent": "critic", "action": "approved", "details": None})
    assert absent_notes == []
    assert null_notes == []
    for step in (absent_steps[0], null_steps[0]):
        assert step.details == {}
        assert step.details_cost_scope == "not_established"
        assert step.cost_usd is None
        assert step.cost_events == []

    invalid_note = "llm_model_variant_step_details_invalid_type_not_projected"
    for invalid_details in (False, 1, "not-an-object", []):
        steps, notes = _steps(
            {
                "agent": "critic",
                "action": "approved",
                "details": invalid_details,
            }
        )
        assert len(steps) == 1
        assert notes == [invalid_note]
        assert steps[0].details == {}
        assert steps[0].details_cost_scope == "not_established"
        assert steps[0].cost_usd is None
        assert steps[0].cost_events == []

    _, top_level_notes = _agent_steps_from_model_variants(
        {"params": {"llm_model_variants": [{"status": "completed", "details": False}]}},
        sensitive_keys=(),
    )
    assert top_level_notes == [invalid_note]
