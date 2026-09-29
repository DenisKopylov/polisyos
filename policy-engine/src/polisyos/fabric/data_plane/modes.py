"""Execution mode dispatch for data ingestion.

Provides:
- batch_incremental: cursor-based incremental ingestion
- record_mode: run ingestion while capturing HTTP responses to CAS
- replay_mode: run ingestion from captured HTTP responses (no network)
- streaming_windowed: per-chunk CAS persistence via fetch_stream()
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_blocking_async, run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.contracts.cursor import CursorState, WatermarkType, WindowStrategy
from polisyos.fabric.data_plane.quarantine import (
    QuarantineRecord,
    persist_quarantine_record,
)
from polisyos.ir.connectors import ConnectorCapability, DataVersion, FetchRequest, VersionStrategy

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.fabric.connectors.contracts import DataSchema
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.streaming import StreamSchemaBinding
    from polisyos.fabric.ingestion import IngestionDependencies
    from polisyos.fabric.storage.tenant_cas import TenantSidecarScope

logger = get_logger(__name__)


class RecordModeCaptureError(RuntimeError):
    """Raised when recorded ingestion fails without retrying through a live path."""


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


def _resolve_mode_sidecar_scope(
    cas_root: Path,
    sidecar_scope: TenantSidecarScope | None,
) -> TenantSidecarScope:
    """Resolve tenant-local sidecar paths as invocation context, not provider state."""
    from polisyos.fabric.ingestion.ingestion_providers import resolve_ingestion_sidecar_scope

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
    manifest_payload: dict[str, Any],
    source_refs: list[Any],
) -> Any:
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
    snapshot_payload: dict[str, Any],
    manifest_ref: Any,
    evidence_ref: Any,
) -> Any:
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


def _non_finite_fields(row: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for key, value in row.items():
        if isinstance(value, bool) or value is None or not isinstance(value, (int, float)):
            continue
        numeric = float(value)
        if math.isinf(numeric) or (math.isnan(numeric) and _looks_metric_field(str(key))):
            fields.append(str(key))
    return fields


class _CursorAwareConnector:
    """Add one stored incremental version at the connector request boundary."""

    def __init__(
        self,
        connector: Any,
        connector_id: str,
        cursor_versions: dict[tuple[str, str], DataVersion],
    ) -> None:
        self._connector = connector
        self._connector_id = connector_id
        self._cursor_versions = cursor_versions

    def fetch(self, handle: Any, request: Any) -> Any:
        """Fetch with the stored version when the request has no cursor."""
        if isinstance(request, FetchRequest) and request.incremental_since is None:
            version = self._cursor_versions.get((self._connector_id, request.dataset_id))
            if version is not None:
                request = replace(request, incremental_since=version)
        return self._connector.fetch(handle, request)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connector, name)


class _CursorAwareRegistry:
    """Delegate registry operations while wrapping fetched connectors."""

    def __init__(
        self,
        registry: Any,
        cursor_versions: dict[tuple[str, str], DataVersion],
    ) -> None:
        self._registry = registry
        self._cursor_versions = cursor_versions

    def get(self, connector_id: str, *args: Any, **kwargs: Any) -> Any:
        """Resolve and wrap one connector from the underlying registry."""
        connector = self._registry.get(connector_id, *args, **kwargs)
        return _CursorAwareConnector(
            connector,
            str(connector_id),
            self._cursor_versions,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._registry, name)


def _connector_supports_incremental(connector: Any) -> bool:
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


def _strategy_value_is_valid(strategy: VersionStrategy, value: str) -> bool:
    """Validate the strategy-specific syntax of a persisted version value."""
    normalized = value.strip()
    if not normalized:
        return False
    if strategy is VersionStrategy.TIMESTAMP:
        return _parse_timestamp_value(normalized) is not None
    if strategy is VersionStrategy.REVISION:
        return normalized.isdigit()
    return True


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


def _admit_incremental_version(
    *,
    connector: Any,
    strategy: VersionStrategy,
    value: str,
    timestamp: datetime,
) -> DataVersion | None:
    """Admit one source version only when capability and value contracts hold."""
    if not _connector_supports_incremental(connector):
        return None
    normalized = value.strip()
    if not _strategy_value_is_valid(strategy, normalized):
        return None
    try:
        return DataVersion(
            strategy=strategy,
            value=normalized,
            timestamp=timestamp,
        )
    except (TypeError, ValueError):
        return None


def _cursor_version(cursor: CursorState, connector: Any) -> DataVersion | None:
    """Reject legacy timestamp cursors until provenance/epoch is contract-bound."""
    strategy = _VERSION_STRATEGY_BY_WATERMARK.get(cursor.watermark_type)
    if strategy is None:
        return None
    if strategy is VersionStrategy.TIMESTAMP:
        # CursorState has no independently admitted source-provenance/epoch
        # field.  Its created_at and watermark_value are not authority for a
        # subsequent incremental request, so remain in full/candidate mode.
        return None
    return _admit_incremental_version(
        connector=connector,
        strategy=strategy,
        value=cursor.watermark_value,
        timestamp=cursor.created_at,
    )


def _cursor_aware_dependencies(
    dependencies: IngestionDependencies,
    cursor_versions: dict[tuple[str, str], DataVersion],
) -> IngestionDependencies:
    """Build ingestion dependencies whose registry injects supported cursors."""
    return replace(
        dependencies,
        registry=_CursorAwareRegistry(dependencies.registry, cursor_versions),
    )


def _resolve_dataset_connectors(
    dependencies: IngestionDependencies | None,
    datasets: list[tuple[str, str]],
) -> dict[tuple[str, str], Any]:
    """Resolve connector instances used by cursor capability admission."""
    if dependencies is None:
        return {}
    resolved: dict[tuple[str, str], Any] = {}
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


def _cursor_result_ref(value: Any) -> str | None:
    """Return an artifact id from a fetch or aggregate evidence reference."""
    artifact_id = getattr(value, "artifact_id", None)
    return str(artifact_id) if artifact_id is not None else None


def _complete_source_boundary(
    fetch_result: Any,
    watermark_type: WatermarkType,
) -> tuple[VersionStrategy, str, datetime] | None:
    """Return a source-backed complete boundary, never a local fetch time."""
    if bool(getattr(fetch_result, "has_more", False)):
        return None
    if getattr(fetch_result, "next_page_token", None) is not None:
        return None

    completeness = getattr(fetch_result, "completeness", None)
    if completeness is not None:
        try:
            coverage = float(completeness)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(coverage) or coverage != 1.0:
            return None
    if getattr(fetch_result, "is_complete", True) is False:
        return None

    strategy = _VERSION_STRATEGY_BY_WATERMARK.get(watermark_type)
    if strategy is None:
        return None
    if strategy is VersionStrategy.TIMESTAMP:
        source_updated_at = getattr(fetch_result, "source_updated_at", None)
        if not (
            isinstance(source_updated_at, datetime)
            and source_updated_at.tzinfo is not None
            and source_updated_at.utcoffset() is not None
        ):
            return None
        source_timestamp = source_updated_at
        version = getattr(fetch_result, "version", None)
        if getattr(version, "strategy", None) is not VersionStrategy.TIMESTAMP:
            return None
        version_value = getattr(version, "value", None)
        version_timestamp = getattr(version, "timestamp", None)
        if not isinstance(version_value, str) or not isinstance(
            version_timestamp, datetime
        ):
            return None
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
        return strategy, source_timestamp.isoformat(), source_timestamp

    version = getattr(fetch_result, "version", None)
    if getattr(version, "strategy", None) is not strategy:
        return None
    value = getattr(version, "value", None)
    timestamp = getattr(version, "timestamp", None)
    if not isinstance(value, str) or not isinstance(timestamp, datetime):
        return None
    return strategy, value, timestamp


def _save_confirmed_cursors(
    *,
    cursor_store: CursorStore,
    connectors: dict[tuple[str, str], Any],
    datasets: list[tuple[str, str]],
    confirmed_results: dict[tuple[str, str], Any],
    result: Any,
) -> None:
    """Keep cursor promotion fail-closed until evidence binding is available.

    The current lease has no verifier that resolves an evidence reference and
    binds its contents to the confirmed dataset and ingestion run.  CAS
    integrity or reference presence is not semantic evidence, so neither
    absent nor non-None references authorize a cursor write here.  The
    evidence-contract owner must supply that bridge before this boundary can
    be reopened.
    """
    del cursor_store, connectors, datasets, confirmed_results
    if getattr(result, "evidence_bundle_ref", None) is None:
        return
    return


def run_batch_incremental(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> Any:
    """Run ingestion in batch_incremental mode.

    1. For each dataset, look up latest cursor via CursorStore.
    2. Build incremental_cursors dict mapping dataset_id → cursor watermark.
    3. Delegate to run_connectors_ingestion with incremental hints.
    4. Extract watermarks from results and save new cursors.
    5. Return IngestionResult with cursor_ref.
    """
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion

    effective_input_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    store = _resolve_mode_store(
        Path(cas_root), effective_input_dependencies, sidecar_scope=invocation_scope
    )
    cursor_store = CursorStore(store, index_root=invocation_scope.cursor_index_root)

    datasets = _extract_datasets(connector_manifest)
    dataset_connectors = _resolve_dataset_connectors(effective_input_dependencies, datasets)
    cursor_versions: dict[tuple[str, str], DataVersion] = {}
    for connector_id, dataset_id in datasets:
        cursor = cursor_store.find_latest_cursor(connector_id, dataset_id)
        if cursor is not None:
            version = _cursor_version(
                cursor,
                dataset_connectors.get((connector_id, dataset_id)),
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

    confirmed_results: dict[tuple[str, str], Any] = {}

    def _capture_result(
        connector_id: str,
        dataset_id: str,
        request: Any,
        fetch_result: Any,
    ) -> None:
        del request
        confirmed_results[(str(connector_id), str(dataset_id))] = fetch_result

    effective_dependencies = (
        _cursor_aware_dependencies(effective_input_dependencies, cursor_versions)
        if cursor_versions
        else effective_input_dependencies
    )

    # Run normal orchestrated ingestion
    result = run_orchestrated_ingestion(
        connector_manifest=connector_manifest,
        source=source,
        license_name=license_name,
        cas_root=cas_root,
        connection_config=connection_config,
        produce_snapshot=produce_snapshot,
        ingestion_dependencies=effective_dependencies,
        sidecar_scope=invocation_scope,
        raw_result_sink=_capture_result,
    )

    _save_confirmed_cursors(
        cursor_store=cursor_store,
        connectors=dataset_connectors,
        datasets=datasets,
        confirmed_results=confirmed_results,
        result=result,
    )

    return result


# ---------------------------------------------------------------------------
# Record mode
# ---------------------------------------------------------------------------


def run_record_mode(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> tuple[Any, str]:
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

    effective_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    session_id = uuid.uuid4().hex

    # Extract connector/dataset info for the session metadata
    datasets = _extract_datasets(connector_manifest)
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
        async def _record_ingestion() -> Any:
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
        from polisyos.fabric.data_plane.orchestrator import IngestionResult

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
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    replay_ref: str,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> Any:
    """Run ingestion using recorded HTTP responses (no network).

    1. Load RecordSession from CAS via replay_ref.
    2. Write fixtures to temp dir via ReplayStore.build_replay_fixture_dir().
    3. Run ingestion — APISimulator in REPLAY mode serves cached responses.
    4. Return IngestionResult.
    """
    import tempfile

    from polisyos.core.artifacts.manifest import ArtifactID
    from polisyos.fabric.data_plane.replay_store import ReplayStore

    effective_dependencies = _resolve_ingestion_dependencies(ingestion_dependencies)
    invocation_scope = _resolve_mode_sidecar_scope(Path(cas_root), sidecar_scope)
    store = _resolve_mode_store(
        Path(cas_root), effective_dependencies, sidecar_scope=invocation_scope
    )
    replay_store = ReplayStore(store)

    # Load session from CAS
    artifact_id = ArtifactID.model_validate(replay_ref)
    session = replay_store.load_record_session(artifact_id)

    with tempfile.TemporaryDirectory(prefix="polisyos_replay_") as tmpdir:
        fixture_dir = Path(tmpdir)
        replay_store.build_replay_fixture_dir(session, fixture_dir)

        # Patch aiohttp to serve from fixtures
        from polisyos.fabric.connectors.testing.simulator import (
            APISimulator,
            SimulatorMode,
        )

        datasets = _extract_datasets(connector_manifest)
        first_connector_id = datasets[0][0] if datasets else "unknown"
        first_dataset_id = datasets[0][1] if datasets else "unknown"

        simulator = APISimulator(
            mode=SimulatorMode.REPLAY,
            fixture_root=fixture_dir,
            connector_id=first_connector_id,
            dataset_id=first_dataset_id,
        )

        async def _replay_ingestion() -> Any:
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

        from polisyos.fabric.data_plane.orchestrator import IngestionResult

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
    rows: Any,
    *,
    connector_id: str,
    dataset_id: str,
    store: Any,
    chunk_index: int,
    schema: DataSchema | None = None,
    schema_binding: StreamSchemaBinding | None = None,
) -> tuple[list[dict[str, Any]], list[str], int]:
    if not isinstance(rows, list):
        rows = [rows]

    valid_rows: list[dict[str, Any]] = []
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
        context: dict[str, Any] = {
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
) -> Callable[..., tuple[list[dict[str, Any]], list[str], int]]:
    """Bind one admitted schema without changing custom sanitizer call shape."""
    schema = getattr(schema_binding, "schema", None)

    def _bound(
        rows: object,
        **kwargs: object,
    ) -> tuple[list[dict[str, Any]], list[str], int]:
        return _sanitize_stream_rows(
            rows,
            schema=schema,
            schema_binding=schema_binding,
            **kwargs,
        )

    return _bound


def run_streaming_windowed(
    *,
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> Any:
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
    connector_manifest: Any,
    source: str,
    license_name: str,
    cas_root: Path,
    connection_config: Any | None = None,
    produce_snapshot: bool = True,
    ingestion_dependencies: IngestionDependencies | None = None,
    sidecar_scope: TenantSidecarScope | None = None,
) -> Any:
    """Run ingestion in streaming_windowed mode.

    This mode uses an event-driven runtime with:
    - resumable stream checkpoints;
    - bounded window accumulators (tumbling/sliding/session/count);
    - duplicate replay suppression;
    - per-record quarantine for poison messages;
    - CDC schema-change artifacts when stream schema drifts.
    """
    from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
    from polisyos.fabric.data_plane.cursor_store import CursorStore
    from polisyos.fabric.data_plane.orchestrator import IngestionResult
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
    datasets = _extract_datasets(connector_manifest)
    connector_registry = ingestion_dependencies.registry

    source_refs: list[Any] = []
    warnings: list[str] = []
    total_chunks = 0
    total_rows = 0
    total_windows = 0
    total_cdc_events = 0
    total_quarantined = 0
    cursor_ref: str | None = None

    for ds_connector_id, ds_dataset_id in datasets:
        runtime_options = _stream_runtime_options_from_manifest(
            connector_manifest,
            dataset_id=ds_dataset_id,
        )
        schema_binding = _resolve_stream_schema_binding(
            connector_registry,
            connector_id=ds_connector_id,
            dataset_id=ds_dataset_id,
        )
        bound_sanitizer = _bind_stream_sanitizer(schema_binding)
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
            )
        else:
            dataset_result = await _run_legacy_stream_dataset_from_fetch_async(
                store=store,
                connector_id=ds_connector_id,
                dataset_id=ds_dataset_id,
                connector_manifest=connector_manifest,
                connection_config=connection_config,
                registry=connector_registry,
                schema_binding=schema_binding,
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
    connector_manifest: Any,
    *,
    dataset_id: str | None = None,
) -> Any:
    from polisyos.fabric.data_plane.streaming import StreamRuntimeOptions
    from polisyos.fabric.data_plane.watermark import WindowPolicy

    raw_streaming: dict[str, Any] = {}
    if isinstance(connector_manifest, dict):
        raw_streaming = dict(connector_manifest.get("streaming", {}) or {})
    else:
        value = getattr(connector_manifest, "streaming", None)
        if isinstance(value, dict):
            raw_streaming = dict(value)

    raw_window = dict(raw_streaming.get("window", {}) or {})
    if not raw_window and isinstance(connector_manifest, dict):
        raw_window = dict(connector_manifest.get("streaming_window", {}) or {})

    strategy_raw = str(raw_window.get("strategy", "tumbling")).strip().lower()
    try:
        strategy = WindowStrategy(strategy_raw)
    except ValueError:
        strategy = WindowStrategy.TUMBLING

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

    return StreamRuntimeOptions(
        partition_key=partition_key,
        batch_size=int(raw_streaming.get("batch_size", 1_000)),
        checkpoint_every_chunks=int(raw_streaming.get("checkpoint_every_chunks", 1)),
        dedupe_key_fields=tuple(
            raw_streaming.get("dedupe_key_fields", ("_message_id", "message_id", "id"))
        ),
        max_dedupe_keys=int(raw_streaming.get("max_dedupe_keys", 4_096)),
        max_buffered_rows=int(raw_streaming.get("max_buffered_rows", 10_000)),
        max_buffered_bytes=int(raw_streaming.get("max_buffered_bytes", 16 * 1024 * 1024)),
        pause_seconds=float(raw_streaming.get("pause_seconds", 0.01)),
        window_policy=window_policy,
    )


def _connector_is_registered(
    connector_id: str,
    *,
    registry: Any | None = None,
) -> bool:
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        resolved_registry.get_entry(connector_id)
        return True
    except Exception:
        return False


def _run_legacy_stream_dataset(
    *,
    store: Any,
    connector_id: str,
    dataset_id: str,
    chunks: list[dict[str, Any]],
    schema_binding: StreamSchemaBinding | None = None,
) -> Any:
    from types import SimpleNamespace

    from polisyos.fabric.connectors.types import DataChunk
    from polisyos.fabric.data_plane.streaming import persist_stream_chunk

    chunk_refs = []
    warnings: list[str] = []
    rows_emitted = 0
    quarantined_rows = 0

    for chunk_data in chunks:
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
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
                    chunk_index=int(chunk_data.get("chunk_index", 0)),
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

    return SimpleNamespace(
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
    store: Any,
    connector_id: str,
    dataset_id: str,
    chunks: list[dict[str, Any]],
    schema_binding: StreamSchemaBinding | None = None,
) -> Any:
    from types import SimpleNamespace

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
        clean_rows, chunk_warnings, chunk_quarantined = _sanitize_stream_rows(
            chunk_data.get("data", []),
            connector_id=connector_id,
            dataset_id=dataset_id,
            store=store,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
            schema=getattr(schema_binding, "schema", None),
            schema_binding=schema_binding,
        )
        warnings.extend(chunk_warnings)
        quarantined_rows += chunk_quarantined
        rows_emitted += len(clean_rows)
        chunk = DataChunk(
            data=clean_rows,
            chunk_index=int(chunk_data.get("chunk_index", 0)),
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

    return SimpleNamespace(
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
    store: Any,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
    schema_binding: StreamSchemaBinding | None = None,
) -> Any:
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


def _extract_datasets(connector_manifest: Any) -> list[tuple[str, str]]:
    """Extract (connector_id, dataset_id) pairs from a manifest."""
    datasets: list[tuple[str, str]] = []
    raw: Any = []
    if hasattr(connector_manifest, "datasets"):
        raw = connector_manifest.datasets
    elif isinstance(connector_manifest, dict):
        raw = connector_manifest.get("datasets", [])

    for ds in raw:
        if isinstance(ds, dict):
            connector_id = ds.get("connector_id", "")
            dataset_id = ds.get("dataset_id", "")
        else:
            connector_id = getattr(ds, "connector_id", "")
            dataset_id = getattr(ds, "dataset_id", "")
        connector_id = str(connector_id or "")
        dataset_id = str(dataset_id or "")
        if connector_id and dataset_id:
            datasets.append((connector_id, dataset_id))
    return datasets


def _resolve_connector_registry(
    *,
    registry: Any | None = None,
) -> Any:
    if registry is not None:
        return registry
    return _default_connector_registry()


def _default_connector_registry() -> Any:
    from polisyos.fabric.connectors.registry import ConnectorRegistry

    return ConnectorRegistry.get_instance()


async def _fetch_stream_for_dataset_async(
    *,
    connector_id: str,
    dataset_id: str,
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch stream chunks for a single dataset without nesting a sync bridge."""
    del connector_manifest
    try:
        resolved_registry = _resolve_connector_registry(registry=registry)
        entry = cast("Any", resolved_registry.get_entry(connector_id))
        if entry is None:
            logger.warning("streaming_windowed: connector %s not found", connector_id)
            return []

        connector_cls = entry.connector_cls
        connector = connector_cls()

        from polisyos.fabric.connectors.capabilities import ConnectorCapability

        capabilities = cast("Any", entry.metadata.capabilities)
        if not (capabilities & ConnectorCapability.STREAMING):
            logger.info(
                "streaming_windowed: connector %s doesn't support streaming, "
                "falling back to single-chunk fetch",
                connector_id,
            )
            return []

        handle = await connector.connect(connection_config)
        try:
            from polisyos.ir.connectors import FetchRequest

            request = FetchRequest(dataset_id=dataset_id)
            chunks: list[dict[str, Any]] = []
            async for chunk in connector.fetch_stream(handle, request):
                data = chunk.data
                rows: list[Any] = []
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
            await connector.disconnect(handle)
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
    connector_manifest: Any,
    connection_config: Any | None,
    registry: Any | None = None,
) -> list[dict[str, Any]]:
    """Fetch stream chunks for a single dataset.

    Returns a list of chunk dicts with keys: chunk_index, row_count,
    is_first, is_last, data (list of row dicts).
    """
    result: list[dict[str, Any]] = run_coro_sync(
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
