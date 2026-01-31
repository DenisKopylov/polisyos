"""
Data composer for multi-source federation.

Implements UNION, JOIN, OVERLAY, and CONSENSUS strategies for combining
existing data from multiple sources with deterministic behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from contextlib import contextmanager
import hashlib
import heapq
import json

import pandas as pd

from polisyos.common.logger import get_logger

from polisyos.fabric.connectors.federation.resolver import ConflictResolver
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    FederationError,
    MergeLogEntry,
    MergeLogSummary,
    SchemaIncompatibilityError,
    SourceMetadata,
)

logger = get_logger(__name__)


@contextmanager
def _noop_span():
    yield None


def _safe_get_tracer():
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
        seed: str | None,
    ) -> None:
        self.audit_level = audit_level
        self.sample_size = max(0, sample_size)
        self.seed = seed or ""
        self.entries: list[MergeLogEntry] = []
        self.summary = MergeLogSummary(sample_seed=self.seed)
        self._sample_heap: list[tuple[int, MergeLogEntry]] = []

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
            self.entries.append(entry)
        elif self.audit_level == AuditLevel.SUMMARY and self.sample_size > 0:
            self._sample(entry)

    def _sample(self, entry: MergeLogEntry) -> None:
        hash_value = self._stable_hash(entry)
        if len(self._sample_heap) < self.sample_size:
            heapq.heappush(self._sample_heap, (-hash_value, entry))
            return

        current_max = -self._sample_heap[0][0]
        if hash_value < current_max:
            heapq.heapreplace(self._sample_heap, (-hash_value, entry))

    def finalize(self) -> None:
        if self.audit_level != AuditLevel.SUMMARY or self.sample_size == 0:
            return
        samples = sorted(
            [(-hash_value, entry) for hash_value, entry in self._sample_heap],
            key=lambda item: item[0],
        )
        self.summary.sample_entries = [entry for _, entry in samples]

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
        return int(hashlib.sha256(encoded).hexdigest(), 16)

    @staticmethod
    def _inc(bucket: dict[str, int], key: str) -> None:
        bucket[key] = bucket.get(key, 0) + 1


class DataComposer:
    """
    Composes data from multiple sources using different strategies.

    Maintains determinism through:
    - Stable sorting (sort by connector_id)
    - Consistent null handling
    - Deterministic tie-breaking
    """

    def __init__(self, conflict_resolver: ConflictResolver):
        """
        Initialize composer with a conflict resolver.

        Args:
            conflict_resolver: Resolver for handling conflicts
        """
        self.resolver = conflict_resolver
        self._last_merge_summary: MergeLogSummary | None = None

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

        # Sort sources by connector_id for determinism
        sources = sorted(sources, key=lambda s: s[1].connector_id)

        collector = MergeLogCollector(
            audit_level=request.audit_level,
            sample_size=request.audit_sample_size,
            seed=request.audit_seed,
        )

        tracer = _safe_get_tracer()
        span_ctx = (
            tracer.start_as_current_span(
                "federation.compose",
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

        merge_log: list[MergeLogEntry] = []

        # Validate key columns exist in all sources
        for df, metadata in sources:
            missing_keys = [k for k in key_columns if k not in df.columns]
            if missing_keys:
                raise SchemaIncompatibilityError(
                    f"Key columns {missing_keys} not found in source {metadata.connector_id}"
                )

        all_rows = []
        for df, metadata in sources:
            df_copy = df.copy()
            df_copy["__source_id"] = metadata.connector_id
            all_rows.append(df_copy)

        combined = pd.concat(all_rows, ignore_index=True)
        combined = combined.sort_values(by=key_columns, kind="mergesort").reset_index(
            drop=True
        )

        source_lookup = {meta.connector_id: meta for _, meta in sources}

        resolved_rows = []
        for key_values, group in combined.groupby(key_columns, sort=True, dropna=False):
            row_key = self._row_key_from_group(key_columns, key_values)
            if len(group) == 1:
                resolved_rows.append(group.iloc[0].drop(labels=["__source_id"]))
                continue

            candidates = []
            for _, row in group.iterrows():
                source_id = row["__source_id"]
                metadata = source_lookup[source_id]
                candidates.append(
                    ConflictCandidate(
                        source_id=source_id,
                        value=row.drop(labels=["__source_id"]).to_dict(),
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
                merge_log.append(resolution.log_entry)

            resolved_rows.append(pd.Series(resolution.chosen_candidate.value))

        result = pd.DataFrame(resolved_rows)
        result = result.sort_values(by=key_columns, kind="mergesort").reset_index(
            drop=True
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
        result_df = result_df.copy()

        column_sources: dict[str, SourceMetadata | None] = {
            col: first_metadata for col in result_df.columns
        }

        for df, metadata in sources[1:]:
            df_copy = df.copy()

            overlapping_cols = set(result_df.columns) & set(df_copy.columns)
            overlapping_cols -= set(join_keys)

            if overlapping_cols:
                logger.info(
                    "JOIN detected overlapping columns",
                    columns=sorted(list(overlapping_cols)),
                )

            result_df = result_df.merge(
                df_copy,
                on=join_keys,
                how=request.join_how,
                suffixes=("_left", "_right"),
                sort=True,
            )

            # Resolve duplicate columns
            for col in sorted(overlapping_cols):
                left_meta = column_sources.get(col)
                if left_meta is None:
                    left_meta = first_metadata
                    logger.warning(
                        "Missing column source mapping; defaulting left metadata",
                        column=col,
                    )

                resolved_col, chosen_meta = self._resolve_duplicate_column(
                    df=result_df,
                    column_name=col,
                    left_meta=left_meta,
                    right_meta=metadata,
                    request=request,
                    join_keys=join_keys,
                    collector=collector,
                )

                result_df[col] = resolved_col
                result_df = result_df.drop(columns=[f"{col}_left", f"{col}_right"])
                column_sources[col] = chosen_meta

            # Track newly added columns
            for col in df_copy.columns:
                if col in join_keys or col in overlapping_cols:
                    continue
                if col not in column_sources:
                    column_sources[col] = metadata

        return result_df

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

        for col in result_df.columns:
            null_mask = result_df[col].isna()
            if not null_mask.any():
                continue

            for secondary_df, secondary_meta in secondaries:
                if col not in secondary_df.columns:
                    continue

                secondary_indexed = secondary_df.set_index(key_columns, drop=True)
                aligned = secondary_indexed[col].reindex(result_df.index)

                fill_mask = null_mask & aligned.notna()
                if fill_mask.any():
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

            consensus_col = self._apply_consensus(values_df, agg_func)

            # Handle non-numeric fallback when needed
            non_numeric_mask = consensus_col.isna() & values_df.notna().any(axis=1)
            if non_numeric_mask.any():
                for idx in values_df.index[non_numeric_mask]:
                    row_key = self._row_key_from_index(key_columns, idx)
                    candidates = []
                    for source_idx, (indexed, metadata) in enumerate(indexed_sources):
                        value = values_df.iloc[values_df.index.get_loc(idx), source_idx]
                        candidates.append(
                            ConflictCandidate(
                                source_id=metadata.connector_id,
                                value=value,
                                metadata=metadata,
                                row_key=row_key,
                                column=col,
                            )
                        )
                    context = ConflictContext(
                        request=request,
                        row_key=row_key,
                        column=col,
                        conflict_type="consensus",
                    )
                    policy_override = (request.column_policies or {}).get(
                        col, request.conflict_policy
                    )
                    resolution = self.resolver.resolve_conflict(
                        candidates,
                        context,
                        policy_override=policy_override,
                        record_log=request.audit_level != AuditLevel.NONE,
                    )
                    consensus_col.loc[idx] = resolution.chosen_candidate.value
                    if resolution.log_entry:
                        collector.record(resolution.log_entry)

            # Logging conflicts where values differ
            if request.audit_level != AuditLevel.NONE:
                distinct_counts = values_df.nunique(axis=1, dropna=True)
                conflict_mask = distinct_counts > 1
                if conflict_mask.any():
                    for idx in values_df.index[conflict_mask]:
                        row_key = self._row_key_from_index(key_columns, idx)
                        entry = MergeLogEntry(
                            row_index=None,
                            row_key=row_key,
                            column=col,
                            conflict_type="consensus",
                            source_a_id=indexed_sources[0][1].connector_id,
                            source_a_value=values_df.iloc[
                                values_df.index.get_loc(idx), 0
                            ],
                            source_a_trust=indexed_sources[0][1].metadata.trust_level,
                            source_b_id="consensus",
                            source_b_value=consensus_col.loc[idx],
                            source_b_trust=indexed_sources[0][1].metadata.trust_level,
                            chosen_source="consensus",
                            chosen_value=consensus_col.loc[idx],
                            resolution_reason=(
                                f"CONSENSUS: {agg_func} of {len(indexed_sources)} sources"
                            ),
                            resolution_policy=agg_func,
                            timestamp=None,
                        )
                        collector.record(entry)

            consensus_stats[col] = {
                "aggregation": agg_func,
                "rows": int(len(consensus_col)),
                "conflicts": int(values_df.nunique(axis=1, dropna=True).gt(1).sum()),
                "sources": len(indexed_sources),
            }

            result[col] = consensus_col

        collector.summary.extra["consensus"] = consensus_stats

        result.index.names = key_columns
        result = result.reset_index()
        return result

    def _apply_consensus(self, values_df: pd.DataFrame, agg_func: str) -> pd.Series:
        if agg_func == "mean":
            numeric_df = values_df.apply(pd.to_numeric, errors="coerce")
            return numeric_df.mean(axis=1)
        if agg_func == "median":
            numeric_df = values_df.apply(pd.to_numeric, errors="coerce")
            return numeric_df.median(axis=1)
        if agg_func == "mode":
            modes = values_df.mode(axis=1, dropna=True)
            if modes.empty:
                return pd.Series([pd.NA] * len(values_df), index=values_df.index)
            return modes.iloc[:, 0]
        raise FederationError(f"Unknown aggregation function: {agg_func}")

    def _resolve_duplicate_column(
        self,
        df: pd.DataFrame,
        column_name: str,
        left_meta: SourceMetadata,
        right_meta: SourceMetadata,
        request: CompositionRequest,
        join_keys: list[str],
        collector: MergeLogCollector,
    ) -> tuple[pd.Series, SourceMetadata | None]:
        left_col = f"{column_name}_left"
        right_col = f"{column_name}_right"

        resolved = df[left_col].copy()
        chosen_sources: list[str] = []

        for idx in df.index:
            left_val = df.at[idx, left_col]
            right_val = df.at[idx, right_col]

            if pd.isna(left_val) and pd.isna(right_val):
                continue

            if not pd.isna(left_val) and not pd.isna(right_val) and left_val == right_val:
                resolved.at[idx] = left_val
                chosen_sources.append(left_meta.connector_id)
                continue

            row_key = {k: df.at[idx, k] for k in join_keys}
            candidates = [
                ConflictCandidate(
                    source_id=left_meta.connector_id,
                    value=left_val,
                    metadata=left_meta,
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
            chosen_sources.append(resolution.chosen_candidate.source_id)

            if resolution.log_entry:
                collector.record(resolution.log_entry)

        chosen_meta: SourceMetadata | None = None
        if chosen_sources:
            unique_sources = set(chosen_sources)
            if len(unique_sources) == 1:
                chosen_source_id = unique_sources.pop()
                if chosen_source_id == left_meta.connector_id:
                    chosen_meta = left_meta
                elif chosen_source_id == right_meta.connector_id:
                    chosen_meta = right_meta

        return resolved, chosen_meta

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
        return {key: value for key, value in zip(key_columns, key_values)}

    def _row_key_from_index(self, key_columns: list[str], index_value: Any) -> dict[str, Any]:
        if len(key_columns) == 1:
            return {key_columns[0]: index_value}
        if isinstance(index_value, tuple):
            return {key: value for key, value in zip(key_columns, index_value)}
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
            raise FederationError(
                f"Primary source '{request.primary_source}' not found"
            )

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
