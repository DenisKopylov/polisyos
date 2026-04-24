"""Data Plane Orchestrator — single-call ingestion + snapshot production.

Solves the double-fetch problem: instead of ingesting data into CAS and then
re-fetching to build a DataSnapshot, the orchestrator reads ingestion artifacts
from CAS and assembles the snapshot directly.
"""

from __future__ import annotations

import asyncio
import copy
import importlib
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
)
from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.cursor import PartitionCursorState
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    DataSnapshotRef,
    EvidenceBundle,
    EvidenceBundleRef,
)
from polisyos.fabric.data_plane.cursor_store import AsyncCursorStoreAdapter, CursorStore
from polisyos.fabric.storage.tenant_cas import tenant_scoped_cas_root

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from polisyos.core.artifacts.protocol import ArtifactStore, AsyncArtifactStore
    from polisyos.fabric.ingestion import IngestionDependencies

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Unified result from orchestrated ingestion."""

    evidence_bundle_ref: EvidenceBundleRef | None = None
    data_snapshot_ref: DataSnapshotRef | None = None
    datasets_fetched: int = 0
    warnings: list[str] = field(default_factory=list)
    cursor_ref: str | None = None
    mode_effective: str | None = None


@dataclass(frozen=True)
class IngestionPartition:
    """One independently resumable ingestion partition."""

    partition_id: str
    partition_key: str
    bounds: dict[str, Any]
    source_cursor: str | None = None
    expected_cardinality: int | None = None
    merge_policy: str = "append"
    tenant_id: str | None = None
    time_partition: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PartitionedIngestionPlan:
    """Execution plan for partitioned ingestion."""

    plan_id: str
    connector_id: str
    dataset_id: str
    partition_key: str
    partitions: tuple[IngestionPartition, ...]
    backend_hint: str = "local_async"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PartitionExecutionResult:
    """Execution outcome for one partition."""

    partition_id: str
    status: str
    evidence_bundle_ref: EvidenceBundleRef | None = None
    data_snapshot_ref: DataSnapshotRef | None = None
    cursor_ref: str | None = None
    warnings: tuple[str, ...] = ()
    error: str | None = None


class ExecutionBackend(Protocol):
    """Backend interface for partition execution."""

    backend_id: str

    async def execute(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]: ...


class LocalAsyncExecutionBackend:
    """Local async backend using bounded gather semantics."""

    backend_id = "local_async"

    def __init__(self, *, max_concurrency: int = 4) -> None:
        self.max_concurrency = max(1, int(max_concurrency))

    async def execute(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def _run(
            job: Callable[[], Awaitable[PartitionExecutionResult]],
        ) -> PartitionExecutionResult:
            async with semaphore:
                return await job()

        return list(await asyncio.gather(*[_run(job) for job in jobs]))


class DelegatingExecutionBackend:
    """Base class for optional distributed execution adapters."""

    def __init__(self, backend_id: str, *, cost_notes: str) -> None:
        self.backend_id = backend_id
        self.cost_notes = cost_notes

    async def execute(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        return cast(
            "list[PartitionExecutionResult]",
            await run_blocking_async(self._execute_sync, jobs),
        )

    def _execute_sync(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        raise NotImplementedError


class DaskExecutionBackend(DelegatingExecutionBackend):
    """Partition execution via Dask distributed futures."""

    def __init__(self, *, client_factory: Callable[[], Any] | None = None) -> None:
        super().__init__(
            "dask",
            cost_notes=(
                "Uses dask.distributed Client futures for partition fan-out. "
                "Requires the optional 'distributed' dependency."
            ),
        )
        self._client_factory = client_factory or _build_default_dask_client

    def _execute_sync(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        client = self._client_factory()
        close_client = getattr(client, "close", None)
        try:
            payloads = [_serialize_partition_job(job) for job in jobs]
            futures = [
                client.submit(_execute_serialized_partition_job, payload, pure=False)
                for payload in payloads
            ]
            if hasattr(client, "gather"):
                raw_results = client.gather(futures)
            else:
                raw_results = [future.result() for future in futures]
            return [_coerce_partition_result(item) for item in raw_results]
        finally:
            if callable(close_client):
                close_client()


class RayExecutionBackend(DelegatingExecutionBackend):
    """Partition execution via Ray remote tasks."""

    def __init__(self) -> None:
        super().__init__(
            "ray",
            cost_notes=(
                "Uses Ray remote functions for partition fan-out. "
                "Requires the optional 'ray' dependency."
            ),
        )

    def _execute_sync(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        ray = _import_optional_module(
            "ray",
            install_hint="Install 'ray' to use the Ray execution backend.",
        )
        payloads = [_serialize_partition_job(job) for job in jobs]
        started_here = False
        if not bool(getattr(ray, "is_initialized", lambda: False)()):
            ray.init(ignore_reinit_error=True, include_dashboard=False)
            started_here = True
        try:
            remote_fn = ray.remote(_execute_serialized_partition_job)
            refs = [remote_fn.remote(payload) for payload in payloads]
            raw_results = ray.get(refs)
            return [_coerce_partition_result(item) for item in raw_results]
        finally:
            if started_here and hasattr(ray, "shutdown"):
                ray.shutdown()


class CeleryExecutionBackend(DelegatingExecutionBackend):
    """Partition execution via Celery tasks."""

    def __init__(self, *, app_factory: Callable[[], Any] | None = None) -> None:
        super().__init__(
            "celery",
            cost_notes=(
                "Uses Celery task submission for partition fan-out. "
                "Defaults to an eager in-memory app unless the caller supplies a broker-backed app."
            ),
        )
        self._app_factory = app_factory or _build_default_celery_app

    def _execute_sync(
        self,
        jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]],
    ) -> list[PartitionExecutionResult]:
        app = self._app_factory()
        task = app.task(name="polisyos.fabric.execute_partition_job")(
            _execute_serialized_partition_job
        )
        payloads = [_serialize_partition_job(job) for job in jobs]
        raw_results = [task.delay(payload).get() for payload in payloads]
        return [_coerce_partition_result(item) for item in raw_results]


def _build_filesystem_artifact_store(cas_root: Path) -> ArtifactStore:
    return cast(
        "ArtifactStore",
        build_artifact_store(
            ArtifactStoreConfig(backend="filesystem", root=str(cas_root)),
        ),
    )


def build_partitioned_ingestion_plan(
    *,
    connector_id: str,
    dataset_id: str,
    partition_key: str,
    partitions: list[dict[str, Any]],
    merge_policy: str = "append",
    backend_hint: str = "local_async",
    tenant_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> PartitionedIngestionPlan:
    """Build a normalized plan for partitioned ingestion."""
    normalized: list[IngestionPartition] = []
    for index, raw in enumerate(partitions):
        raw_bounds = dict(raw.get("bounds", {}))
        normalized.append(
            IngestionPartition(
                partition_id=str(raw.get("partition_id", f"partition-{index}")),
                partition_key=partition_key,
                bounds=raw_bounds,
                source_cursor=raw.get("source_cursor"),
                expected_cardinality=raw.get("expected_cardinality"),
                merge_policy=str(raw.get("merge_policy", merge_policy)),
                tenant_id=raw.get("tenant_id", tenant_id),
                time_partition=raw.get("time_partition"),
                metadata=dict(raw.get("metadata", {})),
            )
        )
    return PartitionedIngestionPlan(
        plan_id=f"{connector_id}:{dataset_id}:{uuid.uuid4().hex[:8]}",
        connector_id=connector_id,
        dataset_id=dataset_id,
        partition_key=partition_key,
        partitions=tuple(normalized),
        backend_hint=backend_hint,
        metadata=dict(metadata or {}),
    )


def run_partitioned_ingestion(
    *,
    plan: PartitionedIngestionPlan,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    backend: ExecutionBackend | str = "local_async",
    partition_handler: Callable[[IngestionPartition], IngestionResult] | None = None,
) -> list[PartitionExecutionResult]:
    """Execute a partition plan and resume only failed or pending partitions."""
    resolved_root = Path(cas_root)
    if any(partition.tenant_id for partition in plan.partitions):
        tenant_id = next(
            partition.tenant_id for partition in plan.partitions if partition.tenant_id is not None
        )
        resolved_root = tenant_scoped_cas_root(cas_root, tenant_id)

    store = _build_filesystem_artifact_store(resolved_root)
    cursor_store = AsyncCursorStoreAdapter(
        CursorStore(store, index_root=resolved_root),
        timeout_seconds=5.0,
    )
    backend_impl = _resolve_execution_backend(backend)

    async def _run_partition(partition: IngestionPartition) -> PartitionExecutionResult:
        persisted = await cursor_store.find_partition_state(
            plan.plan_id,
            partition.partition_id,
        )
        if persisted is not None and persisted.status == "succeeded":
            return PartitionExecutionResult(
                partition_id=partition.partition_id,
                status="skipped",
                cursor_ref=persisted.source_cursor,
            )

        await cursor_store.save_partition_state(
            PartitionCursorState(
                plan_id=plan.plan_id,
                partition_id=partition.partition_id,
                connector_id=plan.connector_id,
                dataset_id=plan.dataset_id,
                partition_key=plan.partition_key,
                partition_bounds=partition.bounds,
                source_cursor=partition.source_cursor,
                expected_cardinality=partition.expected_cardinality,
                merge_policy=partition.merge_policy,
                status="running",
                checkpoint_id=(persisted.checkpoint_id if persisted is not None else None),
                updated_at=_utc_now(),
                metadata={
                    **plan.metadata,
                    **partition.metadata,
                },
            )
        )

        try:
            if partition_handler is not None:
                ingestion_result = await run_blocking_async(partition_handler, partition)
            else:
                partition_manifest = _manifest_for_partition(
                    connector_manifest,
                    plan=plan,
                    partition=partition,
                )
                ingestion_result = await run_blocking_async(
                    run_orchestrated_ingestion,
                    connector_manifest=partition_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=resolved_root,
                    connection_config=connection_config,
                    produce_snapshot=produce_snapshot,
                )

            await cursor_store.save_partition_state(
                PartitionCursorState(
                    plan_id=plan.plan_id,
                    partition_id=partition.partition_id,
                    connector_id=plan.connector_id,
                    dataset_id=plan.dataset_id,
                    partition_key=plan.partition_key,
                    partition_bounds=partition.bounds,
                    source_cursor=ingestion_result.cursor_ref or partition.source_cursor,
                    expected_cardinality=partition.expected_cardinality,
                    merge_policy=partition.merge_policy,
                    status="succeeded",
                    checkpoint_id=ingestion_result.cursor_ref,
                    updated_at=_utc_now(),
                    metadata={
                        **plan.metadata,
                        **partition.metadata,
                    },
                )
            )
            return PartitionExecutionResult(
                partition_id=partition.partition_id,
                status="succeeded",
                evidence_bundle_ref=ingestion_result.evidence_bundle_ref,
                data_snapshot_ref=ingestion_result.data_snapshot_ref,
                cursor_ref=ingestion_result.cursor_ref,
                warnings=tuple(ingestion_result.warnings),
            )
        except Exception as exc:
            await cursor_store.save_partition_state(
                PartitionCursorState(
                    plan_id=plan.plan_id,
                    partition_id=partition.partition_id,
                    connector_id=plan.connector_id,
                    dataset_id=plan.dataset_id,
                    partition_key=plan.partition_key,
                    partition_bounds=partition.bounds,
                    source_cursor=partition.source_cursor,
                    expected_cardinality=partition.expected_cardinality,
                    merge_policy=partition.merge_policy,
                    status="failed",
                    last_error=str(exc),
                    checkpoint_id=(persisted.checkpoint_id if persisted is not None else None),
                    updated_at=_utc_now(),
                    metadata={
                        **plan.metadata,
                        **partition.metadata,
                    },
                )
            )
            return PartitionExecutionResult(
                partition_id=partition.partition_id,
                status="failed",
                error=str(exc),
            )

    def _make_partition_job(
        partition: IngestionPartition,
    ) -> Callable[[], Awaitable[PartitionExecutionResult]]:
        async def _job() -> PartitionExecutionResult:
            return await _run_partition(partition)

        return _job

    jobs: list[Callable[[], Awaitable[PartitionExecutionResult]]] = [
        _make_partition_job(partition) for partition in plan.partitions
    ]
    result: list[PartitionExecutionResult] = run_coro_sync(backend_impl.execute(jobs))
    return result


def run_orchestrated_ingestion(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    tenant_id: str | None = None,
    ingestion_dependencies: IngestionDependencies | None = None,
) -> IngestionResult:
    """Run ingestion and optionally produce a DataSnapshot.

    This avoids the double-fetch problem: data is fetched once during
    ingestion, cached in CAS, and the snapshot is built from cached
    artifacts.
    """
    from polisyos.fabric.ingestion import run_connectors_ingestion

    resolved_cas_root = (
        tenant_scoped_cas_root(cas_root, tenant_id) if tenant_id is not None else Path(cas_root)
    )

    evidence_ref = run_connectors_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=resolved_cas_root,
        connection_config=connection_config,
        dependencies=ingestion_dependencies,
    )

    datasets_fetched = 0
    if hasattr(connector_manifest, "datasets"):
        datasets_fetched = len(connector_manifest.datasets)
    elif isinstance(connector_manifest, dict):
        datasets_fetched = len(connector_manifest.get("datasets", []))

    if not produce_snapshot or evidence_ref is None:
        return IngestionResult(
            evidence_bundle_ref=evidence_ref,
            data_snapshot_ref=None,
            datasets_fetched=datasets_fetched,
        )

    cas_store = _build_filesystem_artifact_store(resolved_cas_root)
    snapshot_ref = run_coro_sync(
        _build_snapshot_from_evidence_async(
            store=ensure_async_artifact_store(cas_store),
            evidence_ref=evidence_ref,
            datasets_fetched=datasets_fetched,
            source=source,
        )
    )

    return IngestionResult(
        evidence_bundle_ref=evidence_ref,
        data_snapshot_ref=snapshot_ref,
        datasets_fetched=datasets_fetched,
    )


async def _build_snapshot_from_evidence_async(
    *,
    store: AsyncArtifactStore,
    evidence_ref: EvidenceBundleRef,
    datasets_fetched: int,
    source: str,
) -> DataSnapshotRef | None:
    """Build a DataSnapshot from evidence bundle artifacts in CAS."""
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions

    evidence_payload = from_canonical_bytes(await store.get_bytes(evidence_ref.artifact_id))
    evidence_bundle = EvidenceBundle.model_validate(evidence_payload)

    if not evidence_bundle.sources:
        logger.warning("orchestrator: evidence bundle has no sources, skipping snapshot")
        return None

    # Use the first source artifact as the primary data reference
    data_ref = evidence_bundle.sources[0]

    # Build a quality report from evidence metadata
    quality_payload = {
        "source": f"orchestrated_ingestion:{source}",
        "datasets_count": datasets_fetched,
        "notes": evidence_bundle.notes,
    }
    quality_ref = await store.put_json(
        quality_payload,
        ArtifactWriteOptions(
            kind="fabric.quality_report",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.fabric.DataQualityReport", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )

    snapshot_inputs = [
        InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref"),
        InputRef(artifact_id=data_ref.artifact_id, role="data_ref"),
        InputRef(artifact_id=quality_ref.artifact_id, role="quality_report_ref"),
    ]

    snapshot = DataSnapshot(
        data_ref=data_ref,
        evidence_ref=evidence_ref,
        quality_report_ref=quality_ref,
        stats={
            "datasets_fetched": datasets_fetched,
            "source": f"orchestrated_ingestion:{source}",
        },
        notes=[
            "fabric.data_plane.orchestrator",
            f"datasets={datasets_fetched}",
        ],
    )

    snapshot_art_ref = await store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=snapshot_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return DataSnapshotRef(artifact_id=snapshot_art_ref.artifact_id)


def _resolve_execution_backend(backend: ExecutionBackend | str) -> ExecutionBackend:
    if not isinstance(backend, str):
        return backend
    if backend == "local_async":
        return LocalAsyncExecutionBackend()
    if backend == "dask":
        return DaskExecutionBackend()
    if backend == "ray":
        return RayExecutionBackend()
    if backend == "celery":
        return CeleryExecutionBackend()
    raise ValueError(f"Unknown execution backend: {backend!r}")


def _manifest_for_partition(
    connector_manifest: Any,
    *,
    plan: PartitionedIngestionPlan,
    partition: IngestionPartition,
) -> Any:
    manifest = copy.deepcopy(connector_manifest)
    if not isinstance(manifest, dict):
        return manifest
    datasets = list(manifest.get("datasets", []))
    updated_datasets: list[dict[str, Any]] = []
    for dataset in datasets:
        if (
            str(dataset.get("connector_id", "")) == plan.connector_id
            and str(dataset.get("dataset_id", "")) == plan.dataset_id
        ):
            updated = dict(dataset)
            merged_filters = dict(updated.get("filters", {}))
            for key, value in partition.bounds.items():
                if isinstance(value, list):
                    merged_filters[str(key)] = list(value)
                else:
                    merged_filters[str(key)] = [str(value)]
            updated["filters"] = merged_filters
            updated_datasets.append(updated)
        else:
            updated_datasets.append(dict(dataset))
    manifest["datasets"] = updated_datasets
    manifest["partition"] = {
        "plan_id": plan.plan_id,
        "partition_id": partition.partition_id,
        "partition_key": partition.partition_key,
        "merge_policy": partition.merge_policy,
        "bounds": partition.bounds,
        "tenant_id": partition.tenant_id,
        "time_partition": partition.time_partition,
    }
    return manifest


def _utc_now() -> Any:
    from polisyos.fabric.temporal import utc_now

    return utc_now()


def _serialize_partition_job(
    job: Callable[[], Awaitable[PartitionExecutionResult]],
) -> bytes:
    serializer = _resolve_job_serializer()
    try:
        return cast("bytes", serializer.dumps(job))
    except Exception as exc:
        raise RuntimeError(
            "Failed to serialize partition job for distributed execution. "
            "Install 'cloudpickle' or use a top-level partition handler."
        ) from exc


def _execute_serialized_partition_job(payload: bytes) -> dict[str, Any]:
    serializer = _resolve_job_serializer()
    job = serializer.loads(payload)
    result = asyncio.run(job())
    return asdict(result)


def _coerce_partition_result(
    payload: PartitionExecutionResult | dict[str, Any],
) -> PartitionExecutionResult:
    if isinstance(payload, PartitionExecutionResult):
        return payload
    if isinstance(payload, dict):
        return PartitionExecutionResult(**payload)
    raise TypeError(f"Unsupported partition execution payload: {type(payload)!r}")


def _resolve_job_serializer() -> Any:
    try:
        return importlib.import_module("cloudpickle")
    except ModuleNotFoundError:
        import pickle

        return pickle


def _import_optional_module(name: str, *, install_hint: str) -> Any:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(install_hint) from exc


def _build_default_dask_client() -> Any:
    distributed = _import_optional_module(
        "distributed",
        install_hint="Install 'distributed' to use the Dask execution backend.",
    )
    client_cls = getattr(distributed, "Client", None)
    if client_cls is None:
        raise RuntimeError("Dask execution backend requires distributed.Client")
    return client_cls(processes=False, threads_per_worker=1)


def _build_default_celery_app() -> Any:
    celery_module = _import_optional_module(
        "celery",
        install_hint="Install 'celery' to use the Celery execution backend.",
    )
    celery_cls = getattr(celery_module, "Celery", None)
    if celery_cls is None:
        raise RuntimeError("Celery execution backend requires celery.Celery")
    app = celery_cls(
        "polisyos.fabric.orchestrator",
        broker="memory://",
        backend="cache+memory://",
    )
    app.conf.task_always_eager = True
    app.conf.task_store_eager_result = True
    return app


__all__ = [
    "CeleryExecutionBackend",
    "DaskExecutionBackend",
    "DelegatingExecutionBackend",
    "ExecutionBackend",
    "IngestionPartition",
    "IngestionResult",
    "LocalAsyncExecutionBackend",
    "PartitionExecutionResult",
    "PartitionedIngestionPlan",
    "RayExecutionBackend",
    "build_partitioned_ingestion_plan",
    "run_orchestrated_ingestion",
    "run_partitioned_ingestion",
]
