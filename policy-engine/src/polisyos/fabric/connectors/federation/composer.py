"""
Data composer for multi-source federation.

Implements UNION, JOIN, OVERLAY, and CONSENSUS strategies for combining
existing data from multiple sources with deterministic behavior.
"""

from __future__ import annotations

import heapq
import json
import threading
import weakref
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.canon import content_hash
from polisyos.core.observability import PolicyOSTracer
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.connectors.federation.profile import (
    MAX_FILE_BYTES,
    MAX_GRAPH_CELLS,
    MAX_ROWS,
    MAX_SOURCES,
    MAX_TOTAL_BYTES,
    admit_frame,
    admit_key_index,
    admit_output_envelope,
    admit_shape,
    align_scalar_series,
    bounded_encode,
    cast_series_losslessly,
    encode_scalar,
    frame_digest,
    scalar_frame,
    scalar_rows,
)
from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    ConflictResolutionError,
    FederationBasisStatus,
    FederationError,
    MergeLogEntry,
    MergeLogSummary,
    SchemaIncompatibilityError,
    SourceMetadata,
)
from polisyos.fabric.numerics.finite import is_finite_number
from polisyos.ir.connectors import ConnectorMetadataSpec

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from polisyos.core.observability import PolicyOSTracer
    from polisyos.fabric.connectors.federation.resolver import ConflictResolver


logger = get_logger(__name__)


@dataclass(frozen=True)
class _CellSource:
    token: str
    declaration: str

    def metadata(self) -> SourceMetadata:
        return _restore_source_declaration(json.loads(self.declaration))


type _LineageMap = dict[str, tuple[_CellSource, ...]]

# Values are immutable bytes, and weak references release receipts with their
# exact owner-produced carrier. Dataframe attrs never admit their own basis.
_OWNED_BASIS: dict[int, tuple[weakref.ReferenceType[pd.DataFrame], str, bytes]] = {}

_LINEAGE_ATTR = "policyos_federation_lineage_v1"


@contextmanager
def _noop_span() -> Iterator[None]:
    yield None


def _default_tracer() -> PolicyOSTracer | None:
    try:
        from polisyos.core.observability import get_tracer

        return get_tracer()
    except Exception:
        return None


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _fresh_internal_name(columns: Iterable[Any], prefix: str) -> str:
    """Return a temporary column name that cannot shadow user data."""
    occupied = set(columns)
    candidate = prefix
    suffix = 0
    while candidate in occupied:
        suffix += 1
        candidate = f"{prefix}_{suffix}"
    return candidate


def _is_missing_scalar(value: object) -> bool:
    """Return whether a scalar value is a pandas missing value."""
    if not pd.api.types.is_scalar(value):
        return False
    try:
        return bool(pd.Series([value], dtype=object).isna().iat[0])
    except TypeError, ValueError:
        return False


def _lineage_map(value: object) -> _LineageMap:
    """Copy an internal relation; only owner-produced immutable origins qualify."""
    if value is None or _is_missing_scalar(value):
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(key, str)
        and isinstance(origins, tuple)
        and all(isinstance(origin, _CellSource) for origin in origins)
        for key, origins in value.items()
    ):
        raise FederationError("Invalid internal federation cell basis")
    return dict(value)


def _frame_content_id(frame: pd.DataFrame) -> str:
    return frame_digest(frame)


def _source_declaration(metadata: SourceMetadata) -> dict[str, Any]:
    """Serialize caller-declared source metadata without implying verification."""
    return {
        "connector_id": metadata.connector_id,
        "metadata": metadata.metadata.model_dump(mode="json"),
        "fetched_at": metadata.fetched_at.isoformat(),
        "row_count": metadata.row_count,
        "last_updated": metadata.last_updated.isoformat() if metadata.last_updated else None,
        "observed_latency_ms": metadata.observed_latency_ms,
    }


def _input_lineage(
    frame: pd.DataFrame, metadata: SourceMetadata, position: int
) -> list[_LineageMap]:
    """Resolve owned derived cells or admit one exact declared leaf occurrence."""
    owned = _read_persisted_lineage(frame)
    if owned is not None:
        return owned
    origin = _leaf_origin(frame, metadata, position)
    return [
        {
            column: (origin,)
            for column, value in zip(frame.columns, row, strict=True)
            if not _is_missing_scalar(value)
        }
        for row in frame.itertuples(False, None)
    ]


def _leaf_origin(frame: pd.DataFrame, metadata: SourceMetadata, position: int) -> _CellSource:
    declaration = bounded_encode(_source_declaration(metadata)).decode()
    # Exact supported content and selected occurrence distinguish duplicate
    # declarations and duplicate identical payloads without inventing issuers.
    import hashlib

    digest = hashlib.sha256(
        bounded_encode([frame_digest(frame), declaration, position])
    ).hexdigest()
    return _CellSource(f"{metadata.connector_id}@{digest}", declaration)


def _restore_source_declaration(value: dict[str, Any]) -> SourceMetadata:
    """Restore source declarations carried by the content-bound lineage sidecar."""
    return SourceMetadata(
        connector_id=str(value["connector_id"]),
        metadata=ConnectorMetadataSpec.model_validate(value["metadata"]),
        fetched_at=datetime.fromisoformat(str(value["fetched_at"])),
        row_count=int(value["row_count"]),
        last_updated=(
            datetime.fromisoformat(str(value["last_updated"]))
            if value.get("last_updated")
            else None
        ),
        observed_latency_ms=value.get("observed_latency_ms"),
    )


def _read_persisted_lineage(frame: pd.DataFrame) -> list[_LineageMap] | None:
    """Resolve an exact owner-held basis; a checksum over attrs is not custody."""
    owned = _OWNED_BASIS.get(id(frame))
    if owned is None or owned[0]() is not frame:
        if _LINEAGE_ATTR in frame.attrs:
            raise FederationError("Unverified lineage attrs require a selected parent")
        return None
    if owned[1] != frame_digest(frame):
        raise FederationError("Owned federation carrier changed after production")
    artifact = json.loads(owned[2])
    if _LINEAGE_ATTR in frame.attrs and bounded_encode(frame.attrs[_LINEAGE_ATTR]) != owned[2]:
        raise FederationError("Owned federation lineage projection changed")
    declarations = artifact["source_declarations"]
    origins = {
        token: _CellSource(token, bounded_encode(value).decode())
        for token, value in declarations.items()
    }
    return [
        {
            column: tuple(
                origins[token] for token in ([tokens] if isinstance(tokens, str) else tokens)
            )
            for column, tokens in row.items()
        }
        for row in artifact["rows"]
    ]


def _attach_persisted_lineage(
    frame: pd.DataFrame,
    lineage: list[_LineageMap],
    all_declarations: dict[str, dict[str, Any]] | None = None,
    basis_status: FederationBasisStatus | None = None,
) -> None:
    """Publish a bounded projection while retaining a separate immutable owner basis."""
    if len(lineage) != len(frame):
        raise FederationError("Incomplete federation cell relation")
    declarations: dict[str, dict[str, Any]] = dict(all_declarations or {})
    rows: list[dict[str, Any]] = []
    relation_bytes = 0
    for row in lineage:
        encoded = {}
        for column, origins in row.items():
            if not origins:
                continue
            tokens = []
            for origin in origins:
                declarations.setdefault(origin.token, json.loads(origin.declaration))
                tokens.append(origin.token)
            encoded[column] = tokens[0] if len(tokens) == 1 else tokens
        relation_bytes += len(bounded_encode(encoded)) + 1
        if relation_bytes > MAX_FILE_BYTES // 2:
            raise FederationError("Federation cell relation exceeds engineering byte profile")
        rows.append(encoded)
    artifact = {
        "version": 2,
        "content_id": frame_digest(frame),
        "source_identity": "exact_selected_occurrence_consumer_declared_issuer",
        "source_declarations": declarations,
        "basis_status": asdict(basis_status or FederationBasisStatus()),
        "rows": rows,
    }
    payload = bounded_encode(artifact, MAX_FILE_BYTES // 2)
    identity = id(frame)
    ref = weakref.ref(frame, lambda _ref: _OWNED_BASIS.pop(identity, None))
    _OWNED_BASIS[identity] = (ref, artifact["content_id"], payload)
    frame.attrs[_LINEAGE_ATTR] = json.loads(payload)


def _selected_parent_carrier(frame: pd.DataFrame, digest: str, position: int) -> pd.DataFrame:
    """Namespace a real verified parent by this selected graph edge occurrence."""
    import hashlib

    basis = _read_persisted_lineage(frame)
    if basis is None:
        raise FederationError("Selected parent has no owned recomputed basis")
    receipt = json.loads(_OWNED_BASIS[id(frame)][2])
    rebased = {}
    declarations = {}
    for token, declaration in receipt["source_declarations"].items():
        suffix = hashlib.sha256(bounded_encode([digest, position, token])).hexdigest()
        connector = declaration["connector_id"]
        rebased[token] = _CellSource(f"{connector}@{suffix}", bounded_encode(declaration).decode())
        declarations[rebased[token].token] = declaration
    copied = frame.copy(deep=True)
    lineage = [
        {
            column: tuple(rebased[origin.token] for origin in origins)
            for column, origins in row.items()
        }
        for row in basis
    ]
    _attach_persisted_lineage(
        copied, lineage, declarations, FederationBasisStatus(selected_bytes="recomputed")
    )
    return copied


def _mark_selected_bytes(frame: pd.DataFrame) -> FederationBasisStatus:
    """Mark reopened bytes recomputed while preserving unknown leaf-history limits."""
    lineage = _read_persisted_lineage(frame)
    if lineage is None:
        raise FederationError("Selected result has no owned derivation basis")
    declarations = json.loads(_OWNED_BASIS[id(frame)][2])["source_declarations"]
    status = FederationBasisStatus(selected_bytes="recomputed")
    _attach_persisted_lineage(frame, lineage, declarations, status)
    return status


def _origins_metadata(origins: tuple[_CellSource, ...]) -> SourceMetadata | None:
    if not origins:
        return None
    if len(origins) != 1:
        raise FederationError(
            "Aggregate cell cannot be ranked as a single declared leaf; "
            "selected aggregate limitation"
        )
    return origins[0].metadata()


class MergeLogCollector:
    """Collects merge log entries with optional sampling and summaries."""

    def __init__(
        self,
        audit_level: AuditLevel,
        sample_size: int,
        max_entries: int,
        seed: str | None,
    ) -> None:
        self.audit_level = audit_level
        self.sample_size = max(0, sample_size)
        self.max_entries = max(0, max_entries)
        self.seed = seed or ""
        self.entries: list[MergeLogEntry] = []
        self.summary = MergeLogSummary(sample_seed=self.seed)
        self._sample_heap: list[tuple[int, int, MergeLogEntry]] = []
        self._sample_sequence = 0
        self._dropped_entries = 0

    def record(self, entry: MergeLogEntry) -> None:
        if self.audit_level == AuditLevel.NONE:
            return

        self.summary.total_conflicts += 1
        self._inc(self.summary.by_policy, entry.resolution_policy or "unknown")
        self._inc(self.summary.by_conflict_type, entry.conflict_type or "unknown")
        self._inc(self.summary.by_column, entry.column or "<row>")
        pair_key = f"{entry.source_a_id}->{entry.source_b_id}"
        self._inc(self.summary.by_source_pair, pair_key)

        if self.audit_level == AuditLevel.FULL:
            if self.max_entries == 0 or len(self.entries) < self.max_entries:
                self.entries.append(entry)
            else:
                self._dropped_entries += 1
        elif self.audit_level == AuditLevel.SUMMARY and self.sample_size > 0:
            self._sample(entry)

    def _sample(self, entry: MergeLogEntry) -> None:
        hash_value = self._stable_hash(entry)
        sequence = self._sample_sequence
        self._sample_sequence += 1
        if len(self._sample_heap) < self.sample_size:
            heapq.heappush(self._sample_heap, (-hash_value, -sequence, entry))
            return

        current_max = -self._sample_heap[0][0]
        if hash_value < current_max:
            heapq.heapreplace(self._sample_heap, (-hash_value, -sequence, entry))

    def finalize(self) -> None:
        self.summary.extra["audit_entries_retained"] = len(self.entries)
        self.summary.extra["audit_entries_dropped"] = self._dropped_entries
        self.summary.extra["audit_entries_truncated"] = self._dropped_entries > 0
        if self.audit_level != AuditLevel.SUMMARY or self.sample_size == 0:
            return
        samples = sorted(
            [(-hash_value, -sequence, entry) for hash_value, sequence, entry in self._sample_heap],
            key=lambda item: (item[0], item[1]),
        )
        self.summary.sample_entries = [entry for _, _, entry in samples]

    def _stable_hash(self, entry: MergeLogEntry) -> int:
        payload = {
            "seed": self.seed,
            "row_key": entry.row_key or {},
            "column": entry.column or "",
            "source_a": entry.source_a_id,
            "source_b": entry.source_b_id,
            "policy": entry.resolution_policy or "",
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return int(content_hash(encoded), 16)

    @staticmethod
    def _inc(bucket: dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1


class DataComposer:
    """
    Composes data from multiple sources using different strategies.

    Maintains determinism through:
    - Stable caller-provided source order
    - Consistent null handling
    - Deterministic tie-breaking
    """

    def __init__(
        self,
        conflict_resolver: ConflictResolver,
        *,
        tracer: PolicyOSTracer | None = None,
    ) -> None:
        """
        Initialize composer with a conflict resolver.

        Args:
            conflict_resolver: Resolver for handling conflicts
            tracer: Optional injected tracer for composition spans
        """
        self.resolver = conflict_resolver
        self._last_merge_summary: MergeLogSummary | None = None
        self._tracer = tracer
        self._composition_lock = threading.Lock()

    def compose(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        strategy: CompositionStrategy,
        request: CompositionRequest,
    ) -> tuple[pd.DataFrame, list[MergeLogEntry]]:
        """Compose serially; concurrent/reentrant use requires a separate composer."""
        if not self._composition_lock.acquire(blocking=False):
            raise FederationError("DataComposer requires serial non-reentrant composition")
        try:
            return self._compose(sources, strategy, request)
        except (ValueError, TypeError, OverflowError) as exc:
            raise FederationError("Composition input is outside the engineering profile") from exc
        finally:
            self._composition_lock.release()

    def _compose(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        strategy: CompositionStrategy,
        request: CompositionRequest,
    ) -> tuple[pd.DataFrame, list[MergeLogEntry]]:
        """
        Compose data from multiple sources using specified strategy.

        Args:
            sources: List of (dataframe, metadata) tuples
            strategy: Composition strategy to use
            request: Full composition request with parameters

        Returns:
            Tuple of (composed_dataframe, merge_log)

        Raises:
            FederationError: If composition fails
            SchemaIncompatibilityError: If schemas are incompatible
        """
        if not sources:
            raise FederationError("Cannot compose with no sources")

        # Preserve caller-provided precedence while keeping deterministic behavior
        # for a fixed request payload.
        sources = list(sources)
        if len(sources) > MAX_SOURCES:
            raise FederationError("Federation source count exceeds engineering profile")
        # Admit aggregate dimensions before scalar scans or lineage/frame copies.
        total_cells = 0
        for frame, _metadata in sources:
            admit_shape(*frame.shape)
            total_cells += frame.shape[0] * frame.shape[1]
        if total_cells > MAX_GRAPH_CELLS:
            raise FederationError("Federation inputs exceed aggregate cell-work profile")
        if len(set().union(*(set(frame.columns) for frame, _ in sources))) > 1_000:
            raise FederationError("Federation input union exceeds column profile")
        if strategy == CompositionStrategy.JOIN:
            # Cardinality is known from keys before even an owned row relation
            # is decoded or a first working dataframe/lineage is copied.
            self._preflight_join(sources, request)
        if strategy in {CompositionStrategy.OVERLAY, CompositionStrategy.CONSENSUS}:
            overlay_keys = self._resolve_key_columns(request, self._resolve_time_dimension(request))
            for frame, _metadata in sources:
                if not overlay_keys or any(key not in frame.columns for key in overlay_keys):
                    raise SchemaIncompatibilityError("OVERLAY key columns are missing")
                if frame.duplicated(overlay_keys, keep=False).any():
                    raise FederationError(
                        "OVERLAY/CONSENSUS duplicate keys require an explicit row-occurrence rule"
                    )
        if strategy != CompositionStrategy.JOIN:
            profile_keys = self._resolve_key_columns(request, self._resolve_time_dimension(request))
            for key in profile_keys:
                declarations = {
                    str(frame[key].dtype) for frame, _ in sources if key in frame.columns
                }
                if len(declarations) > 1:
                    raise SchemaIncompatibilityError(
                        "Mixed key dtypes require an explicit lossless identity profile"
                    )
        total_rows = 0
        input_wire_bytes = 0
        self._basis_status = FederationBasisStatus(selected_bytes="recomputed")
        self._all_source_declarations: dict[str, dict[str, Any]] = {}
        self._input_source_occurrences: list[tuple[str, ...]] = []
        token_bytes = 0
        contributors = 0
        for source_position, (frame, metadata) in enumerate(sources):
            input_wire_bytes += admit_frame(frame)
            if input_wire_bytes > MAX_TOTAL_BYTES:
                raise FederationError("Federation inputs exceed aggregate encoded byte profile")
            owned = _read_persisted_lineage(frame)
            maximum_contributors = 1
            token_bytes = max(token_bytes, len(bounded_encode(metadata.connector_id)) + 67)
            if owned is None:
                self._basis_status = FederationBasisStatus()
                origin = _leaf_origin(frame, metadata, source_position)
                self._all_source_declarations[origin.token] = json.loads(origin.declaration)
                self._input_source_occurrences.append((origin.token,))
            else:
                owned_receipt = json.loads(_OWNED_BASIS[id(frame)][2])
                self._input_source_occurrences.append(tuple(owned_receipt["source_declarations"]))
                if owned_receipt["basis_status"]["selected_bytes"] != "recomputed":
                    self._basis_status = FederationBasisStatus()
                self._all_source_declarations.update(
                    json.loads(_OWNED_BASIS[id(frame)][2])["source_declarations"]
                )
                for row in owned:
                    for origins in row.values():
                        maximum_contributors = max(maximum_contributors, len(origins))
                        for origin in origins:
                            token_bytes = max(token_bytes, len(bounded_encode(origin.token)))
            contributors += maximum_contributors
            total_rows += len(frame)
        self._lineage_token_bytes = token_bytes
        if strategy == CompositionStrategy.JOIN:
            self._preflight_join(sources, request, token_bytes=token_bytes)
            admit_output_envelope(
                sources[:1], len(sources[0][0]), token_bytes=token_bytes, request=request
            )
        columns = set().union(*(set(frame.columns) for frame, _ in sources))
        if strategy != CompositionStrategy.JOIN:
            admit_shape(total_rows, len(columns))
            output_wire = admit_output_envelope(
                sources,
                total_rows,
                contributors=contributors if strategy == CompositionStrategy.CONSENSUS else 1,
                token_bytes=token_bytes,
                request=request,
            )
            if input_wire_bytes + output_wire > MAX_TOTAL_BYTES:
                raise FederationError(
                    "Federation input/output exceeds aggregate encoded byte profile"
                )

        collector = MergeLogCollector(
            audit_level=request.audit_level,
            sample_size=request.audit_sample_size,
            max_entries=request.audit_max_entries,
            seed=request.audit_seed,
        )

        tracer = self._tracer if self._tracer is not None else _default_tracer()
        span_ctx = (
            tracer.start_as_current_span(
                FABRIC_TRACE_NAMES["federation_compose"],
                attributes={
                    "federation.strategy": strategy.value,
                    "federation.source_count": len(sources),
                    "federation.audit_level": request.audit_level.value,
                },
            )
            if tracer
            else _noop_span()
        )
        with span_ctx:
            logger.info(
                "Composing sources",
                strategy=strategy.value,
                sources=[s[1].connector_id for s in sources],
            )

            # Dispatch to strategy-specific method
            if strategy == CompositionStrategy.UNION:
                result = self._union(sources, request, collector)
            elif strategy == CompositionStrategy.JOIN:
                result = self._join(sources, request, collector)
            elif strategy == CompositionStrategy.OVERLAY:
                result = self._overlay(sources, request, collector)
            elif strategy == CompositionStrategy.CONSENSUS:
                result = self._consensus(sources, request, collector)
            else:
                raise FederationError(f"Unknown strategy: {strategy}")

        result = self._restore_output_profile(result, sources, strategy, request)

        collector.finalize()
        collector.summary.extra["basis_status"] = asdict(self._basis_status)
        self._last_merge_summary = collector.summary

        merge_log = []
        if request.audit_level == AuditLevel.FULL:
            merge_log = collector.entries
        elif request.audit_level == AuditLevel.SUMMARY:
            merge_log = collector.summary.sample_entries

        logger.info(
            "Composition complete",
            strategy=strategy.value,
            result_rows=len(result),
            result_cols=len(result.columns),
            conflicts=collector.summary.total_conflicts,
        )

        return result, merge_log

    def _restore_output_profile(
        self,
        result: pd.DataFrame,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        strategy: CompositionStrategy,
        request: CompositionRequest,
    ) -> pd.DataFrame:
        """Project column dtypes only after lossless reconciliation to exact held values."""
        lineage = _read_persisted_lineage(result)
        if lineage is None:
            raise FederationError("Output profile lacks its owned cell basis")
        keys = (
            (request.join_keys or [])
            if strategy == CompositionStrategy.JOIN
            else self._resolve_key_columns(request, self._resolve_time_dimension(request))
        )
        columns = {}
        for column in result.columns:
            aggregation = (
                (request.column_aggregation_funcs or {}).get(column)
                or request.aggregation_func
                or "median"
            )
            if (
                strategy == CompositionStrategy.CONSENSUS
                and column not in keys
                and aggregation in {"mean", "median"}
            ):
                target = "float64"  # Explicit numeric transform, not source-row projection.
            else:
                templates = [
                    frame[column].iloc[:0] for frame, _ in sources if column in frame.columns
                ]
                target_dtype = pd.concat(templates, ignore_index=True).dtype
                if (
                    result[column].isna().any()
                    and pd.api.types.is_integer_dtype(target_dtype)
                    and not pd.api.types.is_extension_array_dtype(target_dtype)
                ):
                    target = "float64"  # Existing pandas null-extension output profile.
                elif (
                    result[column].isna().any()
                    and pd.api.types.is_bool_dtype(target_dtype)
                    and not pd.api.types.is_extension_array_dtype(target_dtype)
                ):
                    target = "object"
                else:
                    target = str(target_dtype)
            columns[column] = cast_series_losslessly(
                result[column],
                target,
                allow_exact_numeric_projection=True,
            )
        projected = pd.DataFrame(columns, index=result.index)
        _attach_persisted_lineage(
            projected, lineage, self._all_source_declarations, self._basis_status
        )
        return projected

    def get_last_merge_summary(self) -> MergeLogSummary | None:
        """Return the summary from the most recent composition run."""
        return self._last_merge_summary

    def _union(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
        collector: MergeLogCollector,
    ) -> pd.DataFrame:
        """
        UNION strategy: Temporal splicing - append rows from different periods.

        Algorithm:
        1. Concatenate all dataframes
        2. Sort by key columns
        3. Detect overlapping periods by key columns
        4. For overlaps, invoke ConflictResolver
        5. Return deduplicated result
        """
        time_dim = self._resolve_time_dimension(request)
        key_columns = self._resolve_key_columns(request, time_dim)
        if not key_columns:
            raise FederationError("UNION strategy requires key_columns or schema")

        # Validate key columns exist in all sources
        for df, metadata in sources:
            missing_keys = [k for k in key_columns if k not in df.columns]
            if missing_keys:
                raise SchemaIncompatibilityError(
                    f"Key columns {missing_keys} not found in source {metadata.connector_id}"
                )

        input_columns = [column for df, _ in sources for column in df.columns]
        source_column = _fresh_internal_name(input_columns, "__policyos_source_id")
        all_rows = []
        row_bases: dict[int, _LineageMap] = {}
        ordinal = 0
        for position, (df, metadata) in enumerate(sources):
            basis = _input_lineage(df, metadata, position)
            df_copy = scalar_frame(df)
            # Keep transport provenance out of the user namespace.  The
            # generated name is local to this operation and is removed before
            # the result is returned, so a real ``__source_id`` column is
            # ordinary data rather than an implementation detail.
            identifiers = list(range(ordinal, ordinal + len(df)))
            row_bases.update(zip(identifiers, basis, strict=True))
            df_copy[source_column] = identifiers
            ordinal += len(df)
            all_rows.append(df_copy)

        combined = pd.concat(all_rows, ignore_index=True)
        combined = combined.sort_values(by=key_columns, kind="mergesort").reset_index(drop=True)

        # Physical selected inputs are declaration-bound tokens.  A logical
        # connector id/version may legitimately occur more than once with a
        # different selected payload or declaration.
        metadata_lookup = {}
        ordinal = 0
        for frame, metadata in sources:
            metadata_lookup.update(
                (index, metadata) for index in range(ordinal, ordinal + len(frame))
            )
            ordinal += len(frame)

        resolved_rows = []
        resolved_lineage: list[_LineageMap] = []
        for key_values, group in combined.groupby(key_columns, sort=True, dropna=False):
            row_key = self._row_key_from_group(key_columns, key_values)
            group_rows = [dict(zip(group.columns, row, strict=True)) for row in scalar_rows(group)]
            if len(group_rows) == 1:
                row = group_rows[0]
                resolved_rows.append(
                    {column: value for column, value in row.items() if column != source_column}
                )
                resolved_lineage.append(row_bases[int(row[source_column])])
                continue

            candidates = []
            for row in group_rows:
                source_id = row[source_column]
                metadata = metadata_lookup[int(source_id)]
                origins = {origin for cell in row_bases[int(source_id)].values() for origin in cell}
                if len(origins) > 1:
                    raise FederationError(
                        "Mixed-source UNION row cannot be ranked as a single declared leaf"
                    )
                if origins:
                    metadata = next(iter(origins)).metadata()
                candidates.append(
                    ConflictCandidate(
                        source_id=metadata.connector_id,
                        value={
                            column: value
                            for column, value in row.items()
                            if column != source_column
                        },
                        metadata=metadata,
                        row_key=row_key,
                    )
                )

            context = ConflictContext(
                request=request,
                row_key=row_key,
                conflict_type="overlap",
            )

            resolution = self.resolver.resolve_conflict(
                candidates,
                context,
                policy_override=request.conflict_policy,
                record_log=request.audit_level != AuditLevel.NONE,
            )

            if resolution.log_entry:
                collector.record(resolution.log_entry)

            chosen = next(
                index
                for index, candidate in enumerate(candidates)
                if candidate is resolution.chosen_candidate
            )
            resolved_rows.append(dict(resolution.chosen_candidate.value))
            resolved_lineage.append(row_bases[int(group_rows[chosen][source_column])])

        if not resolved_rows:
            empty = scalar_frame(sources[0][0].iloc[:0])
            _attach_persisted_lineage(empty, [], self._all_source_declarations, self._basis_status)
            return empty

        result = pd.DataFrame(resolved_rows, dtype=object)
        # groupby already emits canonical key order; preserve the corresponding relation.
        result = result.reset_index(drop=True)
        _attach_persisted_lineage(
            result, resolved_lineage, self._all_source_declarations, self._basis_status
        )
        return result

    def _join(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
        collector: MergeLogCollector,
    ) -> pd.DataFrame:
        """
        JOIN strategy: Column enrichment - merge on join keys.

        Algorithm:
        1. Validate join keys exist in all sources
        2. Perform pandas merge with specified join_how
        3. Detect duplicate columns (suffix conflicts)
        4. For duplicate columns, invoke ConflictResolver
        5. Return merged result
        """
        join_keys = request.join_keys
        if not join_keys:
            raise FederationError("JOIN strategy requires join_keys")

        for df, metadata in sources:
            missing_keys = [k for k in join_keys if k not in df.columns]
            if missing_keys:
                raise SchemaIncompatibilityError(
                    f"Join keys {missing_keys} not found in source {metadata.connector_id}"
                )

        result_df, first_metadata = sources[0]
        persisted_lineage = _input_lineage(result_df, first_metadata, 0)
        result_df = scalar_frame(result_df).reset_index(drop=True)
        lineage_column = _fresh_internal_name(result_df.columns, "__policyos_lineage")
        initial_lineage = persisted_lineage
        result_df[lineage_column] = pd.Series(initial_lineage, index=result_df.index, dtype=object)

        for source_position, (df, metadata) in enumerate(sources[1:], 1):
            right_lineage_values = _input_lineage(df, metadata, source_position)
            df_copy = scalar_frame(df).reset_index(drop=True)

            # A caller may legitimately use the generated-looking lineage
            # name.  Move our sidecar before considering user columns so it
            # can never become part of the public result or a conflict set.
            if lineage_column in df_copy.columns:
                replacement = _fresh_internal_name(
                    [*result_df.columns, *df_copy.columns], "__policyos_lineage"
                )
                result_df = result_df.rename(columns={lineage_column: replacement})
                lineage_column = replacement

            overlapping_cols = (
                (set(result_df.columns) & set(df_copy.columns)) - set(join_keys) - {lineage_column}
            )

            if overlapping_cols:
                logger.info(
                    "JOIN detected overlapping columns",
                    columns=sorted(overlapping_cols),
                )

            used_names = set(result_df.columns) | set(df_copy.columns)
            right_renames: dict[str, str] = {}
            right_key_aliases: dict[str, str] = {}
            for key in join_keys:
                alias = _fresh_internal_name(used_names, "__policyos_right_key")
                used_names.add(alias)
                right_renames[key] = alias
                right_key_aliases[key] = alias
            for column in sorted(overlapping_cols):
                alias = _fresh_internal_name(used_names, "__policyos_right_column")
                used_names.add(alias)
                right_renames[column] = alias

            right_work = df_copy.rename(columns=right_renames)
            right_lineage_column = _fresh_internal_name(
                [*result_df.columns, *right_work.columns],
                "__policyos_right_lineage",
            )
            right_work[right_lineage_column] = pd.Series(
                right_lineage_values, index=right_work.index, dtype=object
            )

            left_work = result_df.copy()
            merge_keys: list[str] = []
            for key in join_keys:
                # Prevent pandas outer null-extension from rounding an integral key
                # before the exact-value reconstitution below.
                left_work[key] = left_work[key].astype(object)
                right_work[right_key_aliases[key]] = right_work[right_key_aliases[key]].astype(
                    object
                )
                merge_key = _fresh_internal_name(
                    [*left_work.columns, *right_work.columns], "__policyos_join_key"
                )
                merge_keys.append(merge_key)
                left_work[merge_key] = self._join_key_values(
                    left_work[key], side="left", match_nulls=request.join_nulls_match
                )
                right_work[merge_key] = self._join_key_values(
                    right_work[right_key_aliases[key]],
                    side="right",
                    match_nulls=request.join_nulls_match,
                )

            result_df = left_work.merge(
                right_work,
                on=merge_keys,
                how=request.join_how,
                sort=False,
            )

            # An outer JOIN carries the right key under an internal alias.
            # Reconstitute the user key without allowing a temporary name to
            # leak into the result.
            for key, right_key in right_key_aliases.items():
                # Keep admitted scalar identity across later JOIN stages: pandas
                # nullable reconstitution may coerce a large integer to float.
                result_df[key] = pd.Series(
                    [
                        right if _is_missing_scalar(left) else left
                        for left, right in zip(result_df[key], result_df[right_key], strict=True)
                    ],
                    index=result_df.index,
                    dtype=object,
                )

            right_only_columns = [
                column
                for column in df_copy.columns
                if column not in join_keys and column not in overlapping_cols
            ]
            merged_lineage: list[_LineageMap] = []
            merged_right_lineage: list[_LineageMap] = []
            for left_basis, right_basis in zip(
                result_df[lineage_column], result_df[right_lineage_column], strict=True
            ):
                row_lineage = _lineage_map(left_basis)
                row_right_lineage = _lineage_map(right_basis)
                for key in join_keys:
                    if key not in row_lineage:
                        row_lineage[key] = row_right_lineage.get(key, ())
                for column in right_only_columns:
                    row_lineage.setdefault(column, row_right_lineage.get(column, ()))
                merged_lineage.append(row_lineage)
                merged_right_lineage.append(row_right_lineage)

            drop_columns = [
                *merge_keys,
                right_lineage_column,
                *right_key_aliases.values(),
            ]
            result_df = result_df.drop(columns=drop_columns)
            result_df[lineage_column] = pd.Series(
                merged_lineage, index=result_df.index, dtype=object
            )

            # Resolve duplicate columns
            for col in sorted(overlapping_cols):
                resolved_col, chosen_lineage = self._resolve_duplicate_column(
                    df=result_df,
                    column_name=col,
                    left_meta=None,
                    right_meta=metadata,
                    request=request,
                    join_keys=join_keys,
                    collector=collector,
                    left_column=col,
                    right_column=right_renames[col],
                    left_lineage=[
                        _lineage_map(value) for value in result_df[lineage_column].tolist()
                    ],
                    right_lineage=merged_right_lineage,
                )

                result_df[col] = resolved_col
                result_df = result_df.drop(columns=[right_renames[col]])
                lineage_values = [_lineage_map(value) for value in result_df[lineage_column]]
                for position, source in enumerate(chosen_lineage):
                    lineage_values[position][col] = source
                result_df[lineage_column] = pd.Series(
                    lineage_values, index=result_df.index, dtype=object
                )

        final_lineage = [_lineage_map(value) for value in result_df[lineage_column].tolist()]
        result_df = result_df.drop(columns=[lineage_column])
        _attach_persisted_lineage(
            result_df, final_lineage, self._all_source_declarations, self._basis_status
        )

        return result_df

    def _preflight_join(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
        *,
        token_bytes: int = 0,
    ) -> int:
        """Admit every intermediate actual row multiplicity before any data copy."""
        from collections import Counter

        keys = request.join_keys
        if request.join_how not in {"inner", "left", "outer"}:
            raise SchemaIncompatibilityError("Unsupported JOIN output relation")
        if not keys:
            raise SchemaIncompatibilityError("JOIN strategy requires join_keys")
        relation = request.join_validate or "many_to_one"
        if relation not in {"one_to_one", "one_to_many", "many_to_one", "many_to_many"}:
            raise SchemaIncompatibilityError("Unsupported JOIN cardinality")
        if request.join_max_rows is not None and request.join_max_rows < 0:
            raise SchemaIncompatibilityError("join_max_rows must be non-negative")
        if relation == "many_to_many" and request.join_max_rows is None:
            raise SchemaIncompatibilityError(
                "many_to_many JOIN requires join_max_rows before materialization"
            )
        limit = (
            min(MAX_ROWS, request.join_max_rows) if request.join_max_rows is not None else MAX_ROWS
        )

        left = self._join_key_counts(sources[0][0], keys)
        for stage, (right_frame, _metadata) in enumerate(sources[1:], 1):
            right = self._join_key_counts(right_frame, keys)

            def known(key: tuple) -> bool:
                return request.join_nulls_match or None not in key

            if relation in {"one_to_one", "one_to_many"} and any(
                count > 1 and known(key) for key, count in left.items()
            ):
                raise SchemaIncompatibilityError(
                    "JOIN cardinality rejects duplicate left keys before materialization"
                )
            if relation in {"one_to_one", "many_to_one"} and any(
                count > 1 and known(key) for key, count in right.items()
            ):
                raise SchemaIncompatibilityError(
                    "JOIN cardinality rejects duplicate right keys before materialization"
                )
            output = Counter()
            rows = self._estimate_join_rows(
                left=left,
                right=right,
                join_keys=keys,
                join_how=request.join_how,
                match_nulls=request.join_nulls_match,
                result_counts=output,
            )
            if rows > limit:
                raise SchemaIncompatibilityError(
                    "JOIN exceeds declared join_max_rows before materialization: "
                    f"estimated={rows}, limit={limit}"
                )
            wire_bound = admit_output_envelope(
                sources[: stage + 1], rows, token_bytes=token_bytes, request=request
            )
            input_wire = sum(admit_frame(frame) for frame, _ in sources[: stage + 1])
            if input_wire + wire_bound > MAX_TOTAL_BYTES:
                raise SchemaIncompatibilityError(
                    "Federation input/output exceeds aggregate encoded byte profile"
                )
            columns = sum(len(frame.columns) for frame, _ in sources[: stage + 1])
            admit_shape(rows, columns + len(keys) + 2)
            left = output
        if len(sources) == 1 and sum(left.values()) > limit:
            raise SchemaIncompatibilityError(
                "JOIN exceeds declared join_max_rows before materialization"
            )
        return sum(left.values())

    @staticmethod
    def _join_key_component(value: Any) -> tuple[object, ...] | None:  # noqa: ANN401
        """Normalize the admitted key equivalence used by counts AND real merges.

        Exact numeric equality unifies booleans, integers and finite floats without
        rounding: Fraction also preserves numeric ordering for pandas outer merges.
        Null is an explicit unknown; only materialization namespaces its occurrence
        when matching unknown identities was not requested. Timestamp instants match
        within the aware/naive band, and strings never become numeric identities.
        """
        encoded = encode_scalar(value)
        kind = encoded["t"]
        if kind == "null":
            return None
        if kind in {"bool", "int", "float64"}:
            if kind == "float64":
                number = float.fromhex(encoded["v"])
                if number == float("-inf"):
                    return (1, -1, 0)
                if number == float("inf"):
                    return (1, 1, 0)
            else:
                number = int(encoded["v"])
            return (1, 0, Fraction(number))
        if kind == "str":
            return (2, encoded["v"])
        if kind == "timestamp":
            stamp = pd.Timestamp(encoded["v"])
            return (3, stamp.tzinfo is not None, int(encoded["ns"]))
        raise SchemaIncompatibilityError("Unsupported JOIN key equivalence profile")

    @staticmethod
    def _join_key_values(
        values: pd.Series,
        *,
        side: str,
        match_nulls: bool,
    ) -> pd.Series:
        normalized = []
        for position, value in enumerate(values):
            component = DataComposer._join_key_component(value)
            normalized.append(
                (0, "" if match_nulls else side, 0 if match_nulls else position)
                if component is None
                else component
            )
        return pd.Series(normalized, index=values.index, dtype=object, name=f"{side}_join_key")

    @staticmethod
    def _join_key_counts(frame: pd.DataFrame, keys: list[str]) -> dict[tuple[object, ...], int]:
        from collections import Counter

        if any(key not in frame.columns for key in keys):
            raise SchemaIncompatibilityError("Join keys missing before materialization")
        return Counter(
            tuple(DataComposer._join_key_component(value) for value in row)
            for row in zip(*(frame[key] for key in keys), strict=True)
        )

    @staticmethod
    def _estimate_join_rows(
        *,
        left: pd.DataFrame | dict[tuple[object, ...], int],
        right: pd.DataFrame | dict[tuple[object, ...], int],
        join_keys: list[str],
        join_how: str,
        match_nulls: bool,
        result_counts: dict[tuple[object, ...], int] | None = None,
    ) -> int:
        """Propagate the actual normalized key relation without a pandas data merge."""
        left_counts = (
            DataComposer._join_key_counts(left, join_keys)
            if isinstance(left, pd.DataFrame)
            else left
        )
        right_counts = (
            DataComposer._join_key_counts(right, join_keys)
            if isinstance(right, pd.DataFrame)
            else right
        )
        output = {} if result_counts is None else result_counts
        for key in left_counts.keys() | right_counts.keys():
            a, b = left_counts.get(key, 0), right_counts.get(key, 0)
            known = match_nulls or None not in key
            if a and b and known:
                output[key] = a * b
            elif join_how == "outer":
                output[key] = a + b
            elif join_how == "left":
                output[key] = a
        return sum(output.values())

    def _overlay(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
        collector: MergeLogCollector,
    ) -> pd.DataFrame:
        """
        OVERLAY strategy: Coalesce - primary source + fill nulls from others.

        Algorithm:
        1. Identify primary source
        2. Start with primary dataframe
        3. For each null value, search secondary sources in priority order
        4. Fill null with first available value
        5. Log all fill operations
        """
        time_dim = self._resolve_time_dimension(request)
        key_columns = self._resolve_key_columns(request, time_dim)
        if not key_columns:
            raise FederationError("OVERLAY strategy requires key_columns or schema")

        for frame, _metadata in sources:
            if any(key not in frame.columns for key in key_columns):
                raise SchemaIncompatibilityError("OVERLAY key columns are missing")
            if frame.duplicated(key_columns, keep=False).any():
                raise FederationError(
                    "OVERLAY duplicate keys require an explicit row-occurrence rule"
                )
        primary_idx = self._select_primary_source_index(sources, request)
        primary = sources[primary_idx]
        secondaries = sources[:primary_idx] + sources[primary_idx + 1 :]
        if request.manual_priorities:
            # Larger numbers are the existing resolver/planner preference.
            # Python's stable sort preserves declared input order for ties and
            # for the no-priority default.
            secondaries = sorted(
                secondaries,
                key=lambda source: request.manual_priorities.get(source[1].connector_id, 0),
                reverse=True,
            )

        result_df, primary_metadata = primary
        primary_basis = _input_lineage(result_df, primary_metadata, primary_idx)
        basis_by_key = {
            tuple(None if _is_missing_scalar(value) else value for value in row): basis
            for row, basis in zip(
                result_df[key_columns].itertuples(False, None), primary_basis, strict=True
            )
        }
        result_df = scalar_frame(result_df)

        # Ensure key columns exist
        for key in key_columns:
            if key not in result_df.columns:
                raise SchemaIncompatibilityError(
                    f"Key column '{key}' not found in primary source "
                    f"{primary_metadata.connector_id}"
                )

        all_columns = set(result_df.columns)
        for df, _ in secondaries:
            all_columns.update(df.columns)

        # Align on key columns
        result_df = result_df.set_index(key_columns, drop=True)
        result_df = result_df.sort_index()
        admit_key_index([primary[0]], key_columns, result_df.index)

        # Add missing columns from secondaries
        for col in sorted(all_columns):
            if col in key_columns:
                continue
            if col not in result_df.columns:
                result_df[col] = pd.NA

        result_basis = [
            dict(
                basis_by_key[
                    tuple(
                        None if _is_missing_scalar(value) else value
                        for value in (idx if isinstance(idx, tuple) else (idx,))
                    )
                ]
            )
            for idx in result_df.index
        ]
        indexed_secondaries: dict[int, pd.DataFrame] = {}
        secondary_bases: dict[int, dict[tuple, _LineageMap]] = {}
        for col in result_df.columns:
            null_mask = result_df[col].isna()
            if not null_mask.any():
                continue

            for secondary_index, (secondary_df, secondary_meta) in enumerate(secondaries):
                if col not in secondary_df.columns:
                    continue

                secondary_indexed = indexed_secondaries.get(secondary_index)
                if secondary_indexed is None:
                    secondary_indexed = secondary_df.set_index(key_columns, drop=True)
                    indexed_secondaries[secondary_index] = secondary_indexed
                    source_position = next(
                        index
                        for index, source in enumerate(sources)
                        if source[0] is secondary_df and source[1] is secondary_meta
                    )
                    basis = _input_lineage(secondary_df, secondary_meta, source_position)
                    secondary_bases[secondary_index] = {
                        tuple(
                            None if _is_missing_scalar(value) else value for value in row
                        ): origins
                        for row, origins in zip(
                            secondary_df[key_columns].itertuples(False, None), basis, strict=True
                        )
                    }
                aligned = align_scalar_series(secondary_indexed[col], result_df.index)

                fill_mask = null_mask & aligned.notna()
                if fill_mask.any():
                    if request.audit_level != AuditLevel.NONE:
                        for idx in result_df.index[fill_mask]:
                            row_key = self._row_key_from_index(key_columns, idx)
                            entry = MergeLogEntry(
                                row_index=None,
                                row_key=row_key,
                                column=col,
                                conflict_type="null_fill",
                                source_a_id=primary_metadata.connector_id,
                                source_a_value=None,
                                source_a_trust=primary_metadata.metadata.trust_level,
                                source_b_id=secondary_meta.connector_id,
                                source_b_value=aligned.loc[idx],
                                source_b_trust=secondary_meta.metadata.trust_level,
                                chosen_source=secondary_meta.connector_id,
                                chosen_value=aligned.loc[idx],
                                resolution_reason=(
                                    f"OVERLAY: fill null from {secondary_meta.connector_id}"
                                ),
                                resolution_policy=ConflictPolicy.FIRST_AVAILABLE.value,
                                timestamp=None,
                            )
                            collector.record(entry)

                    for position, idx in enumerate(result_df.index):
                        if fill_mask.iloc[position]:
                            key = tuple(
                                None if _is_missing_scalar(value) else value
                                for value in (idx if isinstance(idx, tuple) else (idx,))
                            )
                            result_basis[position][col] = secondary_bases[secondary_index][key].get(
                                col, ()
                            )
                    result_df.loc[fill_mask, col] = aligned[fill_mask]
                    null_mask = result_df[col].isna()

                if not null_mask.any():
                    break

        result_df = result_df.reset_index()
        _attach_persisted_lineage(
            result_df, result_basis, self._all_source_declarations, self._basis_status
        )
        return result_df

    def _consensus(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
        collector: MergeLogCollector,
    ) -> pd.DataFrame:
        """
        CONSENSUS strategy: Statistical aggregation across sources.

        Algorithm:
        1. Align all sources on common index
        2. For each cell, collect all non-null values
        3. Apply aggregation function (mean/median/mode)
        4. Handle edge cases (single source, all nulls)
        5. Log statistical decisions
        """
        time_dim = self._resolve_time_dimension(request)
        key_columns = self._resolve_key_columns(request, time_dim)
        if not key_columns:
            raise FederationError("CONSENSUS strategy requires key_columns or schema")

        indexed_sources: list[tuple[pd.DataFrame, SourceMetadata]] = []
        for df, metadata in sources:
            missing_keys = [k for k in key_columns if k not in df.columns]
            if missing_keys:
                raise SchemaIncompatibilityError(
                    f"Key columns {missing_keys} not found in source {metadata.connector_id}"
                )
            indexed = scalar_frame(df).set_index(key_columns, drop=True)
            indexed_sources.append((indexed, metadata))

        # Determine union index
        union_index = indexed_sources[0][0].index
        for indexed, _ in indexed_sources[1:]:
            union_index = union_index.union(indexed.index)
        union_index = union_index.sort_values()
        admit_key_index([frame for frame, _ in sources], key_columns, union_index)

        # Determine common columns (excluding keys)
        common_columns_set = set(indexed_sources[0][0].columns)
        for indexed, _ in indexed_sources[1:]:
            common_columns_set &= set(indexed.columns)
        common_columns = sorted(common_columns_set)

        result = pd.DataFrame(index=union_index)
        source_basis_by_key = []
        for position, (frame, metadata) in enumerate(sources):
            source_basis_by_key.append(
                {
                    tuple(None if _is_missing_scalar(value) else value for value in row): basis
                    for row, basis in zip(
                        frame[key_columns].itertuples(False, None),
                        _input_lineage(frame, metadata, position),
                        strict=True,
                    )
                }
            )
        result_basis: list[_LineageMap] = []
        for idx in union_index:
            key = tuple(
                None if _is_missing_scalar(value) else value
                for value in (idx if isinstance(idx, tuple) else (idx,))
            )
            key_basis = next((basis[key] for basis in source_basis_by_key if key in basis), {})
            result_basis.append({column: key_basis.get(column, ()) for column in key_columns})
        consensus_stats: dict[str, dict[str, Any]] = {}

        for col in common_columns:
            values_df = pd.concat(
                [align_scalar_series(indexed[col], union_index) for indexed, _ in indexed_sources],
                axis=1,
            )

            agg_func = (
                (request.column_aggregation_funcs or {}).get(col)
                or request.aggregation_func
                or "median"
            )

            consensus_col, admissibility = self._apply_consensus(
                values_df=values_df,
                agg_func=agg_func,
                request=request,
                indexed_sources=indexed_sources,
                key_columns=key_columns,
                column=col,
            )

            for position, (idx, row_values) in enumerate(
                zip(values_df.index, scalar_rows(values_df), strict=True)
            ):
                key = tuple(
                    None if _is_missing_scalar(value) else value
                    for value in (idx if isinstance(idx, tuple) else (idx,))
                )
                contributors = []
                for source_position, value in enumerate(row_values):
                    if _is_missing_scalar(value):
                        continue
                    if agg_func != "mode":
                        try:
                            admissible = is_finite_number(float(value))
                        except (TypeError, ValueError):
                            admissible = False
                        if not admissible:
                            continue
                    contributors.extend(
                        source_basis_by_key[source_position].get(key, {}).get(col, ())
                    )
                result_basis[position][col] = tuple(contributors)

            # Logging conflicts where values differ
            if request.audit_level != AuditLevel.NONE:
                distinct_counts = values_df.nunique(axis=1, dropna=True)
                conflict_mask = distinct_counts > 1
                if conflict_mask.any():
                    for row_position, idx in enumerate(values_df.index):
                        if not conflict_mask.iat[row_position]:
                            continue
                        row_key = self._row_key_from_index(key_columns, idx)
                        row_id = json.dumps(row_key, sort_keys=True, default=str)
                        participants = admissibility["participant_sources"].get(row_id, [])
                        exclusions = admissibility["exclusions"].get(row_id, [])
                        source_a_id = (
                            participants[0]
                            if participants
                            else (
                                exclusions[0]["source_id"]
                                if exclusions
                                else indexed_sources[0][1].connector_id
                            )
                        )
                        source_a_index = next(
                            (
                                source_idx
                                for source_idx, (_indexed, metadata) in enumerate(indexed_sources)
                                if metadata.connector_id == source_a_id
                            ),
                            0,
                        )
                        source_a_value = values_df.iat[row_position, source_a_index]
                        consensus_value = consensus_col.iat[row_position]
                        entry = MergeLogEntry(
                            row_index=None,
                            row_key=row_key,
                            column=col,
                            conflict_type="consensus",
                            source_a_id=source_a_id,
                            source_a_value=source_a_value,
                            source_a_trust=indexed_sources[source_a_index][1].metadata.trust_level,
                            source_b_id="consensus",
                            source_b_value=consensus_value,
                            source_b_trust=indexed_sources[0][1].metadata.trust_level,
                            chosen_source="consensus",
                            chosen_value=consensus_value,
                            resolution_reason=(
                                f"CONSENSUS: {agg_func} of {len(participants)} "
                                f"admissible participants; excluded={len(exclusions)}"
                            ),
                            resolution_policy=agg_func,
                            timestamp=None,
                        )
                        collector.record(entry)

            physical = {"participants": {}, "exclusions": {}, "absence": {}}
            for _position, (idx, row_values) in enumerate(
                zip(values_df.index, scalar_rows(values_df), strict=True)
            ):
                key = tuple(
                    None if _is_missing_scalar(value) else value
                    for value in (idx if isinstance(idx, tuple) else (idx,))
                )
                row_id = json.dumps(
                    self._row_key_from_index(key_columns, idx), sort_keys=True, default=str
                )
                participants, exclusions, absence = [], [], []
                for source_position, value in enumerate(row_values):
                    selected = source_basis_by_key[source_position].get(key)
                    if selected is None:
                        absence.append(
                            {
                                "source_position": source_position,
                                "selected_input_occurrences": list(
                                    self._input_source_occurrences[source_position]
                                ),
                                "reason": "key_absent",
                            }
                        )
                        continue
                    origins = selected.get(col, ())
                    if _is_missing_scalar(value):
                        absence.append(
                            {
                                "source_position": source_position,
                                "selected_input_occurrences": list(
                                    self._input_source_occurrences[source_position]
                                ),
                                "reason": "null",
                            }
                        )
                        continue
                    reason = None
                    if agg_func != "mode":
                        try:
                            reason = None if is_finite_number(float(value)) else "non_finite"
                        except (TypeError, ValueError):
                            reason = "non_numeric"
                    tokens = [origin.token for origin in origins]
                    if reason:
                        exclusions.append(
                            {
                                "source_position": source_position,
                                "source_occurrences": tokens,
                                "reason": reason,
                            }
                        )
                    else:
                        participants.extend(tokens)
                physical["participants"][row_id] = participants
                physical["exclusions"][row_id] = exclusions
                physical["absence"][row_id] = absence

            consensus_stats[col] = {
                "aggregation": agg_func,
                "rows": len(consensus_col),
                "conflicts": int(values_df.nunique(axis=1, dropna=True).gt(1).sum()),
                "sources": len(indexed_sources),
                "participants": admissibility["participants"],
                "excluded": admissibility["excluded"],
                "excluded_by_reason": admissibility["excluded_by_reason"],
                "participant_sources": admissibility["participant_sources"],
                "exclusions": admissibility["exclusions"],
                "physical_basis": physical,
            }

            result[col] = consensus_col

        collector.summary.extra["consensus"] = consensus_stats

        result.index.names = key_columns
        result = result.reset_index()
        _attach_persisted_lineage(
            result, result_basis, self._all_source_declarations, self._basis_status
        )
        return result

    def _apply_consensus(
        self,
        *,
        values_df: pd.DataFrame,
        agg_func: str,
        request: CompositionRequest,
        indexed_sources: list[tuple[pd.DataFrame, SourceMetadata]],
        key_columns: list[str],
        column: str,
    ) -> tuple[pd.Series, dict[str, Any]]:
        """Aggregate only admissible values and retain participant evidence."""
        participant_sources: dict[str, list[str]] = {}
        exclusions: dict[str, list[dict[str, str]]] = {}
        excluded_by_reason: dict[str, int] = {}
        participant_count = 0
        excluded_count = 0

        if agg_func == "mode":
            from collections import Counter

            selected_values = []
            for row in scalar_rows(values_df):
                non_null = [value for value in row if not _is_missing_scalar(value)]
                if not non_null:
                    selected_values.append(pd.NA)
                    continue
                frequencies = Counter(non_null)
                maximum = max(frequencies.values())
                tied = [value for value in non_null if frequencies[value] == maximum]
                try:
                    selected_values.append(min(tied))
                except TypeError:
                    selected_values.append(tied[0])
            result = pd.Series(selected_values, index=values_df.index, dtype=object)
            for idx, row in zip(values_df.index, scalar_rows(values_df), strict=True):
                row_key = self._row_key_from_index(key_columns, idx)
                row_id = json.dumps(row_key, sort_keys=True, default=str)
                sources = [
                    indexed_sources[source_idx][1].connector_id
                    for source_idx, value in enumerate(row)
                    if not _is_missing_scalar(value)
                ]
                if sources:
                    participant_sources[row_id] = sources
                    participant_count += len(sources)
            return result, {
                "participants": participant_count,
                "excluded": excluded_count,
                "excluded_by_reason": excluded_by_reason,
                "participant_sources": participant_sources,
                "exclusions": exclusions,
            }

        if agg_func not in {"mean", "median"}:
            raise FederationError(f"Unknown aggregation function: {agg_func}")

        result_values: list[float] = []
        for idx, row in zip(values_df.index, scalar_rows(values_df), strict=True):
            row_key = self._row_key_from_index(key_columns, idx)
            row_id = json.dumps(row_key, sort_keys=True, default=str)
            numeric_values: list[float] = []
            row_participants: list[str] = []
            row_exclusions: list[dict[str, str]] = []
            for source_idx, value in enumerate(row):
                source_id = indexed_sources[source_idx][1].connector_id
                if _is_missing_scalar(value):
                    continue
                reason: str | None
                try:
                    numeric_value = float(value)
                except TypeError, ValueError:
                    reason = "non_numeric"
                else:
                    reason = None if is_finite_number(numeric_value) else "non_finite"

                if reason is not None:
                    row_exclusions.append({"source_id": source_id, "reason": reason})
                    excluded_count += 1
                    excluded_by_reason[reason] = excluded_by_reason.get(reason, 0) + 1
                    continue

                numeric_values.append(numeric_value)
                row_participants.append(source_id)
                participant_count += 1

            if row_participants:
                participant_sources[row_id] = row_participants
            if row_exclusions:
                exclusions[row_id] = row_exclusions

            if request.strict_conflicts and row_exclusions:
                display_reasons = {
                    "non_finite": "non-finite",
                    "non_numeric": "non-numeric",
                }
                reasons = ", ".join(
                    sorted(
                        {
                            display_reasons.get(item["reason"], item["reason"])
                            for item in row_exclusions
                        }
                    )
                )
                raise ConflictResolutionError(
                    f"CONSENSUS {agg_func} rejected {reasons} value(s) "
                    f"for column {column} at row {row_key}"
                )

            if not numeric_values:
                result_values.append(float("nan"))
            elif agg_func == "mean":
                result_values.append(float(pd.Series(numeric_values).mean()))
            else:
                result_values.append(float(pd.Series(numeric_values).median()))

        return pd.Series(result_values, index=values_df.index), {
            "participants": participant_count,
            "excluded": excluded_count,
            "excluded_by_reason": excluded_by_reason,
            "participant_sources": participant_sources,
            "exclusions": exclusions,
        }

    def _resolve_duplicate_column(
        self,
        df: pd.DataFrame,
        column_name: str,
        left_meta: SourceMetadata | None,
        right_meta: SourceMetadata,
        request: CompositionRequest,
        join_keys: list[str],
        collector: MergeLogCollector,
        *,
        left_column: str | None = None,
        right_column: str | None = None,
        left_lineage: list[_LineageMap] | None = None,
        right_lineage: list[_LineageMap] | None = None,
    ) -> tuple[pd.Series[Any], list[tuple[_CellSource, ...]]]:
        left_col = left_column or f"{column_name}_left"
        right_col = right_column or f"{column_name}_right"

        resolved = df[left_col].copy()
        chosen_lineage_values: list[tuple[_CellSource, ...]] = [()] * len(df)

        for position, idx in enumerate(df.index):
            left_val = df.at[idx, left_col]
            right_val = df.at[idx, right_col]
            left_origins = left_lineage[position].get(column_name, ()) if left_lineage else ()
            right_origins = right_lineage[position].get(column_name, ()) if right_lineage else ()
            left_missing = _is_missing_scalar(left_val)
            right_missing = _is_missing_scalar(right_val)

            if left_missing and right_missing:
                chosen_lineage_values[position] = ()
                continue

            if not left_missing and right_missing:
                if not left_origins:
                    raise SchemaIncompatibilityError(
                        f"JOIN provenance missing for non-null column {column_name!r}"
                    )
                chosen_lineage_values[position] = left_origins
                continue

            if left_missing and not right_missing:
                resolved.at[idx] = right_val
                chosen_lineage_values[position] = right_origins
                continue

            if not left_missing and not right_missing and self._values_equal(left_val, right_val):
                if not left_origins:
                    left_origins = right_origins
                resolved.at[idx] = left_val
                chosen_lineage_values[position] = left_origins
                continue

            if not left_origins:
                raise SchemaIncompatibilityError(
                    f"JOIN provenance missing for non-null column {column_name!r}"
                )

            left_source = _origins_metadata(left_origins)
            right_source = _origins_metadata(right_origins)
            if left_source is None or right_source is None:
                raise FederationError("Non-null conflicting cell lacks selected origins")
            row_key = {k: df.at[idx, k] for k in join_keys}
            candidates = [
                ConflictCandidate(
                    source_id=left_source.connector_id,
                    value=left_val,
                    metadata=left_source,
                    row_key=row_key,
                    column=column_name,
                ),
                ConflictCandidate(
                    source_id=right_source.connector_id,
                    value=right_val,
                    metadata=right_source,
                    row_key=row_key,
                    column=column_name,
                ),
            ]

            context = ConflictContext(
                request=request,
                row_key=row_key,
                column=column_name,
                conflict_type="duplicate_column",
            )
            policy_override = (request.column_policies or {}).get(
                column_name, request.conflict_policy
            )
            resolution = self.resolver.resolve_conflict(
                candidates,
                context,
                policy_override=policy_override,
                record_log=request.audit_level != AuditLevel.NONE,
            )
            resolved.at[idx] = resolution.chosen_candidate.value
            chosen_lineage_values[position] = (
                left_origins if resolution.chosen_candidate is candidates[0] else right_origins
            )

            if resolution.log_entry:
                resolution.log_entry.row_index = position
                resolution.log_entry.source_a_occurrence = left_origins[0].token
                resolution.log_entry.source_b_occurrence = right_origins[0].token
                collector.record(resolution.log_entry)

        return resolved, chosen_lineage_values

    @staticmethod
    def _values_equal(left: object, right: object) -> bool:
        """Compare scalar cells without leaking pandas' NA sentinel."""
        try:
            comparison = left == right
            return bool(comparison)
        except TypeError, ValueError:
            return False

    def _resolve_time_dimension(self, request: CompositionRequest) -> str | None:
        if request.time_dimension:
            return request.time_dimension
        if request.schema and request.schema.time_dimension:
            return request.schema.time_dimension
        return None

    def _resolve_key_columns(
        self,
        request: CompositionRequest,
        time_dimension: str | None,
    ) -> list[str]:
        keys: list[str] = []

        if request.key_columns:
            keys.extend(request.key_columns)
        elif request.schema:
            keys.extend(list(request.schema.effective_grain_dims()))
        elif request.join_keys:
            keys.extend(list(request.join_keys))

        if time_dimension and time_dimension not in keys:
            keys.append(time_dimension)

        return _unique_preserve_order([k for k in keys if k])

    def _row_key_from_group(self, key_columns: list[str], key_values: object) -> dict[str, object]:
        if len(key_columns) == 1:
            return {key_columns[0]: key_values}
        if not isinstance(key_values, tuple):
            return {key_columns[0]: key_values}
        return dict(zip(key_columns, key_values, strict=False))

    def _row_key_from_index(self, key_columns: list[str], index_value: object) -> dict[str, object]:
        if len(key_columns) == 1:
            return {key_columns[0]: index_value}
        if isinstance(index_value, tuple):
            return dict(zip(key_columns, index_value, strict=False))
        return {key_columns[0]: index_value}

    def _select_primary_source_index(
        self,
        sources: list[tuple[pd.DataFrame, SourceMetadata]],
        request: CompositionRequest,
    ) -> int:
        if request.primary_source:
            for idx, (_, meta) in enumerate(sources):
                if meta.connector_id == request.primary_source:
                    return idx
            raise FederationError(f"Primary source '{request.primary_source}' not found")

        if request.manual_priorities:
            best_idx = 0
            best_priority = None
            for idx, (_, meta) in enumerate(sources):
                priority = request.manual_priorities.get(meta.connector_id, 0)
                if best_priority is None or priority > best_priority:
                    best_priority = priority
                    best_idx = idx
            return best_idx

        return 0
