from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.ingestion.ingestion_providers import resolve_ingestion_dependencies
from polisyos.ir.connectors import DataVersion, VersionStrategy

_TENANT_A = "00000000-0000-0000-0000-00000000000a"
_PATH_TENANT = "00000000-0000-0000-0000-0000000000ff"


class _NoopSimulator:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def __aenter__(self) -> _NoopSimulator:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False


class _ReplayStoreStub:
    seen_stores: list[object] = []

    def __init__(self, store: object) -> None:
        self._store = store
        self.seen_stores.append(store)

    def save_record_session(self, session: object) -> SimpleNamespace:
        del session
        return SimpleNamespace(artifact_id=SimpleNamespace(hex="record-ref"))

    def load_record_session(self, artifact_id: object) -> object:
        del artifact_id
        return {"session": "replay"}

    def build_replay_fixture_dir(self, session: object, fixture_dir: object) -> None:
        del session, fixture_dir


def _ingestion_bundle(base_root: Path):
    from polisyos.fabric.storage.tenant_cas import TenantSidecarScope

    store = FileSystemCAS(base_root)
    requested_roots: list[Path] = []

    def factory(root: Path):
        requested_roots.append(Path(root))
        return store

    scope = TenantSidecarScope.for_base_root(base_root, _TENANT_A)
    dependencies = resolve_ingestion_dependencies(
        registry=ConnectorRegistry.get_instance(bootstrap=False),
        store_factory=factory,
    )
    return store, requested_roots, scope, dependencies


def _manifest(*, datasets: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "datasets": datasets
        if datasets is not None
        else [{"connector_id": "custody.test@1.0.0", "dataset_id": "events"}],
    }


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        evidence_bundle_ref=None,
        data_snapshot_ref=None,
        datasets_fetched=0,
        warnings=[],
        cursor_ref=None,
        mode_effective="batch_full",
    )


def _inline_blocking_call(monkeypatch: pytest.MonkeyPatch, modes_module: Any) -> None:
    async def inline(func: Any, /, *args: Any, timeout_seconds: float | None = None, **kwargs: Any):
        del timeout_seconds
        return func(*args, **kwargs)

    monkeypatch.setattr(modes_module, "run_blocking_async", inline)


def test_all_mode_paths_forward_the_supplied_dependencies_and_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polisyos.fabric.evidence as evidence_module
    import polisyos.fabric.ingestion as ingestion_module
    from polisyos.fabric.connectors.testing import simulator as simulator_module
    from polisyos.fabric.data_plane import cursor_store as cursor_store_module
    from polisyos.fabric.data_plane import modes as modes_module
    from polisyos.fabric.data_plane import orchestrator as orchestrator_module
    from polisyos.fabric.data_plane import replay_store as replay_store_module
    from polisyos.fabric.data_plane import streaming as streaming_module

    base_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"
    store, requested_roots, scope, dependencies = _ingestion_bundle(base_root)
    cursor_observations: list[tuple[object, Path]] = []
    orchestrator_dependencies: list[object] = []
    connector_dependencies: list[object] = []
    streaming_observations: list[tuple[object, object, object]] = []
    source_ref = SimpleNamespace(artifact_id=SimpleNamespace(hex="stream-source"))
    manifest_ref = SimpleNamespace(artifact_id=SimpleNamespace(hex="stream-manifest"))
    evidence_bundle = object()
    evidence_ref = SimpleNamespace(artifact_id=SimpleNamespace(hex="stream-evidence"))

    class CursorStoreSpy:
        def __init__(self, supplied_store: object, *, index_root: Path):
            cursor_observations.append((supplied_store, Path(index_root)))

        def find_latest_cursor(self, *args: Any, **kwargs: Any):
            del args, kwargs
            return None

    monkeypatch.setattr(cursor_store_module, "CursorStore", CursorStoreSpy)
    monkeypatch.setattr(modes_module, "_resolve_dataset_connectors", lambda *_args: {})

    def capture_orchestrator(**kwargs: Any) -> Any:
        assert kwargs["ingestion_dependencies"] is dependencies
        assert kwargs["sidecar_scope"] is scope
        orchestrator_dependencies.append(kwargs["ingestion_dependencies"])
        return _result()

    monkeypatch.setattr(
        orchestrator_module,
        "run_orchestrated_ingestion",
        capture_orchestrator,
    )
    _ReplayStoreStub.seen_stores.clear()
    monkeypatch.setattr(replay_store_module, "ReplayStore", _ReplayStoreStub)
    monkeypatch.setattr(simulator_module, "APISimulator", _NoopSimulator)
    _inline_blocking_call(monkeypatch, modes_module)

    def capture_connectors(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["dependencies"] is dependencies
        assert kwargs["sidecar_scope"] is scope
        connector_dependencies.append(kwargs["dependencies"])
        return SimpleNamespace(artifact_id=SimpleNamespace(hex="evidence-ref"))

    monkeypatch.setattr(ingestion_module, "run_connectors_ingestion", capture_connectors)

    modes_module.run_batch_incremental(
        connector_manifest=_manifest(),
        source="test",
        license_name="MIT",
        cas_root=base_root,
        produce_snapshot=False,
        ingestion_dependencies=dependencies,
        sidecar_scope=scope,
    )
    modes_module.run_record_mode(
        connector_manifest=_manifest(),
        source="test",
        license_name="MIT",
        cas_root=base_root,
        ingestion_dependencies=dependencies,
        sidecar_scope=scope,
    )
    modes_module.run_replay_mode(
        connector_manifest=_manifest(),
        source="test",
        license_name="MIT",
        cas_root=base_root,
        replay_ref="sha256:" + "0" * 64,
        ingestion_dependencies=dependencies,
        sidecar_scope=scope,
    )

    async def capture_stream_dataset(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["registry"] is dependencies.registry
        assert kwargs["store"] is store
        streaming_observations.append(
            (kwargs["store"], kwargs["cursor_store"], kwargs["registry"])
        )
        return SimpleNamespace(
            warnings=[],
            chunk_refs=[source_ref],
            window_refs=[],
            cdc_event_refs=[],
            chunks_processed=1,
            rows_emitted=1,
            quarantined_rows=0,
            final_cursor_ref=None,
        )

    async def capture_stream_manifest(**kwargs: Any) -> object:
        assert kwargs["store"] is store
        assert kwargs["source_refs"] == [source_ref]
        return manifest_ref

    def capture_evidence_bundle(**kwargs: Any) -> object:
        assert kwargs["sources"] == [manifest_ref, source_ref]
        return evidence_bundle

    def capture_persist_evidence(supplied_store: object, bundle: object) -> object:
        assert supplied_store is store
        assert bundle is evidence_bundle
        return evidence_ref

    monkeypatch.setattr(modes_module, "_connector_is_registered", lambda *_a, **_k: True)
    monkeypatch.setattr(
        streaming_module, "_resolve_stream_schema_binding", lambda *_a, **_k: None
    )
    monkeypatch.setattr(streaming_module, "process_stream_dataset", capture_stream_dataset)
    monkeypatch.setattr(
        modes_module, "_persist_streaming_manifest_async", capture_stream_manifest
    )
    monkeypatch.setattr(evidence_module, "build_evidence_bundle", capture_evidence_bundle)
    monkeypatch.setattr(evidence_module, "persist_evidence_bundle", capture_persist_evidence)

    streaming_result = asyncio.run(
        modes_module._run_streaming_windowed_async(
            connector_manifest=_manifest(),
            source="test",
            license_name="MIT",
            cas_root=base_root,
            produce_snapshot=False,
            ingestion_dependencies=dependencies,
            sidecar_scope=scope,
        )
    )

    assert orchestrator_dependencies == [dependencies]
    assert connector_dependencies == [dependencies, dependencies]
    assert len(streaming_observations) == 1
    assert streaming_observations[0][0] is store
    assert isinstance(streaming_observations[0][1], CursorStoreSpy)
    assert streaming_observations[0][2] is dependencies.registry
    assert streaming_result.evidence_bundle_ref is evidence_ref
    assert streaming_result.mode_effective == "streaming_windowed"
    assert requested_roots == [base_root] * 4
    assert [supplied for supplied, _root in cursor_observations] == [store, store]
    assert [root for _supplied, root in cursor_observations] == [
        scope.cursor_index_root,
        scope.cursor_index_root,
    ]
    assert _ReplayStoreStub.seen_stores == [store, store]


def test_cursor_registry_adaptation_preserves_other_providers(
    tmp_path: Path,
) -> None:
    from polisyos.fabric.data_plane.modes import _cursor_aware_dependencies

    base_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"
    _store, _requested_roots, _scope, dependencies = _ingestion_bundle(base_root)
    adapted = _cursor_aware_dependencies(
        dependencies,
        {
            ("custody.test@1.0.0", "events"): DataVersion(
                strategy=VersionStrategy.REVISION,
                value="17",
                timestamp=datetime(2026, 9, 28, tzinfo=UTC),
            )
        },
    )

    assert adapted is not dependencies
    assert adapted.registry is not dependencies.registry
    assert adapted.tracer is dependencies.tracer
    assert adapted.metrics is dependencies.metrics
    assert adapted.store_factory is dependencies.store_factory


def test_record_capture_failure_does_not_retry_ordinary_ingestion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polisyos.fabric.connectors.testing import simulator as simulator_module
    from polisyos.fabric.data_plane import modes as modes_module
    from polisyos.fabric.data_plane import orchestrator as orchestrator_module

    _inline_blocking_call(monkeypatch, modes_module)
    monkeypatch.setattr(simulator_module, "APISimulator", _NoopSimulator)
    fallback_calls: list[bool] = []

    async def fail_capture(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("capture transport refused")

    def forbidden_fallback(**_kwargs: Any) -> Any:
        fallback_calls.append(True)
        raise AssertionError("record failure must not trigger ordinary ingestion")

    monkeypatch.setattr(modes_module, "run_blocking_async", fail_capture)
    monkeypatch.setattr(orchestrator_module, "run_orchestrated_ingestion", forbidden_fallback)

    with pytest.raises(RuntimeError, match="record_mode_capture_failed"):
        modes_module.run_record_mode(
            connector_manifest=_manifest(),
            source="test",
            license_name="MIT",
            cas_root=tmp_path / "cas",
        )

    assert fallback_calls == []


def test_full_orchestrator_uses_one_supplied_store_for_connectors_and_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import polisyos.fabric.ingestion as ingestion_module
    from polisyos.fabric.data_plane import orchestrator as orchestrator_module
    from polisyos.fabric.ingestion.ingestion_providers import resolve_ingestion_store

    base_root = tmp_path / "tenants" / _PATH_TENANT / "cas"
    store, requested_roots, scope, dependencies = _ingestion_bundle(base_root)
    connector_stores: list[object] = []
    snapshot_stores: list[object] = []
    evidence_ref = SimpleNamespace(artifact_id=SimpleNamespace(hex="evidence-ref"))
    snapshot_ref = SimpleNamespace(artifact_id=SimpleNamespace(hex="snapshot-ref"))

    def connector_ingestion(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["dependencies"] is dependencies
        assert kwargs["sidecar_scope"] is scope
        connector_stores.append(
            resolve_ingestion_store(
                kwargs["cas_root"],
                kwargs["dependencies"],
                sidecar_scope=kwargs["sidecar_scope"],
            )
        )
        return evidence_ref

    def ensure_async(store_arg: object) -> object:
        snapshot_stores.append(store_arg)
        return store_arg

    async def build_snapshot(**kwargs: Any) -> SimpleNamespace:
        assert kwargs["store"] is store
        return snapshot_ref

    monkeypatch.setattr(ingestion_module, "run_connectors_ingestion", connector_ingestion)
    monkeypatch.setattr(orchestrator_module, "ensure_async_artifact_store", ensure_async)
    monkeypatch.setattr(orchestrator_module, "_build_snapshot_from_evidence_async", build_snapshot)

    result = orchestrator_module.run_orchestrated_ingestion(
        connector_manifest=_manifest(),
        source="test",
        license_name="MIT",
        cas_root=base_root,
        ingestion_dependencies=dependencies,
        sidecar_scope=scope,
    )

    assert result.data_snapshot_ref is snapshot_ref
    assert connector_stores == [store]
    assert snapshot_stores == [store]
    assert requested_roots == [base_root, base_root]


def test_streaming_snapshot_uses_owner_tenant_store_for_the_full_artifact_chain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Streaming chunks and snapshot artifacts retain the runtime tenant-store owner."""
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.core.security.tenant_context import (
        get_current_tenant_id_or_none,
        tenant_scope,
    )
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
    from polisyos.fabric.data_plane.modes import run_streaming_windowed
    from polisyos.fabric.ingestion.ingestion_providers import resolve_ingestion_dependencies
    from polisyos.fabric.storage.tenant_cas import TenantSidecarScope
    from polisyos.runtime.http.resilience import guard_runtime_cas

    tenant_a = _TENANT_A
    tenant_b = "00000000-0000-0000-0000-00000000000b"
    cell_a = "00000000-0000-0000-0000-0000000000ca"
    cell_b = "00000000-0000-0000-0000-0000000000cb"
    # The path carries a different tenant-like segment. The authenticated scope
    # below is authoritative for sidecars, so no identity is inferred from the path.
    cas_root = tmp_path / "policy" / "tenants" / _PATH_TENANT / "cas"
    scope = TenantSidecarScope.for_base_root(cas_root, tenant_a)
    source_path = tmp_path / "events.jsonl"
    source_path.write_text(
        '{"_message_id":"r13-snapshot-row-1","value":7}\n',
        encoding="utf-8",
    )

    base_store = FileSystemCAS(cas_root)
    tenant_store = base_store.for_tenant(tenant_a, cell_a)
    guarded_store = guard_runtime_cas(tenant_store)
    other_tenant_store = base_store.for_tenant(tenant_b, cell_b)
    writes: list[tuple[str, str | None, Any]] = []
    original_put_json = tenant_store.put_json

    def track_owned_put_json(
        payload: object,
        opts: Any,
        canon_spec: Any = None,
    ) -> Any:
        write_tenant = get_current_tenant_id_or_none()
        ref = original_put_json(payload, opts, canon_spec=canon_spec)
        writes.append((str(opts.kind), write_tenant, ref))
        return ref

    monkeypatch.setattr(tenant_store, "put_json", track_owned_put_json)

    connection_config = ConnectionConfig(
        url=source_path.as_uri(),
        headers={"X-Stream-ChunkSize": "1"},
    )
    registry = ConnectorRegistry()
    registry.register(EventStreamConnector, config=connection_config)
    requested_roots: list[Path] = []
    factory_results: list[object] = []

    def store_factory(root: Path) -> Any:
        requested_roots.append(Path(root))
        factory_results.append(guarded_store)
        return guarded_store

    dependencies = resolve_ingestion_dependencies(
        registry=registry,
        store_factory=store_factory,
    )

    try:
        with tenant_scope(None, tenant_id=tenant_a, cell_id=cell_a):
            result = run_streaming_windowed(
                connector_manifest={
                    "datasets": [
                        {"connector_id": "stream.jsonl", "dataset_id": "events"},
                    ],
                },
                source="r13-stream-snapshot",
                license_name="MIT",
                cas_root=cas_root,
                connection_config=connection_config,
                produce_snapshot=True,
                ingestion_dependencies=dependencies,
                sidecar_scope=scope,
            )

            assert result.mode_effective == "streaming_windowed"
            assert result.evidence_bundle_ref is not None
            assert result.data_snapshot_ref is not None
            assert requested_roots == [cas_root]
            assert factory_results == [guarded_store]
            assert scope.cursor_index_root == cas_root / "tenants" / tenant_a
            assert scope.cursor_index_root.is_dir()

            snapshot_id = result.data_snapshot_ref.artifact_id
            evidence_id = result.evidence_bundle_ref.artifact_id
            snapshot_payload = from_canonical_bytes(guarded_store.get_bytes(snapshot_id))
            snapshot_manifest = guarded_store.get_manifest(snapshot_id)
            evidence_manifest = guarded_store.get_manifest(evidence_id)

            assert snapshot_manifest.kind == "fabric.data_snapshot"
            assert evidence_manifest.kind == "fabric.evidence_bundle"
            assert snapshot_payload["stats"]["total_rows"] == 1
            snapshot_inputs = {
                item.role: str(item.artifact_id) for item in snapshot_manifest.inputs
            }
            assert snapshot_inputs["evidence_ref"] == str(evidence_id)
            run_manifest_id = snapshot_payload["data_ref"]["artifact_id"]
            assert snapshot_inputs["data_ref"] == run_manifest_id
            run_manifest = guarded_store.get_manifest(run_manifest_id)
            assert run_manifest.kind == "fabric.streaming_run_manifest"

            written_kinds = {kind for kind, _tenant, _ref in writes}
            assert {
                "fabric.stream_chunk",
                "fabric.streaming_run_manifest",
                "fabric.evidence_bundle",
                "fabric.data_snapshot",
            } <= written_kinds
            assert writes
            assert {write_tenant for _kind, write_tenant, _ref in writes} == {tenant_a}

            # The root-only, unbound store can read the same physical blob; the
            # tenant view must still prove that every artifact in this chain was
            # admitted by tenant A's owner before it returns the bytes.
            for _kind, _write_tenant, ref in writes:
                assert guarded_store.get_bytes(ref.artifact_id)
                with tenant_scope(None, tenant_id=tenant_b, cell_id=cell_b):
                    with pytest.raises(ArtifactOwnershipError):
                        other_tenant_store.get_bytes(ref.artifact_id)
    finally:
        guarded_store.close()
        registry.shutdown()

@pytest.mark.parametrize("owner_entrypoint", ["orchestrated", "direct_ingestion"])
def test_wrong_root_store_is_refused_by_owner_before_fetch_or_persist(
    owner_entrypoint: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Exercise both real ingestion owners with a foreign-root provider.

    P37: the guarded predicate is the recomputed equality of the returned
    store's advertised ``root`` and the invocation's ``TenantSidecarScope``
    base root. The owner must reject before connector lookup, fetch, or cache
    sidecar creation.

    P38 boundary: this verifies the advertised root. A backend that reports the
    requested root while writing elsewhere would diverge from that property
    and needs a separate backend-level custody witness.
    """
    import polisyos.fabric.data_plane.orchestrator as orchestrator_module
    import polisyos.fabric.ingestion.ingestion as ingestion_module
    from polisyos.fabric.ingestion import run_connectors_ingestion
    from polisyos.fabric.ingestion.ingestion_providers import IngestionStoreBindingError
    from polisyos.fabric.storage.tenant_cas import TenantSidecarScope

    requested_root = tmp_path / "tenant-a" / "cas"
    foreign_root = tmp_path / "tenant-b" / "cas"
    scope = TenantSidecarScope.for_base_root(requested_root, _TENANT_A)
    owner_events: list[str] = []
    factory_roots: list[Path] = []
    registry_lookups: list[str] = []
    fetch_attempts: list[str] = []
    wrong_root_store = SimpleNamespace(root=foreign_root)

    class _Span:
        def __enter__(self) -> _Span:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            del exc_type, exc, tb
            return False

        def set_attribute(self, key: str, value: object) -> None:
            del key, value

    class _Tracer:
        def start_as_current_span(self, name: str, attributes: object = None) -> _Span:
            del name, attributes
            return _Span()

    class _Registry:
        def get(self, connector_id: str) -> SimpleNamespace:
            owner_events.append("registry_lookup")
            registry_lookups.append(connector_id)
            return SimpleNamespace(metadata=None)

    def store_factory(root: Path) -> Any:
        owner_events.append("store_factory")
        factory_roots.append(Path(root))
        return wrong_root_store

    def unexpected_fetch(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        owner_events.append("fetch")
        fetch_attempts.append("called")
        raise RuntimeError("wrong_root_store_reached_fetch")

    monkeypatch.setattr(ingestion_module, "_sync_fetch", unexpected_fetch)
    dependencies = resolve_ingestion_dependencies(
        registry=_Registry(),  # type: ignore[arg-type]
        tracer=_Tracer(),  # type: ignore[arg-type]
        metrics=SimpleNamespace(),  # type: ignore[arg-type]
        store_factory=store_factory,
    )

    failure: Exception | None = None
    try:
        if owner_entrypoint == "orchestrated":
            orchestrator_module.run_orchestrated_ingestion(
                connector_manifest=_manifest(),
                source="r13_wrong_store_root_probe",
                license_name="open",
                cas_root=requested_root,
                produce_snapshot=False,
                ingestion_dependencies=dependencies,
                sidecar_scope=scope,
            )
        else:
            run_connectors_ingestion(
                connector_manifest=_manifest(),
                source="r13_wrong_store_root_probe",
                license_name="open",
                cas_root=requested_root,
                dependencies=dependencies,
                sidecar_scope=scope,
            )
    except Exception as exc:
        failure = exc

    observed = {
        "factory_roots": factory_roots,
        "owner_events": owner_events,
        "registry_lookups": registry_lookups,
        "fetch_attempts": fetch_attempts,
        "foreign_root_created": foreign_root.exists(),
    }
    expected = {
        "factory_roots": [requested_root],
        "owner_events": ["store_factory"],
        "registry_lookups": [],
        "fetch_attempts": [],
        "foreign_root_created": False,
    }
    assert observed == expected, "wrong-root store escaped owner admission before fetch/persist"
    assert isinstance(failure, IngestionStoreBindingError)
    assert "ingestion_store_root_mismatch" in str(failure)
