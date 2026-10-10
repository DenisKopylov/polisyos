from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.control import CatalogRunProfile, DataResolveRequest
from polisyos.core.contracts.execution_plan import MethodCatalogSnapshot, MethodCatalogSnapshotRef
from polisyos.core.llm.traced_client import TracedLLMClient
from polisyos.runtime.http.execution_policy import RuntimeExecutionPolicyResolver
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control.nl_pipeline import _artifact_ref_from_ref_payload
from polisyos.runtime.http.services.control_registry_providers import ControlRegistryProviders
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CachingLLMClient,
    InMemoryPromptCache,
)
from polisyos.scientist.orchestration.llm.simulated_gateway import SimulatedGatewayLLMClient
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


class _FakeRetrievalService:
    instances: ClassVar[list[_FakeRetrievalService]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
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
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    captured: dict[str, Any] = {}

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
        return _CancelCacheOwnerOnce(
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

    monkeypatch.setattr(
        "polisyos.runtime.http.services.control.nl_pipeline.create_traced_gateway_client",
        _build_monetary_client,
    )
    monkeypatch.setattr("polisyos.fabric.retrieval.RetrievalService", _FakeRetrievalService)
    monkeypatch.setattr("polisyos.scientist.api.run_experiment", _capture_state)
    monkeypatch.setattr(
        "polisyos.foundry.methods.catalog.ensure_all_methods_registered",
        lambda: None,
    )

    def _build_test_catalog_snapshot(*, run_id: str | None = None) -> MethodCatalogSnapshot:
        return MethodCatalogSnapshot(snapshot_id=f"test-catalog-{run_id or 'run'}", run_id=run_id)

    def _persist_test_catalog_snapshot(
        _store: object,
        _snapshot: MethodCatalogSnapshot,
    ) -> MethodCatalogSnapshotRef:
        return MethodCatalogSnapshotRef(artifact_id="sha256:" + "2" * 64)

    monkeypatch.setattr(
        "polisyos.foundry.methods.build_method_catalog_snapshot",
        _build_test_catalog_snapshot,
    )
    monkeypatch.setattr(
        "polisyos.foundry.methods.persist_method_catalog_snapshot",
        _persist_test_catalog_snapshot,
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
    from polisyos.core.artifacts.manifest import ArtifactRef, ArtifactTenantContextInfo, SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.runtime.http.services.control import nl_pipeline as nl_pipeline_module
    from polisyos.runtime.http.services.control.artifacts import (
        verify_runtime_authority_artifact_identity,
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
    observed_authority_ids: set[str] = set()

    def _put_json_with_sibling_default(obj, write_options, canon_spec=None):
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
        ref = original_put_json(obj, write_options, canon_spec)
        if write_options.kind == "runtime_quality.evidence_authority_envelope":
            authority_envelope_puts.append(ref)
        return ref

    monkeypatch.setattr(artifact_store, "put_json", _put_json_with_sibling_default)

    def _recording_get_bytes(artifact_ref):
        artifact_id = str(getattr(artifact_ref, "artifact_id", artifact_ref))
        if artifact_id in observed_authority_ids:
            authority_envelope_reads.append(artifact_ref)
        return original_get_bytes(artifact_ref)

    artifact_store.get_bytes = _recording_get_bytes

    async def _run_blocking_with_sibling_manifest(function, *args, **kwargs):
        result = await original_run_blocking_async(function, *args, **kwargs)
        if function is nl_pipeline_module.write_runtime_authority_artifact:
            writer_store, _event_log, _payload, writer_options = args
            assert writer_store is artifact_store
            readback = verify_runtime_authority_artifact_identity(
                writer_store,
                artifact_id=result.cas_ref.artifact_id,
                opts=writer_options,
                expected_context=result.identity_context,
            )
            assert readback.cas_ref == result.cas_ref
            assert readback.authority_envelope_ref == result.authority_envelope_ref
            assert readback.identity_context == result.identity_context
            authority_write_options.append((result, writer_options))
            selected_ref = result.authority_envelope_ref
            selected_id = str(selected_ref.artifact_id)
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
        service._execute_nl_pipeline(
            run_id=run_id,
            nl_request="Develop an optimal policy for wartime MSMEs in Ukraine.",
            context={
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
            },
            domain_hint="Ukraine wartime MSME support policy",
            data_source=None,
            max_iterations=1,
            llm_models=["simulated-qwen"],
            max_parallel_models=1,
            run_budget_usd=None,
            per_model_budget_usd=None,
            checkpoint_policy="strict",
            execution_plan_ref=None,
            execution_plan_payload=None,
            stop_criteria_payload={},
            governance_constraints_payload=[],
            expected_outputs_payload=[],
            allow_mock_fallback=False,
        )
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
    assert [selected for selected, _sibling in authority_envelope_pairs] == authority_envelope_puts
    assert production_authority_envelope_reads == [
        selected for selected, _sibling in authority_envelope_pairs
    ]
    assert all(isinstance(ref, ArtifactRef) for ref in production_authority_envelope_reads)
    assert all(
        selected.artifact_id == sibling.artifact_id
        and selected.kind == sibling.kind == "runtime_quality.evidence_authority_envelope"
        and selected.media_type == sibling.media_type == "application/json"
        and selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
        for selected, sibling in authority_envelope_pairs
    )
    assert authority_envelope_default_views[0].manifest_profile_sha256 is None


def test_ordinary_nl_post_persists_and_serves_durable_cost_events_after_reopen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.scientist.orchestration.engine.budget import BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import (
        FileBudgetLedger,
    )
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    _forbid_real_gateway_network(monkeypatch)
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService.resolve",
        _FakeRetrievalService.resolve,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.RetrievalService.execute_fetch_plans",
        _FakeRetrievalService.execute_fetch_plans,
    )
    try:
        client = env["client"]
        assert client is not None
        ordinary_run = submit_ordinary_nl_post(env)
        job = ordinary_run["job"]
        job_id = str(ordinary_run["job_id"])
        creation_payload = ordinary_run["creation_payload"]
        creation_outbox = ordinary_run["creation_outbox"]
        assert creation_outbox.payload == creation_payload
        assert creation_payload.get("execution_scope", {}).get("status") == "established"
        completed = job
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
        assert details.root_artifacts

        ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
        reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))

        # This durable begin is the exact crash boundary: the provider intent
        # is written under the admitted run owner and no terminal settlement
        # follows before the ledger is reopened and read by a fresh GET.
        with reopened.producer_run_binding_scope(binding):
            pending = reopened.begin_producer_event_safe(
                "crash-after-begin:ordinary-nl-route",
                "a" * 64,
                key=f"nl-run:{job.run_id}",
                model="simulated-qwen",
                provider="simulated_gateway",
            )
        assert pending.status == "pending" and pending.amount is None
        runtime_context.debug.bind_producer_settlement_store(reopened)
        tampered_run = replace(
            run,
            details=run.details.model_copy(update={"control_job_id": "foreign-job"}),
        )
        rejected_steps, rejection = runtime_context.debug._agent_steps_from_producer_ledger(
            tampered_run
        )
        assert rejected_steps == []
        assert rejection == "llm_producer_control_job_owner_not_established"

        runtime_context.debug.get_run_agents(run)
        response = client.get(f"/api/v1/runs/{core_run_id}/agents")
        assert response.status_code == 200, response.text
        pipeline = response.json()["pipeline"]
        served_events = [
            event
            for attempt in pipeline["attempts"]
            for step in attempt["steps"]
            for event in step.get("cost_events", [])
        ]
        served_by_id = {event["event_id"]: event for event in served_events}
        assert pending.event_id in served_by_id
        pending_view = served_by_id[pending.event_id]
        assert pending_view["settlement_status"] == "pending"
        assert pending_view["cost_origin"] == "unknown"
        assert pending_view["amount"] is None
        assert pending_view["durability"] == "ledger"
        assert pending_view["receipts"] == []
        assert pipeline["cost_usd"] is None
        assert pending_view["model"] == "simulated-qwen"
    finally:
        close_runtime_api_env(env)
