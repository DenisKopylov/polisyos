"""Cache run manifests and expose filtered/paginated runtime index views.

`RunIndexService` adapts persisted Core run directories into immutable
`IndexedRunRecord` snapshots and keeps a short-lived in-memory index for
`/runs` and dependent debug/lineage endpoints.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.contracts.runtime import CursorPage, RunDetails, RunSummary, SourceKind
from polisyos.scientist.decision_validity import DecisionValidityService

from .adapters.core_run import CoreRunAdapterResult, load_core_run


@dataclass(frozen=True)
class IndexedRunRecord:
    """Join a run manifest, API summary/details DTOs, and local file pointers."""
    run_id: str
    source_kind: SourceKind
    details: RunDetails
    summary: RunSummary
    run_dir: Path
    trace_path: Path | None
    workflow_report_ref: ArtifactRef | None
    experiment_state_ref: ArtifactRef | None
    decision_packet_ref: ArtifactRef | None
    manifest_errors: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _RunDirFingerprint:
    """Cheap change detector for one run directory."""

    trace_mtime_ns: int
    trace_size: int


class RunIndexService:
    """Provide TTL-refreshed run listings and artifact-to-tenant lookups.

    The index is rebuilt from `core_runs_root` on demand and cached for
    `refresh_ttl_seconds`. Invalid pagination cursors raise `ValueError`, and
    unknown run ids raise `KeyError`.
    """
    def __init__(
        self,
        *,
        store: ArtifactStore,
        core_runs_root: Path,
        refresh_ttl_seconds: float = 2.0,
        max_cached_runs: int = 10_000,
        metrics: Any | None = None,
    ) -> None:
        self._store = store
        self._core_runs_root = core_runs_root
        self._refresh_ttl_seconds = max(refresh_ttl_seconds, 0.1)
        self._max_cached_runs = max(int(max_cached_runs), 1)
        self._metrics = metrics
        self._decision_validity_service = DecisionValidityService(store)
        self._cache: dict[str, IndexedRunRecord] = {}
        self._artifact_tenants: dict[str, str] = {}
        self._dir_fingerprints: dict[Path, _RunDirFingerprint] = {}
        self._cache_built_at: float = 0.0

    @property
    def store(self) -> ArtifactStore:
        """Return the CAS store used by downstream services."""
        return self._store

    def refresh(self, *, force: bool = False) -> None:
        """Rebuild the cached index when TTL expired or `force=True`."""
        now = time.monotonic()
        if self._cache_built_at > 0.0:
            self._record_cache_staleness(now - self._cache_built_at)
        if not force and (now - self._cache_built_at) < self._refresh_ttl_seconds:
            self._record_cache_event(operation="refresh", outcome="cache_hit")
            return
        started = time.perf_counter()
        self._cache, self._artifact_tenants = self._refresh_index_incremental()
        self._cache_built_at = now
        self._record_cache_event(operation="refresh", outcome="incremental_rebuild")
        self._record_cache_rebuild(
            duration_seconds=time.perf_counter() - started,
            item_count=len(self._cache),
        )

    def list_runs(
        self,
        *,
        limit: int = 50,
        cursor: str | None = None,
        q: str | None = None,
        status: str | None = None,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        tenant_id: str | None = None,
    ) -> tuple[list[RunSummary], CursorPage]:
        """Return one cursor page of run summaries after applying filters.

        Args:
            limit: Requested page size; clamped to the `[1, 200]` API range.
            cursor: Integer offset encoded as a string, or `None` for the first
                page.
            q: Optional case-insensitive substring search applied to run id,
                status, and source kind before pagination.
            status: Optional case-insensitive run status filter.
            from_ts: Optional inclusive lower bound on `started_at`.
            to_ts: Optional inclusive upper bound on `started_at`.
            tenant_id: Optional tenant filter; runs without a tenant are omitted
                when this filter is set.

        Returns:
            A `(summaries, page)` tuple where `page.next_cursor` carries the next
            integer offset when more runs are available.

        Raises:
            ValueError: If `cursor` is not a non-negative integer string.
        """
        self.refresh()
        normalized_from = _as_utc(from_ts)
        normalized_to = _as_utc(to_ts)
        normalized_query = q.strip().lower() if isinstance(q, str) and q.strip() else None
        status_normalized = status.lower() if isinstance(status, str) else None

        runs: list[IndexedRunRecord] = []
        for run in self._cache.values():
            run_started = _as_utc(run.summary.started_at)
            if status_normalized and run.summary.status.lower() != status_normalized:
                continue
            if tenant_id:
                if run.summary.tenant_id:
                    if run.summary.tenant_id != tenant_id:
                        continue
                else:
                    continue
            if normalized_from and run_started and run_started < normalized_from:
                continue
            if normalized_to and run_started and run_started > normalized_to:
                continue
            if normalized_query:
                search_haystack = " ".join(
                    [
                        run.summary.run_id,
                        run.summary.status,
                        str(run.summary.source_kind),
                    ]
                ).lower()
                if normalized_query not in search_haystack:
                    continue
            runs.append(run)

        runs.sort(key=_run_sort_key)

        offset = _parse_cursor(cursor)
        page_limit = min(max(int(limit), 1), 200)
        page_items = runs[offset : offset + page_limit]
        next_cursor = None
        if offset + page_limit < len(runs):
            next_cursor = str(offset + page_limit)

        page = CursorPage(
            limit=page_limit,
            cursor=cursor,
            next_cursor=next_cursor,
            count=len(page_items),
            total=len(runs),
        )
        return [item.summary for item in page_items], page

    def get_run(self, run_id: str) -> IndexedRunRecord:
        """Return one indexed run snapshot.

        Raises:
            KeyError: If `run_id` is unknown after refreshing the cache.
        """
        self.refresh()
        record = self._cache.get(run_id)
        if record is None:
            self._record_cache_event(operation="lookup_run", outcome="miss")
            raise KeyError(run_id)
        self._record_cache_event(operation="lookup_run", outcome="hit")
        return record

    def get_artifact_tenant(self, artifact_id: str) -> str | None:
        """Return the tenant owning an artifact id when the run index can infer it."""
        self.refresh()
        tenant_id = self._artifact_tenants.get(artifact_id)
        self._record_cache_event(
            operation="lookup_artifact_tenant",
            outcome="hit" if tenant_id is not None else "miss",
        )
        return tenant_id

    def resolve_root_artifact_ids(
        self,
        run: IndexedRunRecord,
        *,
        requested_root_ids: list[str] | None = None,
    ) -> list[ArtifactID]:
        """Resolve lineage roots from explicit request ids or run manifest refs.

        If no request override is supplied, the method prefers
        `run.details.root_artifacts` and falls back to the decision packet ref.

        Raises:
            ValueError: If any supplied artifact id is malformed.
        """
        if requested_root_ids:
            return [ArtifactID.model_validate(value) for value in requested_root_ids]

        refs: list[ArtifactRef] = list(run.details.root_artifacts)
        if not refs and run.decision_packet_ref is not None:
            refs = [run.decision_packet_ref]

        return [ArtifactID.model_validate(str(ref.artifact_id)) for ref in refs]

    def _refresh_index_incremental(self) -> tuple[dict[str, IndexedRunRecord], dict[str, str]]:
        index: dict[str, IndexedRunRecord] = {}
        artifact_tenants: dict[str, str] = {}
        next_fingerprints: dict[Path, _RunDirFingerprint] = {}

        if self._core_runs_root.exists():
            for run_dir in sorted(_iter_run_dirs(self._core_runs_root)):
                if len(index) >= self._max_cached_runs:
                    self._record_cache_event(operation="refresh", outcome="capacity_eviction")
                    break
                fingerprint = _fingerprint_run_dir(run_dir)
                if fingerprint is None:
                    continue
                next_fingerprints[run_dir] = fingerprint
                cached = self._cache.get(run_dir.name)
                if (
                    cached is not None
                    and self._dir_fingerprints.get(run_dir) == fingerprint
                ):
                    record = cached
                    self._record_cache_event(operation="adapt_run", outcome="unchanged")
                else:
                    record = self._adapt_core_run(run_dir)
                    self._record_cache_event(
                        operation="adapt_run",
                        outcome="updated" if record is not None else "skipped",
                    )
                if record is None:
                    continue
                index[record.run_id] = record
                _register_artifact_tenants(artifact_tenants, record)

        self._dir_fingerprints = next_fingerprints
        return index, artifact_tenants

    def _adapt_core_run(self, run_dir: Path) -> IndexedRunRecord | None:
        result = load_core_run(store=self._store, run_dir=run_dir)
        if result is None:
            return None
        return _core_result_to_indexed(
            result,
            run_dir=run_dir,
            decision_validity_service=self._decision_validity_service,
        )

    def _record_cache_event(self, *, operation: str, outcome: str) -> None:
        recorder = getattr(self._metrics, "record_runtime_cache_event", None)
        if callable(recorder):
            recorder(
                cache_name="run_index",
                operation=operation,
                outcome=outcome,
            )

    def _record_cache_rebuild(self, *, duration_seconds: float, item_count: int) -> None:
        recorder = getattr(self._metrics, "record_runtime_cache_rebuild", None)
        if callable(recorder):
            recorder(
                cache_name="run_index",
                duration_seconds=duration_seconds,
                item_count=item_count,
            )

    def _record_cache_staleness(self, staleness_seconds: float) -> None:
        recorder = getattr(self._metrics, "set_runtime_cache_staleness", None)
        if callable(recorder):
            recorder(
                cache_name="run_index",
                staleness_seconds=staleness_seconds,
            )


def _core_result_to_indexed(
    result: CoreRunAdapterResult,
    *,
    run_dir: Path,
    decision_validity_service: DecisionValidityService,
) -> IndexedRunRecord:
    validity = None
    superseded_by_ref = None
    if result.decision_packet_ref is not None:
        evaluation, _ = decision_validity_service.get_evaluation(
            str(result.decision_packet_ref.artifact_id)
        )
        validity = evaluation
        if evaluation.superseded_by_ref:
            superseded_by_ref = ArtifactRef(
                artifact_id=evaluation.superseded_by_ref,
                kind=None,
                media_type=None,
            )
    details = RunDetails(
        run_id=result.run_id,
        source_kind="core_run",
        status=result.status,
        started_at=_as_utc(result.started_at),
        finished_at=_as_utc(result.finished_at),
        duration_ms=result.duration_ms,
        tenant_id=result.tenant_id,
        cell_id=result.cell_id,
        execution_profile=result.execution_profile,
        control_job_id=result.control_job_id,
        has_trace=True,
        manifest_ref=result.manifest_ref,
        trace_ref=result.trace_ref,
        capability_manifest_ref=result.capability_manifest_ref,
        root_artifacts=list(result.root_artifacts),
        has_workflow_report=result.workflow_report_ref is not None,
        workflow_report_ref=result.workflow_report_ref,
        warnings=list(result.warnings),
        decision_validity_status=(validity.status if validity is not None else None),
        decision_validity_checked_at=(validity.evaluated_at if validity is not None else None),
        decision_review_required=bool(validity.review_required) if validity is not None else False,
        decision_superseded_by_ref=superseded_by_ref,
    )
    summary = RunSummary(
        run_id=result.run_id,
        source_kind="core_run",
        status=result.status,
        started_at=details.started_at,
        finished_at=details.finished_at,
        duration_ms=details.duration_ms,
        tenant_id=details.tenant_id,
        cell_id=details.cell_id,
        execution_profile=details.execution_profile,
        control_job_id=details.control_job_id,
        has_trace=True,
        root_artifact_count=len(result.root_artifacts),
        has_workflow_report=result.workflow_report_ref is not None,
        warnings=list(result.warnings),
        decision_validity_status=(validity.status if validity is not None else None),
        decision_validity_checked_at=(validity.evaluated_at if validity is not None else None),
        decision_review_required=bool(validity.review_required) if validity is not None else False,
        decision_superseded_by_ref=superseded_by_ref,
    )
    return IndexedRunRecord(
        run_id=result.run_id,
        source_kind="core_run",
        details=details,
        summary=summary,
        run_dir=run_dir,
        trace_path=result.trace_path,
        workflow_report_ref=result.workflow_report_ref,
        experiment_state_ref=result.experiment_state_ref,
        decision_packet_ref=result.decision_packet_ref,
        manifest_errors=result.errors,
    )


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except (TypeError, ValueError) as exc:
        raise ValueError("cursor must be an integer offset") from exc
    if value < 0:
        raise ValueError("cursor must be non-negative")
    return value


def _iter_run_dirs(root: Path):
    for item in root.iterdir():
        if item.is_dir():
            yield item


def _fingerprint_run_dir(run_dir: Path) -> _RunDirFingerprint | None:
    trace_path = run_dir / "trace.jsonl"
    try:
        stat = trace_path.stat()
    except FileNotFoundError:
        return None
    return _RunDirFingerprint(
        trace_mtime_ns=int(stat.st_mtime_ns),
        trace_size=int(stat.st_size),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _run_sort_key(record: IndexedRunRecord) -> tuple[float, str]:
    started = _as_utc(record.summary.started_at)
    if started is None:
        return (float("inf"), record.run_id)
    return (-started.timestamp(), record.run_id)


def _register_artifact_tenants(
    mapping: dict[str, str],
    record: IndexedRunRecord,
) -> None:
    tenant_id = record.details.tenant_id
    if not tenant_id:
        return

    refs: list[ArtifactRef] = list(record.details.root_artifacts)
    if record.details.manifest_ref is not None:
        refs.append(record.details.manifest_ref)
    if record.details.trace_ref is not None:
        refs.append(record.details.trace_ref)
    if record.details.capability_manifest_ref is not None:
        refs.append(record.details.capability_manifest_ref)
    if record.workflow_report_ref is not None:
        refs.append(record.workflow_report_ref)
    if record.experiment_state_ref is not None:
        refs.append(record.experiment_state_ref)
    if record.decision_packet_ref is not None:
        refs.append(record.decision_packet_ref)

    for ref in refs:
        mapping.setdefault(str(ref.artifact_id), tenant_id)
