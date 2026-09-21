"""
Data composer for multi-source federation.

Implements UNION, JOIN, OVERLAY, and CONSENSUS strategies for combining
existing data from multiple sources with deterministic behavior.
"""

from __future__ import annotations

import heapq
import json
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    ConflictResolutionError,
    FederationError,
    MergeLogEntry,
    MergeLogSummary,
    SchemaIncompatibilityError,
    SourceMetadata,
)
from polisyos.fabric._adapters.observability import FABRIC_TRACE_NAMES
from polisyos.fabric.numerics.finite import is_finite_number

logger = get_logger(__name__)


@contextmanager
def _noop_span():
    yield None


def _default_tracer():
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


def _is_missing_scalar(value: Any) -> bool:
    """Return whether a scalar value is a pandas missing value."""
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _lineage_map(value: Any) -> dict[str, SourceMetadata | None]:
    """Copy one internal per-row lineage map without exposing it to callers."""
    if isinstance(value, dict):
        return dict(value)
    return {}


@dataclass
class _SampleEntry:
    hash_value: int
    entry: MergeLogEntry


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
            heapq.heappush(self._sample_heap, (-hash_value, sequence, entry))
            return

        current_max = -self._sample_heap[0][0]
        if hash_value < current_max:
            heapq.heapreplace(self._sample_heap, (-hash_value, sequence, entry))

    def finalize(self) -> None:
        self.summary.extra["audit_entries_retained"] = len(self.entries)
        self.summary.extra["audit_entries_dropped"] = self._dropped_entries
        self.summary.extra["audit_entries_truncated"] = self._dropped_entries > 0
        if self.audit_level != AuditLevel.SUMMARY or self.sample_size == 0:
            return
        samples = sorted(
            [
                (-hash_value, sequence, entry)
                for hash_value, sequence, entry in self._sample_heap
            ],
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
        tracer: Any | None = None,
    ):
        """
        Initialize composer with a conflict resolver.

        Args:
            conflict_resolver: Resolver for handling conflicts
            tracer: Optional injected tracer for composition spans
        """
        self.resolver = conflict_resolver
        self._last_merge_summary: MergeLogSummary | None = None
        self._tracer = tracer

    def compose(
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

        collector.finalize()
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
        for df, metadata in sources:
            df_copy = df.copy()
            # Keep transport provenance out of the user namespace.  The
            # generated name is local to this operation and is removed before
            # the result is returned, so a real ``__source_id`` column is
            # ordinary data rather than an implementation detail.
            df_copy[source_column] = metadata.connector_id
            all_rows.append(df_copy)

        combined = pd.concat(all_rows, ignore_index=True)
        combined = combined.sort_values(by=key_columns, kind="mergesort").reset_index(drop=True)

        source_lookup = {meta.connector_id: meta for _, meta in sources}

        resolved_rows = []
        for key_values, group in combined.groupby(key_columns, sort=True, dropna=False):
            row_key = self._row_key_from_group(key_columns, key_values)
            if len(group) == 1:
                resolved_rows.append(group.iloc[0].drop(labels=[source_column]))
                continue

            candidates = []
            for _, row in group.iterrows():
                source_id = row[source_column]
                metadata = source_lookup[source_id]
                candidates.append(
                    ConflictCandidate(
                        source_id=source_id,
                        value=row.drop(labels=[source_column]).to_dict(),
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

            resolved_rows.append(pd.Series(resolution.chosen_candidate.value))

        if not resolved_rows:
            return combined.drop(columns=[source_column]).iloc[:0].copy()

        result = pd.DataFrame(resolved_rows)
        result = result.sort_values(by=key_columns, kind="mergesort").reset_index(drop=True)

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
        result_df = result_df.copy().reset_index(drop=True)
        lineage_column = _fresh_internal_name(result_df.columns, "__policyos_lineage")
        result_df[lineage_column] = [
            {
                column: first_metadata
                for column in result_df.columns
                if column not in join_keys
            }
            for _ in range(len(result_df))
        ]

        for df, metadata in sources[1:]:
            df_copy = df.copy().reset_index(drop=True)

            # A caller may legitimately use the generated-looking lineage
            # name.  Move our sidecar before considering user columns so it
            # can never become part of the public result or a conflict set.
            if lineage_column in df_copy.columns:
                replacement = _fresh_internal_name(
                    [*result_df.columns, *df_copy.columns], "__policyos_lineage"
                )
                result_df = result_df.rename(columns={lineage_column: replacement})
                lineage_column = replacement

            self._validate_join_cardinality(
                left=result_df,
                right=df_copy,
                join_keys=join_keys,
                request=request,
                right_source_id=metadata.connector_id,
            )

            overlapping_cols = (
                set(result_df.columns) & set(df_copy.columns)
            ) - set(join_keys) - {lineage_column}

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
            right_work[right_lineage_column] = [
                {
                    column: metadata
                    for column in df_copy.columns
                    if column not in join_keys
                }
                for _ in range(len(df_copy))
            ]

            left_work = result_df.copy()
            merge_keys: list[str] = []
            for key in join_keys:
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
                result_df[key] = result_df[key].combine_first(result_df[right_key])

            right_only_columns = [
                column
                for column in df_copy.columns
                if column not in join_keys and column not in overlapping_cols
            ]
            merged_lineage: list[dict[str, SourceMetadata | None]] = []
            for _, row in result_df.iterrows():
                row_lineage = _lineage_map(row.get(lineage_column))
                right_lineage = _lineage_map(row.get(right_lineage_column))
                for column in right_only_columns:
                    row_lineage.setdefault(column, right_lineage.get(column, metadata))
                merged_lineage.append(row_lineage)

            drop_columns = [
                *merge_keys,
                right_lineage_column,
                *right_key_aliases.values(),
            ]
            result_df = result_df.drop(columns=drop_columns)
            result_df[lineage_column] = merged_lineage

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
                    left_lineage=result_df[lineage_column],
                )

                result_df[col] = resolved_col
                result_df = result_df.drop(columns=[right_renames[col]])
                for index, source in chosen_lineage.items():
                    row_lineage = _lineage_map(result_df.at[index, lineage_column])
                    row_lineage[col] = source
                    result_df.at[index, lineage_column] = row_lineage

        result_df = result_df.drop(columns=[lineage_column])

        return result_df

    def _validate_join_cardinality(
        self,
        *,
        left: pd.DataFrame,
        right: pd.DataFrame,
        join_keys: list[str],
        request: CompositionRequest,
        right_source_id: str,
    ) -> None:
        """Reject undeclared expansion before pandas materializes a JOIN."""
        relation = request.join_validate or "many_to_one"
        valid_relations = {"one_to_one", "one_to_many", "many_to_one", "many_to_many"}
        if relation not in valid_relations:
            raise SchemaIncompatibilityError(
                f"Unsupported JOIN cardinality {relation!r}; "
                f"expected one of {sorted(valid_relations)}"
            )

        if request.join_max_rows is not None and request.join_max_rows < 0:
            raise SchemaIncompatibilityError("join_max_rows must be non-negative")

        left_keys = self._join_key_frame(left, join_keys, request.join_nulls_match)
        right_keys = self._join_key_frame(right, join_keys, request.join_nulls_match)
        left_duplicates = bool(left_keys.duplicated(join_keys, keep=False).any())
        right_duplicates = bool(right_keys.duplicated(join_keys, keep=False).any())

        if relation in {"one_to_one", "one_to_many"} and left_duplicates:
            raise SchemaIncompatibilityError(
                f"JOIN cardinality {relation} rejects duplicate left keys "
                f"before materialization (source={right_source_id})"
            )
        if relation in {"one_to_one", "many_to_one"} and right_duplicates:
            raise SchemaIncompatibilityError(
                f"JOIN cardinality {relation} rejects duplicate right keys "
                f"before materialization (source={right_source_id})"
            )

        if request.join_max_rows is not None:
            estimated_rows = self._estimate_join_rows(
                left=left,
                right=right,
                join_keys=join_keys,
                join_how=request.join_how,
                match_nulls=request.join_nulls_match,
            )
            if estimated_rows > request.join_max_rows:
                raise SchemaIncompatibilityError(
                    "JOIN exceeds declared join_max_rows before materialization: "
                    f"estimated={estimated_rows}, limit={request.join_max_rows}"
                )

    @staticmethod
    def _join_key_frame(
        frame: pd.DataFrame,
        join_keys: list[str],
        match_nulls: bool,
    ) -> pd.DataFrame:
        keys = frame.loc[:, join_keys]
        if match_nulls:
            return keys
        return keys.loc[~keys.isna().any(axis=1)]

    @staticmethod
    def _join_key_values(
        values: pd.Series,
        *,
        side: str,
        match_nulls: bool,
    ) -> pd.Series:
        if match_nulls:
            return values.copy()
        # Distinct per-side sentinels preserve the pandas merge path while
        # ensuring two unknown identities never become the same entity.
        sentinel = object()
        return pd.Series(
            [sentinel if _is_missing_scalar(value) else value for value in values],
            index=values.index,
            dtype=object,
            name=f"{side}_join_key",
        )

    @staticmethod
    def _estimate_join_rows(
        *,
        left: pd.DataFrame,
        right: pd.DataFrame,
        join_keys: list[str],
        join_how: str,
        match_nulls: bool,
    ) -> int:
        """Estimate result rows from key frequencies without a data merge."""
        left_keys = DataComposer._join_key_frame(left, join_keys, match_nulls)
        right_keys = DataComposer._join_key_frame(right, join_keys, match_nulls)
        left_counts = left_keys.value_counts(sort=False)
        right_counts = right_keys.value_counts(sort=False)
        matching = 0
        left_unmatched = 0
        right_unmatched = 0
        for key, left_count in left_counts.items():
            right_count = right_counts.get(key, 0)
            if right_count:
                matching += int(left_count) * int(right_count)
            else:
                left_unmatched += int(left_count)
        for key, right_count in right_counts.items():
            if key not in left_counts:
                right_unmatched += int(right_count)

        if join_how == "inner":
            return matching
        if join_how == "left":
            return matching + left_unmatched + (
                len(left) - len(left_keys) if not match_nulls else 0
            )
        return matching + left_unmatched + right_unmatched + (
            len(left) - len(left_keys) + len(right) - len(right_keys)
            if not match_nulls
            else 0
        )

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

        primary_idx = self._select_primary_source_index(sources, request)
        primary = sources[primary_idx]
        secondaries = sources[:primary_idx] + sources[primary_idx + 1 :]

        result_df, primary_metadata = primary
        result_df = result_df.copy()

        # Ensure key columns exist
        for key in key_columns:
            if key not in result_df.columns:
                raise SchemaIncompatibilityError(
                    f"Key column '{key}' not found in primary source {primary_metadata.connector_id}"
                )

        all_columns = set(result_df.columns)
        for df, _ in secondaries:
            all_columns.update(df.columns)

        # Align on key columns
        result_df = result_df.set_index(key_columns, drop=True)
        result_df = result_df.sort_index()

        # Add missing columns from secondaries
        for col in sorted(all_columns):
            if col in key_columns:
                continue
            if col not in result_df.columns:
                result_df[col] = pd.NA

        indexed_secondaries: dict[int, pd.DataFrame] = {}
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
                aligned = secondary_indexed[col].reindex(result_df.index)

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

                    result_df.loc[fill_mask, col] = aligned[fill_mask]
                    null_mask = result_df[col].isna()

                if not null_mask.any():
                    break

        result_df = result_df.reset_index()
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
            indexed = df.set_index(key_columns, drop=True)
            indexed_sources.append((indexed, metadata))

        # Determine union index
        union_index = indexed_sources[0][0].index
        for indexed, _ in indexed_sources[1:]:
            union_index = union_index.union(indexed.index)
        union_index = union_index.sort_values()

        # Determine common columns (excluding keys)
        common_columns = set(indexed_sources[0][0].columns)
        for indexed, _ in indexed_sources[1:]:
            common_columns &= set(indexed.columns)
        common_columns = sorted(common_columns)

        result = pd.DataFrame(index=union_index)
        consensus_stats: dict[str, dict[str, Any]] = {}

        for col in common_columns:
            values_df = pd.concat(
                [indexed[col].reindex(union_index) for indexed, _ in indexed_sources],
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

            # Logging conflicts where values differ
            if request.audit_level != AuditLevel.NONE:
                distinct_counts = values_df.nunique(axis=1, dropna=True)
                conflict_mask = distinct_counts > 1
                if conflict_mask.any():
                    for idx in values_df.index[conflict_mask]:
                        row_key = self._row_key_from_index(key_columns, idx)
                        row_id = json.dumps(row_key, sort_keys=True, default=str)
                        participants = admissibility["participant_sources"].get(row_id, [])
                        exclusions = admissibility["exclusions"].get(row_id, [])
                        source_a_id = participants[0] if participants else (
                            exclusions[0]["source_id"]
                            if exclusions
                            else indexed_sources[0][1].connector_id
                        )
                        source_a_index = next(
                            (
                                source_idx
                                for source_idx, (_indexed, metadata) in enumerate(indexed_sources)
                                if metadata.connector_id == source_a_id
                            ),
                            0,
                        )
                        entry = MergeLogEntry(
                            row_index=None,
                            row_key=row_key,
                            column=col,
                            conflict_type="consensus",
                            source_a_id=source_a_id,
                            source_a_value=values_df.iloc[
                                values_df.index.get_loc(idx), source_a_index
                            ],
                            source_a_trust=indexed_sources[source_a_index][1].metadata.trust_level,
                            source_b_id="consensus",
                            source_b_value=consensus_col.loc[idx],
                            source_b_trust=indexed_sources[0][1].metadata.trust_level,
                            chosen_source="consensus",
                            chosen_value=consensus_col.loc[idx],
                            resolution_reason=(
                                f"CONSENSUS: {agg_func} of {len(participants)} "
                                f"admissible participants; excluded={len(exclusions)}"
                            ),
                            resolution_policy=agg_func,
                            timestamp=None,
                        )
                        collector.record(entry)

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
            }

            result[col] = consensus_col

        collector.summary.extra["consensus"] = consensus_stats

        result.index.names = key_columns
        result = result.reset_index()
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
            modes = values_df.mode(axis=1, dropna=True)
            result = (
                modes.iloc[:, 0]
                if not modes.empty
                else pd.Series([pd.NA] * len(values_df), index=values_df.index)
            )
            for idx, row in values_df.iterrows():
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
        for idx, row in values_df.iterrows():
            row_key = self._row_key_from_index(key_columns, idx)
            row_id = json.dumps(row_key, sort_keys=True, default=str)
            numeric_values: list[float] = []
            row_participants: list[str] = []
            row_exclusions: list[dict[str, str]] = []
            for source_idx, value in enumerate(row):
                source_id = indexed_sources[source_idx][1].connector_id
                if _is_missing_scalar(value):
                    continue
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
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
        left_lineage: pd.Series | None = None,
    ) -> tuple[pd.Series, pd.Series]:
        left_col = left_column or f"{column_name}_left"
        right_col = right_column or f"{column_name}_right"

        resolved = df[left_col].copy()
        chosen_lineage = pd.Series(index=df.index, dtype=object)

        for idx in df.index:
            left_val = df.at[idx, left_col]
            right_val = df.at[idx, right_col]
            left_source = left_meta
            if left_lineage is not None:
                left_source = _lineage_map(left_lineage.at[idx]).get(column_name)

            left_missing = _is_missing_scalar(left_val)
            right_missing = _is_missing_scalar(right_val)

            if left_missing and right_missing:
                chosen_lineage.at[idx] = None
                continue

            if not left_missing and right_missing:
                if left_source is None:
                    raise SchemaIncompatibilityError(
                        f"JOIN provenance missing for non-null column {column_name!r}"
                    )
                chosen_lineage.at[idx] = left_source
                continue

            if left_missing and not right_missing:
                resolved.at[idx] = right_val
                chosen_lineage.at[idx] = right_meta
                continue

            if not left_missing and not right_missing and self._values_equal(left_val, right_val):
                if left_source is None:
                    left_source = right_meta
                resolved.at[idx] = left_val
                chosen_lineage.at[idx] = left_source
                continue

            if left_source is None:
                raise SchemaIncompatibilityError(
                    f"JOIN provenance missing for non-null column {column_name!r}"
                )

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
                    source_id=right_meta.connector_id,
                    value=right_val,
                    metadata=right_meta,
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
            chosen_lineage.at[idx] = (
                left_source
                if resolution.chosen_candidate.source_id == left_source.connector_id
                else right_meta
            )

            if resolution.log_entry:
                collector.record(resolution.log_entry)

        return resolved, chosen_lineage

    @staticmethod
    def _values_equal(left: Any, right: Any) -> bool:
        """Compare scalar cells without leaking pandas' NA sentinel."""
        try:
            comparison = left == right
            return bool(comparison)
        except (TypeError, ValueError):
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

    def _row_key_from_group(self, key_columns: list[str], key_values: Any) -> dict[str, Any]:
        if len(key_columns) == 1:
            return {key_columns[0]: key_values}
        if not isinstance(key_values, tuple):
            return {key_columns[0]: key_values}
        return dict(zip(key_columns, key_values, strict=False))

    def _row_key_from_index(self, key_columns: list[str], index_value: Any) -> dict[str, Any]:
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
