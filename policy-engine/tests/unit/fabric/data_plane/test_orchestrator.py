"""Tests for the Data Plane orchestrator."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    EvidenceBundle,
    EvidenceBundleRef,
)

if TYPE_CHECKING:
    from pathlib import Path
from polisyos.fabric.data_plane.orchestrator import (
    CeleryExecutionBackend,
    DaskExecutionBackend,
    IngestionResult,
    RayExecutionBackend,
    build_partitioned_ingestion_plan,
    run_orchestrated_ingestion,
    run_partitioned_ingestion,
)
from polisyos.fabric.quality.processing_guarantees import (
    batch_processing_contract,
    processing_contract_snapshot,
)


def _make_evidence_bundle(store: FileSystemCAS) -> EvidenceBundleRef:
    """Create a minimal EvidenceBundle in CAS and return its ref."""
    # First, create a data artifact that will be referenced by the evidence bundle
    data_ref = store.put_json(
        {"rows": [{"x": 1}]},
        PutOptions(
            kind="fabric.data_payload",
            media_type="application/json",
            schema=SchemaInfo(name="test.data", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    bundle = EvidenceBundle(
        sources=[data_ref],
        notes=["test evidence bundle"],
    )
    ref = store.put_json(
        bundle,
        PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.EvidenceBundle", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return EvidenceBundleRef(artifact_id=ref.artifact_id)


class TestIngestionResult:
    def test_defaults(self):
        result = IngestionResult()
        assert result.evidence_bundle_ref is None
        assert result.data_snapshot_ref is None
        assert result.datasets_fetched == 0
        assert result.warnings == []

    def test_with_values(self):
        result = IngestionResult(datasets_fetched=3, warnings=["w1"])
        assert result.datasets_fetched == 3
        assert result.warnings == ["w1"]


@pytest.mark.asyncio
async def test_delegating_backend_uses_shared_blocking_bridge(monkeypatch: pytest.MonkeyPatch):
    from polisyos.fabric.data_plane.orchestrator import DelegatingExecutionBackend

    class _TestBackend(DelegatingExecutionBackend):
        def __init__(self) -> None:
            super().__init__(backend_id="test", cost_notes="test")

        def _execute_sync(self, jobs: list[Any]) -> list[str]:
            del jobs
            return ["ok"]

    calls = {"count": 0}

    async def _fake_run_blocking_async(
        func: Any,
        /,
        *args: Any,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> Any:
        del timeout_seconds
        calls["count"] += 1
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator.run_blocking_async",
        _fake_run_blocking_async,
    )

    backend = _TestBackend()
    assert await backend.execute([]) == ["ok"]
    assert calls["count"] == 1


class TestRunOrchestratedIngestion:
    def test_produce_snapshot_false(self, tmp_path: Path):
        """When produce_snapshot=False, snapshot_ref should be None."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is None
        assert result.datasets_fetched == 1

    def test_produce_snapshot_true(self, tmp_path: Path):
        """When produce_snapshot=True, a DataSnapshot should be built from evidence."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is not None
        assert result.datasets_fetched == 1

        # Verify the snapshot was persisted in CAS and is a valid DataSnapshot
        from polisyos.core.canon import from_canonical_bytes

        snapshot_payload = from_canonical_bytes(
            store.get_bytes(result.data_snapshot_ref.artifact_id)
        )
        snapshot = DataSnapshot.model_validate(snapshot_payload)
        assert snapshot.evidence_ref == evidence_ref
        assert snapshot.quality_report_ref is not None
        assert snapshot.stats["datasets_fetched"] == 1
        assert "fabric.data_plane.orchestrator" in snapshot.notes

    def test_produce_snapshot_true_uses_async_artifact_adapter(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter

        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)
        evidence_ref = _make_evidence_bundle(store)
        seen_kinds: list[str] = []
        original_put_json = AsyncArtifactStoreAdapter.put_json

        async def _tracked_put_json(self, obj: object, opts: object, canon_spec: object = None):
            seen_kinds.append(str(getattr(opts, "kind", "")))
            return await original_put_json(self, obj, opts, canon_spec=canon_spec)

        monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "test", "dataset_id": "ds1"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.data_snapshot_ref is not None
        assert seen_kinds == ["fabric.quality_report", "fabric.data_snapshot"]

    def test_no_evidence_ref_returns_none_snapshot(self, tmp_path: Path):
        """When ingestion returns None, snapshot should also be None."""
        cas_root = tmp_path / ".polisyos"

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref is None
        assert result.data_snapshot_ref is None

    def test_empty_evidence_sources_skips_snapshot(self, tmp_path: Path):
        """When evidence bundle has no sources, snapshot should be None."""
        cas_root = tmp_path / ".polisyos"
        store = FileSystemCAS(cas_root)

        # Create evidence bundle with empty sources
        bundle = EvidenceBundle(sources=[], notes=["empty"])
        ref = store.put_json(
            bundle,
            PutOptions(
                kind="fabric.evidence_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.EvidenceBundle", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        evidence_ref = EvidenceBundleRef(artifact_id=ref.artifact_id)

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=evidence_ref,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={"datasets": [{"connector_id": "x", "dataset_id": "y"}]},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=True,
            )

        assert result.evidence_bundle_ref == evidence_ref
        assert result.data_snapshot_ref is None

    def test_connection_config_passed_through(self, tmp_path: Path):
        """connection_config should be forwarded to run_connectors_ingestion."""
        cas_root = tmp_path / ".polisyos"
        fake_config = {"url": "https://test.api.com", "timeout": 30}

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ) as mock_ingest:
            run_orchestrated_ingestion(
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=cas_root,
                connection_config=fake_config,
                produce_snapshot=False,
            )

        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args.kwargs
        assert call_kwargs["connection_config"] == fake_config

    def test_ingestion_dependencies_passed_through(self, tmp_path: Path) -> None:
        """Explicit ingestion dependencies should flow unchanged to the ingestion entrypoint."""
        from polisyos.fabric.ingestion import IngestionDependencies

        cas_root = tmp_path / ".polisyos"

        class _DummySpan:
            def __enter__(self) -> _DummySpan:
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                del exc_type, exc, tb
                return False

            def set_attribute(self, key: str, value: object) -> None:
                del key, value

        class _DummyTracer:
            def start_as_current_span(self, name: str, attributes=None):
                del name, attributes
                return _DummySpan()

        class _DummyMetrics:
            pass

        class _DummyRegistry:
            pass

        deps = IngestionDependencies(
            registry=_DummyRegistry(),  # type: ignore[arg-type]
            tracer=_DummyTracer(),  # type: ignore[arg-type]
            metrics=_DummyMetrics(),  # type: ignore[arg-type]
        )

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ) as mock_ingest:
            run_orchestrated_ingestion(
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
                ingestion_dependencies=deps,
            )

        assert mock_ingest.call_args is not None
        assert mock_ingest.call_args.kwargs["dependencies"] is deps

    def test_datasets_counted_from_dict_manifest(self, tmp_path: Path):
        """datasets_fetched should reflect the number of datasets in manifest dict."""
        cas_root = tmp_path / ".polisyos"

        with patch(
            "polisyos.fabric.ingestion.run_connectors_ingestion",
            return_value=None,
        ):
            result = run_orchestrated_ingestion(
                connector_manifest={
                    "datasets": [
                        {"connector_id": "a", "dataset_id": "d1"},
                        {"connector_id": "b", "dataset_id": "d2"},
                        {"connector_id": "c", "dataset_id": "d3"},
                    ]
                },
                source="test",
                license_name="open",
                cas_root=cas_root,
                produce_snapshot=False,
            )

        assert result.datasets_fetched == 3


class _InMemoryJobSerializer:
    def __init__(self) -> None:
        self._store: dict[bytes, object] = {}
        self._next = 0

    def dumps(self, value: object) -> bytes:
        key = f"job-{self._next}".encode()
        self._next += 1
        self._store[key] = value
        return key

    def loads(self, payload: bytes) -> object:
        return self._store[payload]


def _build_test_partition_plan():
    return build_partitioned_ingestion_plan(
        connector_id="test.connector",
        dataset_id="dataset.partitioned",
        partition_key="year",
        partitions=[
            {"partition_id": "2024", "bounds": {"year": 2024}},
            {"partition_id": "2025", "bounds": {"year": 2025}},
        ],
    )


def _build_trusted_partition_plan():
    return build_partitioned_ingestion_plan(
        connector_id="test.connector",
        dataset_id="dataset.partitioned",
        partition_key="year",
        partitions=[
            {"partition_id": "2024", "bounds": {"year": 2024}},
            {"partition_id": "2025", "bounds": {"year": 2025}},
        ],
        metadata={
            "lineage_ref": "lineage:test.connector:dataset.partitioned",
            "quality_contract_ref": "fabric.quality.test.connector.v1",
            "access_classification": "public",
            "replay_ref": "tests/_data/fabric/shared/test.replay.json",
            "processing": processing_contract_snapshot(batch_processing_contract()),
        },
    )


def _partition_handler(partition) -> IngestionResult:
    return IngestionResult(
        cursor_ref=f"cursor:{partition.partition_id}",
        warnings=[f"partition:{partition.partition_id}"],
    )


class TestDistributedExecutionBackends:
    def test_backend_resolution_returns_real_adapters(self) -> None:
        from polisyos.fabric.data_plane.orchestrator import _resolve_execution_backend

        assert isinstance(_resolve_execution_backend("dask"), DaskExecutionBackend)
        assert isinstance(_resolve_execution_backend("ray"), RayExecutionBackend)
        assert isinstance(_resolve_execution_backend("celery"), CeleryExecutionBackend)

    def test_partitioned_ingestion_uses_dask_client_submit(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        import polisyos.fabric.data_plane.orchestrator as orchestrator

        serializer = _InMemoryJobSerializer()
        submitted: list[bytes] = []

        class FakeDaskFuture:
            def __init__(self, value):
                self._value = value

            def result(self):
                return self._value

        class FakeDaskClient:
            closed = False

            def submit(self, func, payload, pure=False):
                submitted.append(payload)
                return FakeDaskFuture(func(payload))

            def gather(self, futures):
                return [future.result() for future in futures]

            def close(self):
                self.closed = True

        client = FakeDaskClient()
        monkeypatch.setattr(orchestrator, "_resolve_job_serializer", lambda: serializer)

        results = run_partitioned_ingestion(
            plan=_build_trusted_partition_plan(),
            connector_manifest={"datasets": []},
            source="test",
            license_name="open",
            cas_root=tmp_path / "cas",
            backend=DaskExecutionBackend(client_factory=lambda: client),
            partition_handler=_partition_handler,
        )

        assert [result.partition_id for result in results] == ["2024", "2025"]
        assert all(result.status == "succeeded" for result in results)
        assert len(submitted) == 2
        assert client.closed is True

    def test_partitioned_ingestion_uses_ray_remote_tasks(self, monkeypatch, tmp_path: Path) -> None:
        import polisyos.fabric.data_plane.orchestrator as orchestrator

        serializer = _InMemoryJobSerializer()
        remote_payloads: list[bytes] = []

        class FakeRayModule:
            def __init__(self) -> None:
                self._initialized = False
                self.shutdown_called = False

            def is_initialized(self):
                return self._initialized

            def init(self, **kwargs):
                self._initialized = True

            def shutdown(self):
                self.shutdown_called = True
                self._initialized = False

            def remote(self, func):
                class RemoteFn:
                    def remote(self_inner, payload):
                        remote_payloads.append(payload)
                        return lambda: func(payload)

                return RemoteFn()

            def get(self, refs):
                return [ref() for ref in refs]

        fake_ray = FakeRayModule()
        monkeypatch.setattr(orchestrator, "_resolve_job_serializer", lambda: serializer)
        monkeypatch.setitem(sys.modules, "ray", fake_ray)

        results = run_partitioned_ingestion(
            plan=_build_trusted_partition_plan(),
            connector_manifest={"datasets": []},
            source="test",
            license_name="open",
            cas_root=tmp_path / "cas",
            backend="ray",
            partition_handler=_partition_handler,
        )

        assert [result.status for result in results] == ["succeeded", "succeeded"]
        assert len(remote_payloads) == 2
        assert fake_ray.shutdown_called is True

    def test_partitioned_ingestion_uses_celery_task_submission(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        import polisyos.fabric.data_plane.orchestrator as orchestrator

        serializer = _InMemoryJobSerializer()
        delayed_payloads: list[bytes] = []

        class FakeAsyncResult:
            def __init__(self, value):
                self._value = value

            def get(self):
                return self._value

        class FakeTask:
            def __init__(self, func):
                self._func = func

            def delay(self, payload):
                delayed_payloads.append(payload)
                return FakeAsyncResult(self._func(payload))

        class FakeCeleryApp:
            def __init__(self) -> None:
                self.conf = SimpleNamespace(
                    task_always_eager=False,
                    task_store_eager_result=False,
                )

            def task(self, *, name):
                def decorator(func):
                    return FakeTask(func)

                return decorator

        monkeypatch.setattr(orchestrator, "_resolve_job_serializer", lambda: serializer)

        results = run_partitioned_ingestion(
            plan=_build_trusted_partition_plan(),
            connector_manifest={"datasets": []},
            source="test",
            license_name="open",
            cas_root=tmp_path / "cas",
            backend=CeleryExecutionBackend(app_factory=FakeCeleryApp),
            partition_handler=_partition_handler,
        )

        assert [result.status for result in results] == ["succeeded", "succeeded"]
        assert len(delayed_payloads) == 2

    def test_distributed_backend_rejects_missing_trust_metadata(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="distributed execution requires trust metadata"):
            run_partitioned_ingestion(
                plan=_build_test_partition_plan(),
                connector_manifest={"datasets": []},
                source="test",
                license_name="open",
                cas_root=tmp_path / "cas",
                backend=DaskExecutionBackend(client_factory=lambda: object()),
                partition_handler=_partition_handler,
            )

    def test_partitioned_ingestion_uses_shared_blocking_bridge_for_partition_work(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        import polisyos.fabric.data_plane.orchestrator as orchestrator

        calls = {"count": 0}

        async def _fake_run_blocking_async(
            func: Any,
            /,
            *args: Any,
            timeout_seconds: float | None = None,
            **kwargs: Any,
        ) -> Any:
            del timeout_seconds
            calls["count"] += 1
            return func(*args, **kwargs)

        monkeypatch.setattr(
            orchestrator,
            "run_blocking_async",
            _fake_run_blocking_async,
        )

        results = run_partitioned_ingestion(
            plan=_build_test_partition_plan(),
            connector_manifest={"datasets": []},
            source="test",
            license_name="open",
            cas_root=tmp_path / "cas",
            partition_handler=_partition_handler,
        )

        assert [result.status for result in results] == ["succeeded", "succeeded"]
        assert calls["count"] >= 2
