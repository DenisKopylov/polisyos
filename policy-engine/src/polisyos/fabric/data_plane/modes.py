"""Execution mode dispatch for data ingestion.

Provides:
- batch_incremental: cursor-based incremental ingestion
- record_mode: run ingestion while capturing HTTP responses to CAS
- replay_mode: run ingestion from captured HTTP responses (no network)
- streaming_windowed: per-chunk CAS persistence via fetch_stream()
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypedDict, TypeGuard, cast

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.contracts.cursor import CursorState, WatermarkType, WindowStrategy
from polisyos.fabric.connectors._async_iterators import resolve_async_iterator

# Runtime binding preserves four documented mode routes (AD-E02-FABRIC-REFLECTION-01;
# FABRIC-TC001-007).
from polisyos.fabric.connectors.base import ConnectionConfig  # noqa: TC001
from polisyos.fabric.data_plane.orchestrator import IngestionResult
from polisyos.fabric.data_plane.quarantine import (
    IndexedArtifactStore,
    QuarantineRecord,
    persist_quarantine_record,
)
from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions
from polisyos.fabric.ingestion import ConnectorManifestSpec
from polisyos.fabric.ingestion.ingestion_providers import (
    IngestionDependencies,
    _BatchConnectorRegistry,
    _BatchIngestionDependencies,
    _BatchIngestionDependenciesView,
)
from polisyos.fabric.storage.tenant_cas import TenantSidecarScope
from polisyos.ir.connectors import (
    ConnectorCapability,
    DataVersion,
    FetchRequest,
    FetchResult,
    VersionStrategy,
)

ConnectorManifestInput = Mapping[str, object] | Path | str | ConnectorManifestSpec


class _ArgumentNotProvided:
    """Sentinel that keeps omitted proxy arguments distinct from explicit defaults."""


_ARGUMENT_NOT_PROVIDED = _ArgumentNotProvided()


def _argument_was_provided[T](value: T | _ArgumentNotProvided) -> TypeGuard[T]:
    """Narrow a supplied proxy argument while treating every sentinel as omission."""
    return not isinstance(value, _ArgumentNotProvided)


class _RegistryGetKwargs(TypedDict, total=False):
    enable_cache: bool
    _registration_binding: _ConnectorRegistrationBinding | None


class _RegistryConnectionKwargs(TypedDict, total=False):
    _registration_binding: _ConnectorRegistrationBinding | None


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from polisyos.core.artifacts import ArtifactRef, ArtifactStore
    from polisyos.core.contracts.fabric import EvidenceBundleRef
    from polisyos.fabric.connectors._registry_models import (
        _ConnectorRegistrationBinding,
    )
    from polisyos.fabric.connectors.base import ConnectionHandle, SourceConnectorValue
    from polisyos.fabric.connectors.contracts import DataSchema
    from polisyos.fabric.connectors.registry import ConnectorEntry
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.streaming import StreamSchemaBinding
    from polisyos.fabric.ingestion.source_progress import ReconciledSourceFrame

logger = get_logger(__name__)


class RecordModeCaptureError(RuntimeError):
    """Raised when recorded ingestion fails without retrying through a live path."""


@dataclass(frozen=True)
class _LegacyStreamDatasetResult:
    """Typed result shared by the legacy streaming persistence adapters."""

    chunk_refs: list[ArtifactRef]
    window_refs: list[ArtifactRef]
    cdc_event_refs: list[ArtifactRef]
    warnings: list[str]
    rows_emitted: int
    chunks_processed: int
    quarantined_rows: int
    final_cursor_ref: str | None
    source_progress_scope: dict[str, object] | None = None


class _StreamDatasetResultSummary(Protocol):
    """Read-only fields shared by registered and legacy stream result owners."""

    @property
    def chunk_refs(self) -> Sequence[ArtifactRef]: ...

    @property
    def window_refs(self) -> Sequence[ArtifactRef]: ...

    @property
    def cdc_event_refs(self) -> Sequence[ArtifactRef]: ...

    @property
    def warnings(self) -> Sequence[str]: ...

    @property
    def rows_emitted(self) -> int: ...

    @property
    def chunks_processed(self) -> int: ...

    @property
    def quarantined_rows(self) -> int: ...

    @property
    def final_cursor_ref(self) -> str | None: ...

    @property
    def source_progress_scope(self) -> dict[str, object] | None: ...


class _LegacyStreamChunk(TypedDict):
    """Fields emitted by the typed streaming connector before legacy persistence."""

    chunk_index: int
    row_count: int
    is_first: bool
    is_last: bool
    data: list[object]


_VERSION_STRATEGY_BY_WATERMARK: dict[WatermarkType, VersionStrategy] = {
    WatermarkType.TIMESTAMP: VersionStrategy.TIMESTAMP,
    WatermarkType.ETAG: VersionStrategy.ETAG,
    WatermarkType.REVISION: VersionStrategy.REVISION,
}


def _resolve_ingestion_dependencies(
    dependencies: IngestionDependencies | None,
) -> IngestionDependencies:
    """Resolve providers once while preserving a caller-supplied bundle unchanged."""
    if dependencies is not None:
        return dependencies
    from polisyos.fabric.ingestion import resolve_ingestion_dependencies

    return resolve_ingestion_dependencies()


def _orchestrator_manifest_input(
    connector_manifest: ConnectorManifestInput,
) -> ConnectorManifestSpec | Path | str:
    """Normalize mapping inputs to the existing typed ingestion manifest owner."""
    if isinstance(connector_manifest, (ConnectorManifestSpec, Path, str)):
        return connector_manifest
    from polisyos.fabric.ingestion.ingestion import _normalize_connector_manifest

    return _normalize_connector_manifest(connector_manifest)


def _resolve_mode_sidecar_scope(
    cas_root: Path,
    sidecar_scope: TenantSidecarScope | None,
) -> TenantSidecarScope:
    """Resolve tenant-local sidecar paths as invocation context, not provider state."""
    from polisyos.fabric.ingestion.ingestion_providers import (
        resolve_ingestion_sidecar_scope,
    )

    if sidecar_scope is not None and not isinstance(sidecar_scope, TenantSidecarScope):
        raise TypeError("sidecar_scope must be a TenantSidecarScope")

    return resolve_ingestion_sidecar_scope(
        Path(cas_root),
        sidecar_scope=sidecar_scope,
    )


def _resolve_mode_store(
    cas_root: Path,
    dependencies: IngestionDependencies,
    *,
    sidecar_scope: TenantSidecarScope,
) -> ArtifactStore:
    """Resolve the same owner-supplied store used by connector ingestion."""
    from polisyos.fabric.ingestion.ingestion_providers import resolve_ingestion_store

    return resolve_ingestion_store(
        Path(cas_root),
        dependencies,
        sidecar_scope=sidecar_scope,
    )


async def _persist_streaming_manifest_async(
    *,
    store: ArtifactStore,
    manifest_payload: dict[str, object],
    source_refs: list[ArtifactRef],
) -> ArtifactRef:
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    async_store = ensure_async_artifact_store(store)
    return await async_store.put_json(
        manifest_payload,
        ArtifactWriteOptions(
            kind="fabric.streaming_run_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="fabric.StreamingRunManifest", version="1.0"),
            inputs=[
                InputRef(artifact_id=ref.artifact_id, role="stream_artifact") for ref in source_refs
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


async def _persist_streaming_snapshot_async(
    *,
    store: ArtifactStore,
    snapshot_payload: dict[str, object],
    manifest_ref: ArtifactRef,
    evidence_ref: EvidenceBundleRef,
) -> ArtifactRef:
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec

    async_store = ensure_async_artifact_store(store)
    return await async_store.put_json(
        snapshot_payload,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                InputRef(artifact_id=manifest_ref.artifact_id, role="data_ref"),
                InputRef(artifact_id=evidence_ref.artifact_id, role="evidence_ref"),
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _looks_metric_field(field_name: str) -> bool:
    lowered = str(field_name).strip().lower()
    if lowered in {"value", "metric", "score", "rate", "total", "count"}:
        return True
    return any(
        marker in lowered
        for marker in ("metric", "score", "value", "amount", "rate", "count", "total")
    )


def _non_finite_fields(row: Mapping[str, object]) -> list[str]:
    fields: list[str] = []
    for key, value in row.items():
        if isinstance(value, bool) or value is None or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if math.isinf(numeric) or (math.isnan(numeric) and _looks_metric_field(str(key))):
            fields.append(str(key))
    return fields


@dataclass(frozen=True)
class _ReconciledFetch:
    """One exact sent request and source result reconciled by the owner reader."""

    sent_request: FetchRequest
    raw_result: FetchResult[object]
    materialized_result: FetchResult[object]


class _CursorAwareConnector:
    """Add one stored incremental version at the connector request boundary."""

    def __init__(
        self,
        connector: SourceConnectorValue[object],
        connector_id: str,
        frames: dict[tuple[str, str], ReconciledSourceFrame],
        reconciled: dict[tuple[str, str], _ReconciledFetch],
    ) -> None:
        self._connector = connector
        self._connector_id = connector_id
        self._frames = frames
        self._reconciled = reconciled

    async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[object]:
        """Fetch the exact persisted request, then reconcile the full source view."""
        key = (self._connector_id, request.dataset_id)
        frame = self._frames.get(key)
        if frame is None:
            return await self._connector.fetch(handle, request)
        # The bounded finite source owns this exact file replay. An arbitrary
        # network connector cannot borrow a separate fixture's authority.
        from polisyos.fabric.ingestion.source_progress import SourceProgressAdmissionError

        try:
            result = frame.replay_fetch(handle.config, request)
            materialized = frame.reconcile_fetch(request, result)
        except (OSError, TypeError, ValueError) as exc:
            raise SourceProgressAdmissionError(
                "actual_finite_replay_unavailable",
                connector_id=self._connector_id,
                dataset_id=request.dataset_id,
            ) from exc
        self._reconciled[key] = _ReconciledFetch(request, result, materialized)
        return materialized

    def __getattr__(self, name: str) -> object:
        return getattr(self._connector, name)


class _CursorAwareRegistry:
    """Delegate registry operations while wrapping fetched connectors."""

    def __init__(
        self,
        registry: _BatchConnectorRegistry,
        frames: dict[tuple[str, str], ReconciledSourceFrame],
        reconciled: dict[tuple[str, str], _ReconciledFetch],
    ) -> None:
        self._registry = registry
        self._frames = frames
        self._reconciled = reconciled
        self._finite_handles: dict[str, ConnectionHandle] = {}

    def get(
        self,
        connector_id: str,
        version: str | None | _ArgumentNotProvided = _ARGUMENT_NOT_PROVIDED,
        *,
        enable_cache: bool | _ArgumentNotProvided = _ARGUMENT_NOT_PROVIDED,
        _registration_binding: _ConnectorRegistrationBinding
        | None
        | _ArgumentNotProvided = _ARGUMENT_NOT_PROVIDED,
    ) -> SourceConnectorValue[object]:
        """Resolve and wrap one connector, preserving supplied argument presence."""
        kwargs: _RegistryGetKwargs = {}
        if _argument_was_provided(enable_cache):
            kwargs["enable_cache"] = enable_cache
        if _argument_was_provided(_registration_binding):
            kwargs["_registration_binding"] = _registration_binding

        if _argument_was_provided(version):
            connector = self._registry.get(connector_id, version, **kwargs)
        else:
            connector = self._registry.get(connector_id, **kwargs)
        wrapped = _CursorAwareConnector(
            connector,
            connector_id,
            self._frames,
            self._reconciled,
        )
        return cast("SourceConnectorValue[object]", wrapped)

    def get_entry(self, connector_id: str) -> ConnectorEntry:
        """Return the original registered entry without changing its owner."""
        return self._registry.get_entry(connector_id)

    async def get_connection(
        self,
        connector_id: str,
        config: ConnectionConfig | None | _ArgumentNotProvided = _ARGUMENT_NOT_PROVIDED,
        *,
        _registration_binding: _ConnectorRegistrationBinding
        | None
        | _ArgumentNotProvided = _ARGUMENT_NOT_PROVIDED,
    ) -> ConnectionHandle:
        """Acquire actual replay-file handles or forward the unchanged live path."""
        finite = [
            frame for (owner, _dataset), frame in self._frames.items() if owner == connector_id
        ]
        if finite:
            from polisyos.fabric.connectors.base import ConnectionHandle

            selected = config if _argument_was_provided(config) else None
            selected = selected or self._registry.get_entry(connector_id).default_config
            if selected is None:
                raise ValueError("finite replay has no actual connection")
            admitted = [frame.bind_transport(selected) for frame in finite]
            if any(
                frame.transport_identity != original.transport_identity
                for frame, original in zip(admitted, finite, strict=True)
            ):
                raise ValueError("finite replay physical transport changed before acquisition")
            # No network pool is opened: this mode's producer performs actual
            # bounded file IO. Lifetime is still explicit and checked below.
            handle = ConnectionHandle(connector_id=connector_id, config=selected)
            self._finite_handles[handle.session_id] = handle
            return handle
        kwargs: _RegistryConnectionKwargs = {}
        if _argument_was_provided(_registration_binding):
            kwargs["_registration_binding"] = _registration_binding

        if _argument_was_provided(config):
            return await self._registry.get_connection(connector_id, config, **kwargs)
        return await self._registry.get_connection(connector_id, **kwargs)

    async def _get_connection_with_live_permit(
        self,
        connector_id: str,
        config: ConnectionConfig | None,
        *,
        dataset_id: str,
        permit: object,
    ) -> ConnectionHandle:
        """Forward live-permit acquisition to the exact registry owner."""
        return await self._registry._get_connection_with_live_permit(
            connector_id, config, dataset_id=dataset_id, permit=permit
        )

    async def release_connection(self, connector_id: str, handle: ConnectionHandle) -> None:
        """Release through the exact replay or registry owner that acquired it."""
        if self._finite_handles.get(handle.session_id) is handle:
            del self._finite_handles[handle.session_id]
            return
        await self._registry.release_connection(connector_id, handle)

    def __getattr__(self, name: str) -> object:
        return getattr(self._registry, name)


def _connector_supports_incremental(connector: object) -> bool:
    """Return whether a connector declares the incremental fetch capability."""
    capabilities = getattr(connector, "capabilities", None)
    if capabilities is None:
        metadata = getattr(connector, "metadata", None)
        capabilities = getattr(metadata, "capabilities", None)
    if isinstance(capabilities, ConnectorCapability):
        flags = capabilities
    elif isinstance(capabilities, int):
        try:
            flags = ConnectorCapability(capabilities)
        except ValueError:
            return False
    else:
        return False
    return bool(flags & ConnectorCapability.INCREMENTAL_FETCH)


def _parse_timestamp_value(value: str) -> datetime | None:
    """Parse one source timestamp and reject timezone-free values."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _cursor_version(
    cursor: CursorState,
    connector: object,
    *,
    frame: ReconciledSourceFrame | None = None,
    store: ArtifactStore | None = None,
) -> DataVersion | None:
    """Issue a hint only after exact persisted source evidence is re-admitted.

    Legacy ETAG/revision/timestamp syntax and capabilities carry no authority.
    Without an independent source-owner reader they all remain full-fetch only.
    """
    if frame is None or store is None or not _connector_supports_incremental(connector):
        return None
    return frame.admit_cursor(cursor, store)


def _cursor_aware_dependencies(
    dependencies: IngestionDependencies,
    frames: dict[tuple[str, str], ReconciledSourceFrame],
    reconciled: dict[tuple[str, str], _ReconciledFetch],
) -> _BatchIngestionDependencies:
    """Build a batch view whose registry reconciles real source result bytes."""
    return _BatchIngestionDependenciesView(
        registry=_CursorAwareRegistry(dependencies.registry, frames, reconciled),
        tracer=dependencies.tracer,
        metrics=dependencies.metrics,
        store_factory=dependencies.store_factory,
    )


def _resolve_dataset_connectors(
    dependencies: IngestionDependencies | None,
    datasets: list[tuple[str, str]],
) -> dict[tuple[str, str], object]:
    """Resolve connector instances used by cursor capability admission."""
    if dependencies is None:
        return {}
    resolved: dict[tuple[str, str], object] = {}
    for connector_id, dataset_id in datasets:
        try:
            resolved[(connector_id, dataset_id)] = dependencies.registry.get(connector_id)
        except Exception as exc:
            logger.warning(
                "batch_incremental: capability metadata unavailable for %s:%s: %s",
                connector_id,
                dataset_id,
                exc,
            )
    return resolved


def _cursor_result_ref(value: object) -> str | None:
    """Return an artifact id from a fetch or aggregate evidence reference."""
    artifact_id = getattr(value, "artifact_id", None)
    return str(artifact_id) if artifact_id is not None else None


def _complete_source_boundary(
    fetch_result: FetchResult[object],
    watermark_type: WatermarkType,
) -> tuple[VersionStrategy, str, datetime] | None:
    """Return a source-backed complete boundary, never a local fetch time."""
    if fetch_result.has_more or fetch_result.next_page_token is not None:
        return None
    if not math.isfinite(fetch_result.completeness) or fetch_result.completeness != 1.0:
        return None
    if not fetch_result.is_complete:
        return None

    strategy = _VERSION_STRATEGY_BY_WATERMARK.get(watermark_type)
    if strategy is None:
        return None
    if strategy is VersionStrategy.TIMESTAMP:
        source_timestamp = fetch_result.source_updated_at
        if (
            source_timestamp is None
            or source_timestamp.tzinfo is None
            or source_timestamp.utcoffset() is None
        ):
            return None
        version = fetch_result.version
        if version.strategy is not VersionStrategy.TIMESTAMP:
            return None
        version_value = version.value
        version_timestamp = version.timestamp
        parsed_version_value = _parse_timestamp_value(version_value)
        if parsed_version_value is None:
            return None
        if (
            version_timestamp.tzinfo is None
            or version_timestamp.utcoffset() is None
            or version_timestamp != parsed_version_value
            or source_timestamp != parsed_version_value
        ):
            return None
        return strategy, version_value, source_timestamp

    version = fetch_result.version
    if version.strategy is not strategy:
        return None
    return strategy, version.value, version.timestamp


def _save_confirmed_cursors(
    *,
    cursor_store: CursorStore,
    store: ArtifactStore,
    connectors: dict[tuple[str, str], object],
    datasets: list[tuple[str, str]],
    confirmed_results: dict[tuple[str, str], FetchResult[object]],
    persisted_results: dict[
        tuple[str, str],
        tuple[
            FetchRequest, FetchResult[object], FetchResult[object], ArtifactRef, EvidenceBundleRef
        ],
    ],
    result: IngestionResult,
    frames: dict[tuple[str, str], ReconciledSourceFrame],
    reconciled: dict[tuple[str, str], _ReconciledFetch],
    predecessors: dict[tuple[str, str], CursorState | None],
) -> set[tuple[str, str]]:
    """Conditionally promote only independently reconciled per-source progress."""
    evidence_ref = getattr(result, "evidence_bundle_ref", None)
    if evidence_ref is None:
        return set()

    try:
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import artifact_ref_identity_key
        from polisyos.core.contracts.fabric import EvidenceBundle
        from polisyos.core.contracts.provenance import ProvenanceCoreGraph, RelationType

        evidence = EvidenceBundle.model_validate(load_core_json_artifact(store, evidence_ref))
        provenance_ref = evidence.provenance_ref
        if provenance_ref is None:
            return set()
        graph_payload = load_core_json_artifact(
            store,
            ArtifactID.model_validate(provenance_ref.artifact_id),
        )
        graph = ProvenanceCoreGraph.from_dict(graph_payload)
        if (
            graph.graph_id != provenance_ref.graph_id
            or graph.compute_stable_id() != provenance_ref.stable_id
        ):
            return set()
    except Exception:
        logger.warning("batch_incremental: persisted evidence could not be resolved and bound")
        return set()

    try:
        from polisyos.fabric.ingestion.ingestion import _cache_payload_ref_matches_result
        from polisyos.fabric.ingestion.source_progress import snapshot_fetch_request
    except ImportError:
        logger.warning("batch_incremental: cursor evidence verifier is unavailable")
        return set()

    admitted: set[tuple[str, str]] = set()
    activity = graph.activities.get("connector_ingestion_run")
    if activity is None:
        return set()

    for connector_id, dataset_id in datasets:
        key = (connector_id, dataset_id)
        connector = connectors.get(key)
        captured = confirmed_results.get(key)
        receipt = persisted_results.get(key)
        frame = frames.get(key)
        reconciliation = reconciled.get(key)
        if (
            connector is None
            or captured is None
            or receipt is None
            or frame is None
            or reconciliation is None
            or not _connector_supports_incremental(connector)
        ):
            continue
        request, source_result, persisted_result, payload_ref, receipt_evidence_ref = receipt
        if (
            captured is not source_result
            or source_result is not reconciliation.materialized_result
            or request != reconciliation.sent_request
        ):
            continue
        if artifact_ref_identity_key(receipt_evidence_ref) != artifact_ref_identity_key(
            evidence_ref
        ):
            continue

        previous = predecessors[key]
        if previous is not None and frame.admit_cursor(previous, store) is None:
            # An unverified legacy cursor cannot silently become authority by
            # a normal fetch. Explicit migration first admits a complete basis.
            continue
        watermark_type = next(
            (
                watermark
                for watermark, strategy in _VERSION_STRATEGY_BY_WATERMARK.items()
                if strategy is frame.current.version.strategy
            ),
            None,
        )
        if watermark_type is None:
            continue
        source_boundary = _complete_source_boundary(source_result, watermark_type)
        persisted_boundary = _complete_source_boundary(persisted_result, watermark_type)
        if source_boundary is None or persisted_boundary is None:
            continue
        if source_boundary != persisted_boundary:
            continue

        try:
            frame.assert_current()
            frame.assert_transport_current()
            frame.verify_materialization(persisted_result)
            if not _cache_payload_ref_matches_result(store, payload_ref, persisted_result):
                continue
            if not any(
                artifact_ref_identity_key(source_ref) == artifact_ref_identity_key(payload_ref)
                for source_ref in evidence.sources
            ):
                continue
            entity_id = f"dataset.{connector_id}.{dataset_id}"
            entity = graph.entities.get(entity_id)
            if entity is None:
                continue
            attributes = entity.attributes
            expected_content_hash = persisted_result.version.content_hash
            expected_updated_at = (
                persisted_result.source_updated_at.isoformat()
                if persisted_result.source_updated_at is not None
                else None
            )
            artifact_id = getattr(payload_ref, "artifact_id", None)
            artifact_hex = getattr(artifact_id, "hex", None)
            if (
                entity.created_at != persisted_result.fetched_at
                or attributes.get("fetch_status") != "complete"
                or attributes.get("cache_key") != request.cache_key
                or attributes.get("data_artifact_id") != artifact_hex
                or attributes.get("version_strategy") != persisted_result.version.strategy.value
                or attributes.get("version_value") != persisted_result.version.value
                or attributes.get("content_hash") != expected_content_hash
                or attributes.get("source_updated_at") != expected_updated_at
                or attributes.get("row_count") != persisted_result.row_count
                or attributes.get("completeness") != str(persisted_result.completeness)
            ):
                continue
            if not any(
                edge.source_id == entity_id
                and edge.target_id == "connector_ingestion_run"
                and edge.relation is RelationType.WAS_GENERATED_BY
                for edge in graph.edges
            ):
                continue
        except Exception:
            logger.warning(
                "batch_incremental: source evidence binding failed for %s:%s",
                connector_id,
                dataset_id,
            )
            continue

        try:
            witness_ref = frame.witness(store)
        except (LookupError, OSError, TypeError, ValueError):
            continue
        strategy, watermark_value, _source_time = source_boundary
        cursor = CursorState(
            cursor_id=f"{connector_id}:{dataset_id}",
            connector_id=connector_id,
            dataset_id=dataset_id,
            watermark_type=watermark_type,
            watermark_value=watermark_value,
            created_at=datetime.now(UTC),
            ingestion_run_id=_cursor_result_ref(evidence_ref),
            evidence_bundle_ref=_cursor_result_ref(evidence_ref),
            metadata={
                "cache_key": request.cache_key,
                "source_artifact_id": artifact_hex,
                "provenance_artifact_id": provenance_ref.artifact_id,
                "provenance_stable_id": provenance_ref.stable_id,
                "source_version_strategy": strategy.value,
                "source_version_value": watermark_value,
                "source_content_hash": expected_content_hash,
                "source_progress": {
                    "witness_ref": witness_ref.model_dump(mode="json"),
                    "payload_ref": payload_ref.model_dump(mode="json"),
                    "evidence_ref": evidence_ref.model_dump(mode="json"),
                    "actual_request_key": request.cache_key,
                    "actual_request": snapshot_fetch_request(request),
                },
            },
        )
        from polisyos.fabric.data_plane.cursor_store import CursorStoreConflict

        try:
            cursor_ref = cursor_store.save_cursor_if_unchanged(cursor, expected_cursor=previous)
        except CursorStoreConflict:
            result.warnings.append(f"source_cursor_predecessor_changed:{connector_id}:{dataset_id}")
            continue
        result.cursor_ref = str(cursor_ref.artifact_id)
        admitted.add(key)

    return admitted


def run_batch_incremental(
    *,
    connector_manifest: ConnectorManifestInput,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: ConnectionConfig | dict[str, object] | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> IngestionResult:
    """Run ingestion in batch_incremental mode.

    1. For each dataset, look up latest cursor via CursorStore.
    2. Build incremental_cursors dict mapping dataset_id → cursor watermark.
    3. Delegate to run_connectors_ingestion with incremental hints.
    4. Extract watermarks from results and save new cursors.
    5. Return IngestionResult with cursor_ref.
    """
    datasets = _extract_datasets(connector_manifest)
    if len(datasets) != len(set(datasets)):
        raise ValueError("batch_incremental source dataset identities must be unique")
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
    from polisyos.fabric.data_plane.streaming import normalize_connection_config
    from polisyos.fabric.ingestion.source_progress import resolve_source_progress_frame

    effective_input_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    store = _resolve_mode_store(
        Path(cas_root), effective_input_dependencies, sidecar_scope=invocation_scope
    )
    cursor_store = CursorStore(store, index_root=invocation_scope.cursor_index_root)

    dataset_connectors = _resolve_dataset_connectors(effective_input_dependencies, datasets)
    cursor_versions: dict[tuple[str, str], DataVersion] = {}
    frames: dict[tuple[str, str], ReconciledSourceFrame] = {}
    predecessors: dict[tuple[str, str], CursorState | None] = {}
    admission_warnings: list[str] = []
    for connector_id, dataset_id in datasets:
        key = (connector_id, dataset_id)
        try:
            frame = resolve_source_progress_frame(
                effective_input_dependencies.source_progress_readers,
                connector_id=connector_id,
                dataset_id=dataset_id,
                tenant_id=invocation_scope.tenant_id,
            )
            if frame is not None:
                selected_config = normalize_connection_config(connection_config)
                if selected_config is None:
                    selected_config = effective_input_dependencies.registry.get_entry(
                        connector_id
                    ).default_config
                if selected_config is None:
                    raise ValueError("actual source connection is unavailable")
                frame = frame.bind_transport(selected_config)
        except (LookupError, OSError, TypeError, ValueError):
            frame = None
        if frame is not None:
            frames[key] = frame
            admission_warnings.append(
                f"source_progress_scope:{connector_id}:{dataset_id}:finite_source_fixture;"
                "production_currentness=not_established"
            )
        else:
            admission_warnings.append(
                f"source_progress_not_established:{connector_id}:{dataset_id}"
            )
        cursor = cursor_store.find_latest_cursor(connector_id, dataset_id)
        predecessors[key] = cursor
        if cursor is not None:
            version = _cursor_version(
                cursor,
                dataset_connectors.get((connector_id, dataset_id)),
                frame=frame,
                store=store,
            )
            if version is None:
                continue
            cursor_versions[(connector_id, dataset_id)] = version
            logger.info(
                "batch_incremental: cursor found for %s:%s → %s",
                connector_id,
                dataset_id,
                cursor.watermark_value,
            )

    confirmed_results: dict[tuple[str, str], FetchResult[object]] = {}
    persisted_results: dict[
        tuple[str, str],
        tuple[
            FetchRequest, FetchResult[object], FetchResult[object], ArtifactRef, EvidenceBundleRef
        ],
    ] = {}

    def _capture_result(
        connector_id: str,
        dataset_id: str,
        request: FetchRequest,
        fetch_result: FetchResult[object],
    ) -> None:
        del request
        confirmed_results[(str(connector_id), str(dataset_id))] = fetch_result

    def _capture_persisted_result(
        connector_id: str,
        dataset_id: str,
        request: FetchRequest,
        source_result: FetchResult[object],
        persisted_result: FetchResult[object],
        payload_ref: ArtifactRef,
        evidence_ref: EvidenceBundleRef,
    ) -> None:
        persisted_results[(str(connector_id), str(dataset_id))] = (
            request,
            source_result,
            persisted_result,
            payload_ref,
            evidence_ref,
        )

    reconciled: dict[tuple[str, str], _ReconciledFetch] = {}
    effective_dependencies = (
        _cursor_aware_dependencies(effective_input_dependencies, frames, reconciled)
        if frames
        else effective_input_dependencies
    )

    def _admit_request(connector_id: str, request: FetchRequest) -> FetchRequest:
        version = cursor_versions.get((connector_id, request.dataset_id))
        if request.incremental_since is not None:
            raise ValueError("incremental predecessor must come from admitted cursor intake")
        return replace(request, incremental_since=version) if version is not None else request

    # Run normal orchestrated ingestion
    result = run_orchestrated_ingestion(
        connector_manifest=_orchestrator_manifest_input(connector_manifest),
        source=source,
        license_name=license_name,
        cas_root=cas_root,
        connection_config=connection_config,
        produce_snapshot=False,
        ingestion_dependencies=effective_dependencies,
        sidecar_scope=invocation_scope,
        raw_result_sink=_capture_result,
        request_transform=_admit_request,
        persisted_result_sink=_capture_persisted_result,
        continue_on_fetch_error=True,
    )

    result.warnings.extend(admission_warnings)
    advanced = _save_confirmed_cursors(
        cursor_store=cursor_store,
        store=store,
        connectors=dataset_connectors,
        datasets=datasets,
        confirmed_results=confirmed_results,
        persisted_results=persisted_results,
        result=result,
        frames=frames,
        reconciled=reconciled,
        predecessors=predecessors,
    )
    missing_progress = set(datasets) - advanced
    if missing_progress:
        result.warnings.extend(
            f"source_cursor_not_advanced:{connector_id}:{dataset_id}"
            for connector_id, dataset_id in sorted(missing_progress)
        )
        result.status = "partial" if result.datasets_fetched else "failed"
        result.data_snapshot_ref = None
        if result.evidence_bundle_ref is not None:
            from polisyos.fabric.ingestion.source_progress import project_partial_source_scope

            result.evidence_bundle_ref = project_partial_source_scope(
                store,
                result.evidence_bundle_ref,
                frames=frames,
                advanced=advanced,
            )
    elif (
        produce_snapshot and result.status == "completed" and result.evidence_bundle_ref is not None
    ):
        from polisyos.core.artifacts.async_store import ensure_async_artifact_store
        from polisyos.fabric.data_plane.orchestrator import _build_snapshot_from_evidence_async
        from polisyos.fabric.ingestion.source_collection import materialize_source_collection

        collection_ref, collection_evidence_ref = materialize_source_collection(
            store=store,
            evidence_ref=result.evidence_bundle_ref,
            datasets=tuple(datasets),
            persisted_results=persisted_results,
            frames=frames,
        )
        result.evidence_bundle_ref = collection_evidence_ref

        # Compose the existing snapshot producer only after the complete
        # per-source admission/progress result is known. A partial invocation
        # must not create a nominally complete snapshot and merely hide its ref.
        result.data_snapshot_ref = run_coro_sync(
            _build_snapshot_from_evidence_async(
                store=ensure_async_artifact_store(store),
                evidence_ref=result.evidence_bundle_ref,
                datasets_fetched=result.datasets_fetched,
                source=source,
                data_ref_override=collection_ref,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Record mode
# ---------------------------------------------------------------------------


def run_record_mode(
    *,
    connector_manifest: ConnectorManifestInput,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: ConnectionConfig | dict[str, object] | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> tuple[IngestionResult, str]:
    """Run ingestion with HTTP recording enabled.

    1. Create APISimulator in RECORD mode with a temp fixture_root.
    2. Run ingestion inside the simulator context.
    3. Collect captured fixtures from the temp directory.
    4. Persist RecordSession to CAS via ReplayStore.
    5. Return (IngestionResult, canonical record ArtifactID).
    """
    import tempfile
    import uuid

    from polisyos.core.artifacts import ArtifactOwnershipError
    from polisyos.core.security import TenantIsolationError
    from polisyos.fabric.connectors.testing.simulator import APISimulator, SimulatorMode
    from polisyos.fabric.data_plane.replay_store import (
        ReplayStore,
        make_record_session,
    )
    from polisyos.fabric.data_plane.streaming import normalize_connection_config

    connection_config = normalize_connection_config(connection_config)
    datasets = _extract_datasets(connector_manifest)
    effective_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    session_id = uuid.uuid4().hex

    # Extract connector/dataset info for the session metadata
    connector_datasets = [{"connector_id": ds[0], "dataset_id": ds[1]} for ds in datasets]

    with tempfile.TemporaryDirectory(prefix="polisyos_record_") as tmpdir:
        fixture_root = Path(tmpdir)

        # Determine connector_id for the simulator
        first_connector_id = datasets[0][0] if datasets else "unknown"
        first_dataset_id = datasets[0][1] if datasets else "unknown"

        simulator = APISimulator(
            mode=SimulatorMode.RECORD,
            fixture_root=fixture_root,
            connector_id=first_connector_id,
            dataset_id=first_dataset_id,
        )

        # Run ingestion with recording — the simulator patches aiohttp globally
        # so any HTTP calls during ingestion are intercepted.
        # Note: APISimulator is async context manager. Since ingestion uses
        # run_coro_sync internally, we wrap in our own async context.
        async def _record_ingestion() -> EvidenceBundleRef | None:
            async with simulator:
                from polisyos.fabric.ingestion import run_connectors_ingestion

                evidence_ref = await run_blocking_async(
                    run_connectors_ingestion,
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                    dependencies=effective_dependencies,
                    sidecar_scope=invocation_scope,
                )
                return evidence_ref

        try:
            evidence_ref = run_coro_sync(_record_ingestion())
        except (ArtifactOwnershipError, TenantIsolationError):
            raise
        except Exception as exc:
            logger.warning(
                "Record-mode capture failed; refusing an unrecorded retry",
                exception_type=type(exc).__name__,
            )
            raise RecordModeCaptureError("record_mode_capture_failed") from exc

        # Build result from evidence_ref

        datasets_fetched = len(datasets)
        result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=datasets_fetched,
            mode_effective="record",
        )

        # Collect fixtures and persist session
        session = make_record_session(
            session_id=session_id,
            fixture_root=fixture_root,
            connector_datasets=connector_datasets,
        )
        store = _resolve_mode_store(
            Path(cas_root), effective_dependencies, sidecar_scope=invocation_scope
        )
        replay_store = ReplayStore(store)
        ref = replay_store.save_record_session(session)

        return result, str(ref.artifact_id)


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------


def run_replay_mode(
    *,
    connector_manifest: ConnectorManifestInput,
    source: str,
    license_name: str,
    cas_root: Path,
    replay_ref: str,
    connection_config: ConnectionConfig | dict[str, object] | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> IngestionResult:
    """Run ingestion using recorded HTTP responses (no network).

    1. Load RecordSession from CAS via replay_ref.
    2. Write fixtures to temp dir via ReplayStore.build_replay_fixture_dir().
    3. Run ingestion — APISimulator in REPLAY mode serves cached responses.
    4. Return IngestionResult.
    """
    import tempfile

    from polisyos.core.artifacts import ArtifactID
    from polisyos.fabric.data_plane.replay_store import ReplayStore
    from polisyos.fabric.data_plane.streaming import normalize_connection_config

    connection_config = normalize_connection_config(connection_config)
    datasets = _extract_datasets(connector_manifest)
    effective_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    store = _resolve_mode_store(
        Path(cas_root), effective_dependencies, sidecar_scope=invocation_scope
    )
    replay_store = ReplayStore(store)

    # Load session from CAS
    artifact_id = ArtifactID.model_validate(replay_ref)
    session = replay_store.load_record_session(artifact_id.root)

    with tempfile.TemporaryDirectory(prefix="polisyos_replay_") as tmpdir:
        fixture_dir = Path(tmpdir)
        replay_store.build_replay_fixture_dir(session, fixture_dir)

        # Patch aiohttp to serve from fixtures
        from polisyos.fabric.connectors.testing.simulator import (
            APISimulator,
            SimulatorMode,
        )

        first_connector_id = datasets[0][0] if datasets else "unknown"
        first_dataset_id = datasets[0][1] if datasets else "unknown"

        simulator = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=fixture_dir,
            connector_id=first_connector_id,
            dataset_id=first_dataset_id,
        )

        async def _replay_ingestion() -> EvidenceBundleRef | None:
            async with simulator:
                from polisyos.fabric.ingestion import run_connectors_ingestion

                return await run_blocking_async(
                    run_connectors_ingestion,
                    connector_manifest=connector_manifest,
                    source=source,
                    license_name=license_name,
                    cas_root=cas_root,
                    connection_config=connection_config,
                    dependencies=effective_dependencies,
                    sidecar_scope=invocation_scope,
                )

        evidence_ref = run_coro_sync(_replay_ingestion())

        result = IngestionResult(
            evidence_bundle_ref=evidence_ref,
            datasets_fetched=len(datasets),
            mode_effective="replay",
        )
        return result


# ---------------------------------------------------------------------------
# Streaming windowed mode
# ---------------------------------------------------------------------------


def _sanitize_stream_rows(
    rows: object,
    *,
    connector_id: str,
    dataset_id: str,
    store: ArtifactStore,
    chunk_index: int,
    schema: DataSchema | None = None,
    schema_binding: StreamSchemaBinding | None = None,
) -> tuple[list[dict[str, object]], list[str], int]:
    if not isinstance(rows, list):
        rows = [rows]

    valid_rows: list[dict[str, object]] = []
    warnings: list[str] = []
    quarantined = 0
    if schema is None:
        signatures = {
            tuple(sorted(str(key) for key in row)) for row in rows if isinstance(row, dict)
        }
        if len(signatures) > 1:
            warnings.append(
                f"schema_not_established for {connector_id}:{dataset_id}; "
                "heterogeneous object rows retained for investigation"
            )

    field_by_name = {field.name: field for field in schema.fields} if schema else {}
    required_fields = set(schema.required_field_names()) if schema else set()
    schema_version = str(schema.version) if schema else "1.0"
    for row_index, row in enumerate(rows):
        reason: str | None = None
        context: dict[str, object] = {
            "chunk_index": chunk_index,
            "row_index": row_index,
        }
        if not isinstance(row, dict):
            reason = "poison_stream_message"
            context["message"] = "stream message is not a JSON object"
        else:
            if schema is not None:
                actual_fields = set(row)
                missing_required = sorted(required_fields - actual_fields)
                if missing_required:
                    reason = "poison_stream_message"
                    context["missing_required_fields"] = missing_required
                else:
                    non_nullable = sorted(
                        field_name
                        for field_name, field in field_by_name.items()
                        if field_name in row
                        and row[field_name] is None
                        and not field.nullable
                        and field_name not in schema.allowed_null_fields
                    )
                    if non_nullable:
                        reason = "poison_stream_message"
                        context["non_nullable_fields"] = non_nullable

            if reason is None and schema is not None:
                from polisyos.fabric.data_plane.schema_rows import field_value_violation

                violations = {
                    name: violation
                    for name, field in field_by_name.items()
                    if name in row and row[name] is not None
                    if (violation := field_value_violation(row[name], field)) is not None
                }
                if violations:
                    reason = (
                        "non_finite_metric"
                        if "schema_non_finite" in violations.values()
                        else "poison_stream_message"
                    )
                    context["field_violations"] = violations

            if reason is None:
                non_finite = _non_finite_fields(row)
                if non_finite:
                    reason = "non_finite_metric"
                    context["fields"] = non_finite

            if schema_binding is not None:
                context["schema_binding"] = schema_binding.snapshot()

        if reason is None:
            valid_rows.append(row)
            continue

        quarantined += 1
        warnings.append(
            f"quarantined stream row {row_index} from {connector_id}:{dataset_id} "
            f"chunk {chunk_index} because of {reason}"
        )
        if not isinstance(store, IndexedArtifactStore):
            raise TypeError(
                "stream row quarantine requires an IndexedArtifactStore with a local Path root"
            )
        persist_quarantine_record(
            store,
            record=QuarantineRecord.new(
                reason=reason,
                severity="error",
                source=f"connector.stream:{connector_id}:{dataset_id}",
                schema_version=schema_version,
                trace_id=f"{connector_id}:{dataset_id}:chunk:{chunk_index}:row:{row_index}",
                downstream_impacts=(
                    "streaming_windowed",
                    "evidence_bundle",
                    "data_snapshot",
                ),
                context=context,
            ),
            raw_payload=row,
        )

    return valid_rows, warnings, quarantined


def _bind_stream_sanitizer(
    schema_binding: StreamSchemaBinding | None,
) -> Callable[..., tuple[list[dict[str, object]], list[str], int]]:
    """Bind one admitted schema without changing custom sanitizer call shape."""
    schema = getattr(schema_binding, "schema", None)

    def _bound(
        rows: object,
        *,
        connector_id: str,
        dataset_id: str,
        store: ArtifactStore,
        chunk_index: int,
    ) -> tuple[list[dict[str, object]], list[str], int]:
        return _sanitize_stream_rows(
            rows,
            schema=schema,
            schema_binding=schema_binding,
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=chunk_index,
        )

    return _bound


def run_streaming_windowed(
    *,
    connector_manifest: ConnectorManifestInput,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: ConnectionConfig | dict[str, object] | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> IngestionResult:
    return run_coro_sync(
        _run_streaming_windowed_async(
            connector_manifest=connector_manifest,
            source=source,
            license_name=license_name,
            cas_root=cas_root,
            connection_config=connection_config,
            produce_snapshot=produce_snapshot,
            ingestion_dependencies=ingestion_dependencies,
            sidecar_scope=sidecar_scope,
        )
    )


async def _run_streaming_windowed_async(
    *,
    connector_manifest: ConnectorManifestInput,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: ConnectionConfig | dict[str, object] | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> IngestionResult:
    """Run ingestion in streaming_windowed mode.

    This mode uses an event-driven runtime with:
    - resumable stream checkpoints;
    - bounded window accumulators (tumbling/sliding/session/count);
    - duplicate replay suppression;
    - per-record quarantine for poison messages;
    - CDC schema-change artifacts when stream schema drifts.
    """
    datasets, manifest_mapping = _normalize_mode_manifest(connector_manifest)
    _stream_runtime_options_from_manifest(manifest_mapping)

    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.streaming import (
        _resolve_stream_schema_binding,
        process_stream_dataset,
    )
    from polisyos.fabric.evidence import build_evidence_bundle, persist_evidence_bundle

    ingestion_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    store = _resolve_mode_store(
        Path(cas_root), ingestion_dependencies, sidecar_scope=invocation_scope
    )
    cursor_store = CursorStore(store, index_root=invocation_scope.cursor_index_root)
    connector_registry = ingestion_dependencies.registry

    source_refs: list[ArtifactRef] = []
    source_scopes: dict[str, object] = {}
    warnings: list[str] = []
    total_chunks = 0
    total_rows = 0
    total_windows = 0
    total_cdc_events = 0
    total_quarantined = 0
    cursor_ref: str | None = None

    for ds_connector_id, ds_dataset_id in datasets:
        runtime_options = _stream_runtime_options_from_manifest(
            manifest_mapping,
            dataset_id=ds_dataset_id,
        )
        schema_binding = _resolve_stream_schema_binding(
            connector_registry,
            connector_id=ds_connector_id,
            dataset_id=ds_dataset_id,
        )
        bound_sanitizer = _bind_stream_sanitizer(schema_binding)
        dataset_result: _StreamDatasetResultSummary
        if _connector_is_registered(ds_connector_id, registry=connector_registry):
            dataset_result = await process_stream_dataset(
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                store=store,
                cursor_store=cursor_store,
                sanitize_rows=bound_sanitizer,
                runtime_options=runtime_options,
                connection_config=connection_config,
                registry=connector_registry,
                schema_binding=schema_binding,
                source_progress_readers=ingestion_dependencies.source_progress_readers,
                tenant_id=invocation_scope.tenant_id,
            )
        else:
            from polisyos.fabric.data_plane.streaming import StreamDedupeUnsupported

            if runtime_options.processing_contract.idempotency.enabled:
                raise StreamDedupeUnsupported(
                    "legacy streaming has no source-owned event/version admission bridge"
                )
            dataset_result = await _run_legacy_stream_dataset_from_fetch_async(
                store=store,
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                connector_manifest=connector_manifest,
                connection_config=connection_config,
                registry=connector_registry,
                schema_binding=schema_binding,
            )
        from polisyos.fabric.ingestion.source_collection import source_namespace

        source_scopes[source_namespace(ds_connector_id, ds_dataset_id)] = (
            dataset_result.source_progress_scope
            if dataset_result.source_progress_scope is not None
            else {"status": "not_established", "admission_scope": "candidate_only"}
        )
        warnings.extend(dataset_result.warnings)
        source_refs.extend(dataset_result.chunk_refs)
        source_refs.extend(dataset_result.window_refs)
        source_refs.extend(dataset_result.cdc_event_refs)
        total_chunks += dataset_result.chunks_processed
        total_rows += dataset_result.rows_emitted
        total_windows += len(dataset_result.window_refs)
        total_cdc_events += len(dataset_result.cdc_event_refs)
        total_quarantined += dataset_result.quarantined_rows
        if dataset_result.final_cursor_ref is not None:
            cursor_ref = dataset_result.final_cursor_ref

    if not source_refs:
        return IngestionResult(
            datasets_fetched=len(datasets),
            mode_effective="streaming_windowed",
            warnings=warnings or ["No data chunks received"],
            cursor_ref=cursor_ref,
        )

    manifest_payload = {
        "source": f"streaming_windowed:{source}",
        "license_name": license_name,
        "datasets": [
            {
                "connector_id": connector_id,
                "dataset_id": dataset_id,
            }
            for connector_id, dataset_id in datasets
        ],
        "total_chunks": total_chunks,
        "total_rows": total_rows,
        "total_windows": total_windows,
        "total_cdc_events": total_cdc_events,
        "quarantined_rows": total_quarantined,
        "source_progress_scopes": source_scopes,
        "production_currentness": "not_established",
    }
    manifest_ref = await _persist_streaming_manifest_async(
        store=store,
        manifest_payload=manifest_payload,
        source_refs=source_refs,
    )
    evidence_bundle = build_evidence_bundle(
        sources=[manifest_ref, *source_refs],
        notes=[
            f"streaming_windowed source={source}",
            f"datasets={len(datasets)}",
            f"chunks={total_chunks}",
            f"rows={total_rows}",
            f"windows={total_windows}",
            f"cdc_events={total_cdc_events}",
            f"quarantined_rows={total_quarantined}",
            (
                "Source scopes are bound in the streaming manifest; finite replay never "
                "establishes production currentness, rights or live event meaning."
            ),
        ],
    )
    evidence_ref = await run_blocking_async(persist_evidence_bundle, store, evidence_bundle)

    data_snapshot_ref = None
    if produce_snapshot:
        snapshot = DataSnapshot(
            data_ref=manifest_ref,
            evidence_ref=evidence_ref,
            stats={
                "datasets_fetched": len(datasets),
                "total_chunks": total_chunks,
                "total_rows": total_rows,
                "total_windows": total_windows,
                "total_cdc_events": total_cdc_events,
                "quarantined_rows": total_quarantined,
                "source": f"streaming_windowed:{source}",
            },
            notes=[
                "fabric.data_plane.streaming_windowed",
                (
                    "source_progress_scope=see_data_ref_manifest; "
                    "production_currentness=not_established"
                ),
                f"window_strategy={_stream_runtime_options_from_manifest(connector_manifest).window_policy.strategy.value}",
            ],
        )
        snapshot_ref = await _persist_streaming_snapshot_async(
            store=store,
            snapshot_payload=snapshot.model_dump(mode="json"),
            manifest_ref=manifest_ref,
            evidence_ref=evidence_ref,
        )
        data_snapshot_ref = DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)

    return IngestionResult(
        evidence_bundle_ref=evidence_ref,
        data_snapshot_ref=data_snapshot_ref,
        datasets_fetched=len(datasets),
        mode_effective="streaming_windowed",
        warnings=warnings,
        cursor_ref=cursor_ref,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stream_runtime_options_from_manifest(
    connector_manifest: ConnectorManifestInput,
    *,
    dataset_id: str | None = None,
) -> StreamRuntimeOptions:
    from polisyos.fabric.data_plane.watermark import WindowPolicy

    if isinstance(connector_manifest, ConnectorManifestSpec):
        manifest_mapping: Mapping[str, object] = {}
    elif isinstance(connector_manifest, Mapping):
        manifest_mapping = connector_manifest
    else:
        from polisyos.fabric.ingestion.ingestion import _connector_manifest_mapping

        manifest_mapping = _connector_manifest_mapping(connector_manifest)

    raw_streaming_value = manifest_mapping.get("streaming", {})
    if "streaming" in manifest_mapping and not isinstance(raw_streaming_value, Mapping):
        raise ValueError("connector manifest field 'streaming' must be a mapping")
    raw_streaming = dict(raw_streaming_value) if isinstance(raw_streaming_value, Mapping) else {}

    raw_window_value = raw_streaming.get("window", {})
    if "window" in raw_streaming and not isinstance(raw_window_value, Mapping):
        raise ValueError("connector manifest field 'streaming.window' must be a mapping")
    nested_window = dict(raw_window_value) if isinstance(raw_window_value, Mapping) else {}

    legacy_window_value = manifest_mapping.get("streaming_window", {})
    if "streaming_window" in manifest_mapping and not isinstance(legacy_window_value, Mapping):
        raise ValueError("connector manifest field 'streaming_window' must be a mapping")
    legacy_window = dict(legacy_window_value) if isinstance(legacy_window_value, Mapping) else {}
    raw_window = nested_window or legacy_window

    strategy_raw = str(raw_window.get("strategy", "tumbling")).strip().lower()
    try:
        strategy = WindowStrategy(strategy_raw)
    except ValueError as exc:
        raise ValueError(f"unsupported streaming window strategy: {strategy_raw!r}") from exc

    window_policy = WindowPolicy(
        strategy=strategy,
        size=raw_window.get("size", 1),
        slide=raw_window.get("slide"),
        session_gap_seconds=raw_window.get("session_gap_seconds"),
        timestamp_field=str(raw_window.get("timestamp_field", "event_time")),
    )
    partition_key = str(raw_streaming.get("partition_key", "default"))
    if dataset_id:
        partition_key = str(raw_streaming.get("partition_key", dataset_id))

    dedupe_fields: tuple[str, ...] | None = None
    if "dedupe_key_fields" in raw_streaming:
        raw_fields = raw_streaming["dedupe_key_fields"]
        if (
            not isinstance(raw_fields, (tuple, list))
            or not raw_fields
            or any(not isinstance(name, str) or not name.strip() for name in raw_fields)
            or len(set(raw_fields)) != len(raw_fields)
        ):
            raise ValueError("streaming dedupe_key_fields must contain unique nonempty names")
        dedupe_fields = tuple(raw_fields)
    return StreamRuntimeOptions(
        partition_key=partition_key,
        batch_size=int(raw_streaming.get("batch_size", 1_000)),
        checkpoint_every_chunks=int(raw_streaming.get("checkpoint_every_chunks", 1)),
        dedupe_key_fields=dedupe_fields,
        max_dedupe_keys=int(raw_streaming.get("max_dedupe_keys", 4_096)),
        max_buffered_rows=int(raw_streaming.get("max_buffered_rows", 10_000)),
        max_buffered_bytes=int(raw_streaming.get("max_buffered_bytes", 16 * 1024 * 1024)),
        max_input_rows=raw_streaming.get("max_input_rows"),
        max_input_bytes=raw_streaming.get("max_input_bytes"),
        max_output_refs=raw_streaming.get("max_output_refs", 4_096),
        pause_seconds=float(raw_streaming.get("pause_seconds", 0.01)),
        window_policy=window_policy,
    )


def _connector_is_registered(
    connector_id: str,
    *,
    registry: _BatchConnectorRegistry | None = None,
) -> bool:
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        resolved_registry.get_entry(connector_id)
        return True
    except Exception:
        return False


def _run_legacy_stream_dataset(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    chunks: list[_LegacyStreamChunk],
    schema_binding: StreamSchemaBinding | None = None,
) -> _LegacyStreamDatasetResult:
    from polisyos.fabric.connectors.types import DataChunk
    from polisyos.fabric.data_plane.streaming import persist_stream_chunk

    chunk_refs = []
    warnings: list[str] = []
    rows_emitted = 0
    quarantined_rows = 0

    for chunk_data in chunks:
        chunk_index = int(chunk_data.get("chunk_index", 0))
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=chunk_index,
            schema=getattr(schema_binding, "schema", None),
            schema_binding=schema_binding,
        )
        warnings.extend(chunk_warnings)
        quarantined_rows += chunk_quarantined
        rows_emitted += len(clean_rows)
        chunk_refs.append(
            persist_stream_chunk(
                store=store,
                connector_id=connector_id,
                dataset_id=dataset_id,
                partition_key="default",
                chunk=DataChunk(
                    data=clean_rows,
                    chunk_index=chunk_index,
                    row_count=len(clean_rows),
                    bytes_size=0,
                    is_first=bool(chunk_data.get("is_first", False)),
                    is_last=bool(chunk_data.get("is_last", False)),
                ),
                rows=clean_rows,
                dedupe_dropped=0,
                schema_binding=schema_binding,
                visible_fields=tuple(sorted({str(key) for row in clean_rows for key in row})),
            )
        )

    return _LegacyStreamDatasetResult(
        chunk_refs=chunk_refs,
        window_refs=[],
        cdc_event_refs=[],
        warnings=warnings,
        rows_emitted=rows_emitted,
        chunks_processed=len(chunks),
        quarantined_rows=quarantined_rows,
        final_cursor_ref=None,
    )


async def _run_legacy_stream_dataset_async(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    chunks: list[_LegacyStreamChunk],
    schema_binding: StreamSchemaBinding | None = None,
) -> _LegacyStreamDatasetResult:
    from polisyos.core.artifacts.async_store import ensure_async_artifact_store
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.fabric.connectors.types import DataChunk

    async_store = ensure_async_artifact_store(store)
    chunk_refs = []
    warnings: list[str] = []
    rows_emitted = 0
    quarantined_rows = 0

    for chunk_data in chunks:
        chunk_index = int(chunk_data.get("chunk_index", 0))
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=chunk_index,
            schema=getattr(schema_binding, "schema", None),
            schema_binding=schema_binding,
        )
        warnings.extend(chunk_warnings)
        quarantined_rows += chunk_quarantined
        rows_emitted += len(clean_rows)
        chunk = DataChunk(
            data=clean_rows,
            chunk_index=chunk_index,
            row_count=len(clean_rows),
            bytes_size=0,
            is_first=bool(chunk_data.get("is_first", False)),
            is_last=bool(chunk_data.get("is_last", False)),
        )
        chunk_refs.append(
            await async_store.put_json(
                {
                    "connector_id": connector_id,
                    "dataset_id": dataset_id,
                    "partition_key": "default",
                    "chunk_index": int(chunk.chunk_index),
                    "row_count": len(clean_rows),
                    "bytes_size": int(getattr(chunk, "bytes_size", 0) or 0),
                    "resume_token": getattr(chunk, "resume_token", None),
                    "is_first": bool(getattr(chunk, "is_first", False)),
                    "is_last": bool(getattr(chunk, "is_last", False)),
                    "dedupe_dropped": 0,
                    "schema_binding": (
                        schema_binding.snapshot()
                        if schema_binding is not None
                        else {"status": "not_established"}
                    ),
                    "visible_fields": sorted({str(key) for row in clean_rows for key in row}),
                    "data": clean_rows,
                },
                ArtifactWriteOptions(
                    kind="fabric.stream_chunk",
                    media_type="application/json",
                    schema=SchemaInfo(name="fabric.StreamChunk", version="2.0"),
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
        )

    return _LegacyStreamDatasetResult(
        chunk_refs=chunk_refs,
        window_refs=[],
        cdc_event_refs=[],
        warnings=warnings,
        rows_emitted=rows_emitted,
        chunks_processed=len(chunks),
        quarantined_rows=quarantined_rows,
        final_cursor_ref=None,
    )


async def _run_legacy_stream_dataset_from_fetch_async(
    *,
    store: ArtifactStore,
    connector_id: str,
    dataset_id: str,
    connector_manifest: ConnectorManifestInput,
    connection_config: ConnectionConfig | dict[str, object] | None,
    registry: _BatchConnectorRegistry | None = None,
    schema_binding: StreamSchemaBinding | None = None,
) -> _LegacyStreamDatasetResult:
    chunks = await _fetch_stream_for_dataset_async(
        connector_id=connector_id,
        dataset_id=dataset_id,
        connector_manifest=connector_manifest,
        connection_config=connection_config,
        registry=registry,
    )
    return await _run_legacy_stream_dataset_async(
        store=store,
        connector_id=connector_id,
        dataset_id=dataset_id,
        chunks=chunks,
        schema_binding=schema_binding,
    )


def _normalize_mode_manifest(
    connector_manifest: ConnectorManifestInput,
) -> tuple[list[tuple[str, str]], Mapping[str, object]]:
    """Validate one manifest and return its dataset identities and raw options."""
    from polisyos.fabric.ingestion.ingestion import _connector_manifest_mapping

    if isinstance(connector_manifest, ConnectorManifestSpec):
        spec = connector_manifest
        raw_manifest: Mapping[str, object] = {}
    elif isinstance(connector_manifest, (Mapping, Path, str)):
        raw_manifest = _connector_manifest_mapping(connector_manifest)
        spec = ConnectorManifestSpec.from_mapping(raw_manifest)
    elif hasattr(connector_manifest, "datasets"):
        raw_datasets = connector_manifest.datasets
        if not isinstance(raw_datasets, list):
            raise ValueError("connector manifest 'datasets' must be a list of mappings")
        normalized_datasets: list[Mapping[str, object]] = []
        for index, dataset in enumerate(raw_datasets):
            if isinstance(dataset, Mapping):
                normalized_datasets.append(dataset)
                continue
            connector_id = getattr(dataset, "connector_id", None)
            dataset_id = getattr(dataset, "dataset_id", None)
            if not isinstance(connector_id, str) or not connector_id.strip():
                raise ValueError(f"connector manifest dataset {index} has invalid connector_id")
            if not isinstance(dataset_id, str) or not dataset_id.strip():
                raise ValueError(f"connector manifest dataset {index} has invalid dataset_id")
            normalized_datasets.append({"connector_id": connector_id, "dataset_id": dataset_id})
        spec = ConnectorManifestSpec.from_mapping({"datasets": normalized_datasets})
        raw_manifest = {
            field: getattr(connector_manifest, field)
            for field in ("streaming", "streaming_window")
            if hasattr(connector_manifest, field)
        }
    else:
        raise TypeError("connector_manifest must be a mapping, Path, str, or ConnectorManifestSpec")

    return [(dataset.connector_id, dataset.dataset_id) for dataset in spec.datasets], raw_manifest


def _extract_datasets(
    connector_manifest: ConnectorManifestInput,
) -> list[tuple[str, str]]:
    """Extract dataset pairs through the shared manifest intake validator."""
    datasets, _ = _normalize_mode_manifest(connector_manifest)
    return datasets


def _resolve_connector_registry(
    *,
    registry: _BatchConnectorRegistry | None = None,
) -> _BatchConnectorRegistry:
    if registry is not None:
        return registry
    return _default_connector_registry()


def _default_connector_registry() -> _BatchConnectorRegistry:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return ConnectorRegistry.get_instance()


async def _fetch_stream_for_dataset_async(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: ConnectorManifestInput,
    connection_config: ConnectionConfig | dict[str, object] | None,
    registry: _BatchConnectorRegistry | None = None,
) -> list[_LegacyStreamChunk]:
    """Fetch stream chunks for a single dataset without nesting a sync bridge."""
    del connector_manifest
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        entry = resolved_registry.get_entry(connector_id)
        if entry is None:
            logger.warning("streaming_windowed: connector %s not found", connector_id)
            return []

        connector = resolved_registry.get(connector_id)

        capabilities = connector.capabilities
        if not (capabilities & ConnectorCapability.STREAMING):
            logger.info(
                "streaming_windowed: connector %s doesn't support streaming, "
                "falling back to single-chunk fetch",
                connector_id,
            )
            return []

        from polisyos.fabric.data_plane.streaming import normalize_connection_config

        handle = await resolved_registry.get_connection(
            connector_id, normalize_connection_config(connection_config)
        )
        try:
            from polisyos.ir.connectors import FetchRequest

            request = FetchRequest(dataset_id=dataset_id)
            chunks: list[_LegacyStreamChunk] = []
            stream = await resolve_async_iterator(connector.fetch_stream(handle, request))
            async for chunk in stream:
                data = chunk.data
                rows: list[object] = []
                if hasattr(data, "to_dict"):
                    rows = await run_blocking_async(
                        data.to_dict,
                        orient="records",
                    )
                elif isinstance(data, list):
                    rows = data

                chunks.append(
                    {
                        "chunk_index": chunk.chunk_index,
                        "row_count": chunk.row_count,
                        "is_first": chunk.is_first,
                        "is_last": chunk.is_last,
                        "data": rows,
                    }
                )
            return chunks
        finally:
            await resolved_registry.release_connection(connector_id, handle)
    except Exception as exc:
        logger.warning(
            "streaming_windowed: failed to stream %s:%s: %s",
            connector_id,
            dataset_id,
            exc,
        )
        return []


def _fetch_stream_for_dataset(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: ConnectorManifestInput,
    connection_config: ConnectionConfig | dict[str, object] | None,
    registry: _BatchConnectorRegistry | None = None,
) -> list[_LegacyStreamChunk]:
    """Fetch stream chunks for a single dataset.

    Returns a list of chunk dicts with keys: chunk_index, row_count,
    is_first, is_last, data (list of row dicts).
    """
    result: list[_LegacyStreamChunk] = run_coro_sync(
        _fetch_stream_for_dataset_async(
            connector_id=connector_id,
            dataset_id=dataset_id,
            connector_manifest=connector_manifest,
            connection_config=connection_config,
            registry=registry,
        )
    )
    return result


__all__ = [
    "run_batch_incremental",
    "run_record_mode",
    "run_replay_mode",
    "run_streaming_windowed",
]
