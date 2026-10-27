"""Exercise lease-bound cache reuse through an ordinary NL control POST."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    FileSystemCAS,
    artifact_manifest_profile_sha256,
)
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import GatewayLLMConfig
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReuseRequest,
)
from polisyos.scientist.orchestration.llm.simulated_gateway import (
    DEFAULT_SIMULATED_MODEL_IDS,
    SimulatedGatewayLLMClient,
)
from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env


class _CurrentLocalSnapshotOwner:
    """Test-only permission owner that reopens the exact fixture CAS snapshot."""

    def __init__(self, cas_root: Path) -> None:
        self._store = FileSystemCAS(cas_root, ownership_enforced=True)
        self._control_store: Any | None = None
        self.epoch = "local-permission-epoch-1"
        self.active = True
        self.requests: list[CacheReuseRequest] = []
        self.allowed_requests: list[CacheReuseRequest] = []

    def authorize_reuse(self, request: CacheReuseRequest) -> CacheReuseDecision | None:
        self.requests.append(request)
        if not self.active or self._control_store is None:
            return None
        try:
            admission = self._control_store.current_execution_job_admission()
            scope = admission.scope
            if (
                scope.status != "established"
                or scope.actor_authenticated is not True
                or not scope.actor_subject
                or request.actor_id != scope.actor_subject
                or request.tenant != scope.tenant_id
                or request.scope != f"{scope.tenant_id}/{scope.cell_id}"
                or len(request.evidence) != 1
            ):
                return None
            evidence = request.evidence[0]
            snapshot_ref = DataSnapshotRef(artifact_id=ArtifactID.model_validate(evidence.ref))
            manifest = self._store.get_manifest(snapshot_ref.artifact_id)
            content = self._store.get_bytes(snapshot_ref.artifact_id)
            digest = "sha256:" + hashlib.sha256(content).hexdigest()
            if (
                manifest.kind != snapshot_ref.kind
                or manifest.media_type != snapshot_ref.media_type
                or manifest.artifact_id != snapshot_ref.artifact_id
                or manifest.integrity.sha256 != digest.removeprefix("sha256:")
                or evidence.version != artifact_manifest_profile_sha256(manifest)
                or evidence.immutable is not True
                or evidence.content != content
                or evidence.content_hash != digest
                or str(manifest.artifact_id) != digest
            ):
                return None
        except Exception:
            return None
        self.allowed_requests.append(request)
        return CacheReuseDecision(
            issuer="local-test-snapshot-owner",
            epoch=self.epoch,
            actor_id=request.actor_id,
            tenant=request.tenant,
            scope=request.scope,
            purpose=request.purpose,
            model=request.model,
            parameters_digest=request.parameters_digest,
            evidence=request.evidence,
        )


class _CountingSimulatedGateway:
    """Keep NL outputs valid while counting physical provider calls."""

    provider = "r3-local-simulated"

    def __init__(self, model: str) -> None:
        self.calls = 0
        self._client = SimulatedGatewayLLMClient(
            model=model,
            provider_hint=self.provider,
            supported_model_ids=tuple(dict.fromkeys((model, *DEFAULT_SIMULATED_MODEL_IDS))),
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)

    async def generate(self, **kwargs: Any) -> Any:
        self.calls += 1
        return await self._client.generate(**kwargs)


def _cache_owner_override(owner: _CurrentLocalSnapshotOwner) -> RuntimeContainerOverrides:
    """Attach the candidate DI field without making the baseline test fail at construction."""
    overrides = RuntimeContainerOverrides()
    object.__setattr__(overrides, "llm_cache_reuse_authorizer", owner)
    return overrides


def _event_rows(value: object) -> list[dict[str, Any]]:
    """Collect serialized cost rows from the ordinary control-job API view."""
    rows: list[dict[str, Any]] = []

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for key in ("cost_events", "nl_preflight_cost_events"):
                raw = item.get(key)
                if isinstance(raw, list):
                    rows.extend(row for row in raw if isinstance(row, dict))
            for nested in item.values():
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    return rows


def _ordinary_post_and_dispatch(env: dict[str, object], *, snapshot_id: str) -> dict[str, Any]:
    """Run the normal POST and its already-admitted control worker to completion."""
    from tests._helpers.control_worker import dispatch_one_control_job

    client = env["client"]
    app = env["app"]
    control_service = app.state._control_service
    worker = getattr(control_service, "_worker", None)
    if worker is not None:
        worker.stop()
    response = client.post(
        "/api/v1/control/runs/nl",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json={
            "request": "Analyze a small-business liquidity support policy.",
            "llm_model": "simulated-qwen",
            "max_iterations": 1,
            "data_source": {"data_snapshot_ref": snapshot_id},
        },
    )
    assert response.status_code == 200, response.text
    launch = response.json()
    job_id = str(launch["job_id"])
    control_store = control_service._control_store
    job = control_store.get_job(job_id)
    assert job is not None and job.run_id
    creation_payload = control_store.get_job_created_event_payload(job_id)
    assert creation_payload["execution_scope"]["status"] == "established"
    dispatch_one_control_job(
        store=control_store,
        handler=control_service._process_control_job,
        expected_job_id=job_id,
    )
    completed = control_store.get_job(job_id)
    assert completed is not None and completed.state == "completed"
    runtime_context = app.state.runtime_container.runtime_api_context
    core_run_id = str(completed.progress["core_run_id"])
    runtime_context.run_index.refresh(force=True)
    run = runtime_context.run_index.get_run(core_run_id)
    assert run is not None
    binding, note = runtime_context.debug._producer_run_binding_for_indexed_run(run)
    assert binding is not None and note is None
    assert binding.run_id == core_run_id
    assert binding.control_job_id == job_id
    return {
        "job": completed,
        "job_id": job_id,
        "run_id": core_run_id,
        "binding": binding,
        "creation_payload": creation_payload,
    }


def test_control_plane_reuses_only_current_owner_authorized_snapshot(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """The ordinary NL route reuses a pinned CAS snapshot only while its owner permits it."""
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.scientist.orchestration.llm import factory as llm_factory

    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    local_config = GatewayLLMConfig(
        base_url="http://127.0.0.1:1/v1",
        api_key="sk-r3-local-fixture-key",
        timeout_s=2.0,
        max_retries=0,
        cache_ttl_s=60.0,
        cache_maxsize=32,
        enable_prompt_sanitizer=False,
    )
    monkeypatch.setattr(
        llm_factory.GatewayLLMConfig,
        "from_env",
        classmethod(lambda _cls: local_config),
    )
    providers: list[_CountingSimulatedGateway] = []

    def build_gateway(**kwargs: Any) -> _CountingSimulatedGateway:
        provider = _CountingSimulatedGateway(str(kwargs["model"]))
        providers.append(provider)
        return provider

    monkeypatch.setattr(llm_factory, "GatewayLLMClient", build_gateway)
    real_factory = llm_factory.create_traced_gateway_client
    pipeline_clients: list[Any] = []

    def observe_pipeline_factory(**kwargs: Any) -> Any:
        client = real_factory(**kwargs)
        if kwargs.get("require_reuse_authorization") is True:
            pipeline_clients.append(client)
        return client

    monkeypatch.setattr(nl_pipeline, "create_traced_gateway_client", observe_pipeline_factory)

    cas_root = tmp_path / ".polisyos"
    owner = _CurrentLocalSnapshotOwner(cas_root)
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "container_overrides": _cache_owner_override(owner),
        },
    )
    try:
        app = env["app"]
        control_service = app.state._control_service
        owner._control_store = control_service._control_store
        snapshot_id = str(env["data_snapshot_artifact_id"])
        snapshot_ref = DataSnapshotRef(artifact_id=ArtifactID.model_validate(snapshot_id))
        assert snapshot_ref.kind == "fabric.data_snapshot"

        first = _ordinary_post_and_dispatch(env, snapshot_id=str(snapshot_ref.artifact_id))
        assert len(pipeline_clients) == 1
        first_provider = pipeline_clients[-1]._client._client
        first_physical_calls = first_provider.calls
        assert first_physical_calls > 0
        first_scope = first["creation_payload"]["execution_scope"]
        assert first_scope["actor_subject"] == first["job"].submitted_by

        second = _ordinary_post_and_dispatch(env, snapshot_id=str(snapshot_ref.artifact_id))
        assert len(pipeline_clients) == 2
        second_provider = pipeline_clients[-1]._client._client
        assert owner.allowed_requests
        second_scope = second["creation_payload"]["execution_scope"]
        assert second_scope["actor_subject"] == second["job"].submitted_by
        assert any(
            request.actor_id == second_scope["actor_subject"]
            and request.tenant == second_scope["tenant_id"]
            and request.scope == f"{second_scope['tenant_id']}/{second_scope['cell_id']}"
            for request in owner.allowed_requests
        )

        settlement_store = app.state.runtime_container.llm_producer_settlement_store
        ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
        reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        second_records = reopened.list_producer_events_for_run_safe(second["binding"])
        reuse_rows = [record for record in second_records if record.cost_origin == "reuse"]
        assert reuse_rows
        assert second_provider.calls < first_physical_calls
        assert all(record.origin_event_id and record.amount == 0 for record in reuse_rows)
        api_job = env["client"].get(f"/api/v1/control/jobs/{second['job_id']}")
        assert api_job.status_code == 200, api_job.text
        assert any(row.get("cost_origin") == "reuse" for row in _event_rows(api_job.json()))
        assert settlement_store.list_producer_events_for_run_safe(second["binding"])

        owner.active = False
        owner.epoch = "local-permission-revoked"
        third = _ordinary_post_and_dispatch(env, snapshot_id=str(snapshot_ref.artifact_id))
        third_records = reopened.list_producer_events_for_run_safe(third["binding"])
        assert not any(record.cost_origin == "reuse" for record in third_records)
        assert third_records
    finally:
        close_runtime_api_env(env)


@pytest.mark.parametrize("configured", [False, True])
def test_authorizer_preserves_no_key_and_explicit_uncached_modes(
    monkeypatch: Any,
    tmp_path: Path,
    configured: bool,
) -> None:
    """Providing an authorizer never creates an unusable/disabled cache."""
    from polisyos.scientist.orchestration.llm import factory as llm_factory

    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    gateway = (
        GatewayLLMConfig(
            base_url="http://127.0.0.1:1/v1",
            api_key="local-fixture-key",
            cache_maxsize=0,
            cache_ttl_s=60,
        )
        if configured
        else None
    )
    monkeypatch.setattr(llm_factory.GatewayLLMConfig, "from_env", classmethod(lambda _cls: gateway))
    owner = _CurrentLocalSnapshotOwner(tmp_path / ".polisyos")
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"container_overrides": _cache_owner_override(owner)},
    )
    try:
        assert env["app"].state.runtime_container.llm_prompt_cache is None
    finally:
        close_runtime_api_env(env)
