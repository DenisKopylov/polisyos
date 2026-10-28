"""Exercise lease-bound cache reuse through an ordinary NL control POST."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import (
    ArtifactID,
    FileSystemCAS,
    artifact_manifest_profile_sha256,
    read_core_manifest_profile,
)
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.llm.factory import GatewayLLMConfig
from polisyos.scientist.orchestration.llm.prepared_request import prepare_immutable_call
from polisyos.scientist.orchestration.llm.prompt_cache import (
    CacheReuseDecision,
    CacheReuseRequest,
    CachingLLMClient,
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
            snapshot_ref = DataSnapshotRef(
                artifact_id=ArtifactID.model_validate(evidence.ref),
                manifest_profile_sha256=evidence.version,
            )
            manifest = read_core_manifest_profile(self._store, snapshot_ref)[0]
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

    def prepare_cache_request(self, *args: Any, **kwargs: Any) -> Any:
        return prepare_immutable_call(self.generate, args, kwargs, reusable=True)

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
            for key in ("cost_events", "nl_preflight_cost_events", "n4_generation_cost_events"):
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


def _ordinary_post_and_dispatch(
    env: dict[str, object], *, snapshot_id: str | dict[str, Any], require_completed: bool = True
) -> dict[str, Any]:
    """Run the normal POST and its already-admitted control worker to completion."""
    from polisyos.runtime.http.services.adapters.core_run import derive_control_job_core_run_id
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
    assert completed is not None
    if not require_completed:
        from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding

        scope = creation_payload["execution_scope"]
        return {
            "job": completed,
            "job_id": job_id,
            "control_run_id": job.run_id,
            "binding": BudgetLedgerProducerRunBinding(
                run_id=job.run_id,
                tenant_id=scope["tenant_id"],
                cell_id=scope["cell_id"],
                profile_id=job.effective_execution_profile,
                control_job_id=job_id,
            ),
        }
    assert completed.state == "completed"
    assert completed.progress["stage"] == "n4_proposal_only"
    assert completed.progress["status"] == "candidate_limited"
    assert completed.progress["limitation_code"] == "cycle_substrate_context_unavailable"
    assert all(
        completed.progress[stage] == "not_run" for stage in ("n5_status", "n8_status", "n9_status")
    )
    runtime_context = app.state.runtime_container.runtime_api_context
    core_run_id = str(completed.progress["core_run_id"])
    runtime_context.run_index.refresh(force=True)
    run = runtime_context.run_index.get_run(core_run_id)
    assert run is not None
    binding, note = runtime_context.debug._producer_run_binding_for_indexed_run(run)
    assert binding is not None and note is None
    # The ledger uses the persisted logical NL run; the Core index uses the
    # owner's attempt-specific derived run. Reconcile both instead of making
    # one string stand in for two different identities.
    assert binding.run_id == job.run_id == completed.run_id == creation_payload["run_id"]
    assert binding.control_job_id == job_id
    assert run.run_id == run.details.run_id == core_run_id
    core_attempt = completed.progress["core_run_attempt"]
    assert type(core_attempt) is int and core_attempt == completed.attempt and core_attempt >= 1
    assert core_run_id == derive_control_job_core_run_id(
        job_id=job_id,
        control_run_id=binding.run_id,
        attempt=core_attempt,
    )
    return {
        "job": completed,
        "job_id": job_id,
        "control_run_id": binding.run_id,
        "core_run_id": core_run_id,
        "binding": binding,
        "creation_payload": creation_payload,
        "raw_request": "Analyze a small-business liquidity support policy.",
    }


@pytest.mark.parametrize("include_span_judge", [False, True])
@pytest.mark.parametrize("exact_profile", [False, True])
def test_control_plane_reuses_only_current_owner_authorized_snapshot(
    monkeypatch: Any,
    tmp_path: Path,
    include_span_judge: bool,
    exact_profile: bool,
) -> None:
    """The ordinary NL route reuses a pinned CAS snapshot only while its owner permits it."""
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.scientist.orchestration.llm import factory as llm_factory

    # The existing built-in profile establishes its default determinism in source.
    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
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
    providers: list[SimulatedGatewayLLMClient] = []
    physical_calls: list[dict[str, Any]] = []
    original_generate = SimulatedGatewayLLMClient.generate
    owner_ref: list[_CurrentLocalSnapshotOwner] = []

    async def observe_physical(client: SimulatedGatewayLLMClient, **kwargs: Any) -> Any:
        assert owner_ref and owner_ref[0]._control_store is not None
        admission = owner_ref[0]._control_store.current_execution_job_admission()
        physical_calls.append(
            {
                "job_id": admission.job.job_id,
                "run_id": admission.job.run_id,
                "attempt": admission.attempt,
                "kwargs": dict(kwargs),
            }
        )
        if client not in providers:
            providers.append(client)
        return await original_generate(client, **kwargs)

    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", observe_physical)
    real_factory = llm_factory.create_traced_gateway_client
    pipeline_clients: list[Any] = []

    def observe_pipeline_factory(**kwargs: Any) -> Any:
        client = real_factory(**kwargs)
        if client is not None:
            pipeline_clients.append(client)
        return client

    monkeypatch.setattr(nl_pipeline, "create_traced_gateway_client", observe_pipeline_factory)
    monkeypatch.setattr(llm_factory, "create_traced_gateway_client", observe_pipeline_factory)
    if include_span_judge:
        from polisyos.runtime.quality.proving_ground import bounded_request_agent
        from polisyos.scientist.validation import citation_faithfulness

        original_admissibility = nl_pipeline._assert_design_problem_admissibility_grounded

        def observe_admissibility(**kwargs: Any) -> None:
            original_admissibility(**kwargs)
            # Exercise the real sibling validator/thread bridge under an explicit
            # test client injection. Its result supplies no authority to the compiler.
            judge_client = bounded_request_agent.create_traced_gateway_client(
                model_name="simulated-qwen",
                run_id="layer3-gy-span-support-runtime",
                model_variant_id="span-support-accounting-fixture",
            )
            assert judge_client is not None
            current = owner_ref[0]._control_store.current_execution_job_admission()
            assert judge_client._run_id == current.job.run_id
            before = len(physical_calls)
            citation_faithfulness.evaluate_span_claim_entailment(
                claim={
                    "claim_id": "claim.audit",
                    "claim_family": "causal",
                    "claim_text": "School attendance improved after the stipend program.",
                    "direction": "positive",
                    "data_refs": ["openalex:test"],
                    "source_attribution": "openalex:test",
                    "method_refs": ["did"],
                    "identification_strategy": "did",
                    "citation_refs": ["span.audit"],
                },
                evidence={
                    "ref_id": "span.audit",
                    "source_id": "openalex:test",
                    "section": "abstract",
                    "text": "We find that the program raised student participation.",
                    "source_content_sha256": "sha256:test",
                },
                client=judge_client,
            )
            citation_faithfulness._close_span_support_client(judge_client)
            assert len(physical_calls) == before + 1

        monkeypatch.setattr(
            nl_pipeline, "_assert_design_problem_admissibility_grounded", observe_admissibility
        )

    cas_root = tmp_path / ".polisyos"
    owner = _CurrentLocalSnapshotOwner(cas_root)
    owner_ref.append(owner)
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
        selected_snapshot: str | dict[str, Any] = str(snapshot_ref.artifact_id)
        if exact_profile:
            from polisyos.core.security.tenant_context import tenant_scope

            with tenant_scope(
                None, tenant_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", cell_id="cell-a"
            ):
                manifest = app.state.runtime_container.runtime_api_context.store.get_manifest(
                    snapshot_ref.artifact_id
                )
            selected_snapshot = snapshot_ref.model_copy(
                update={"manifest_profile_sha256": artifact_manifest_profile_sha256(manifest)}
            ).model_dump(mode="json")

        before_first_calls = len(physical_calls)
        first = _ordinary_post_and_dispatch(env, snapshot_id=selected_snapshot)
        first_clients = [
            client for client in pipeline_clients if client._run_id == first["control_run_id"]
        ]
        assert first_clients
        prompt_cache = app.state.runtime_container.llm_prompt_cache
        assert prompt_cache is not None
        assert all(
            isinstance(client._client, CachingLLMClient)
            and client._client._require_reuse_authorization is True
            and client._client._cache is prompt_cache
            for client in first_clients
        )
        first_physical_calls = len(physical_calls) - before_first_calls
        assert first_physical_calls > 0
        first_scope = first["creation_payload"]["execution_scope"]
        assert first_scope["actor_subject"] == first["job"].submitted_by
        ledger_path = Path(env["cas_root"]) / "runs" / ".runtime" / "llm-cost-ledger.json"
        reopened = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(ledger_path))
        first_records = reopened.list_producer_events_for_run_safe(first["binding"])
        assert first_records
        assert sum(record.cost_origin != "reuse" for record in first_records) == sum(
            call["run_id"] == first["control_run_id"] for call in physical_calls
        )
        assert all(record.control_job_attempt == first["job"].attempt for record in first_records)
        assert all(
            "cache_reuse" not in call["kwargs"].get("metadata", {})
            and "scope" not in call["kwargs"].get("metadata", {})
            and "tenant" not in call["kwargs"].get("metadata", {})
            for call in physical_calls
        )
        first_event_ids = {
            record.event_id
            for record in first_records
            if record.cost_origin in {"reported", "estimated"}
        }

        before_second_calls = len(physical_calls)
        second = _ordinary_post_and_dispatch(env, snapshot_id=selected_snapshot)
        second_clients = [
            client for client in pipeline_clients if client._run_id == second["control_run_id"]
        ]
        assert second_clients
        assert all(
            isinstance(client._client, CachingLLMClient)
            and client._client._require_reuse_authorization is True
            and client._client._cache is prompt_cache
            for client in second_clients
        )
        assert not any(client in first_clients for client in second_clients)
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
        second_records = reopened.list_producer_events_for_run_safe(second["binding"])
        reuse_rows = [record for record in second_records if record.cost_origin == "reuse"]
        assert reuse_rows
        second_physical_calls = len(physical_calls) - before_second_calls
        assert second_physical_calls < first_physical_calls
        assert all(
            record.origin_event_id in first_event_ids
            and record.amount == 0
            and record.status == "committed"
            and record.run_binding == second["binding"]
            for record in reuse_rows
        )
        api_job = env["client"].get(f"/api/v1/control/jobs/{second['job_id']}")
        assert api_job.status_code == 200, api_job.text
        assert api_job.json()["progress"]["producer_cost_projection_status"] == "reconciled"
        assert api_job.json()["progress"]["producer_cost_basis"] == "core_trace_producer_intents"
        api_reuse_rows = [
            row for row in _event_rows(api_job.json()) if row.get("cost_origin") == "reuse"
        ]
        assert api_reuse_rows
        assert {row["event_id"] for row in api_reuse_rows} <= {
            record.event_id for record in reuse_rows
        }
        records_by_id = {record.event_id: record for record in second_records}
        for row in _event_rows(api_job.json()):
            record = records_by_id[row["event_id"]]
            assert row["origin_event_id"] == record.origin_event_id
            assert row["cost_origin"] == record.cost_origin
            assert row["amount"] == (str(record.amount) if record.amount is not None else None)
            assert row["settlement_status"] == record.status
            assert row["durability"] == "ledger"
            assert row["payload_digest"] == record.payload_digest
            assert row["control_job_attempt"] == record.control_job_attempt == second["job"].attempt
            assert row["pre_admission_attempt_id"] == record.pre_admission_attempt_id
        assert all(row["origin_event_id"] in first_event_ids for row in api_reuse_rows)
        assert settlement_store.list_producer_events_for_run_safe(second["binding"])

        owner.active = False
        owner.epoch = "local-permission-revoked"
        third = _ordinary_post_and_dispatch(env, snapshot_id=selected_snapshot)
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


def _configured_cache_runtime(monkeypatch: Any, tmp_path: Path) -> tuple[Any, Any]:
    """Use the existing built-in deterministic profile and actual runtime owners."""
    from polisyos.scientist.orchestration.llm import factory as llm_factory

    monkeypatch.setenv("POLISYOS_LLM_SIMULATION_MODE", "1")
    config = GatewayLLMConfig(
        base_url="http://127.0.0.1:1/v1",
        api_key="local-profile-fixture-key",
        cache_ttl_s=60,
        cache_maxsize=32,
        enable_prompt_sanitizer=False,
    )
    monkeypatch.setattr(llm_factory.GatewayLLMConfig, "from_env", classmethod(lambda _cls: config))
    owner = _CurrentLocalSnapshotOwner(tmp_path / ".polisyos")
    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={"container_overrides": _cache_owner_override(owner)},
    )
    owner._control_store = env["app"].state._control_service._control_store
    return env, owner


@pytest.mark.parametrize("drift", ["missing", "changed", "foreign_attempt"])
def test_fresh_job_cost_projection_refuses_ledger_drift(
    monkeypatch: Any, tmp_path: Path, drift: str
) -> None:
    env, _owner = _configured_cache_runtime(monkeypatch, tmp_path)
    try:
        run = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        endpoint = f"/api/v1/control/jobs/{run['job_id']}"
        positive = env["client"].get(endpoint)
        assert positive.status_code == 200
        assert positive.json()["progress"]["producer_cost_projection_status"] == "reconciled"
        original_rows = _event_rows(positive.json())
        assert original_rows
        ledger_path = Path(env["cas_root"]) / "runs/.runtime/llm-cost-ledger.json"
        original = ledger_path.read_bytes()
        payload = json.loads(original)
        event_id = original_rows[0]["event_id"]
        if drift == "missing":
            del payload["producer_settlements"][event_id]
            payload["spend_receipts"].pop(event_id, None)
        elif drift == "changed":
            payload["producer_settlements"][event_id]["amount"] = "123.45"
            payload["spend_receipts"][event_id]["amount"] = "123.45"
        else:
            payload["producer_settlements"][event_id]["control_job_attempt"] = (
                run["job"].attempt + 1
            )
        try:
            ledger_path.write_text(json.dumps(payload))
            negative = env["client"].get(endpoint)
            assert negative.status_code == 200
            assert (
                negative.json()["progress"]["producer_cost_projection_status"] == "not_established"
            )
            assert not _event_rows(negative.json())
            assert negative.json()["progress"]["stage"] == "n4_proposal_only"
        finally:
            ledger_path.write_bytes(original)
        restored = env["client"].get(endpoint)
        assert restored.status_code == 200
        assert _event_rows(restored.json()) == original_rows
    finally:
        close_runtime_api_env(env)


@pytest.mark.parametrize("stale_field", ["attempt", "lease_owner", "actor"])
def test_matching_snapshot_decision_cannot_replace_live_job_admission(
    monkeypatch: Any, tmp_path: Path, stale_field: str
) -> None:
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

    env, owner = _configured_cache_runtime(monkeypatch, tmp_path)
    try:
        _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        original_scope = ControlPlaneStore.verify_llm_producer_admission

        def stale_scope(store: Any, *, expected: Any) -> Any:
            if stale_field == "attempt":
                expected = replace(expected, attempt=expected.attempt + 1)
            elif stale_field == "lease_owner":
                expected = replace(expected, job=replace(expected.job, lease_owner="stale-worker"))
            else:
                expected = replace(
                    expected, scope=replace(expected.scope, actor_subject="stale-actor")
                )
            return original_scope(store, expected=expected)

        # Only the captured receipt changes. The actual store, current actor,
        # permissive snapshot callback, candidate markers and cached bytes stay.
        monkeypatch.setattr(ControlPlaneStore, "verify_llm_producer_admission", stale_scope)
        physical: list[object] = []
        original_generate = SimulatedGatewayLLMClient.generate

        async def count_physical(provider: Any, **kwargs: Any) -> Any:
            physical.append(provider)
            return await original_generate(provider, **kwargs)

        monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", count_physical)
        second = _ordinary_post_and_dispatch(
            env,
            snapshot_id=str(env["data_snapshot_artifact_id"]),
            require_completed=False,
        )
        assert owner.active
        ledger = BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(Path(env["cas_root"]) / "runs/.runtime/llm-cost-ledger.json"),
        )
        rows = ledger.list_producer_events_for_run_safe(second["binding"])
        assert not physical
        assert not rows
    finally:
        close_runtime_api_env(env)


def test_ordinary_n4_unknown_provider_sampling_stays_uncached(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from polisyos.scientist.orchestration.llm import factory as llm_factory

    env, owner = _configured_cache_runtime(monkeypatch, tmp_path)
    monkeypatch.delenv("POLISYOS_LLM_SIMULATION_MODE", raising=False)
    providers: list[_CountingSimulatedGateway] = []

    def build_gateway(**kwargs: Any) -> _CountingSimulatedGateway:
        provider = _CountingSimulatedGateway(str(kwargs["model"]))
        providers.append(provider)
        return provider

    monkeypatch.setattr(llm_factory, "GatewayLLMClient", build_gateway)
    try:
        _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        before = sum(provider.calls for provider in providers)
        second = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        physical = sum(provider.calls for provider in providers) - before
        assert physical > 0
        ledger = BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(Path(env["cas_root"]) / "runs/.runtime/llm-cost-ledger.json"),
        )
        rows = ledger.list_producer_events_for_run_safe(second["binding"])
        assert len(rows) == physical
        assert not any(row.cost_origin == "reuse" for row in rows)
        assert not owner.allowed_requests
    finally:
        close_runtime_api_env(env)


def _install_unobserved_citation_call(monkeypatch: Any, owner: Any, event_ids: list[str]) -> None:
    """Exercise the actual sibling alias without a proposal call observer."""
    from polisyos.runtime.http.services.control import nl_pipeline
    from polisyos.runtime.quality.proving_ground import bounded_request_agent
    from polisyos.scientist.orchestration.engine import BudgetLedgerProducerRunBinding
    from polisyos.scientist.validation import citation_faithfulness

    original = nl_pipeline._assert_design_problem_admissibility_grounded

    def checked(**kwargs: Any) -> None:
        original(**kwargs)
        admission = owner._control_store.current_execution_job_admission()
        binding = BudgetLedgerProducerRunBinding(
            run_id=admission.job.run_id,
            control_job_id=admission.job.job_id,
            tenant_id=admission.scope.tenant_id,
            cell_id=admission.scope.cell_id,
            profile_id=admission.job.effective_execution_profile,
        )
        client = bounded_request_agent.create_traced_gateway_client(
            model_name="simulated-qwen",
            run_id="layer3-gy-span-support-runtime",
            model_variant_id="span-support-accounting-fixture",
        )
        assert client is not None and client._run_id == binding.run_id
        middleware = client._producer_settlement_store
        before = {row.event_id for row in middleware.list_producer_events_for_run_safe(binding)}
        try:
            citation_faithfulness.evaluate_span_claim_entailment(
                claim={
                    "claim_id": "claim.audit",
                    "claim_family": "causal",
                    "claim_text": "School attendance improved after the stipend program.",
                    "direction": "positive",
                    "data_refs": ["openalex:test"],
                    "source_attribution": "openalex:test",
                    "method_refs": ["did"],
                    "identification_strategy": "did",
                    "citation_refs": ["span.audit"],
                },
                evidence={
                    "ref_id": "span.audit",
                    "source_id": "openalex:test",
                    "section": "abstract",
                    "text": "We find that the program raised student participation.",
                    "source_content_sha256": "sha256:test",
                },
                client=client,
            )
        finally:
            citation_faithfulness._close_span_support_client(client)
        after = {row.event_id for row in middleware.list_producer_events_for_run_safe(binding)}
        assert len(after - before) == 1
        event_ids.extend(after - before)

    monkeypatch.setattr(nl_pipeline, "_assert_design_problem_admissibility_grounded", checked)


@pytest.mark.parametrize("removed", ["producer_row", "spend_receipt"])
def test_actual_unobserved_citation_is_in_reopened_complete_basis(
    monkeypatch: Any,
    tmp_path: Path,
    removed: str,
) -> None:
    env, owner = _configured_cache_runtime(monkeypatch, tmp_path)
    citation_ids: list[str] = []
    _install_unobserved_citation_call(monkeypatch, owner, citation_ids)
    try:
        run = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        assert len(citation_ids) == 1
        citation_id = citation_ids[0]
        _terminal, basis, proposal = _read_current_producer_source(env, run)
        assert citation_id in basis
        observed = {row.event_id for row in proposal.producer_cost_events}
        assert citation_id not in observed
        endpoint = f"/api/v1/control/jobs/{run['job_id']}"
        positive = env["client"].get(endpoint)
        assert positive.status_code == 200
        assert citation_id in {row["event_id"] for row in _event_rows(positive.json())}
        ledger = Path(env["cas_root"]) / "runs/.runtime/llm-cost-ledger.json"
        original = ledger.read_bytes()
        payload = json.loads(original)
        assert observed <= set(payload["producer_settlements"])
        if removed == "producer_row":
            del payload["producer_settlements"][citation_id]
        else:
            del payload["spend_receipts"][citation_id]
        assert observed <= set(payload["producer_settlements"])
        try:
            ledger.write_text(json.dumps(payload))
            negative = env["client"].get(endpoint)
            assert negative.status_code == 200
            assert (
                negative.json()["progress"]["producer_cost_projection_status"] == "not_established"
            )
            assert not _event_rows(negative.json())
            # Source/proposal/terminal bytes are unchanged; the separate witness
            # still names the exact missing logical producer event.
            assert citation_id in _read_current_producer_source(env, run)[1]
        finally:
            ledger.write_bytes(original)
        assert (
            env["client"].get(endpoint).json()["progress"]["producer_cost_projection_status"]
            == "reconciled"
        )
    finally:
        close_runtime_api_env(env)


@pytest.mark.parametrize(
    "changed", ["absent_attempt", "wrong_attempt", "wrong_core", "empty_stale"]
)
def test_fresh_job_reader_requires_current_typed_proposal_attempt(
    monkeypatch: Any,
    tmp_path: Path,
    changed: str,
) -> None:
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    env, _owner = _configured_cache_runtime(monkeypatch, tmp_path)
    try:
        run = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        endpoint = f"/api/v1/control/jobs/{run['job_id']}"
        assert (
            env["client"].get(endpoint).json()["progress"]["producer_cost_projection_status"]
            == "reconciled"
        )
        updates: dict[str, Any] = {}
        if changed == "absent_attempt":
            updates.update(core_run_id=None, control_job_attempt=None)
        elif changed == "wrong_core":
            updates["core_run_id"] = "other-core"
        else:
            updates["control_job_attempt"] = run["job"].attempt + 1
        if changed == "empty_stale":
            updates.update(nl_preflight_cost_events=(), n4_generation_cost_events=())
        _alternative_ref, alternate = _persist_alternative_proposal(env, run, **updates)

        def changed_reader(_repository: Any, *_args: Any, **_kwargs: Any) -> Any:
            return alternate

        monkeypatch.setattr(
            GenerationSourceRepository, "load_candidate_proposal_for_served_job", changed_reader
        )
        # A reader-boundary removal witness; actual terminal, locator and ledger
        # stay valid, so only the consumer's typed attempt comparison can refuse.
        response = env["client"].get(endpoint)
        assert response.status_code == 200
        assert response.json()["progress"]["producer_cost_projection_status"] == "not_established"
        assert not _event_rows(response.json())
    finally:
        close_runtime_api_env(env)


@pytest.mark.parametrize("failure", ["unavailable", "timeout"])
def test_fresh_job_projection_preserves_typed_dependency_failure(
    monkeypatch: Any,
    tmp_path: Path,
    failure: str,
) -> None:
    from polisyos.runtime.http.errors import (
        RuntimeDependencyTimeoutError,
        RuntimeDependencyUnavailableError,
    )

    env, _owner = _configured_cache_runtime(monkeypatch, tmp_path)
    try:
        run = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        middleware = env["app"].state.runtime_container.llm_producer_settlement_store
        error = (
            RuntimeDependencyUnavailableError
            if failure == "unavailable"
            else RuntimeDependencyTimeoutError
        )("control_plane_store")

        def unavailable(_binding: Any) -> Any:
            raise error

        monkeypatch.setattr(middleware, "list_producer_events_for_run_safe", unavailable)
        response = env["client"].get(f"/api/v1/control/jobs/{run['job_id']}")
        assert response.status_code == error.status_code
        assert not _event_rows(response.json())
    finally:
        close_runtime_api_env(env)


def _read_current_producer_source(env: Any, run: Any) -> tuple[Any, Any, Any]:
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.http.services.adapters.core_run import (
        load_completed_control_job_core_run_source,
    )
    from polisyos.runtime.http.services.control.producer_basis import (
        read_control_job_producer_basis,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalLocator,
    )

    service = env["app"].state._control_service
    with tenant_scope(None, tenant_id=run["binding"].tenant_id, cell_id=run["binding"].cell_id):
        terminal = load_completed_control_job_core_run_source(
            store=service._artifact_store,
            core_runs_root=service._core_runs_root,
            job=run["job"],
            expected_control_run_id=run["control_run_id"],
            tenant_id=run["binding"].tenant_id,
            cell_id=run["binding"].cell_id,
        )
        basis = read_control_job_producer_basis(
            store=service._artifact_store,
            terminal=terminal,
            run_binding=run["binding"],
            attempt=run["job"].attempt,
        )
        proposal = GenerationSourceRepository(
            service._artifact_store
        ).load_candidate_proposal_for_served_job(
            N4CandidateProposalLocator.model_validate(
                run["job"].progress["candidate_proposal_ref"]
            ),
            job_id=run["job_id"],
            run_id=run["control_run_id"],
            tenant_id=run["binding"].tenant_id,
            cell_id=run["binding"].cell_id,
            raw_request=run["raw_request"],
        )
    return terminal, basis, proposal


def _persist_alternative_proposal(env: Any, run: Any, **updates: Any) -> tuple[Any, Any]:
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateProposalLocator,
    )

    service = env["app"].state._control_service
    source = _read_current_producer_source(env, run)[2]
    arguments = {
        "job_id": run["job_id"],
        "run_id": run["control_run_id"],
        "tenant_id": run["binding"].tenant_id,
        "cell_id": run["binding"].cell_id,
        "raw_request": run["raw_request"],
        "problem": source.problem,
        "proposal": source.proposal,
        "simulation_disposition": source.simulation_disposition,
        "nl_preflight_cost_events": source.nl_preflight_cost_events,
        "n4_generation_cost_events": source.n4_generation_cost_events,
        "core_run_id": source.core_run_id,
        "control_job_attempt": source.control_job_attempt,
    }
    arguments.update(updates)
    with tenant_scope(None, tenant_id=run["binding"].tenant_id, cell_id=run["binding"].cell_id):
        repository = GenerationSourceRepository(service._artifact_store)
        reference = repository.persist_candidate_proposal(**arguments)
        alternate = repository.load_candidate_proposal_for_served_job(
            N4CandidateProposalLocator(artifact_ref=reference),
            job_id=run["job_id"],
            run_id=run["control_run_id"],
            tenant_id=run["binding"].tenant_id,
            cell_id=run["binding"].cell_id,
            raw_request=run["raw_request"],
        )
    return reference, alternate


def test_fresh_job_reader_joins_exact_proposal_output_profile(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    from polisyos.runtime.quality.generation_source import N4CandidateProposalLocator

    env, _owner = _configured_cache_runtime(monkeypatch, tmp_path)
    try:
        run = _ordinary_post_and_dispatch(env, snapshot_id=str(env["data_snapshot_artifact_id"]))
        endpoint = f"/api/v1/control/jobs/{run['job_id']}"
        assert (
            env["client"].get(endpoint).json()["progress"]["producer_cost_projection_status"]
            == "reconciled"
        )
        alternative_ref, alternate = _persist_alternative_proposal(
            env,
            run,
            nl_preflight_cost_events=(),
            n4_generation_cost_events=(),
        )
        assert alternate.core_run_id == run["core_run_id"]
        assert alternate.control_job_attempt == run["job"].attempt
        control_store = env["app"].state._control_service._control_store
        original = control_store.get_job

        def swapped(job_id: str) -> Any:
            record = original(job_id)
            if job_id != run["job_id"] or record is None:
                return record
            return replace(
                record,
                progress={
                    **record.progress,
                    "candidate_proposal_ref": N4CandidateProposalLocator(
                        artifact_ref=alternative_ref
                    ).model_dump(mode="json"),
                },
            )

        monkeypatch.setattr(control_store, "get_job", swapped)
        # Both sources are valid for the same job/run/request/attempt. The new
        # locator alone is not the proposal selected by the terminal output.
        response = env["client"].get(endpoint)
        assert response.status_code == 200
        assert response.json()["progress"]["producer_cost_projection_status"] == "not_established"
        assert not _event_rows(response.json())
    finally:
        close_runtime_api_env(env)


def test_ordinary_job_refuses_an_actual_begin_without_attempt_attribution(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    """A live admitted job cannot substitute expected facts for its ledger receipt."""
    env, owner = _configured_cache_runtime(monkeypatch, tmp_path)
    original_begin = BudgetMiddleware.begin_producer_event_safe
    actual_begins: list[Any] = []
    physical_job_calls: list[str] = []
    original_generate = SimulatedGatewayLLMClient.generate

    def lose_actual_attempt(middleware: Any, *args: Any, **kwargs: Any) -> Any:
        current = middleware._producer_attempt_scope.get()
        if current is None or current.control_job_attempt is None:
            return original_begin(middleware, *args, **kwargs)
        token = middleware._producer_attempt_scope.set(None)
        try:
            receipt = original_begin(middleware, *args, **kwargs)
            actual_begins.append(receipt)
            return receipt
        finally:
            middleware._producer_attempt_scope.reset(token)

    async def count_job_physical(provider: Any, **kwargs: Any) -> Any:
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            ControlJobLeaseLostError,
        )

        try:
            admission = owner._control_store.current_execution_job_admission()
        except (ControlJobExecutionAdmissionError, ControlJobLeaseLostError):
            pass  # The separate POST pre-admission producer is outside this job.
        else:
            physical_job_calls.append(admission.job.job_id)
        return await original_generate(provider, **kwargs)

    monkeypatch.setattr(BudgetMiddleware, "begin_producer_event_safe", lose_actual_attempt)
    monkeypatch.setattr(SimulatedGatewayLLMClient, "generate", count_job_physical)
    try:
        run = _ordinary_post_and_dispatch(
            env, snapshot_id=str(env["data_snapshot_artifact_id"]), require_completed=False
        )
        assert run["job"].state == "failed"
        assert actual_begins and not physical_job_calls
        assert all(row.run_binding == run["binding"] for row in actual_begins)
        assert all(
            row.control_job_attempt is None and row.status == "pending" for row in actual_begins
        )
        ledger = FileBudgetLedger(Path(env["cas_root"]) / "runs/.runtime/llm-cost-ledger.json")
        rows = ledger.list_producer_events_for_run(run["binding"])
        assert {row.event_id for row in rows} == {row.event_id for row in actual_begins}
        assert all(row.control_job_attempt is None and row.status == "pending" for row in rows)
        response = env["client"].get(f"/api/v1/control/jobs/{run['job_id']}")
        assert response.status_code == 200
        # Preserve any separate, legitimately attributed POST pre-admission
        # accounting; a failed job has no complete current producer basis.
        assert response.json()["progress"].get("producer_cost_projection_status") != "reconciled"
    finally:
        close_runtime_api_env(env)
